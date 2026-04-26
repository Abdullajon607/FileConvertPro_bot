import os
import re
import uuid
import logging
from datetime import datetime, timezone

def setup_logger(log_dir: str) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("bot")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(os.path.join(log_dir, "bot.log"), encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.isoformat()

def from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)

def today_str_local() -> str:
    return datetime.now().date().isoformat()

def rand_name(prefix: str, ext: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}.{ext}"

def safe_ext(filename: str | None) -> str:
    if not filename:
        return ""
    return os.path.splitext(filename)[1].lower()

def is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", (s or "").strip(), re.I))

def size_ok(file_size: int | None, max_mb: int) -> bool:
    if not file_size:
        return True
    return file_size <= max_mb * 1024 * 1024

def human_err(e: Exception) -> str:
    s = str(e).strip()
    return s if s else e.__class__.__name__
