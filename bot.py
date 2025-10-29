import os
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

# ================== CONFIG ==================
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# Render надає URL в змінній оточення RENDER_EXTERNAL_URL.
# Залишаю фолбек на твій домен, щоб працювало відразу.
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://babybot-deploy-j9fy.onrender.com")

# ================== LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================== TG OBJECTS ==============
bot = Bot(token=TOKEN)
app = Flask(__name__)

# Класичний Dispatcher із PTB 13.x
dispatcher = Dispatcher(bot, update_queue=None, workers=0, use_context=True)

# ================== HANDLERS ================
def start(update: Update, context):
    update.message.reply_text("Привіт! 👶 Бот запущено на Render 24/7.")

def echo(update: Update, context):
    # Просто відповідаємо тим самим текстом — для перевірки
    update.message.reply_text(update.message.text)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

# ================== ROUTES ==================
@app.route("/")
def index():
    return "Bot is running 🟢"

@app.route("/set-webhook")
def set_webhook():
    bot.delete_webhook()
    ok = bot.set_webhook(url=f"{WEBHOOK_URL}/webhook/{TOKEN}")
    return {"ok": ok, "url": f"{WEBHOOK_URL}/webhook/{TOKEN}"}

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    except Exception as e:
        logger.exception("webhook error: %s", e)
        return "error", 500
    return "ok"

# ================== MAIN ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
