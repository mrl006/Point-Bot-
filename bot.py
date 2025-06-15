import os
import logging
from telegram import Update, ChatMember
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

client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["points_db"]
users = db["users"]

logging.basicConfig(level=logging.INFO)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Welcome to Racking Bot!</b>\n\n"
        "📊 Use <code>/leaderboard</code> to view the top scorers\n"
        "🎯 Use <code>/mypoints</code> to check your score\n"
        "🏅 Admins can use <code>/award @username 10</code> to give points",
        parse_mode="HTML"
    )

# /myid
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 Your Telegram ID: <code>{update.effective_user.id}</code>",
        parse_mode="HTML"
    )

# /award
async def award(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if chat.type in ["group", "supergroup"]:
        member: ChatMember = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text(
                "🚫 <b>Access Denied:</b> Only group admins or the bot owner can use this command.",
                parse_mode="HTML"
            )
            return
    else:
        if user.id != ADMIN_ID:
            await update.message.reply_text(
                "🚫 <b>Access Denied:</b> Only the bot owner can use this command.",
                parse_mode="HTML"
            )
            return

    if len(context.args) != 2:
        await update.message.reply_text(
            "❗ <b>Usage:</b> <code>/award @username 10</code>",
            parse_mode="HTML"
        )
        return

    username = context.args[0].lstrip("@")
    try:
        points = int(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Points must be a number.", parse_mode="HTML")
        return

    if not username:
        await update.message.reply_text("❗ Username missing or invalid.", parse_mode="HTML")
        return

    user_doc = users.find_one({"username": username})
    if not user_doc:
        users.insert_one({"username": username, "points": points})
    else:
        users.update_one({"username": username}, {"$inc": {"points": points}})

    await update.message.reply_text(
        f"✅ <b>+{points} pts</b> awarded to <b>@{username}</b>!",
        parse_mode="HTML"
    )

# /leaderboard
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = list(users.find().sort("points", -1).limit(10))
    if not top:
        await update.message.reply_text("📉 No leaderboard data yet.")
        return

    msg = "<b>🏆 Leaderboard:</b>\n\n"
    for i, u in enumerate(top, 1):
        msg += f"{i}. @{u['username']} — <b>{u['points']} pts</b>\n"
    await update.message.reply_text(msg, parse_mode="HTML")

# /mypoints
async def mypoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    if not username:
        await update.message.reply_text(
            "⚠️ Please set a public @username in Telegram to track your score.",
            parse_mode="HTML"
        )
        return

    user_doc = users.find_one({"username": username})
    pts = user_doc["points"] if user_doc else 0
    await update.message.reply_text(
        f"📦 <b>@{username}</b>, you currently have <b>{pts} pts</b>.",
        parse_mode="HTML"
    )

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
