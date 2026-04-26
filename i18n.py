from typing import Dict, Any

DEFAULT_LANG = "uz"

TEXT: Dict[str, Dict[str, str]] = {
  "uz": {
    "choose_lang":"Tilni tanlang:",
    "menu":"🌟 Asosiy menyu:\nQuyidagi xizmatlardan birini tanlang:",

    "pdf2docx":"📄 PDF ➡️ DOCX",
    "docx2pdf":"📝 DOCX ➡️ PDF",
    "text2docx":"✍️ Matn ➡️ DOCX",
    "text2pptx":"📊 Matn ➡️ PPTX",
    "img2docx":"🖼 Rasm ➡️ DOCX",

    "translit":"🔤 Kiril ↔️ Lotin",
    "pay":"💎 Premium & To‘lov",

    "send_file":"📎 Iltimos, faylni yuboring.",
    "send_text":"✍️ Iltimos, matn yuboring.",

    "processing":"⏳ Fayl tayyorlanmoqda, biroz kuting...",
    "done":"✅ Muvaffaqiyatli yakunlandi!",
    "bad_input":"⚠️ Fayl yuboring.",
    "too_big":"⚠️ Fayl juda katta. Limit: {mb} MB",

    "limit_over":"🔒 Bepul limit tugadi. Premium kerak.",
    "free_left":"✅ Bugun 1 marta bepul ishlaydi.",
    "premium_active":"✅ Premium faol. Tugash: {until}",

    "pay_choose":"To‘lov turini tanlang:",
    "pay_premium_choose":"Premium paketni tanlang:",
    "pay_info":"To‘lov karta:\n💳 {card}\n👤 {owner}\n\nTo‘lov qiling va чек/skrin yuboring.",
    "pending_exists":"⏳ Sizda pending to‘lov bor. Kuting.",
    "sent_admin":"✅ Adminga yuborildi. Tasdiqlansa aktiv bo‘ladi.",
    "approved_user":"✅ Tasdiqlandi! {msg}",
    "rejected_user":"❌ Rad etildi. Qayta urinib ko‘ring.",

    "tr_choose":"Yo‘nalishni tanlang:",
    "admin_only":"⛔ Admin emas.",

    "need_lo":"DOCX→PDF uchun LibreOffice kerak. (.env LIBREOFFICE_PATH ni to‘g‘ri qiling)",
  },
  "ru": {
    "choose_lang":"Выберите язык:",
    "menu":"🌟 Главное меню:\nВыберите нужную услугу:",

    "pdf2docx":"📄 PDF ➡️ DOCX",
    "docx2pdf":"📝 DOCX ➡️ PDF",
    "text2docx":"✍️ Текст ➡️ DOCX",
    "text2pptx":"📊 Текст ➡️ PPTX",
    "img2docx":"🖼 Фото ➡️ DOCX",

    "translit":"🔤 Кир ↔️ Лат",
    "pay":"💎 Premium & Оплата",

    "send_file":"📎 Пожалуйста, отправьте файл.",
    "send_text":"✍️ Пожалуйста, отправьте текст.",

    "processing":"⏳ Обработка файла, подождите...",
    "done":"✅ Успешно завершено!",
    "bad_input":"⚠️ Отправьте файл.",
    "too_big":"⚠️ Файл слишком большой. Лимит: {mb} MB",

    "limit_over":"🔒 Бесплатный лимит закончился. Нужен Premium.",
    "free_left":"✅ 1 бесплатный запуск в день.",
    "premium_active":"✅ Premium активен до: {until}",

    "pay_choose":"Выберите тип оплаты:",
    "pay_premium_choose":"Выберите Premium пакет:",
    "pay_info":"Оплата на карту:\n💳 {card}\n👤 {owner}\n\nОплатите и отправьте чек/скрин.",
    "pending_exists":"⏳ У вас есть pending-платёж.",
    "sent_admin":"✅ Отправлено админу.",
    "approved_user":"✅ Подтверждено! {msg}",
    "rejected_user":"❌ Отклонено.",

    "tr_choose":"Выберите направление:",
    "admin_only":"⛔ Вы не админ.",

    "need_lo":"Для DOCX→PDF нужен LibreOffice. Проверьте LIBREOFFICE_PATH в .env",
  },
  "en": {
    "choose_lang":"Choose language:",
    "menu":"🌟 Main Menu:\nPlease choose a service:",

    "pdf2docx":"📄 PDF ➡️ DOCX",
    "docx2pdf":"📝 DOCX ➡️ PDF",
    "text2docx":"✍️ Text ➡️ DOCX",
    "text2pptx":"📊 Text ➡️ PPTX",
    "img2docx":"🖼 Image ➡️ DOCX",

    "translit":"🔤 Cyr ↔️ Lat",
    "pay":"💎 Premium & Payment",

    "send_file":"📎 Please send a file.",
    "send_text":"✍️ Please send text.",

    "processing":"⏳ Processing your file, please wait...",
    "done":"✅ Successfully completed!",
    "bad_input":"⚠️ Send a file.",
    "too_big":"⚠️ File too large. Limit: {mb} MB",

    "limit_over":"🔒 Free limit is over. Premium required.",
    "free_left":"✅ 1 free run per day.",
    "premium_active":"✅ Premium active until: {until}",

    "pay_choose":"Choose payment type:",
    "pay_premium_choose":"Choose Premium plan:",
    "pay_info":"Pay to card:\n💳 {card}\n👤 {owner}\n\nPay and send receipt/screenshot.",
    "pending_exists":"⏳ You already have a pending payment.",
    "sent_admin":"✅ Sent to admin.",
    "approved_user":"✅ Approved! {msg}",
    "rejected_user":"❌ Rejected.",

    "tr_choose":"Choose direction:",
    "admin_only":"⛔ Not an admin.",

    "need_lo":"DOCX→PDF requires LibreOffice. Check LIBREOFFICE_PATH in .env",
  }
}

def t(lang: str, key: str, **kwargs: Any) -> str:
    lang = lang if lang in TEXT else DEFAULT_LANG
    s = TEXT[lang].get(key, TEXT[DEFAULT_LANG].get(key, key))
    
    try:
        return s.format(**kwargs)
    except KeyError as e:
        # Agar .format() uchun zarur bo'lgan argument berilmasa, bot qotib qolmasligi uchun xatolikni ushlaymiz
        return f"{s} (⚠️ Xatolik: {e} parametri yetishmayapti)"
