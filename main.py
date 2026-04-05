import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("ultra_fast_cover_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 🔥 user data store
user_data = {}

# ================= START =================
@app.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text(
        "🔥 ULTRA FAST COVER BOT\n\n"
        "1️⃣ Pehle cover image bhej\n"
        "2️⃣ Fir jitne video bhejne hai bhej (1,2,3,4...)\n\n"
        "⚡ Same order + instant send"
    )

# ================= SAVE COVER =================
@app.on_message(filters.photo)
async def save_cover(client, message: Message):
    user_id = message.from_user.id

    # 🧹 old thumb delete
    if user_id in user_data:
        old_thumb = user_data[user_id].get("thumb")
        if old_thumb and os.path.exists(old_thumb):
            os.remove(old_thumb)

    thumb_path = await message.download()

    user_data[user_id] = {
        "thumb": thumb_path,
        "queue": []
    }

    await message.reply_text("✅ Cover saved! Ab video bhej")

# ================= HANDLE VIDEOS =================
@app.on_message(filters.video)
async def handle_video(client, message: Message):
    user_id = message.from_user.id

    if user_id not in user_data:
        return await message.reply_text("❌ Pehle cover image bhej!")

    # queue maintain (order safe)
    user_data[user_id]["queue"].append(message)

    await process_queue(client, user_id)


# ================= PROCESS QUEUE =================
async def process_queue(client, user_id):
    queue = user_data[user_id]["queue"]
    thumb = user_data[user_id]["thumb"]

    while queue:
        msg = queue.pop(0)

        caption = msg.caption or ""

        try:
            await client.send_video(
                chat_id=msg.chat.id,
                video=msg.video.file_id,   # ⚡ FAST
                caption=caption,           # ✅ SAME
                thumb=thumb,               # fake cover
                supports_streaming=True
            )
        except Exception as e:
            await msg.reply_text(f"❌ Error: {e}")

        await asyncio.sleep(0.2)  # anti flood safety


# ================= CLEANUP (optional auto reset) =================
@app.on_message(filters.command("reset"))
async def reset(client, message: Message):
    user_id = message.from_user.id

    if user_id in user_data:
        thumb = user_data[user_id].get("thumb")
        if thumb and os.path.exists(thumb):
            os.remove(thumb)

        user_data.pop(user_id)

    await message.reply_text("🧹 Data reset ho gaya!")


print("✅ ULTRA FAST BOT STARTED...")
app.run()
