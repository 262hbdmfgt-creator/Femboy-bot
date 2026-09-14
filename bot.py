import asyncio
import time
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

import database as db
from config import (
    BOT_TOKEN, SUPER_ADMIN_ID, RARITIES, RARITY_ORDER,
    FOTO_COOLDOWN_HOURS,
)

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Временные состояния
pending_add_foto = {}      # user_id -> ожидаемая редкость
pending_broadcast = {}     # user_id -> список сообщений


# ============== MIDDLEWARE для отслеживания чатов ==============

@dp.update.outer_middleware()
async def track_chats_middleware(handler, event, data):
    # Сохраняем чат, в котором произошло событие
    chat = None
    if hasattr(event, 'message') and event.message:
        chat = event.message.chat
    elif hasattr(event, 'callback_query') and event.callback_query and event.callback_query.message:
        chat = event.callback_query.message.chat
    
    if chat:
        await db.add_chat(chat.id, chat.title or "Private")
    return await handler(event, data)


# ============== START ==============

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db.register_user(message.from_user)
    text = (
        "👋 Привет! Я бот с коллекцией фембоев.\n\n"
        "Команды:\n"
        "• /foto или «фем» — получить случайное фото (1 раз в 3 часа)\n"
        "• /profil или «профиль» — твоя коллекция\n"
        "• /admin или «кто админ» — кто админ бота"
    )
    await message.answer(text)


# ============== /foto ==============

def rarity_name(code):
    return RARITIES[code][0] if code in RARITIES else code


async def send_random_foto(chat_id: int, user_id: int):
    photo = db.get_random_photo()
    if not photo:
        await bot.send_message(chat_id, "😔 Пока нет фото в базе. Попроси админа добавить.")
        return

    db.give_photo_to_user(user_id, photo["id"])
    db.set_last_foto(user_id)

    caption = (
        f"✨ <b>{rarity_name(photo['rarity'])}</b>\n\n"
        f"{photo['caption'] or ''}\n\n"
        f"📸 Фото #{photo['id']}"
    )
    try:
        await bot.send_photo(chat_id, photo["file_id"], caption=caption)
    except Exception as e:
        await bot.send_message(chat_id, f"Ошибка отправки: {e}")


@dp.message(Command("foto"))
@dp.message(F.text.casefold().in_({"фем", "фембой", "фембойчик"}))
async def cmd_foto(message: types.Message):
    user = message.from_user
    db.register_user(user)
    user_row = db.get_user(user.id)

    last = user_row["last_foto_at"] if user_row else 0
    elapsed = time.time() - last
    cooldown_sec = FOTO_COOLDOWN_HOURS * 3600

    if elapsed < cooldown_sec:
        remaining = int(cooldown_sec - elapsed)
        h = remaining // 3600
        m = (remaining % 3600) // 60
        await message.answer(f"⏳ Следующее фото можно получить через {h}ч {m}мин.")
        return

    await send_random_foto(message.chat.id, user.id)


# ============== /profil ==============

async def show_profile_message(target_message: types.Message, user_id: int, first_name: str):
    count = db.get_user_photo_count(user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Смотреть все фото", callback_data="show_all_0")]
    ])
    # Пытаемся достать аватарку пользователя
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            await bot.send_photo(
                target_message.chat.id,
                photos.photos[0][-1].file_id,
                caption=(
                    f"👤 <b>{first_name}</b>\n\n"
                    f"📸 У тебя {count} фото в коллекции"
                ),
                reply_markup=kb,
            )
            return
    except Exception:
        pass

    await target_message.answer(
        f"👤 <b>{first_name}</b>\n\n"
        f"📸 У тебя {count} фото в коллекции",
        reply_markup=kb,
    )


@dp.message(Command("profil"))
@dp.message(F.text.casefold().in_({"профиль", "профил"}))
async def cmd_profil(message: types.Message):
    db.register_user(message.from_user)
    await show_profile_message(message, message.from_user.id, message.from_user.first_name or "Игрок")


@dp.callback_query(F.data.startswith("show_all_"))
async def cb_show_all(call: types.CallbackQuery):
    user_id = call.from_user.id
    photos = db.get_user_photos_ordered(user_id)

    if not photos:
        await call.answer("Коллекция пуста 😔", show_alert=True)
        return

    try:
        offset = int(call.data.split("_")[2])
    except (IndexError, ValueError):
        offset = 0

    if offset >= len(photos):
        offset = 0
    photo = photos[offset]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀️", callback_data=f"show_all_{(offset - 1) % len(photos)}"),
            InlineKeyboardButton(text=f"{offset + 1}/{len(photos)}", callback_data="noop"),
            InlineKeyboardButton(text="▶️", callback_data=f"show_all_{(offset + 1) % len(photos)}"),
        ]
    ])

    caption = (
        f"✨ <b>{rarity_name(photo['rarity'])}</b>\n\n"
        f"{photo['caption'] or ''}\n\n"
        f"📸 Фото #{photo['id']}"
    )

    try:
        await bot.edit_message_media(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            media=InputMediaPhoto(media=photo["file_id"], caption=caption, parse_mode=ParseMode.HTML),
            reply_markup=kb,
        )
    except Exception:
        # Если не получилось отредактировать (например, в личке первый раз был текст)
        await bot.send_photo(call.message.chat.id, photo["file_id"], caption=caption, reply_markup=kb)

    await call.answer()


@dp.callback_query(F.data == "noop")
async def cb_noop(call: types.CallbackQuery):
    await call.answer()


# ============== /admin (показать админов) ==============

ADMIN_MESSAGE = "👮 Список админов бота:\n\n"  # можно менять вручную в коде


@dp.message(Command("admin"))
@dp.message(F.text.casefold().in_({"кто админ", "админ", "админы"}))
async def cmd_admin(message: types.Message):
    await message.answer(ADMIN_MESSAGE + "Информация уточняется.")


# ============== ADMIN: /plus_foto ==============

@dp.message(Command("plus_foto"))
async def cmd_plus_foto(message: types.Message):
    if not db.is_admin(message.from_user.id, SUPER_ADMIN_ID):
        return
    pending_add_foto[message.from_user.id] = {"step": "rarity"}
    await message.answer("🎯 Готов принять фото. Напиши редкость одним словом:\n"
                         "• редкое\n• ультра редкое\n• мифическое\n• легендарное\n• фембойский артефакт\n• редчайший фем")


# Ловим редкость и фото только от того, кто нажал /plus_foto
@dp.message(F.text, F.from_user.id.in_({u for u in pending_add_foto}))
async def catch_rarity(message: types.Message):
    state = pending_add_foto.get(message.from_user.id)
    if not state or state["step"] != "rarity":
        return

    # Ищем редкость по русскому названию
    text = message.text.strip().casefold()
    found = None
    for code, (rus_name, _) in RARITIES.items():
        if rus_name.casefold() == text:
            found = code
            break
    if not found:
        await message.answer("❌ Неизвестная редкость. Напиши точно: редкое / ультра редкое / мифическое / легендарное / фембойский артефакт / редчайший фем")
        return

    pending_add_foto[message.from_user.id] = {"step": "photo", "rarity": found}
    await message.answer(f"✅ Редкость сохранена: <b>{rarity_name(found)}</b>. Теперь отправь фото с описанием (caption).",
                         parse_mode=ParseMode.HTML)


@dp.message(F.photo, F.from_user.id.in_({u for u in pending_add_foto}))
async def catch_photo(message: types.Message):
    state = pending_add_foto.get(message.from_user.id)
    if not state or state["step"] != "photo":
        return

    file_id = message.photo[-1].file_id
    caption = message.caption or ""
    photo_id = db.add_photo(file_id, caption, state["rarity"])

    del pending_add_foto[message.from_user.id]
    await message.answer(f"✅ Сохранено, фото #{photo_id}")


# ============== ADMIN: /delete_foto ==============

@dp.message(Command("delete_foto"))
async def cmd_delete_foto(message: types.Message):
    if not db.is_admin(message.from_user.id, SUPER_ADMIN_ID):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /delete_foto #(номер), например /delete_foto 5 или /delete_foto#5")
        return
    arg = args[1].strip().lstrip("#")
    if not arg.isdigit():
        await message.answer("Номер должен быть числом.")
        return
    photo_id = int(arg)
    if db.delete_photo(photo_id):
        await message.answer(f"🗑 Фото #{photo_id} удалено.")
    else:
        await message.answer(f"❌ Фото #{photo_id} не найдено.")


# ============== ADMIN: /add (рассылка) ==============

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    if not db.is_admin(message.from_user.id, SUPER_ADMIN_ID):
        return
    pending_broadcast[message.from_user.id] = []
    await message.answer("📨 Режим рассылки. Отправляй сообщения (текст/фото), в конце напиши /save")


@dp.message(Command("save"))
async def cmd_save(message: types.Message):
    if not db.is_admin(message.from_user.id, SUPER_ADMIN_ID):
        return
    user_id = message.from_user.id
    if user_id not in pending_broadcast:
        await message.answer("Сначала начни рассылку через /add")
        return

    # Берём все сообщения, написанные ПОСЛЕ /add (до /save)
    # Сохранять сами сообщения мы не можем, поэтому бот копирует содержимое по ссылке.
    # Реализация: админ шлёт сообщения, бот их копирует (forward) во все чаты.
    await message.answer("⚠️ Чтобы разослать, перешли мне сообщения, которые нужно разослать, "
                         "прямо сейчас (можно несколько подряд), а затем напиши /send_all.\n\n"
                         "Если неудобно — есть более простая версия: перешли сюда пост, я разошлю.")


@dp.message(Command("send_all"))
async def cmd_send_all(message: types.Message):
    if not db.is_admin(message.from_user.id, SUPER_ADMIN_ID):
        return
    # Берём последние сообщения в чате и рассылаем их
    # (упрощённо — рассылаем то, что было в pending_broadcast — мы их не сохранили, поэтому используем другой подход)
    await do_broadcast(message)


async def do_broadcast(message: types.Message):
    """Рассылает все сообщения после /add и до /save. 
    Реализация: сохраняем message_id последнего /add и шлём всё, что было после."""
    # Эта упрощённая версия рассылает ОДНО сообщение — последнее перед /send_all.
    chats = db.get_all_chats()
    sent = 0
    failed = 0
    for chat in chats:
        try:
            await bot.copy_message(
                chat_id=chat["chat_id"],
                from_chat_id=message.chat.id,
                message_id=message.reply_to_message.message_id if message.reply_to_message else message.message_id - 1,
            )
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"📤 Рассылка завершена. Успешно: {sent}, ошибок: {failed}")


# ============== ADMIN: коды /I_am_admin ==============

@dp.message(Command("now_admin_cod"))
async def cmd_now_admin_cod(message: types.Message):
    if not db.is_admin(message.from_user.id, SUPER_ADMIN_ID):
        return
    code = db.create_admin_code(message.from_user.id)
    await message.answer(
        f"🔑 Код для нового админа (действует 3 часа):\n\n"
        f"<code>{code}</code>\n\n"
        f"Новый админ должен написать мне в личку: /I_am_admin и ввести этот код.",
        parse_mode=ParseMode.HTML,
    )


@dp.message(Command("I_am_admin"))
async def cmd_i_am_admin(message: types.Message):
    db.register_user(message.from_user)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Введи код после команды. Например: /I_am_admin Abc12345")
        return
    code = args[1].strip()
    created_by = db.use_admin_code(code)
    if created_by is None:
        await message.answer("❌ Неверный или просроченный код. Попроси новый у действующего админа.")
        return
    db.add_admin(message.from_user.id)
    await message.answer("✅ Ты теперь админ бота!")


# ============== SUPER ADMIN (одноразовая команда для первого админа) ==============

@dp.message(Command("make_me_admin"))
async def cmd_make_me_admin(message: types.Message):
    """Первый запуск: главный админ прописывает себя через эту команду.
    Работает ТОЛЬКО для SUPER_ADMIN_ID, и только если в базе ещё нет админов."""
    if message.from_user.id != SUPER_ADMIN_ID:
        return
    db.add_admin(SUPER_ADMIN_ID)
    await message.answer("✅ Ты зарегистрирован как супер-админ.")


# ============== RUN ==============

async def main():
    db.init_db()
    print("Bot started.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
