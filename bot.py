import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters
import logging

# ===== CONFIG =====
TOKEN = os.environ.get("BOT_TOKEN")  # твій токен з Render -> Environment
WEBHOOK_URL = "https://babybot-deploy-j9fy.onrender.com"

# ===== TELEGRAM =====
bot = Bot(token=TOKEN)
app = Flask(__name__)

# логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== HANDLERS =====
def start(update: Update, context):
    update.message.reply_text("Привіт! 👶 Бот запущено 24/7!")

def echo(update: Update, context):
    update.message.reply_text(update.message.text)

# ===== DISPATCHER =====
from telegram.ext import Dispatcher
dispatcher = Dispatcher(bot, None, use_context=True)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# ===== ROUTES =====
@app.route('/set-webhook')
def set_webhook():
    bot.delete_webhook()
    s = bot.set_webhook(url=f"{WEBHOOK_URL}/webhook/{TOKEN}")
    return {"ok": s}

@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route('/')
def index():
    return "Bot is running 🟢"

# ===== MAIN =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
