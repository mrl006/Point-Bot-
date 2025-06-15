import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
ADMIN_ID_STR = os.getenv("ADMIN_ID")

if not TOKEN or not MONGO_URI or not ADMIN_ID_STR:
    raise ValueError("❌ Missing environment variables: BOT_TOKEN, MONGO_URI, or ADMIN_ID")

ADMIN_ID = int(ADMIN_ID_STR)

# Fix SSL issue with MongoDB Atlas
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["points_db"]
users = db["users"]

logging.basicConfig(level=logging.INFO)

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the Ranking Bot!\n\n"
        "Use /leaderboard to see top users\n"
        "Use /mypoints to check your score\n"
        "Admins can use /award @username 10 to give points."
    )

# /myid command to check your Telegram ID
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID: {update.effective_user.id}")

# /award command (admin only)
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
    except ValueError:
        await update.message.reply_text("Points must be a number.")
        return

    if not username:
        await update.message.reply_text("❗ Username missing or invalid.")
        return

    user = users.find_one({"username": username})
    if not user:
        users.insert_one({"username": username, "points": points})
    else:
        users.update_one({"username": username}, {"$inc": {"points": points}})

    await update.message.reply_text(f"✅ Awarded {points} pts to @{username}.")

# /leaderboard command
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = users.find().sort("points", -1).limit(10)
    if top.count() == 0:
        await update.message.reply_text("🏆 No users on the leaderboard yet.")
        return

    msg = "🏆 Leaderboard:\n"
    for i, u in enumerate(top, 1):
        msg += f"{i}. @{u['username']} – {u['points']} pts\n"
    await update.message.reply_text(msg)

# /mypoints command
async def mypoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    if not username:
        await update.message.reply_text("❗ Please set a public @username in Telegram to track your score.")
        return

    user = users.find_one({"username": username})
    pts = user["points"] if user else 0
    await update.message.reply_text(f"🧮 @{username}, you have {pts} pts.")

# Start the bot
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("award", award))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("mypoints", mypoints))
    print("Bot is running 🎯")
    app.run_polling()
