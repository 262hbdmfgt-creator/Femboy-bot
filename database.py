import aiosqlite
import time
import os

DB_PATH = os.getenv("DB_PATH", "bot.db")


async def init_db():
    """Создаёт все таблицы. Вызывается один раз при старте бота."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица чатов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                type TEXT,
                title TEXT,
                added_at INTEGER
            )
        """)

        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at INTEGER
            )
        """)

        # Таблица фото пользователей (для коллекции)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_id TEXT,
                rarity TEXT,
                caption TEXT,
                added_at INTEGER
            )
        """)

        # Таблица профилей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                bio TEXT,
                collection_count INTEGER DEFAULT 0,
                rare_count INTEGER DEFAULT 0
            )
        """)

        await db.commit()


async def add_chat(chat_id, chat_type, title):
    """Добавляет или обновляет чат."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO chats (chat_id, type, title, added_at) VALUES (?, ?, ?, ?)",
                (chat_id, chat_type, title, int(time.time()))
            )
            await db.commit()
    except Exception as e:
        print(f"add_chat error: {e}")


async def add_user(user_id, username=None, first_name=None, last_name=None):
    """Добавляет или обновляет пользователя."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO users 
                   (user_id, username, first_name, last_name, registered_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, username, first_name, last_name, int(time.time()))
            )
            await db.commit()
    except Exception as e:
        print(f"add_user error: {e}")


async def add_photo(user_id, file_id, rarity, caption):
    """Добавляет фото в коллекцию пользователя."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO user_photos 
                   (user_id, file_id, rarity, caption, added_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, file_id, rarity, caption, int(time.time()))
            )
            await db.commit()
    except Exception as e:
        print(f"add_photo error: {e}")


async def get_user_photos(user_id, limit=50):
    """Возвращает фото пользователя."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM user_photos WHERE user_id = ? ORDER BY added_at DESC LIMIT ?",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        print(f"get_user_photos error: {e}")
        return []


async def delete_photo(photo_id):
    """Удаляет фото по id."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM user_photos WHERE id = ?",
                (photo_id,)
            )
            await db.commit()
    except Exception as e:
        print(f"delete_photo error: {e}")


async def get_profile(user_id):
    """Возвращает профиль пользователя."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM profiles WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"get_profile error: {e}")
        return None


async def update_profile(user_id, bio=None):
    """Обновляет био профиля."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO profiles (user_id, bio) VALUES (?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET bio = excluded.bio""",
                (user_id, bio)
            )
            await db.commit()
    except Exception as e:
        print(f"update_profile error: {e}")
