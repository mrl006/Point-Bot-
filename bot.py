import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["points_db"]
users = db["users"]

logging.basicConfig(level=logging.INFO)

async def award(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /award @username 10")
        return

    username = context.args[0].lstrip("@")
    try:
        points = int(context.args[1])
    except:
        await update.message.reply_text("Points must be a number.")
        return

    user = users.find_one({"username": username})
    if not user:
        users.insert_one({"username": username, "points": points})
    else:
        users.update_one({"username": username}, {"$inc": {"points": points}})

    await update.message.reply_text(f"✅ Awarded {points} pts to @{username}.")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = users.find().sort("points", -1).limit(10)
    msg = "🏆 Leaderboard:\n"
    for i, u in enumerate(top, 1):
        msg += f"{i}. @{u['username']} – {u['points']} pts\n"
    await update.message.reply_text(msg)

async def mypoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    user = users.find_one({"username": username})
    pts = user["points"] if user else 0
    await update.message.reply_text(f"🧮 @{username}, you have {pts} pts.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("award", award))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("mypoints", mypoints))
    print("Bot is running 🎯")
    app.run_polling()
