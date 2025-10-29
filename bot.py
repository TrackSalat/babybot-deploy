import os
import json
from datetime import datetime, timedelta
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InputMediaPhoto, BotCommand
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)

# === Конфіг ===
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Не знайдено BOT_TOKEN у змінних середовища.")

DATA_FILE = "data.json"  # тимчасове зберігання (на Render без диска — зникає після рестарту)

# ---- стани ----
ASK_FOOD, ASK_AMOUNT, ASK_SLEEP_ACTION = range(3)
ASK_POOP_PHOTO = 3
ASK_STATS_CATEGORY = 4
ASK_STATS_RANGE = 5

# ---- формати дат ----
UA_MONTHS = {
    1: "Січня", 2: "Лютого", 3: "Березня", 4: "Квітня", 5: "Травня", 6: "Червня",
    7: "Липня", 8: "Серпня", 9: "Вересня", 10: "Жовтня", 11: "Листопада", 12: "Грудня"
}
def fmt_date_uk(d: datetime) -> str:
    return f"{d.day} {UA_MONTHS[d.month]}"
def fmt_date_time_uk(d: datetime) -> str:
    return f"{d.day} {UA_MONTHS[d.month]} {d.strftime('%H:%M')}"
def fmt_minutes(total_min: int) -> str:
    h = total_min // 60
    m = total_min % 60
    return f"{h} год {m} хв"

# ---- меню (клавіатура) ----
def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["/eat", "/sleep"], ["/poop", "/stats"]], resize_keyboard=True)

# офіційне меню команд Telegram з емоджі
async def set_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start",  "🏁 Почати / показати меню"),
        BotCommand("eat",    "🍽️ Записати їжу"),
        BotCommand("sleep",  "😴 Сон (заснув/прокинувся)"),
        BotCommand("poop",   "💩 Покакав (фото опційно)"),
        BotCommand("stats",  "📊 Статистика"),
        BotCommand("menu",   "🔘 Показати меню"),
        BotCommand("cancel", "✖️ Скасувати діалог"),
    ])

# ---- IO ----
def save_data(entry):
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []
    data.append(entry)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# ---- /start & /menu ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! Це трекер для Ріка 👶\n\n"
        "Команди:\n"
        "🍽️ /eat — записати їжу\n"
        "😴 /sleep — сон (заснув/прокинувся)\n"
        "💩 /poop — покакaв (фото опційно)\n"
        "📊 /stats — статистика\n"
        "🔘 /menu — показати меню\n"
        "✖️ /cancel — скасувати",
        reply_markup=main_menu_kb()
    )

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню:", reply_markup=main_menu_kb())

# ---- /eat ----
async def eat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Що дитина з’їла?")
    return ASK_FOOD

async def eat_food(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["food"] = update.message.text.strip()
    await update.message.reply_text("Скільки мл (або напиши '-' якщо не суміш)?")
    return ASK_AMOUNT

async def eat_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    food = context.user_data.get("food", "")
    amount = update.message.text.strip()
    entry = {"type": "eat", "food": food, "amount": amount, "time": datetime.now().strftime("%Y-%m-%d %H:%M")}
    save_data(entry)
    now = datetime.now()
    await update.message.reply_text(
        f"✅ Записано: {food}, {amount}, {fmt_date_time_uk(now)}\nГотово. Обери дію:",
        reply_markup=main_menu_kb()
    )
    return ConversationHandler.END

# ---- /sleep ----
async def sleep_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup([["😴 Заснув", "🌞 Прокинувся"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Обери подію сну:", reply_markup=kb)
    return ASK_SLEEP_ACTION

async def sleep_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()
    now = datetime.now()
    data = load_data()

    if "засн" in text:
        entry = {"type": "sleep", "action": "sleep_start", "time": now.strftime("%Y-%m-%d %H:%M")}
        save_data(entry)
        await update.message.reply_text(
            f"😴 Записано: Заснув, {fmt_date_time_uk(now)}\nГотово. Обери дію:",
            reply_markup=main_menu_kb()
        )
    elif "прок" in text or "прос" in text:
        entry = {"type": "sleep", "action": "sleep_end", "time": now.strftime("%Y-%m-%d %H:%M")}
        save_data(entry)
        # знайти останній "Заснув"
        sleep_start_entry = None
        for e in reversed(data):
            if e.get("type") == "sleep" and e.get("action") == "sleep_start":
                sleep_start_entry = e
                break
        message = f"😴 Записано: Прокинувся, {fmt_date_time_uk(now)}"
        if sleep_start_entry:
            start_time = datetime.strptime(sleep_start_entry["time"], "%Y-%m-%d %H:%M")
            diff = now - start_time
            hours, remainder = divmod(diff.seconds, 3600)
            minutes = remainder // 60
            message += f"\n🕒 Спав: {hours} год {minutes} хв"
        else:
            message += "\n⚠️ Не знайдено попереднього засинання."
        message += "\nГотово. Обери дію:"
        await update.message.reply_text(message, reply_markup=main_menu_kb())
    else:
        await update.message.reply_text("Напиши «Заснув» або «Прокинувся».")
        return ASK_SLEEP_ACTION
    return ConversationHandler.END

# ---- /poop ----
async def poop_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entry = {
        "type": "poop",
        "action": "pooped",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "photo_file_id": None
    }
    context.user_data["last_poop_entry"] = entry
    await update.message.reply_text("💩 Записано: Покакав. Можеш надіслати фото (або '-' щоб пропустити).")
    return ASK_POOP_PHOTO

async def poop_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entry = context.user_data.get("last_poop_entry")
    if not entry:
        await update.message.reply_text("Спробуй ще раз: /poop", reply_markup=main_menu_kb())
        return ConversationHandler.END
    if update.message.photo:
        entry["photo_file_id"] = update.message.photo[-1].file_id
        save_data(entry)
        when = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M")
        msg = f"✅ 💩 Записано: {fmt_date_time_uk(when)} + фото"
    else:
        save_data(entry)
        when = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M")
        msg = f"✅ 💩 Записано: {fmt_date_time_uk(when)} (без фото)"
    context.user_data.pop("last_poop_entry", None)
    await update.message.reply_text(msg + "\nГотово. Обери дію:", reply_markup=main_menu_kb())
    return ConversationHandler.END

# ---- /stats ----
async def stats_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup([["📊 Усе"], ["🥗 Їжа"], ["😴 Сон"], ["💩 Какашки"]],
                             one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Яку категорію показати?", reply_markup=kb)
    return ASK_STATS_CATEGORY

async def stats_pick_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat_raw = (update.message.text or "Усе").lower()
    if "їжа" in cat_raw:
        cat = "їжа"
    elif "сон" in cat_raw:
        cat = "сон"
    elif "какаш" in cat_raw:
        cat = "какашки"
    else:
        cat = "усе"
    context.user_data["stats_cat"] = cat

    kb = ReplyKeyboardMarkup([["Сьогодні"], ["7 днів"], ["30 днів"]],
                             one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("За який період?", reply_markup=kb)
    return ASK_STATS_RANGE

def parse_range(text: str) -> int | None:
    t = (text or "").strip().lower()
    if t.startswith("сьог"): return 1
    if t.startswith("7"):    return 7
    if t.startswith("30"):   return 30
    return None

async def stats_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InputMediaPhoto
    days = parse_range(update.message.text)
    if not days:
        await update.message.reply_text("Оберіть: Сьогодні / 7 днів / 30 днів")
        return ASK_STATS_RANGE

    cat = context.user_data.get("stats_cat", "усе")
    data = load_data()
    now = datetime.now()
    since = (now - timedelta(days=days-1)).replace(hour=0, minute=0, second=0, microsecond=0)

    items = []
    for e in data:
        try:
            t = datetime.strptime(e.get("time",""), "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if t >= since:
            items.append((t, e))
    items.sort(key=lambda x: x[0])

    eat_cnt, total_ml, foods, last_eat, last_food = 0, 0, [], None, None
    poop_cnt, last_poop, poop_photos = 0, None, []
    sleep_total_min, last_sleep_start = 0, None
    last_sleep_end = None
    per_day_sleep_min = {}

    for t, e in items:
        if e["type"] == "eat":
            eat_cnt += 1
            last_eat, last_food = t, e.get("food")
            foods.append((t, e.get("food","")))
            amt = str(e.get("amount","")).strip()
            if amt.isdigit():
                total_ml += int(amt)
        elif e["type"] == "poop":
            poop_cnt += 1
            last_poop = t
            if e.get("photo_file_id"):
                poop_photos.append((t, e["photo_file_id"]))
        elif e["type"] == "sleep":
            if e.get("action") == "sleep_start":
                last_sleep_start = t
            elif e.get("action") == "sleep_end" and last_sleep_start:
                diff_min = int((t - last_sleep_start).total_seconds() // 60)
                if diff_min > 0:
                    sleep_total_min += diff_min
                    day_key = t.date()
                    per_day_sleep_min[day_key] = per_day_sleep_min.get(day_key, 0) + diff_min
                last_sleep_end = t
                last_sleep_start = None

    unique_foods, seen = [], set()
    for _, f in foods:
        name = (f or "").strip()
        if name and name not in seen:
            seen.add(name)
            unique_foods.append(name)

    title = "сьогодні" if days == 1 else f"останні {days} днів"
    lines = [f"📊 Статистика за {title}:"]

    if cat in ("усе", "їжа"):
        lines.append(f"🍽️ Прийомів: {eat_cnt}")
        lines.append(f"🍼 Сумарно суміші: {total_ml} мл")
        if unique_foods:
            lines.append("🥗 Продукти: " + ", ".join(unique_foods))
        if last_eat:
            lines.append(f"   Останній прийом: {fmt_date_time_uk(last_eat)} ({last_food})")

    if cat in ("усе", "какашки"):
        lines.append(f"💩 Какашки: {poop_cnt}")
        if last_poop:
            lines.append(f"   Останній раз: {fmt_date_time_uk(last_poop)}")

    if cat in ("усе", "сон"):
        if days == 1:
            lines.append(f"😴 Сон сьогодні: {fmt_minutes(sleep_total_min)}")
        else:
            lines.append(f"😴 Сон за період: {fmt_minutes(sleep_total_min)}")
            avg = sleep_total_min // days
            lines.append(f"📈 Середнє за день: {fmt_minutes(avg)}")
            if per_day_sleep_min:
                lines.append("🗓️ По днях:")
                for day in sorted(per_day_sleep_min.keys()):
                    d = datetime.combine(day, datetime.min.time())
                    lines.append(f" • {fmt_date_uk(d)} — {fmt_minutes(per_day_sleep_min[day])}")
            else:
                lines.append("🗓️ По днях: даних нема")

        if last_sleep_end:
            diff = now - last_sleep_end
            mins_ago = int(diff.total_seconds() // 60)
            lines.append(f"⏱️ Востаннє спав: {fmt_minutes(mins_ago)} тому")
        elif last_sleep_start:
            diff = now - last_sleep_start
            lines.append(f"⏱️ Зараз спить: {fmt_minutes(int(diff.total_seconds() // 60))}")

    await update.message.reply_text("\n".join(lines), reply_markup=main_menu_kb())

    if cat == "какашки" and poop_photos:
        batch = []
        for t, fid in poop_photos:
            caption = f"💩 {fmt_date_time_uk(t)}"
            batch.append(InputMediaPhoto(media=fid, caption=caption))
            if len(batch) == 10:
                try:
                    await update.message.chat.send_media_group(batch)
                except Exception:
                    pass
                batch = []
        if batch:
            try:
                await update.message.chat.send_media_group(batch)
            except Exception:
                pass

    return ConversationHandler.END

# ---- cancel ----
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("last_poop_entry", None)
    await update.message.reply_text("✖️ Скасовано. Меню:", reply_markup=main_menu_kb())
    return ConversationHandler.END

# ---- wiring ----
app = ApplicationBuilder().token(TOKEN).build()
app.post_init = set_bot_commands  # встановлюємо меню команд

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", show_menu))

eat_conv = ConversationHandler(
    entry_points=[CommandHandler("eat", eat_start)],
    states={
        ASK_FOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, eat_food)],
        ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, eat_amount)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
app.add_handler(eat_conv)

sleep_conv = ConversationHandler(
    entry_points=[CommandHandler("sleep", sleep_start)],
    states={ASK_SLEEP_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, sleep_action)]},
    fallbacks=[CommandHandler("cancel", cancel)],
)
app.add_handler(sleep_conv)

poop_conv = ConversationHandler(
    entry_points=[CommandHandler("poop", poop_start)],
    states={
        ASK_POOP_PHOTO: [
            MessageHandler(filters.PHOTO, poop_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, poop_photo),
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
app.add_handler(poop_conv)

stats_conv = ConversationHandler(
    entry_points=[CommandHandler("stats", stats_start)],
    states={
        ASK_STATS_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, stats_pick_range)],
        ASK_STATS_RANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, stats_show)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
app.add_handler(stats_conv)

app.run_polling()
