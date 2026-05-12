import os
import asyncio
import aiohttp
import time
import re
import html
from datetime import timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import load_config
from db import DB
from states import LangFlow, ConvertFlow, ImgConvertFlow, TranslitFlow, PaymentFlow, ContactAdminFlow
from keyboards import (
    kb_lang, kb_main, kb_pay_kind,
    kb_premium_plans, kb_admin_payment, kb_finish_images
)
from i18n import t, get_all
from utils import (
    setup_logger, ensure_dir, week_str_local,
    utcnow, iso, from_iso, rand_name, safe_ext,
    size_ok, human_err, is_url
)

from services.translit import latin_to_cyr, cyr_to_latin
from services.convert import pdf_to_docx, docx_to_pdf, text_to_docx, text_to_pptx, images_to_docx_embed


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
        p = os.path.join(tmp, rand_name("in", ext))
        f = await m.bot.get_file(m.document.file_id, request_timeout=300)
        await m.bot.download_file(f.file_path, p, timeout=300)
        return (p, "file")

    if m.photo:
        p = os.path.join(tmp, rand_name("in", "jpg"))
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
        raise RuntimeError("BOT_TOKEN bo'sh (.env ni tekshir)")

    ensure_dir(cfg.tmp_dir)
    ensure_dir(cfg.log_dir)
    asyncio.create_task(cleanup_tmp_files(cfg.tmp_dir))
    await db.init()

    bot = Bot(cfg.token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(m: Message, state: FSMContext):
        await db.ensure_user(m.from_user.id)
        await state.set_state(LangFlow.choosing)
        await m.answer(t("uz", "choose_lang"), reply_markup=kb_lang())

    @dp.message(Command("give_premium"))
    async def cmd_give_premium(m: Message):
        if m.from_user.id not in cfg.admin_ids:
            return
            
        parts = m.text.split()
        if len(parts) < 3:
            await m.answer("⚠️ Format: /give_premium <user_id> <kun_soni>\nMasalan: /give_premium 6907296588 365")
            return
        
        try:
            target_id = int(parts[1])
            days = int(parts[2])
        except ValueError:
            await m.answer("❌ Xato! user_id va kun soni faqat raqamlardan iborat bo'lishi kerak.")
            return
            
        await db.ensure_user(target_id)
        old = await db.get_premium_until(target_id)
        base = utcnow()
        if old:
            old_dt = from_iso(old)
            if old_dt > base:
                base = old_dt
        new_until = base + timedelta(days=days)
        await db.set_premium_until(target_id, iso(new_until))
        
        await m.answer(f"✅ {target_id} idli foydalanuvchiga {days} kunlik premium berildi.\n⏰ Tugash vaqti: {iso(new_until)}")
        
        try:
            user_lang = await db.get_lang(target_id)
            nice_date = new_until.strftime("%d.%m.%Y %H:%M")
            await m.bot.send_message(target_id, t(user_lang, "approved_user", days=days, date=nice_date), parse_mode="HTML")
        except Exception:
            pass

    @dp.callback_query(F.data.startswith("lang:"))
    async def set_lang(c: CallbackQuery, state: FSMContext):
        lang = c.data.split(":", 1)[1]
        await db.ensure_user(c.from_user.id)
        await db.set_lang(c.from_user.id, lang)
        await state.clear()
        await c.message.delete()
        await c.message.answer(t(lang, "menu"), reply_markup=kb_main(lang))
        await c.answer()

    @dp.callback_query(F.data == "menu:back")
    async def back_menu(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        await state.clear()
        await c.message.delete()
        await c.message.answer(t(lang, "menu"), reply_markup=kb_main(lang))
        await c.answer()

    @dp.message(F.text.in_(get_all("profile")))
    async def menu_profile(m: Message, state: FSMContext):
        await state.clear()
        uid = m.from_user.id
        lang = await db.get_lang(uid)
        prem, until = await is_premium(uid)
        week = week_str_local()
        await db.ensure_usage(uid, week)
        c_used, t_used = await db.get_usage(uid, week)
        total_used = c_used + t_used
        
        status = f"💎 Premium (Tugash: {until})" if prem else "Standart"
        limit_info = "Cheksiz" if prem else f"{max(0, 3 - total_used)} ta qoldi (Haftalik: 3 ta)"
        
        text = (
            f"👤 <b>Sizning profilingiz:</b>\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"📊 Status: {status}\n"
            f"🔄 Bepul limitlar: {limit_info}"
        )
        await m.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]]))

    # ---------------- CONTACT ADMIN ----------------
    @dp.message(F.text.in_(get_all("contact_admin")))
    async def menu_contact_admin(m: Message, state: FSMContext):
        lang = await db.get_lang(m.from_user.id)
        await state.clear()
        await state.set_state(ContactAdminFlow.awaiting_message)
        await m.answer(
            t(lang, "send_admin_msg"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]])
        )

    @dp.message(ContactAdminFlow.awaiting_message)
    async def admin_message_received(m: Message, state: FSMContext):
        uid = m.from_user.id
        lang = await db.get_lang(uid)
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
    @dp.message(F.text.in_(get_all("translit")))
    async def menu_translit(m: Message, state: FSMContext):
        lang = await db.get_lang(m.from_user.id)
        await state.clear()
        await state.set_state(TranslitFlow.awaiting_text)
        await m.answer(
            t(lang, "send_text"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]])
        )

    @dp.message(TranslitFlow.awaiting_text)
    async def tr_do(m: Message, state: FSMContext):
        uid = m.from_user.id
        lang = await db.get_lang(uid)
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
    @dp.message(F.text.in_(get_all("pay")))
    async def menu_pay(m: Message, state: FSMContext):
        lang = await db.get_lang(m.from_user.id)
        await state.clear()
        await state.set_state(PaymentFlow.choosing_kind)
        await m.answer(t(lang, "pay_choose"), reply_markup=kb_pay_kind(lang))

    @dp.callback_query(F.data == "pay:back")
    async def pay_back(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        await state.set_state(PaymentFlow.choosing_kind)
        await c.message.delete()
        await c.message.answer(t(lang, "pay_choose"), reply_markup=kb_pay_kind(lang))
        await c.answer()

    @dp.callback_query(F.data == "pay:kind:premium")
    async def pay_kind_premium(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        await state.set_state(PaymentFlow.choosing_plan)
        await c.message.delete()
        await c.message.answer(
            t(lang, "pay_premium_choose"),
            reply_markup=kb_premium_plans(cfg.price_1, cfg.price_7, cfg.price_30, cfg.price_365)
        )
        await c.answer()


    @dp.callback_query(F.data.startswith("pay:premium:"))
    async def pay_premium_choose(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
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
    async def payment_proof(m: Message, state: FSMContext):
        lang = await db.get_lang(m.from_user.id)
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
    async def admin_action(c: CallbackQuery):
        if c.from_user.id not in cfg.admin_ids:
            lang = await db.get_lang(c.from_user.id)
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
            return

        if action == "reject":
            await db.mark_rejected(pid, c.from_user.id, reason=None)
            user_lang = await db.get_lang(user_id)
            await c.bot.send_message(user_id, t(user_lang, "rejected_user"))
            await c.answer("Rejected")
            return

    # ---------------- CORE FEATURES ----------------
    action_texts = get_all("pdf2docx") + get_all("docx2pdf") + get_all("text2docx") + get_all("text2pptx") + get_all("img2docx")
    @dp.message(F.text.in_(action_texts))
    async def choose_action(m: Message, state: FSMContext):
        uid = m.from_user.id
        lang = await db.get_lang(uid)
        
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

        msg_text = ""
        if action == "img2docx":
            await state.set_state(ImgConvertFlow.awaiting_image)
            await state.update_data(images=[])
            msg_text = "🖼 " + t(lang, "send_file") + " Bir nechta rasm yuborishingiz mumkin."
        elif action in ("text2docx", "text2pptx"):
            await state.set_state(ConvertFlow.awaiting_text)
            msg_text = t(lang, "send_text")
        else:
            await state.set_state(ConvertFlow.awaiting_file)
            msg_text = t(lang, "send_file")

        if not prem:
            msg_text += "\n\n" + t(lang, "free_left")
        else:
            msg_text += "\n\n" + t(lang, "premium_active", until=until)

        await m.answer(msg_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="menu:back")]]))

    @dp.message(ConvertFlow.awaiting_text)
    async def do_text(m: Message, state: FSMContext):
        uid = m.from_user.id
        lang = await db.get_lang(uid)
        prem, _ = await is_premium(uid)

        if not prem and not await can_free(uid, "convert"):
            await m.answer(t(lang, "limit_over"))
            await state.clear()
            return

        action = (await state.get_data()).get("action")
        text = (m.text or "").strip()
        if not text:
            await m.answer(t(lang, "send_text"))
            return

        proc_msg = await m.answer(t(lang, "processing"))

        async def job():
            if action == "text2docx":
                out = os.path.join(cfg.tmp_dir, rand_name("text", "docx"))
                await asyncio.to_thread(text_to_docx, text, out, "Generated Document")
                return out
            if action == "text2pptx":
                out = os.path.join(cfg.tmp_dir, rand_name("text", "pptx"))
                await asyncio.to_thread(text_to_pptx, text, out, "Generated Slides")
                return out
            raise RuntimeError("not_supported")

        try:
            out_path = await run_heavy(uid, job)
            await m.answer_document(_sendable(out_path), caption=t(lang, "done"), request_timeout=300)
            await m.answer(t(lang, "menu"), reply_markup=kb_main(lang))
            if not prem:
                await mark_used(uid, "convert")
        except Exception as e:
            logger.info(f"text error: {human_err(e)}")
            await m.answer(f"⚠️ Xatolik: {human_err(e)}")
        finally:
            try:
                await proc_msg.delete()
            except Exception: pass
            if 'out_path' in locals() and out_path and os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass

    @dp.message(ImgConvertFlow.awaiting_image)
    async def do_img_upload(m: Message, state: FSMContext):
        uid = m.from_user.id
        lang = await db.get_lang(uid)
        
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
    async def do_img_finish(c: CallbackQuery, state: FSMContext):
        uid = c.from_user.id
        lang = await db.get_lang(uid)
        prem, _ = await is_premium(uid)
        
        data = await state.get_data()
        images = data.get("images", [])
        
        if not images:
            await c.answer("Rasm yubormadingiz!", show_alert=True)
            return
            
        await c.message.edit_text(t(lang, "processing"))
        
        async def job():
            out = os.path.join(cfg.tmp_dir, rand_name("scan", "docx"))
            await asyncio.to_thread(images_to_docx_embed, images, out, "Scan")
            return out

        try:
            out_path = await run_heavy(uid, job)
            await c.message.answer_document(_sendable(out_path), caption=t(lang, "done"), request_timeout=300)
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
            if 'out_path' in locals() and out_path and os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass
            for img in images:
                if os.path.exists(img):
                    try: os.remove(img)
                    except: pass
            await state.clear()

    @dp.message(ConvertFlow.awaiting_file)
    async def do_file(m: Message, state: FSMContext):
        uid = m.from_user.id
        lang = await db.get_lang(uid)
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
                    raise RuntimeError("PDF yuboring.")
                out = os.path.join(cfg.tmp_dir, rand_name("out", "docx"))
                await asyncio.to_thread(pdf_to_docx, in_path, out)
                return out

            if action == "docx2pdf":
                if ext != ".docx":
                    raise RuntimeError("DOCX yuboring.")
                if not cfg.libreoffice_path or not os.path.exists(cfg.libreoffice_path):
                    raise RuntimeError(t(lang, "need_lo"))
                out_pdf = await asyncio.to_thread(docx_to_pdf, cfg.libreoffice_path, in_path, cfg.tmp_dir)
                return out_pdf

            raise RuntimeError("not_supported")

        try:
            out_path = await run_heavy(uid, job)
            await m.answer_document(_sendable(out_path), caption=t(lang, "done"), request_timeout=300)
            await m.answer(t(lang, "menu"), reply_markup=kb_main(lang))
            if not prem:
                await mark_used(uid, "convert")
        except Exception as e:
            logger.info(f"file error: {human_err(e)}")
            await m.answer(f"⚠️ Xatolik: {human_err(e)}")
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


    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
