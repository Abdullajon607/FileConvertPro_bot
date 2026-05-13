import os
import asyncio
from aiohttp import web
import aiohttp
import time
import re
import html
from datetime import timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.context import FSMContext
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import load_config
from db import DB
from states import LangFlow, ConvertFlow, ImgConvertFlow, TranslitFlow, PaymentFlow, ContactAdminFlow, CompressFlow, AdminFlow
from middlewares import LanguageMiddleware
from keyboards import (
    kb_lang, kb_main, kb_pay_kind,
    kb_premium_plans, kb_admin_payment, kb_finish_images,
    kb_text_confirmation, kb_admin_main, kb_ocr_lang, 
)
from i18n import t, get_all
from utils import (
    setup_logger, ensure_dir, week_str_local,
    utcnow, iso, from_iso, rand_name, safe_ext,
    size_ok, human_err, is_url
)
from services.translit import latin_to_cyr, cyr_to_latin
from services.convert import pdf_to_docx, docx_to_pdf, text_to_docx, text_to_pptx, images_to_docx_embed
from services.ocr import configure_tesseract, ocr_image
from services.compress import compress_pdf, compress_office_file


cfg = load_config()
db = DB(cfg.db_path)
logger = setup_logger(cfg.log_dir)

GLOBAL_SEM = asyncio.Semaphore(10) # Bir vaqtda 10 ta og'ir jarayon ishlashi mumkin
USER_LOCKS: dict[int, asyncio.Lock] = {}

def ulock(uid: int) -> asyncio.Lock:
    if uid not in USER_LOCKS:
        USER_LOCKS[uid] = asyncio.Lock()
    return USER_LOCKS[uid]

async def run_heavy(uid: int, coro_fn):
    async with ulock(uid):
        async with GLOBAL_SEM:
            return await coro_fn()

async def cleanup_tmp_files(tmp_dir: str, max_age: int = 3600):
    """Eski vaqtinchalik fayllarni fon rejimida tozalab turadi."""
    while True:
        try:
            now = time.time()
            for filename in os.listdir(tmp_dir):
                path = os.path.join(tmp_dir, filename)
                if os.path.isfile(path) and (now - os.path.getmtime(path) > max_age):
                    os.remove(path)
                    logger.info(f"Auto-cleaned: {filename}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        await asyncio.sleep(1800) # Har 30 minutda tekshirish

async def download_url(url: str, dest_path: str, timeout=300):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                while True:
                    chunk = await resp.content.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)

async def is_premium(user_id: int) -> tuple[bool, str | None]:
    if user_id in cfg.admin_ids:
        return (True, "Admin 👑 (Cheksiz)")
    pu = await db.get_premium_until(user_id)
    if not pu:
        return (False, None)
    until = from_iso(pu)
    if until > utcnow():
        return (True, pu)
    return (False, None)

async def can_free(user_id: int, kind: str) -> bool:
    week = week_str_local()
    await db.ensure_usage(user_id, week)
    c_used, t_used = await db.get_usage(user_id, week)
    
    # Hamma funksiyalar uchun umumiy haftasiga 3 ta bepul limit:
    total_used = c_used + t_used
    return total_used < 3

async def mark_used(user_id: int, kind: str):
    week = week_str_local()
    await db.ensure_usage(user_id, week)
    if kind == "convert":
        await db.inc_usage(user_id, week, "convert_used")
    elif kind == "translit":
        await db.inc_usage(user_id, week, "translit_used")

def _sendable(path: str) -> FSInputFile:
    if not os.path.exists(path):
        raise RuntimeError("Natija fayli topilmadi.")
    return FSInputFile(path)

async def get_file_from_message(m: Message) -> tuple[str | None, str | None]:
    tmp = cfg.tmp_dir

    if m.document:
        if not size_ok(m.document.file_size, cfg.max_file_mb):
            return (None, "too_big")
        ext = safe_ext(m.document.file_name).lstrip(".") or "bin"
        p = os.path.join(tmp, rand_name("f", ext))
        f = await m.bot.get_file(m.document.file_id, request_timeout=300)
        await m.bot.download_file(f.file_path, p, timeout=300)
        return (p, "file")

    if m.photo:
        p = os.path.join(tmp, rand_name("f", "jpg"))
        f = await m.bot.get_file(m.photo[-1].file_id, request_timeout=300)
        await m.bot.download_file(f.file_path, p, timeout=300)
        return (p, "file")

    if m.text and is_url(m.text.strip()):
        p = os.path.join(tmp, rand_name("url", "bin"))
        await download_url(m.text.strip(), p)
        return (p, "url")

    return (None, None)

async def main():
    if not cfg.token:
        raise RuntimeError("BOT_TOKEN topilmadi! .env fayli yo'q yoki ichi bo'sh.")

    ensure_dir(cfg.tmp_dir)
    ensure_dir(cfg.log_dir)
    asyncio.create_task(cleanup_tmp_files(cfg.tmp_dir))
    configure_tesseract(cfg.tesseract_path) # Tesseractni konfiguratsiya qilish
    await db.init()

    bot = Bot(cfg.token)
    storage = RedisStorage.from_url(cfg.redis_url)
    dp = Dispatcher(storage=storage)

    if cfg.admin_log_channel_id:
        logger.addHandler(TelegramLogHandler(bot, cfg.admin_log_channel_id))

    dp.message.middleware(LanguageMiddleware(db))
    dp.callback_query.middleware(LanguageMiddleware(db))

    @dp.message(CommandStart())
    async def start(m: Message, state: FSMContext, lang: str):
        await state.set_state(LangFlow.choosing)
        await m.answer(t("uz", "choose_lang"), reply_markup=kb_lang())

    @dp.message(Command("admin"))
    async def cmd_admin_panel(m: Message, state: FSMContext, lang: str):
        if m.from_user.id not in cfg.admin_ids:
            await m.answer(t(lang, "admin_only"))
            return
        await state.set_state(AdminFlow.main)
        await m.answer(t(lang, "admin_panel_title"), reply_markup=kb_admin_main(lang))

    @dp.callback_query(F.data.startswith("lang:"))
    async def set_lang(c: CallbackQuery, state: FSMContext, lang: str):
        await db.ensure_user(c.from_user.id)
        await db.set_lang(c.from_user.id, lang)
        await state.clear()
        await c.message.delete()
        await c.message.answer(t(lang, "menu"), reply_markup=kb_main(lang))
        await c.answer()

    @dp.callback_query(F.data == "menu:back") # Bu callback har doim ishlaydi, shuning uchun lang argumenti kerak
    async def back_menu(c: CallbackQuery, state: FSMContext, lang: str):
        await state.clear()
        await c.message.delete()
        await c.message.answer(t(lang, "menu"), reply_markup=kb_main(lang))
        await c.answer()

    # ---------------- CONTACT ADMIN ----------------
    @dp.message(F.text.in_(get_all("contact_admin")))
    async def menu_contact_admin(m: Message, state: FSMContext, lang: str):
        await state.clear()
        await state.set_state(ContactAdminFlow.awaiting_message)
        await m.answer(
            t(lang, "send_admin_msg"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]])
        )

    @dp.message(ContactAdminFlow.awaiting_message)
    async def admin_message_received(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        info_text = f"📩 <b>Yangi murojaat!</b>\n👤 Kimdan: <a href='tg://user?id={uid}'>{html.escape(m.from_user.full_name)}</a>\n🆔 ID: <code>{uid}</code>"
        for admin_id in cfg.admin_ids:
            try:
                await m.bot.send_message(admin_id, info_text, parse_mode="HTML")
                await m.bot.copy_message(chat_id=admin_id, from_chat_id=m.chat.id, message_id=m.message_id) # Foydalanuvchining xabarini aynan o'zini forward / nusxalash
            except Exception: pass
        await m.answer(t(lang, "admin_msg_sent"))
        await m.answer(t(lang, "menu"), reply_markup=kb_main(lang))
        await state.clear()

    # ---------------- TRANSLIT ----------------
    @dp.message(F.text.in_(get_all("translit"))) # lang argumentini qo'shish
    async def menu_translit(m: Message, state: FSMContext, lang: str):
        await state.clear()
        await state.set_state(TranslitFlow.awaiting_text)
        await m.answer(
            t(lang, "send_text"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]])
        )

    @dp.message(TranslitFlow.awaiting_text)
    async def tr_do(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        prem, _ = await is_premium(uid)

        if not prem and not await can_free(uid, "translit"):
            await m.answer(t(lang, "limit_over"))
            await state.clear()
            return

        text = (m.text or "").strip()
        if not text:
            await m.answer(t(lang, "send_text"))
            return

        # Matn ichida qandaydir kiril harfi qatnashgan bo'lsa uni Lotinga, aks holda Kirilga o'giramiz
        if re.search(r'[А-Яа-яЁёЎўҚқҒғҲҳ]', text):
            out = cyr_to_latin(text)
        else:
            out = latin_to_cyr(text)
            
        await m.answer(out, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]]))

        if not prem:
            await mark_used(uid, "translit")

    # ---------------- PAYMENTS ----------------
    @dp.message(F.text.in_(get_all("pay"))) # lang argumentini qo'shish
    async def menu_pay(m: Message, state: FSMContext, lang: str):
        await state.clear()
        await state.set_state(PaymentFlow.choosing_kind)
        await m.answer(t(lang, "pay_choose"), reply_markup=kb_pay_kind(lang))

    @dp.callback_query(F.data == "pay:back") # lang argumentini qo'shish
    async def pay_back(c: CallbackQuery, state: FSMContext, lang: str):
        await state.set_state(PaymentFlow.choosing_kind)
        await c.message.delete()
        await c.message.answer(t(lang, "pay_choose"), reply_markup=kb_pay_kind(lang))
        await c.answer()

    @dp.callback_query(F.data == "pay:kind:premium")
    async def pay_kind_premium(c: CallbackQuery, state: FSMContext, lang: str):
        await state.set_state(PaymentFlow.choosing_plan)
        await c.message.delete()
        await c.message.answer(
            t(lang, "pay_premium_choose"),
            reply_markup=kb_premium_plans(cfg.price_1, cfg.price_7, cfg.price_30, cfg.price_365)
        )
        await c.answer()


    @dp.callback_query(F.data.startswith("pay:premium:"))
    async def pay_premium_choose(c: CallbackQuery, state: FSMContext, lang: str):
        days = int(c.data.split(":")[-1])
        amount = cfg.price_1 if days == 1 else cfg.price_7 if days == 7 else cfg.price_30 if days == 30 else cfg.price_365
        pid = await db.create_payment_premium(c.from_user.id, days, amount)
        await state.set_state(PaymentFlow.awaiting_proof)
        await state.update_data(payment_id=pid)
        text = t(lang, "pay_info") + f"\n\n⭐ Premium: {days} kun\n💵 {amount} so‘m\n📎 Chek yuboring."
        await c.message.delete()
        await c.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="pay:back")]]))
        await c.answer()


    @dp.message(PaymentFlow.awaiting_proof)
    async def payment_proof(m: Message, state: FSMContext, lang: str):
        data = await state.get_data()
        pid = data.get("payment_id")
        if not pid:
            await m.answer("Xatolik. /start bosing.")
            return

        proof_file_id = None
        if m.photo:
            proof_file_id = m.photo[-1].file_id
        elif m.document:
            proof_file_id = m.document.file_id
        if not proof_file_id:
            await m.answer("📎 Chek rasm yoki fayl yuboring.")
            return

        await db.attach_proof(pid, proof_file_id)
        pay = await db.get_payment(pid)
        if not pay:
            await m.answer("Topilmadi.")
            return

        _id, user_id, kind, plan_days, ocr_credits, amount, status, proof, created_at = pay
        caption = (
            f"💰 TO‘LOV (PENDING)\n"
            f"payment_id: {pid}\n"
            f"user_id: {user_id}\n"
            f"kind: {kind}\n"
            f"premium_days: {plan_days}\n"
            f"ocr_credits: {ocr_credits}\n"
            f"amount: {amount}\n"
            f"created: {created_at}\n"
        )

        for admin_id in cfg.admin_ids:
            try:
                if m.photo:
                    await m.bot.send_photo(admin_id, proof_file_id, caption=caption, reply_markup=kb_admin_payment(pid))
                else:
                    await m.bot.send_document(admin_id, proof_file_id, caption=caption, reply_markup=kb_admin_payment(pid))
            except Exception as e:
                logger.info(f"admin send failed: {human_err(e)}")

        await m.answer(t(lang, "sent_admin"))
        await m.answer(t(lang, "menu"), reply_markup=kb_main(lang))
        await state.clear()

    @dp.callback_query(F.data.startswith("admin:"))
    async def admin_action(c: CallbackQuery, lang: str):
        if c.from_user.id not in cfg.admin_ids:
            await c.answer(t(lang, "admin_only"), show_alert=True)
            return

        _, action, pid_s = c.data.split(":")
        pid = int(pid_s)
        pay = await db.get_payment(pid)
        if not pay:
            await c.answer("Not found", show_alert=True)
            return

        _id, user_id, kind, plan_days, ocr_credits, amount, status, proof, created_at = pay
        if status != "pending":
            await c.answer(f"Already {status}", show_alert=True)
            return

        if action == "approve":
            await db.mark_approved(pid, c.from_user.id)
            user_lang = await db.get_lang(user_id)
            if kind == "premium":
                old = await db.get_premium_until(user_id)
                base = utcnow()
                if old:
                    old_dt = from_iso(old)
                    if old_dt > base:
                        base = old_dt
                new_until = base + timedelta(days=int(plan_days))
                await db.set_premium_until(user_id, iso(new_until))
                nice_date = new_until.strftime("%d.%m.%Y %H:%M")
                await c.bot.send_message(user_id, t(user_lang, "approved_user", days=plan_days, date=nice_date), parse_mode="HTML")
            await c.answer("Approved")
            await c.message.edit_reply_markup(reply_markup=None)
            return

        if action == "reject":
            await db.mark_rejected(pid, c.from_user.id, reason=None)
            user_lang = await db.get_lang(user_id)
            await c.bot.send_message(user_id, t(user_lang, "rejected_user"))
            await c.answer("Rejected")
            await c.message.edit_reply_markup(reply_markup=None)
            return

    @dp.callback_query(F.data == "admin_panel:view_payments")
    async def admin_view_payments(c: CallbackQuery, state: FSMContext, lang: str):
        if c.from_user.id not in cfg.admin_ids:
            return await c.answer(t(lang, "admin_only"), show_alert=True)

        await state.set_state(AdminFlow.viewing_payments)
        payments = await db.get_pending_payments()
        
        if not payments:
            await c.message.edit_text(t(lang, "admin_panel_title") + "\n\n" + "Hozircha kutilayotgan to'lovlar yo'q.", reply_markup=kb_admin_main(lang))
            await c.answer()
            return
            
        await c.message.edit_text(t(lang, "admin_panel_title") + "\n\n" + "Kutilayotgan to'lovlar ro'yxati:")
        
        for pay in payments:
            _id, user_id, kind, plan_days, ocr_credits, amount, status, proof, created_at = pay
            caption = (
                f"💰 TO‘LOV (PENDING)\n"
                f"payment_id: {_id}\n"
                f"user_id: {user_id}\n"
                f"kind: {kind}\n"
                f"premium_days: {plan_days}\n"
                f"ocr_credits: {ocr_credits}\n"
                f"amount: {amount}\n"
                f"created: {created_at}\n"
            )
            try:
                await c.bot.send_photo(c.from_user.id, proof, caption=caption, reply_markup=kb_admin_payment(_id))
            except Exception as e:
                logger.error(f"Admin panel payment view error: {human_err(e)}")
                await c.bot.send_message(c.from_user.id, f"To'lovni ko'rsatishda xatolik (ID: {_id}): {human_err(e)}")
        await c.answer()

    @dp.callback_query(F.data == "admin_panel:give_premium")
    async def admin_premium_start(c: CallbackQuery, state: FSMContext, lang: str):
        if c.from_user.id not in cfg.admin_ids: return
        await state.set_state(AdminFlow.awaiting_premium_user_id)
        await c.message.edit_text(
            t(lang, "admin_prompt_user_id"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_panel:main")]])
        )
        await c.answer()

    @dp.message(AdminFlow.awaiting_premium_user_id)
    async def admin_premium_id_received(m: Message, state: FSMContext, lang: str):
        if m.from_user.id not in cfg.admin_ids: return
        if not m.text or not m.text.isdigit():
            await m.answer("❌ Iltimos, faqat raqamlardan iborat User ID yuboring.")
            return
        
        await state.update_data(target_user_id=int(m.text))
        await state.set_state(AdminFlow.awaiting_premium_days)
        await m.answer(t(lang, "admin_prompt_days"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_panel:main")]]))

    @dp.message(AdminFlow.awaiting_premium_days)
    async def admin_premium_days_received(m: Message, state: FSMContext, lang: str):
        if m.from_user.id not in cfg.admin_ids: return
        if not m.text or not m.text.isdigit():
            await m.answer("❌ Iltimos, kunlar sonini raqamda yuboring.")
            return

        days = int(m.text)
        data = await state.get_data()
        target_id = data.get("target_user_id")

        await db.ensure_user(target_id)
        old = await db.get_premium_until(target_id)
        base = utcnow()
        if old:
            old_dt = from_iso(old)
            if old_dt > base:
                base = old_dt
        
        new_until = base + timedelta(days=days)
        await db.set_premium_until(target_id, iso(new_until))
        
        # Adminni xabardor qilish
        await m.answer(t(lang, "admin_premium_given", user_id=target_id, days=days), parse_mode="HTML")
        
        # Foydalanuvchini xabardor qilish
        try:
            user_lang = await db.get_lang(target_id)
            nice_date = new_until.strftime("%d.%m.%Y %H:%M")
            await m.bot.send_message(target_id, t(user_lang, "approved_user", days=days, date=nice_date), parse_mode="HTML")
        except Exception as e:
            logger.info(f"Foydalanuvchiga xabar yuborib bo'lmadi: {e}")

        # Panelga qaytish
        await state.set_state(AdminFlow.main)
        await m.answer(t(lang, "admin_panel_title"), reply_markup=kb_admin_main(lang))


    @dp.callback_query(F.data == "admin_panel:broadcast")
    async def admin_broadcast_start(c: CallbackQuery, state: FSMContext, lang: str):
        if c.from_user.id not in cfg.admin_ids: return
        
        await state.set_state(AdminFlow.awaiting_broadcast)
        await c.message.edit_text(
            "📢 Hamma foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring (rasm, matn, video va h.k.):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_panel:main")]])
        )
        await c.answer()

    @dp.callback_query(F.data == "admin_panel:main")
    async def admin_panel_back(c: CallbackQuery, state: FSMContext, lang: str):
        if c.from_user.id not in cfg.admin_ids: return
        await state.set_state(AdminFlow.main)
        await c.message.edit_text(t(lang, "admin_panel_title"), reply_markup=kb_admin_main(lang))
        await c.answer()

    @dp.message(AdminFlow.awaiting_broadcast)
    async def admin_broadcast_execute(m: Message, state: FSMContext, lang: str):
        if m.from_user.id not in cfg.admin_ids: return
            
        users = await db.get_all_users()
        count = 0
        failed = 0
        
        status_msg = await m.answer(f"⏳ Xabar yuborilmoqda: 0/{len(users)}...")
        
        for uid in users:
            try:
                # m.copy_to xabarning turidan qat'iy nazar (rasm, video, matn) aynan o'zini nusxalaydi
                await m.copy_to(uid)
                count += 1
                if count % 20 == 0: # Har 20 ta xabarda statusni yangilab turamiz
                    await status_msg.edit_text(f"⏳ Xabar yuborilmoqda: {count}/{len(users)}...")
                await asyncio.sleep(0.05) # Telegram limitlariga tushib qolmaslik uchun kichik pauza
            except Exception:
                failed += 1
                
        await status_msg.edit_text(f"✅ Xabar yuborish yakunlandi.\n\n👤 Muvaffaqiyatli: {count}\n❌ Muvaffaqiyatsiz (bloklaganlar): {failed}")
        await state.set_state(AdminFlow.main)
        await m.answer(t(lang, "admin_panel_title"), reply_markup=kb_admin_main(lang))

    # ---------------- CORE FEATURES ----------------
    @dp.message(F.text.in_(get_all("compress"))) # lang argumentini qo'shish
    async def menu_compress(m: Message, state: FSMContext, lang: str):
        await state.clear()
        await state.set_state(CompressFlow.awaiting_file)
        await m.answer(
            t(lang, "send_compress_file"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]])
        )

    action_texts = get_all("pdf2docx") + get_all("docx2pdf") + get_all("text2docx") + get_all("text2pptx") + get_all("img2docx")
    @dp.message(F.text.in_(action_texts)) # lang argumentini qo'shish
    async def choose_action(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        
        text = m.text
        if text in get_all("pdf2docx"): action = "pdf2docx"
        elif text in get_all("docx2pdf"): action = "docx2pdf"
        elif text in get_all("text2docx"): action = "text2docx"
        elif text in get_all("text2pptx"): action = "text2pptx"
        elif text in get_all("img2docx"): action = "img2docx"
        else: return

        is_admin = uid in cfg.admin_ids

        prem, until = await is_premium(uid)
        if not prem and not await can_free(uid, "convert"):
            await m.answer(t(lang, "limit_over"))
            return

        await state.clear()
        await state.update_data(action=action)

        if action == "img2docx":
            await state.set_state(ImgConvertFlow.awaiting_image)
            await state.update_data(images=[])
            msg_text = "🖼 Bir nechta rasm yuboring:"
        elif action in ("text2docx", "text2pptx"):
            await state.set_state(ConvertFlow.awaiting_text)
            await state.update_data(accumulated_text="")
            msg_text = "✍️ Matn yuboring:"
        else:
            await state.set_state(ConvertFlow.awaiting_file)
            msg_text = "📎 Fayl yuboring:"

        await m.answer(msg_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]]))

    @dp.message(StateFilter(ConvertFlow.awaiting_text, ConvertFlow.awaiting_text_confirmation))
    async def handle_text_input(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        
        # Limitni har bir xabar kelganda tekshiramiz (yomon niyatli foydalanuvchilar serverni band qilmasligi uchun)
        prem, _ = await is_premium(uid)
        if not prem and not await can_free(uid, "convert"):
            await m.answer(t(lang, "limit_over"))
            await state.clear()
            return
    
        current_text = (m.text or "").strip()
        if not current_text:
            await m.answer(t(lang, "send_text"))
            return
    
        data = await state.get_data()
        accumulated = data.get("accumulated_text", "")
        if accumulated:
            accumulated += "\n" + current_text
        else:
            accumulated = current_text
            
        await state.update_data(accumulated_text=accumulated)
        await state.set_state(ConvertFlow.awaiting_text_confirmation)
        
        # Oldingi tasdiqlash xabari bo'lsa o'chirish
        old_msg = data.get("conf_msg_id")
        if old_msg:
            try: await m.bot.delete_message(m.chat.id, old_msg)
            except: pass
            
        msg = await m.answer(
            t(lang, "text_received_confirm") + f"\n\n" + t(lang, "current_text_length", length=len(accumulated)),
            reply_markup=kb_text_confirmation(lang)
        )
        await state.update_data(conf_msg_id=msg.message_id)

    @dp.callback_query(F.data == "text_convert:confirm")
    async def confirm_text_conversion(c: CallbackQuery, state: FSMContext):
        uid = c.from_user.id
        lang = await db.get_lang(uid)
        prem, _ = await is_premium(uid)
    
        if not prem and not await can_free(uid, "convert"):
            await c.message.edit_text(t(lang, "limit_over"))
            await state.clear()
            return
            
        out_path = None
        data = await state.get_data()
        action = data.get("action")
        final_text = data.get("accumulated_text", "").strip()

        if not final_text:
            return await c.answer(t(lang, "send_text"), show_alert=True)

        await c.message.edit_text(t(lang, "processing"))

        async def job():
            if action == "text2docx":
                out = os.path.join(cfg.tmp_dir, rand_name("Hujjat", "docx"))
                await asyncio.to_thread(text_to_docx, final_text, out, "Generated Document")
                return out
            elif action == "text2pptx":
                out = os.path.join(cfg.tmp_dir, rand_name("Slayd", "pptx"))
                await asyncio.to_thread(text_to_pptx, final_text, out, "Generated Slides")
                return out
            raise RuntimeError("Noma'lum amal")

        try:
            out_path = await run_heavy(uid, job)
            await c.message.answer_document(_sendable(out_path), caption=t(lang, "done"), parse_mode="HTML", request_timeout=300)
            await c.message.answer(t(lang, "menu"), reply_markup=kb_main(lang))
            if not prem:
                await mark_used(uid, "convert")
        except Exception as e:
            logger.error(f"Text conversion error: {e}")
            await c.message.answer(f"⚠️ Xatolik: {human_err(e)}")
        finally:
            if out_path and os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass
            await state.clear()
            try: await c.message.delete()
            except: pass

    @dp.callback_query(F.data == "text_convert:cancel")
    async def cancel_text_input(c: CallbackQuery, state: FSMContext, lang: str):
        await c.message.edit_text(t(lang, "text_input_cancelled"))
        await c.message.answer(t(lang, "menu"), reply_markup=kb_main(lang))
        await state.clear()
        await c.answer()
    @dp.message(ImgConvertFlow.awaiting_image)
    async def do_img_upload(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        
        in_path, kind = await get_file_from_message(m)
        if kind == "too_big":
            await m.answer(t(lang, "too_big", mb=cfg.max_file_mb))
            return
        if not in_path:
            await m.answer(t(lang, "bad_input"))
            return
            
        ext = os.path.splitext(in_path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            await m.answer("Rasm yuboring (JPG/PNG).")
            return

        # Albom kelganda rasmlar adashib ketmasligi uchun Lock (ulock) dan foydalanamiz
        async with ulock(uid):
            data = await state.get_data()
            images = data.get("images", [])
            images.append(in_path)
            await state.update_data(images=images)
            count = len(images)
            prev_msg = data.get("img_msg_id")
            
        if prev_msg:
            try: await m.bot.delete_message(m.chat.id, prev_msg)
            except: pass
            
        msg = await m.answer(t(lang, "img_received", count=count), reply_markup=kb_finish_images(lang))
        await state.update_data(img_msg_id=msg.message_id)

    @dp.callback_query(F.data == "do:img2docx_finish")
    async def do_img_finish(c: CallbackQuery, state: FSMContext, lang: str):
        uid = c.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        out_path = None
        prem, _ = await is_premium(uid)
        
        data = await state.get_data()
        images = data.get("images", [])
        
        if not images:
            return await c.answer("Rasm yubormadingiz!", show_alert=True)

        await c.message.edit_text(t(lang, "processing"))
        
        async def job():
            out = os.path.join(cfg.tmp_dir, rand_name("Word", "docx"))
            await asyncio.to_thread(images_to_docx_embed, images, out)
            return out

        try:
            out_path = await run_heavy(uid, job)
            await c.message.answer_document(_sendable(out_path), caption=t(lang, "done"), parse_mode="HTML", request_timeout=300)
            await c.message.answer(t(lang, "menu"), reply_markup=kb_main(lang))
            if not prem:
                await mark_used(uid, "convert")
        except Exception as e:
            logger.info(f"file error: {human_err(e)}")
            await c.message.answer(f"⚠️ Xatolik: {human_err(e)}")
        finally:
            try:
                await c.message.delete()
            except Exception: pass
            if out_path and os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass
            for img in images:
                if os.path.exists(img):
                    try: os.remove(img)
                    except: pass
            await state.clear()

    @dp.message(CompressFlow.awaiting_file)
    async def do_compress(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        prem, _ = await is_premium(uid)

        in_path, kind = await get_file_from_message(m)
        if kind == "too_big":
            await m.answer(t(lang, "too_big", mb=cfg.max_file_mb))
            return
        if not in_path:
            await m.answer(t(lang, "bad_input"))
            return

        out_path = None
        proc_msg = await m.answer(t(lang, "processing"))
        ext = os.path.splitext(in_path)[1].lower()

        async def job():
            out = os.path.join(cfg.tmp_dir, rand_name("Siqilgan", ext.lstrip('.')))
            if ext == ".pdf":
                return await asyncio.to_thread(compress_pdf, cfg.gs_path, in_path, out)
            elif ext in (".docx", ".pptx"):
                return await asyncio.to_thread(compress_office_file, in_path, out)
            else:
                raise RuntimeError("Faqat PDF, DOCX yoki PPTX siqish mumkin.")

        try:
            out_path = await run_heavy(uid, job)
            # Siqilganlik darajasini ko'rsatish
            old_bytes = os.path.getsize(in_path)
            new_bytes = os.path.getsize(out_path)

            def format_size(b: int) -> str:
                if b < 1024 * 1024:
                    return f"{b/1024:.1f}KB"
                return f"{b/(1024*1024):.1f}MB"

            caption = t(lang, "done") + f"\n📉 {format_size(old_bytes)} ➡️ {format_size(new_bytes)}"
            
            await m.answer_document(_sendable(out_path), caption=caption, parse_mode="HTML")
            await m.answer(t(lang, "menu"), reply_markup=kb_main(lang))
            if not prem:
                await mark_used(uid, "convert")
        except Exception as e:
            logger.error(f"Compress error: {e}")
            await m.answer(f"⚠️ Xatolik: {human_err(e)}")
        finally:
            await proc_msg.delete()
            if os.path.exists(in_path): os.remove(in_path)
            if out_path and os.path.exists(out_path):
                os.remove(out_path)
            await state.clear()

    # ---------------- OCR ----------------
    @dp.message(F.text.in_(get_all("ocr_menu")))
    async def menu_ocr(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        
        # Premium tekshiruvi
        prem, _ = await is_premium(uid)
        if not prem:
            credits = await db.get_ocr_credits(uid)
            if credits <= 0:
                await m.answer(t(lang, "ocr_no_credits"))
                return
        
        await state.clear()
        await state.set_state(OcrFlow.awaiting_image)
        await m.answer(
            t(lang, "send_ocr_image"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]])
        )

    @dp.message(OcrFlow.awaiting_image)
    async def do_ocr_image(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz

        in_path, kind = await get_file_from_message(m)
        if kind == "too_big":
            await m.answer(t(lang, "too_big", mb=cfg.max_file_mb))
            return
        if not in_path:
            await m.answer(t(lang, "bad_input"))
            return
            
        ext = os.path.splitext(in_path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            await m.answer(t(lang, "err_not_image"))
            if os.path.exists(in_path): os.remove(in_path)
            return

        await state.update_data(ocr_image_path=in_path)
        await state.set_state(OcrFlow.choosing_lang)
        await m.answer(t(lang, "ocr_choose_lang"), reply_markup=kb_ocr_lang())

    @dp.callback_query(F.data.startswith("ocr_lang:"))
    async def do_ocr_lang_choice(c: CallbackQuery, state: FSMContext, lang: str):
        uid = c.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        ocr_lang = c.data.split(":", 1)[1]

        data = await state.get_data()
        image_path = data.get("ocr_image_path")
        if not image_path or not os.path.exists(image_path):
            await c.message.edit_text("Xatolik: Rasm topilmadi. Qayta urinib ko'ring.")
            await state.clear()
            return

        prem, _ = await is_premium(uid)
        if not prem and not await db.consume_ocr_credit(uid):
            await c.message.edit_text(t(lang, "ocr_no_credits"))
            await state.clear()
            if os.path.exists(image_path): os.remove(image_path)
            return

        await c.message.edit_text(t(lang, "ocr_processing"))
        try:
            result_text = await asyncio.to_thread(ocr_image, image_path, ocr_lang)
            await c.message.answer(f"<b>{t(lang, 'ocr_result')}</b>\n\n{html.escape(result_text)}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"OCR error: {e}")
            await c.message.answer(t(lang, "err_generic"))
        finally:
            if os.path.exists(image_path): os.remove(image_path)
            await state.clear()
            await c.message.answer(t(lang, "menu"), reply_markup=kb_main(lang))

    @dp.message(ConvertFlow.awaiting_file)
    async def do_file(m: Message, state: FSMContext, lang: str):
        uid = m.from_user.id # Middleware langni olib beradi, lekin uidni o'zimiz olamiz
        prem, _ = await is_premium(uid)

        if not prem and not await can_free(uid, "convert"):
            await m.answer(t(lang, "limit_over"))
            await state.clear()
            return

        action = (await state.get_data()).get("action")
        in_path, kind = await get_file_from_message(m)
        if kind == "too_big":
            await m.answer(t(lang, "too_big", mb=cfg.max_file_mb))
            return
        if not in_path:
            await m.answer(t(lang, "bad_input"))
            return

        proc_msg = await m.answer(t(lang, "processing"))
        ext = os.path.splitext(in_path)[1].lower()

        async def job():
            if action == "pdf2docx":
                if ext != ".pdf":
                    raise ValueError("err_not_pdf")
                out = os.path.join(cfg.tmp_dir, rand_name("Fayl", "docx"))
                await asyncio.to_thread(pdf_to_docx, in_path, out)
                return out

            if action == "docx2pdf":
                if ext != ".docx":
                    raise ValueError("err_not_docx")
                # Linuxda soffice odatda /usr/bin/soffice da bo'ladi
                lo_path = cfg.libreoffice_path or "/usr/bin/soffice"
                if not os.path.exists(lo_path):
                    raise RuntimeError(t(lang, "need_lo"))
                out_pdf = await asyncio.to_thread(docx_to_pdf, lo_path, in_path, cfg.tmp_dir)
                return out_pdf
            raise RuntimeError("not_supported")

        try:
            out_path = await run_heavy(uid, job)
            await m.answer_document(_sendable(out_path), caption=t(lang, "done"), parse_mode="HTML", request_timeout=300)
            await m.answer(t(lang, "menu"), reply_markup=kb_main(lang))
            if not prem:
                await mark_used(uid, "convert")
        except ValueError as ve:
            # Biz bilgan xatoliklar (til kalitlari orqali yuboriladi)
            err_key = str(ve)
            await m.answer(t(lang, err_key))
        except Exception as e:
            logger.error(f"file error: {e}", exc_info=True)
            await m.answer(t(lang, "err_generic"))
        finally:
            try:
                await proc_msg.delete()
            except Exception: pass
            if 'in_path' in locals() and in_path and os.path.exists(in_path):
                try: os.remove(in_path)
                except: pass
            if 'out_path' in locals() and out_path and os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass

    if not cfg.webhook_url:
        logger.info("Starting polling...")
        await dp.start_polling(bot)
    else:
        logger.info(f"Starting webhook on {cfg.webhook_url}...")
        await bot.set_webhook(cfg.webhook_url)
        
        app = web.Application()
        # Webhook pathini URL dan ajratib olamiz (masalan, /webhook)
        webhook_path = "/" + cfg.webhook_url.split("/")[-1]
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)
        setup_application(app, dp, bot=bot)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=cfg.webapp_host, port=cfg.webapp_port)
        await site.start()
        # Bot ishlab turishi uchun cheksiz kutish
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
