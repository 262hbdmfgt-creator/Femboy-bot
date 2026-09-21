import aiosqlite
import time
import secrets
import string
import os

DB_PATH = os.getenv("DB_PATH", "bot.db")


# ============== ИНИЦИАЛИЗАЦИЯ ==============

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
                last_foto_at INTEGER DEFAULT 0,
                registered_at INTEGER
            )
        """)

        # Таблица фото (общая база всех фембоев)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                rarity TEXT NOT NULL,
                caption TEXT,
                added_at INTEGER
            )
        """)

        # Таблица фото пользователей (коллекция: кто какие фото получил)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                photo_id INTEGER NOT NULL,
                received_at INTEGER
            )
        """)

        # Таблица админов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_at INTEGER
            )
        """)

        # Таблица кодов для новых админов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_codes (
                code TEXT PRIMARY KEY,
                created_by INTEGER,
                created_at INTEGER,
                expires_at INTEGER,
                used INTEGER DEFAULT 0
            )
        """)

        await db.commit()


# ============== ЧАТЫ ==============

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


async def get_all_chats():
    """Возвращает список всех чатов."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT chat_id FROM chats") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        print(f"get_all_chats error: {e}")
        return []


# ============== ПОЛЬЗОВАТЕЛИ ==============

async def register_user(user):
    """Регистрирует или обновляет пользователя. Принимает объект User из aiogram."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO users 
                   (user_id, username, first_name, last_name, registered_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    user.id,
                    user.username,
                    user.first_name,
                    user.last_name,
                    int(time.time())
                )
            )
            await db.commit()
    except Exception as e:
        print(f"register_user error: {e}")


async def get_user(user_id):
    """Возвращает данные пользователя."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"get_user error: {e}")
        return None


async def set_last_foto(user_id):
    """Обновляет время последнего получения фото."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET last_foto_at = ? WHERE user_id = ?",
                (int(time.time()), user_id)
            )
            await db.commit()
    except Exception as e:
        print(f"set_last_foto error: {e}")


# ============== ФОТО (общая база) ==============

async def add_photo(file_id, caption, rarity):
    """Добавляет фото в общую базу. Возвращает id нового фото."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO photos (file_id, rarity, caption, added_at) 
                   VALUES (?, ?, ?, ?)""",
                (file_id, rarity, caption, int(time.time()))
            )
            await db.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"add_photo error: {e}")
        return None


async def get_random_photo():
    """Возвращает случайное фото из общей базы."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM photos ORDER BY RANDOM() LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    except Exception as e:
        print(f"get_random_photo error: {e}")
        return None


async def delete_photo(photo_id):
    """Удаляет фото из общей базы. Возвращает True если удалено."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM photos WHERE id = ?",
                (photo_id,)
            )
            await db.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"delete_photo error: {e}")
        return False


# ============== КОЛЛЕКЦИЯ ПОЛЬЗОВАТЕЛЯ ==============

async def give_photo_to_user(user_id, photo_id):
    """Добавляет фото в коллекцию пользователя."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO user_photos (user_id, photo_id, received_at) 
                   VALUES (?, ?, ?)""",
                (user_id, photo_id, int(time.time()))
            )
            await db.commit()
    except Exception as e:
        print(f"give_photo_to_user error: {e}")


async def get_user_photo_count(user_id):
    """Возвращает количество фото в коллекции пользователя."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM user_photos WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except Exception as e:
        print(f"get_user_photo_count error: {e}")
        return 0


async def get_user_photos_ordered(user_id):
    """Возвращает все фото пользователя из коллекции (с данными о rarity и caption)."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT p.id, p.file_id, p.rarity, p.caption, up.received_at
                   FROM user_photos up
                   JOIN photos p ON p.id = up.photo_id
                   WHERE up.user_id = ?
                   ORDER BY up.received_at DESC""",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        print(f"get_user_photos_ordered error: {e}")
        return []


# ============== АДМИНЫ ==============

async def add_admin(user_id):
    """Добавляет ползователя в админы."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO admins (user_id, added_at) VALUES (?, ?)",
                (user_id, int(time.time()))
            )
            await db.commit()
    except Exception as e:
        print(f"add_admin error: {e}")


async def is_admin(user_id, super_admin_id):
    """Проверяет, является ли пользователь админом (включая супер-админа)."""
    if user_id == super_admin_id:
        return True
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM admins WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
    except Exception as e:
        print(f"is_admin error: {e}")
        return False


# ============== КОДЫ ДЛЯ НОВЫХ АДМИНОВ ==============

def _generate_code(length=8):
    """Генерирует случайный код из букв и цифр."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def create_admin_code(created_by):
    """Создаёт код для нового админа (действует 3 часа)."""
    try:
        code = _generate_code()
        now = int(time.time())
        expires = now + 3 * 3600
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO admin_codes (code, created_by, created_at, expires_at, used) 
                   VALUES (?, ?, ?, ?, 0)""",
                (code, created_by, now, expires)
            )
            await db.commit()
        return code
    except Exception as e:
        print(f"create_admin_code error: {e}")
        return None


async def use_admin_code(code):
    """Использует код. Возвращает created_by если код валидный, иначе None."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM admin_codes WHERE code = ? AND used = 0 AND expires_at > ?",
                (code, int(time.time()))
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                # Помечаем код использованным
                await db.execute(
                    "UPDATE admin_codes SET used = 1 WHERE code = ?",
                    (code,)
                )
                await db.commit()
                return row["created_by"]
    except Exception as e:
        print(f"use_admin_code error: {e}")
        return None
