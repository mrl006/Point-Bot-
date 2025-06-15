import os
import logging
from datetime import datetime, timedelta
from telegram import Update, ChatMember
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from pymongo import MongoClient
from dotenv import load_dotenv
import random

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
logs = db["logs"]

logging.basicConfig(level=logging.INFO)

def get_badge(points):
    if points >= 500:
        return "🥇 Master"
    elif points >= 100:
        return "🥈 Intermediate"
    elif points > 0:
        return "🥉 Beginner"
    else:
        return "❌ Newbie"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 <b>Welcome to Ranking Bot!</b>\n\n"
        f"📍 Group: <b>{update.effective_chat.title or 'Private Chat'}</b>\n"
        "📊 Use <code>/leaderboard</code> to view top scorers in this group\n"
        "🎯 Use <code>/mypoints</code> to check your score\n"
        "🏅 Admins: <code>/award</code>, <code>/reset</code>\n"
        "🎁 Use <code>/daily</code> to claim your bonus!",
        parse_mode="HTML"
    )

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 Your Telegram ID: <code>{update.effective_user.id}</code>",
        parse_mode="HTML"
    )

async def award(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    group_id = chat.id
    group_name = chat.title or "Private"

    if chat.type in ["group", "supergroup"]:
        member: ChatMember = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("🚫 Only admins can use this.", parse_mode="HTML")
            return
    else:
        if user.id != ADMIN_ID:
            await update.message.reply_text("🚫 Not authorized.", parse_mode="HTML")
            return

    if len(context.args) != 2:
        await update.message.reply_text("❗ Usage: <code>/award @user 10</code>", parse_mode="HTML")
        return

    username = context.args[0].lstrip("@")
    try:
        points = int(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Points must be a number.", parse_mode="HTML")
        return

    users.update_one(
        {"username": username, "group_id": group_id},
        {"$inc": {"points": points}, "$set": {"group_name": group_name}},
        upsert=True
    )

    logs.insert_one({
        "giver": user.username,
        "receiver": username,
        "points": points,
        "group_id": group_id,
        "group_name": group_name,
        "time": datetime.utcnow().isoformat()
    })

    await update.message.reply_text(
        f"✅ <b>@{username}</b> received <b>{points} pts</b> in <b>{group_name}</b>!",
        parse_mode="HTML"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    group_id = chat.id

    if chat.type in ["group", "supergroup"]:
        member: ChatMember = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ["administrator", "creator"]:
            await update.message.reply_text("🚫 Only admins can use this.", parse_mode="HTML")
            return
    else:
        if user.id != ADMIN_ID:
            await update.message.reply_text("🚫 Not authorized.", parse_mode="HTML")
            return

    if len(context.args) != 1:
        await update.message.reply_text("❗ Usage: <code>/reset @user</code>", parse_mode="HTML")
        return

    username = context.args[0].lstrip("@")
    users.update_one({"username": username, "group_id": group_id}, {"$set": {"points": 0}})
    await update.message.reply_text(f"♻️ <b>@{username}</b>'s points reset to 0 in this group.", parse_mode="HTML")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    group_id = chat.id
    group_name = chat.title or "Private"

    top = list(users.find({"group_id": group_id}).sort("points", -1).limit(10))
    if not top:
        await update.message.reply_text("📉 No leaderboard data for this group.")
        return

    msg = f"<b>🏆 Leaderboard – {group_name}:</b>\n\n"
    for i, u in enumerate(top, 1):
        badge = get_badge(u['points'])
        msg += f"{i}. @{u['username']} — <b>{u['points']} pts</b> {badge}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

async def mypoints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    group_id = update.effective_chat.id

    if not username:
        await update.message.reply_text("⚠️ Set a public @username to track points.", parse_mode="HTML")
        return

    doc = users.find_one({"username": username, "group_id": group_id})
    pts = doc["points"] if doc else 0
    badge = get_badge(pts)

    await update.message.reply_text(
        f"📦 <b>@{username}</b>\nPoints: <b>{pts}</b>\nBadge: {badge}",
        parse_mode="HTML"
    )

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    group_id = update.effective_chat.id
    group_name = update.effective_chat.title or "Private"

    if not username:
        await update.message.reply_text("⚠️ Set a @username first.", parse_mode="HTML")
        return

    doc = users.find_one({"username": username, "group_id": group_id})
    now = datetime.utcnow()
    if doc and "lastClaim" in doc:
        last = datetime.fromisoformat(doc["lastClaim"])
        if now - last < timedelta(hours=24):
            await update.message.reply_text("🕒 You already claimed your daily bonus today.", parse_mode="HTML")
            return

    bonus = random.randint(10, 50)
    users.update_one(
        {"username": username, "group_id": group_id},
        {"$inc": {"points": bonus}, "$set": {"lastClaim": now.isoformat(), "group_name": group_name}},
        upsert=True
    )

    await update.message.reply_text(f"🎁 You claimed <b>{bonus} pts</b> today in this group!", parse_mode="HTML")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("award", award))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("mypoints", mypoints))
    app.add_handler(CommandHandler("daily", daily))
    print("Bot is running 🎯")
    app.run_polling()
