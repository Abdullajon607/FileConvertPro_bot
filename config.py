import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _parse_admins(raw: str) -> list[int]:
    out: list[int] = []
    for x in (raw or "").split(","):
        x = x.strip()
        if x.isdigit():
            out.append(int(x))
    return out

@dataclass(frozen=True)
class Config:
    token: str
    admin_ids: list[int]

    card_number: str
    card_owner: str

    price_7: int
    price_30: int
    price_365: int

    price_ocr_1: int
    price_ocr_10: int

    max_file_mb: int
    tmp_dir: str
    log_dir: str
    db_path: str

    libreoffice_path: str
    tesseract_path: str

def load_config() -> Config:
    return Config(
        token=os.getenv("BOT_TOKEN", "").strip(),
        admin_ids=_parse_admins(os.getenv("ADMIN_IDS", "")),

        card_number=os.getenv("CARD_NUMBER", "").strip(),
        card_owner=os.getenv("CARD_OWNER", "").strip(),

        price_7=int(os.getenv("PRICE_7", "15000")),
        price_30=int(os.getenv("PRICE_30", "39000")),
        price_365=int(os.getenv("PRICE_365", "299000")),

        price_ocr_1=int(os.getenv("PRICE_OCR_1", "9000")),
        price_ocr_10=int(os.getenv("PRICE_OCR_10", "69000")),

        max_file_mb=int(os.getenv("MAX_FILE_MB", "50")),
        tmp_dir=os.getenv("TMP_DIR", "./tmp"),
        log_dir=os.getenv("LOG_DIR", "./logs"),
        db_path=os.getenv("DB_PATH", "./bot.db"),

        libreoffice_path=os.getenv("LIBREOFFICE_PATH", "").strip(),
        tesseract_path=os.getenv("TESSERACT_PATH", "").strip(),
    )
