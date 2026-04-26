from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "pdf2docx"), callback_data="do:pdf2docx"),
            InlineKeyboardButton(text=t(lang, "docx2pdf"), callback_data="do:docx2pdf")
        ],
        [
            InlineKeyboardButton(text=t(lang, "text2docx"), callback_data="do:text2docx"),
            InlineKeyboardButton(text=t(lang, "text2pptx"), callback_data="do:text2pptx")
        ],
        [
            InlineKeyboardButton(text=t(lang, "img2docx"), callback_data="do:img2docx"),
            InlineKeyboardButton(text=t(lang, "translit"), callback_data="menu:translit")
        ],
        [
            InlineKeyboardButton(text=t(lang, "pay"), callback_data="menu:pay")
        ],
    ])

def kb_translit_dir(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 Kiril ➡️ Lotin", callback_data="tr:cl"),
            InlineKeyboardButton(text="🇺🇿 Lotin ➡️ Kiril", callback_data="tr:lc")
        ],
        [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:back")],
    ])

def kb_pay_kind(lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Premium", callback_data="pay:kind:premium")
        ],
        [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:back")],
    ])

def kb_premium_plans(p7: int, p30: int, p365: int):
    return InlineKeyboardMarkup(inline_keyboard=[
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
