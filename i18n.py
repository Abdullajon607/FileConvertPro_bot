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
    "compress":"🗜 Hajmni siqish (MB)",

    "translit":"🔤 Kiril ↔️ Lotin",
    "pay":"💎 Premium & To‘lov",
    "profile":"👤 Profil",
    "contact_admin":"📞 Adminga yozish",
    "send_admin_msg":"✍️ Adminga yubormoqchi bo'lgan xabaringizni yozing (savol, taklif yoki shikoyat):",
    "admin_msg_sent":"✅ Xabaringiz adminga muvaffaqiyatli yuborildi.",

    "send_file":"📎 Iltimos, faylni yuboring.",
    "send_text":"✍️ Iltimos, matn yuboring.",
    "send_compress_file":"📎 Siqish uchun faylni yuboring (PDF, DOCX, PPTX):",

    "img_received":"🖼 {count}-rasm qabul qilindi. Yana rasm yuborishingiz mumkin.\n\nBarcha rasmlarni yuborib bo'lgan bo'lsangiz, quyidagi tugmani bosing:",
    "btn_finish_images":"✅ Word qilib berish",

    "processing":"⏳ Fayl tayyorlanmoqda, biroz kuting...",
    "done":"✅ Muvaffaqiyatli yakunlandi!",
    "bad_input":"⚠️ Fayl yuboring.",
    "too_big":"⚠️ Fayl juda katta. Limit: {mb} MB",

    "limit_over":"🔒 Bepul limit tugadi. Premium kerak.",
    "free_left":"✅ Haftasiga jami 3 ta bepul limit beriladi.",
    "premium_active":"✅ Premium faol. Tugash: {until}",

    "pay_choose":"To‘lov turini tanlang:",
    "pay_premium_choose":"Premium paketni tanlang:",
    "pay_info":"To‘lov kartalari:\n💳 9860040102335870 (Madraximov A)\n💳 4413597604153971 (Madraximov A)\n\nTo‘lov qiling va чек/skrin yuboring.",
    "pending_exists":"⏳ Sizda pending to‘lov bor. Kuting.",
    "sent_admin":"✅ Adminga yuborildi. Tasdiqlansa aktiv bo‘ladi.",
    "approved_user":"🎉 <b>To‘lovingiz tasdiqlandi!</b>\n\n💎 Sizga {days} kunlik Premium taqdim etildi.\n⏰ Amal qilish muddati: <b>{date}</b>\n\n<i>Botdan cheksiz foydalanishingiz mumkin!</i>",
    "rejected_user":"❌ Rad etildi. Qayta urinib ko‘ring.",

    "text_received_confirm":"Matn qabul qilindi. Yana matn qo'shmoqchimisiz yoki konvertatsiya qilishni tasdiqlaysizmi?",
    "btn_confirm_text":"✅ Tasdiqlash",
    "btn_cancel_text_input":"❌ Bekor qilish",
    "text_input_cancelled":"❌ Matn kiritish bekor qilindi.",
    "current_text_length":"Hozircha {length} ta belgi kiritildi.",

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
    "compress":"🗜 Сжать размер (МБ)",

    "translit":"🔤 Кир ↔️ Лат",
    "pay":"💎 Premium & Оплата",
    "profile":"👤 Мой профиль",
    "contact_admin":"📞 Связаться с админом",
    "send_admin_msg":"✍️ Напишите ваше сообщение для администратора:",
    "admin_msg_sent":"✅ Ваше сообщение успешно отправлено.",

    "send_file":"📎 Пожалуйста, отправьте файл.",
    "send_text":"✍️ Пожалуйста, отправьте текст.",
    "send_compress_file":"📎 Отправьте файл для сжатия (PDF, DOCX, PPTX):",

    "img_received":"🖼 {count} фото получено. Вы можете отправить еще.\n\nЕсли вы отправили все фото, нажмите кнопку ниже:",
    "btn_finish_images":"✅ Создать Word",

    "processing":"⏳ Обработка файла, подождите...",
    "done":"✅ Успешно завершено!",
    "bad_input":"⚠️ Отправьте файл.",
    "too_big":"⚠️ Файл слишком большой. Лимит: {mb} MB",

    "limit_over":"🔒 Бесплатный лимит закончился. Нужен Premium.",
    "free_left":"✅ Дается 3 бесплатных лимита в неделю.",
    "premium_active":"✅ Premium активен до: {until}",

    "pay_choose":"Выберите тип оплаты:",
    "pay_premium_choose":"Выберите Premium пакет:",
    "pay_info":"Оплата на карты:\n💳 9860040102335870 (Madraximov A)\n💳 4413597604153971 (Madraximov A)\n\nОплатите и отправьте чек/скрин.",
    "pending_exists":"⏳ У вас есть pending-платёж.",
    "sent_admin":"✅ Отправлено админу.",
    "approved_user":"🎉 <b>Ваш платеж подтвержден!</b>\n\n💎 Вам предоставлен Premium на {days} дней.\n⏰ Срок действия: <b>{date}</b>\n\n<i>Теперь вы можете использовать бота без ограничений!</i>",
    "rejected_user":"❌ Отклонено.",

    "text_received_confirm":"Текст получен. Хотите добавить еще текст или подтвердить конвертацию?",
    "btn_confirm_text":"✅ Подтвердить",
    "btn_cancel_text_input":"❌ Отменить",
    "text_input_cancelled":"❌ Ввод текста отменен.",
    "current_text_length":"Введено {length} символов.",

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
    "compress":"🗜 Compress Size (MB)",

    "translit":"🔤 Cyr ↔️ Lat",
    "pay":"💎 Premium & Payment",
    "profile":"👤 My Profile",
    "contact_admin":"📞 Contact Admin",
    "send_admin_msg":"✍️ Write your message to the administrator:",
    "admin_msg_sent":"✅ Your message has been sent successfully.",

    "send_file":"📎 Please send a file.",
    "send_text":"✍️ Please send text.",
    "send_compress_file":"📎 Send file to compress (PDF, DOCX, PPTX):",

    "img_received":"🖼 {count} image(s) received. You can send more.\n\nIf you are done, click the button below:",
    "btn_finish_images":"✅ Generate Word",

    "processing":"⏳ Processing your file, please wait...",
    "done":"✅ Successfully completed!",
    "bad_input":"⚠️ Send a file.",
    "too_big":"⚠️ File too large. Limit: {mb} MB",

    "limit_over":"🔒 Free limit is over. Premium required.",
    "free_left":"✅ 3 free limits per week.",
    "premium_active":"✅ Premium active until: {until}",

    "pay_choose":"Choose payment type:",
    "pay_premium_choose":"Choose Premium plan:",
    "pay_info":"Pay to cards:\n💳 9860040102335870 (Madraximov A)\n💳 4413597604153971 (Madraximov A)\n\nPay and send receipt/screenshot.",
    "pending_exists":"⏳ You already have a pending payment.",
    "sent_admin":"✅ Sent to admin.",
    "approved_user":"🎉 <b>Your payment has been approved!</b>\n\n💎 You have been granted {days} days of Premium.\n⏰ Valid until: <b>{date}</b>\n\n<i>You can now use the bot without limits!</i>",
    "rejected_user":"❌ Rejected.",

    "text_received_confirm":"Text received. Do you want to add more text or confirm conversion?",
    "btn_confirm_text":"✅ Confirm",
    "btn_cancel_text_input":"❌ Cancel",
    "text_input_cancelled":"❌ Text input cancelled.",
    "current_text_length":"{length} characters entered so far.",

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

def get_all(key: str) -> list[str]:
    return [TEXT[lang].get(key) for lang in TEXT if key in TEXT[lang]]
