import sqlite3
import time
from config import DB_PATH, RARITIES


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт таблицы, если их нет."""
    conn = get_conn()
    cur = conn.cursor()

    # Фото
    cur.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            caption TEXT,
            rarity TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)

    # Пользователи
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_foto_at INTEGER DEFAULT 0,
            registered_at INTEGER NOT NULL
        )
    """)

    # Связь пользователь <-> полученные фото (чтобы знать коллекцию)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_photos (
            user_id INTEGER NOT NULL,
            photo_id INTEGER NOT NULL,
            obtained_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, photo_id)
        )
    """)

    # Админы
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at INTEGER NOT NULL
        )
    """)

    # Одноразовые коды для /I_am_admin
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_codes (
            code TEXT PRIMARY KEY,
            created_by INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            used INTEGER DEFAULT 0
        )
    """)

    # Все чаты, в которых бот состоит (для /add рассылки)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT,
            added_at INTEGER NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ---------- USERS ----------

def register_user(user):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, registered_at)
        VALUES (?, ?, ?, ?)
    """, (user.id, user.username, user.first_name, int(time.time())))
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def set_last_foto(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_foto_at = ? WHERE user_id = ?",
                (int(time.time()), user_id))
    conn.commit()
    conn.close()


# ---------- PHOTOS ----------

def add_photo(file_id, caption, rarity):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO photos (file_id, caption, rarity, created_at)
        VALUES (?, ?, ?, ?)
    """, (file_id, caption, rarity, int(time.time())))
    photo_id = cur.lastrowid
    conn.commit()
    conn.close()
    return photo_id


def get_random_photo():
    """Возвращает фото согласно шансам редкости."""
    import random
    conn = get_conn()
    cur = conn.cursor()

    rand = random.randint(1, 100)
    cumulative = 0
    chosen_rarity = None
    for code, (_, chance) in RARITIES.items():
        cumulative += chance
        if rand <= cumulative:
            chosen_rarity = code
            break

    # Берём случайное фото этой редкости
    cur.execute("SELECT * FROM photos WHERE rarity = ? ORDER BY RANDOM() LIMIT 1",
                (chosen_rarity,))
    row = cur.fetchone()
    conn.close()
    return row


def get_photo(photo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
    row = cur.fetchone()
    conn.close()
    return row


def delete_photo(photo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    affected = cur.rowcount
    # удаляем из коллекций пользователей
    cur.execute("DELETE FROM user_photos WHERE photo_id = ?", (photo_id,))
    conn.commit()
    conn.close()
    return affected > 0


def give_photo_to_user(user_id, photo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO user_photos (user_id, photo_id, obtained_at)
        VALUES (?, ?, ?)
    """, (user_id, photo_id, int(time.time())))
    conn.commit()
    conn.close()


def get_user_photos_ordered(user_id):
    """Возвращает список фото пользователя, отсортированный по редкости (от самой редкой)."""
    rarity_priority = {code: i for i, code in enumerate(RARITY_ORDER)}
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.* FROM photos p
        JOIN user_photos up ON p.id = up.photo_id
        WHERE up.user_id = ?
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    rows = list(rows)
    rows.sort(key=lambda r: (rarity_priority.get(r["rarity"], 99), -r["id"]))
    return rows


def get_user_photo_count(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM user_photos WHERE user_id = ?",
                (user_id,))
    row = cur.fetchone()
    conn.close()
    return row["cnt"]


# ---------- ADMINS ----------

def is_admin(user_id, super_admin_id):
    if user_id == super_admin_id:
        return True
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def add_admin(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO admins (user_id, added_at) VALUES (?, ?)",
                (user_id, int(time.time())))
    conn.commit()
    conn.close()


def create_admin_code(created_by):
    import random, string
    digits = "".join(random.choices(string.digits, k=7))
    letters = "".join(random.choices(string.ascii_letters, k=3))
    code_chars = list(digits + letters)
    random.shuffle(code_chars)
    code = "".join(code_chars)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO admin_codes (code, created_by, created_at) VALUES (?, ?, ?)
    """, (code, created_by, int(time.time())))
    conn.commit()
    conn.close()
    return code


def use_admin_code(code):
    """Проверяет код. Возвращает created_by если валидный, иначе None."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admin_codes WHERE code = ? AND used = 0", (code,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None
    # Проверяем срок (3 часа)
    if int(time.time()) - row["created_at"] > 3 * 3600:
        conn.close()
        return None
    cur.execute("UPDATE admin_codes SET used = 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return row["created_by"]


# ---------- CHATS (для /add рассылки) ----------

def add_chat(chat_id, chat_type, title):
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO chats (chat_id, type, title, added_at) VALUES (?, ?, ?, ?)
    """, (chat_id, chat_type, title, int(time.time())))
    conn.commit()
    conn.close()


def get_all_chats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM chats")
    rows = cur.fetchall()
    conn.close()
    return rows
