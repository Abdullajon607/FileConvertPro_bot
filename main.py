import os
import asyncio
import aiohttp
from datetime import timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import load_config
from db import DB
from states import LangFlow, ConvertFlow, TranslitFlow, PaymentFlow
from keyboards import (
    kb_lang, kb_main, kb_translit_dir, kb_pay_kind,
    kb_premium_plans, kb_admin_payment
)
from i18n import t
from utils import (
    setup_logger, ensure_dir, today_str_local,
    utcnow, iso, from_iso, rand_name, safe_ext,
    size_ok, human_err, is_url
)

from services.translit import latin_to_cyr, cyr_to_latin
from services.convert import pdf_to_docx, docx_to_pdf, text_to_docx, text_to_pptx, image_to_docx_embed


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
    day = today_str_local()
    await db.ensure_usage(user_id, day)
    c_used, t_used = await db.get_usage(user_id, day)
    if kind == "convert":
        return c_used < 1
    if kind == "translit":
        return t_used < 1
    return False

async def mark_used(user_id: int, kind: str):
    day = today_str_local()
    await db.ensure_usage(user_id, day)
    if kind == "convert":
        await db.inc_usage(user_id, day, "convert_used")
    elif kind == "translit":
        await db.inc_usage(user_id, day, "translit_used")

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
            await m.bot.send_message(target_id, t(user_lang, "approved_user", msg=f"Sizga {days} kunlik premium sovg'a qilindi!"))
        except Exception:
            pass

    @dp.callback_query(F.data.startswith("lang:"))
    async def set_lang(c: CallbackQuery, state: FSMContext):
        lang = c.data.split(":", 1)[1]
        await db.ensure_user(c.from_user.id)
        await db.set_lang(c.from_user.id, lang)
        await state.clear()
        await c.message.edit_text(t(lang, "menu"), reply_markup=kb_main(lang))
        await c.answer()

    @dp.callback_query(F.data == "menu:back")
    async def back_menu(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        await state.clear()
        await c.message.edit_text(t(lang, "menu"), reply_markup=kb_main(lang))
        await c.answer()

    # ---------------- TRANSLIT ----------------
    @dp.callback_query(F.data == "menu:translit")
    async def menu_translit(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        await state.clear()
        await state.set_state(TranslitFlow.choosing_dir)
        await c.message.answer(t(lang, "tr_choose"), reply_markup=kb_translit_dir(lang))
        await c.answer()

    @dp.callback_query(F.data.startswith("tr:"))
    async def tr_choose(c: CallbackQuery, state: FSMContext):
        direction = c.data.split(":")[1]
        await state.set_state(TranslitFlow.awaiting_text)
        await state.update_data(tr_dir=direction)
        lang = await db.get_lang(c.from_user.id)
        await c.message.answer(t(lang, "send_text"))
        await c.answer()

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

        d = (await state.get_data()).get("tr_dir", "cl")
        out = cyr_to_latin(text) if d == "cl" else latin_to_cyr(text)
        await m.answer(out)

        if not prem:
            await mark_used(uid, "translit")
        await state.clear()

    # ---------------- PAYMENTS ----------------
    @dp.callback_query(F.data == "menu:pay")
    async def menu_pay(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        await state.clear()
        await state.set_state(PaymentFlow.choosing_kind)
        await c.message.answer(t(lang, "pay_choose"), reply_markup=kb_pay_kind(lang))
        await c.answer()

    @dp.callback_query(F.data == "pay:back")
    async def pay_back(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        await state.set_state(PaymentFlow.choosing_kind)
        await c.message.answer(t(lang, "pay_choose"), reply_markup=kb_pay_kind(lang))
        await c.answer()

    @dp.callback_query(F.data == "pay:kind:premium")
    async def pay_kind_premium(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        await state.set_state(PaymentFlow.choosing_plan)
        await c.message.answer(
            t(lang, "pay_premium_choose"),
            reply_markup=kb_premium_plans(cfg.price_7, cfg.price_30, cfg.price_365)
        )
        await c.answer()


    @dp.callback_query(F.data.startswith("pay:premium:"))
    async def pay_premium_choose(c: CallbackQuery, state: FSMContext):
        lang = await db.get_lang(c.from_user.id)
        days = int(c.data.split(":")[-1])
        amount = cfg.price_7 if days == 7 else cfg.price_30 if days == 30 else cfg.price_365
        pid = await db.create_payment_premium(c.from_user.id, days, amount)
        await state.set_state(PaymentFlow.awaiting_proof)
        await state.update_data(payment_id=pid)
        await c.message.answer(t(lang, "pay_info", card=cfg.card_number, owner=cfg.card_owner))
        await c.message.answer(f"⭐ Premium: {days} kun\n💵 {amount} so‘m\n📎 Chek yuboring.")
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
            if kind == "premium":
                old = await db.get_premium_until(user_id)
                base = utcnow()
                if old:
                    old_dt = from_iso(old)
                    if old_dt > base:
                        base = old_dt
                new_until = base + timedelta(days=int(plan_days))
                await db.set_premium_until(user_id, iso(new_until))
                msg = f"Premium {plan_days} kun. Until: {iso(new_until)}"
            user_lang = await db.get_lang(user_id)
            await c.bot.send_message(user_id, t(user_lang, "approved_user", msg=msg))
            await c.answer("Approved")
            return

        if action == "reject":
            await db.mark_rejected(pid, c.from_user.id, reason=None)
            user_lang = await db.get_lang(user_id)
            await c.bot.send_message(user_id, t(user_lang, "rejected_user"))
            await c.answer("Rejected")
            return

    # ---------------- CORE FEATURES ----------------
    @dp.callback_query(F.data.startswith("do:"))
    async def choose_action(c: CallbackQuery, state: FSMContext):
        uid = c.from_user.id
        lang = await db.get_lang(uid)
        action = c.data.split(":", 1)[1]
        is_admin = uid in cfg.admin_ids


        prem, until = await is_premium(uid)
        if not prem and not await can_free(uid, "convert"):
            await c.message.answer(t(lang, "limit_over"))
            await c.answer()
            return

        await state.clear()
        await state.update_data(action=action)

        if action in ("text2docx", "text2pptx"):
            await state.set_state(ConvertFlow.awaiting_text)
            await c.message.answer(t(lang, "send_text"))
        else:
            await state.set_state(ConvertFlow.awaiting_file)
            await c.message.answer(t(lang, "send_file"))

        if not prem:
            await c.message.answer(t(lang, "free_left"))
        else:
            await c.message.answer(t(lang, "premium_active", until=until))

        await c.answer()

    @dp.message(ConvertFlow.awaiting_text)
    async def do_text(m: Message, state: FSMContext):
        uid = m.from_user.id
        lang = await db.get_lang(uid)
        prem, _ = await is_premium(uid)

        action = (await state.get_data()).get("action")
        text = (m.text or "").strip()
        if not text:
            await m.answer(t(lang, "send_text"))
            return

        await m.answer(t(lang, "processing"))

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
            await m.answer_document(_sendable(out_path), request_timeout=300)
            await m.answer(t(lang, "done"))
            if not prem:
                await mark_used(uid, "convert")
        except Exception as e:
            logger.info(f"text error: {human_err(e)}")
            await m.answer(f"⚠️ Xatolik: {human_err(e)}")
        finally:
            await state.clear()

    @dp.message(ConvertFlow.awaiting_file)
    async def do_file(m: Message, state: FSMContext):
        uid = m.from_user.id
        lang = await db.get_lang(uid)
        prem, _ = await is_premium(uid)

        action = (await state.get_data()).get("action")
        in_path, kind = await get_file_from_message(m)
        if kind == "too_big":
            await m.answer(t(lang, "too_big", mb=cfg.max_file_mb))
            return
        if not in_path:
            await m.answer(t(lang, "bad_input"))
            return

        await m.answer(t(lang, "processing"))
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

            if action == "img2docx":
                if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                    raise RuntimeError("Rasm yuboring (JPG/PNG).")
                out = os.path.join(cfg.tmp_dir, rand_name("scan", "docx"))
                await asyncio.to_thread(image_to_docx_embed, in_path, out, "Scan")
                return out

            raise RuntimeError("not_supported")

        try:
            out_path = await run_heavy(uid, job)
            await m.answer_document(_sendable(out_path), request_timeout=300)
            await m.answer(t(lang, "done"))
            if not prem:
                await mark_used(uid, "convert")
        except Exception as e:
            logger.info(f"file error: {human_err(e)}")
            await m.answer(f"⚠️ Xatolik: {human_err(e)}")
        finally:
            await state.clear()


    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
