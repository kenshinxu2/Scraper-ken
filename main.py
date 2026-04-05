import os
from pyrogram import Client, filters

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("fast_cover_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# user wise thumb store
user_thumb = {}

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "🔥 FAST COVER BOT READY\n\n"
        "1️⃣ Pehle image bhej (cover)\n"
        "2️⃣ Fir video bhej\n\n"
        "⚡ Ultra fast processing"
    )

# 📸 Save user cover image
@app.on_message(filters.photo)
async def save_thumb(client, message):
    thumb_path = await message.download()

    user_thumb[message.from_user.id] = thumb_path

    await message.reply_text("✅ Cover saved successfully!")

# 🎬 Handle video
@app.on_message(filters.video)
async def handle_video(client, message):
    user_id = message.from_user.id

    if user_id not in user_thumb:
        return await message.reply_text("❌ Pehle cover image bhej!")

    thumb = user_thumb[user_id]

    caption = message.caption or ""

    await client.send_video(
        chat_id=message.chat.id,
        video=message.video.file_id,  # ⚡ FAST (no download)
        caption=caption,              # ✅ same caption
        thumb=thumb,                 # fake cover
        supports_streaming=True
    )
