import os
import asyncio
from datetime import timedelta
from db import DB
from config import load_config
from utils import utcnow, iso

async def main():
    # Har doim aniq bot.db manzilini topish
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "bot.db")
    
    db = DB(db_path)
    
    user_id = 6907296588
    days = 365 # 1 yillik premium
    
    await db.init()
    await db.ensure_user(user_id)
    new_until = utcnow() + timedelta(days=days)
    await db.set_premium_until(user_id, iso(new_until))
    print(f"✅ {user_id} foydalanuvchiga {days} kunga premium berildi! Tugash vaqti: {iso(new_until)}")

if __name__ == "__main__":
    asyncio.run(main())