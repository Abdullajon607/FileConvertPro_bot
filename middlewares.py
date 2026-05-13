from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from db import DB

class LanguageMiddleware(BaseMiddleware):
    def __init__(self, db: DB):
        self.db = db

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        await self.db.ensure_user(user_id) # Foydalanuvchi bazada borligini tekshirish
        data["lang"] = await self.db.get_lang(user_id) # Tilni yuklab, handlerga uzatish
        return await handler(event, data)