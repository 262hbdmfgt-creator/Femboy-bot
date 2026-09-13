import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID"))
DB_PATH = os.getenv("DB_PATH", "femboy.db")

# Редкости: код -> (русское название, шанс в %)
RARITIES = {
    "rare":       ("Редкое", 40),
    "ultra_rare": ("Ультра редкое", 25),
    "mythic":     ("Мифическое", 15),
    "legendary":  ("Легендарное", 12),
    "artifact":   ("Фембойский артефакт", 6),
    "rarest":     ("Редчайший фем", 2),
}

# Порядок отображения в профиле (от самых редких к менее)
RARITY_ORDER = ["rarest", "artifact", "legendary", "mythic", "ultra_rare", "rare"]

# Кулдаун /foto
FOTO_COOLDOWN_HOURS = 3
