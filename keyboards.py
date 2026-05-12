from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from i18n import t

def kb_lang():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 UZ", callback_data="lang:uz"),
            InlineKeyboardButton(text="🇷🇺 RU", callback_data="lang:ru"),
            InlineKeyboardButton(text="🇬🇧 EN", callback_data="lang:en"),
        ]
    ])

def kb_main(lang: str):
    return ReplyKeyboardMarkup(keyboard=[
        [
            KeyboardButton(text=t(lang, "pdf2docx")),
            KeyboardButton(text=t(lang, "docx2pdf"))
        ],
        [
            KeyboardButton(text=t(lang, "text2docx")),
            KeyboardButton(text=t(lang, "text2pptx"))
        ],
        [
            KeyboardButton(text=t(lang, "img2docx")),
            KeyboardButton(text=t(lang, "translit"))
        ],
        [
            KeyboardButton(text=t(lang, "pay")),
            KeyboardButton(text=t(lang, "compress"))
        ],
        [
            KeyboardButton(text=t(lang, "contact_admin"))
        ],
    ], resize_keyboard=True)

def kb_pay_kind(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Premium", callback_data="pay:kind:premium")
        ],
        [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:back")],
    ])

def kb_premium_plans(p1: int, p7: int, p30: int, p365: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"1 kun — {p1} so‘m", callback_data="pay:premium:1")],
        [InlineKeyboardButton(text=f"7 kun — {p7} so‘m", callback_data="pay:premium:7")],
        [InlineKeyboardButton(text=f"30 kun — {p30} so‘m", callback_data="pay:premium:30")],
        [InlineKeyboardButton(text=f"1 yil — {p365} so‘m", callback_data="pay:premium:365")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="pay:back")],
    ])

def kb_admin_payment(pid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin:approve:{pid}")],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"admin:reject:{pid}")],
    ])

def kb_finish_images(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_finish_images"), callback_data="do:img2docx_finish")]
    ])

def kb_text_confirmation(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_confirm_text"), callback_data="text_convert:confirm")],
        [InlineKeyboardButton(text=t(lang, "btn_cancel_text_input"), callback_data="text_convert:cancel")]
    ])
