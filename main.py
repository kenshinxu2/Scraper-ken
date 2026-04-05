import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InputMediaVideo
import subprocess

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Client("video_cover_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# Generate thumbnail using FFmpeg (HD fake cover)
def generate_thumb(video, thumb):
    cmd = [
        "ffmpeg", "-i", video,
        "-ss", "00:00:01",
        "-vframes", "1",
        "-vf", "scale=320:320",
        thumb
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@app.on_message(filters.video)
async def handle_video(client, message):
    msg = await message.reply_text("⚡ Processing...")

    file_path = await message.download()
    thumb_path = file_path + ".jpg"

    # Create thumbnail
    generate_thumb(file_path, thumb_path)

    # Keep original caption
    caption = message.caption if message.caption else ""

    await client.send_video(
        chat_id=message.chat.id,
        video=file_path,
        caption=caption,
        thumb=thumb_path,
        supports_streaming=True
    )

    os.remove(file_path)
    os.remove(thumb_path)

    await msg.delete()


app.run()
