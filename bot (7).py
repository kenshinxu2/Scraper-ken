import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image
import io
from collections import deque

# Environment variables for bot token, API ID, and API Hash
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Initialize the bot client using pyrofork
app = Client("video_cover_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Dictionaries to store state per user
# Queues to ensure 1,2,3,4 order is maintained
user_video_queues = {} # user_id -> deque of video messages
user_photo_queues = {} # user_id -> deque of photo messages
user_processing_lock = {} # user_id -> asyncio.Lock to ensure sequential processing

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    await message.reply_text(
        "Hello! Send me a video, and then send me an image to use as its cover/thumbnail. "
        "I will send the video back with the new cover, preserving its caption. "
        "Please send videos one by one if you want to change their covers individually."
    )

@app.on_message(filters.video & filters.private)
async def handle_video(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_video_queues:
        user_video_queues[user_id] = deque()
    
    user_video_queues[user_id].append(message)
    # Check if we can start processing
    asyncio.create_task(process_user_queue(client, user_id, message.chat.id))

@app.on_message(filters.photo & filters.private)
async def handle_photo(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_photo_queues:
        user_photo_queues[user_id] = deque()
    
    user_photo_queues[user_id].append(message)
    # Check if we can start processing
    asyncio.create_task(process_user_queue(client, user_id, message.chat.id))

async def process_user_queue(client: Client, user_id: int, chat_id: int):
    # Ensure only one process runs for a user at a time to maintain order
    if user_id not in user_processing_lock:
        user_processing_lock[user_id] = asyncio.Lock()
    
    if user_processing_lock[user_id].locked():
        return

    async with user_processing_lock[user_id]:
        while user_id in user_video_queues and user_video_queues[user_id] and \
              user_id in user_photo_queues and user_photo_queues[user_id]:
            
            video_message = user_video_queues[user_id].popleft()
            photo_message = user_photo_queues[user_id].popleft()
            
            original_caption = video_message.caption if video_message.caption else ""
            
            try:
                # Download and process image
                status_msg = await client.send_message(chat_id, "Processing a video from your queue...")
                photo_path = await client.download_media(photo_message.photo.file_id)
                thumbnail_bytes = await process_thumbnail_image(photo_path)
                
                # Download video
                video_path = await client.download_media(video_message.video.file_id)
                
                # Send back video with new cover
                await client.send_video(
                    chat_id=chat_id,
                    video=video_path,
                    caption=original_caption,
                    thumb=thumbnail_bytes,
                    duration=video_message.video.duration,
                    width=video_message.video.width,
                    height=video_message.video.height,
                    supports_streaming=True
                )
                await status_msg.delete()
                
                # Cleanup
                if os.path.exists(photo_path): os.remove(photo_path)
                if os.path.exists(video_path): os.remove(video_path)
                
            except Exception as e:
                await client.send_message(chat_id, f"Error processing a video: {e}")

async def process_thumbnail_image(image_path: str) -> io.BytesIO:
    """Processes an image to meet Telegram thumbnail requirements."""
    img = Image.open(image_path)

    # Resize to max 320x320 while maintaining aspect ratio
    img.thumbnail((320, 320), Image.Resampling.LANCZOS)

    # Convert to JPEG and compress to less than 200KB
    output_bytes = io.BytesIO()
    quality = 95 # Start with high quality
    while True:
        output_bytes.seek(0)
        img.save(output_bytes, format="JPEG", quality=quality)
        if output_bytes.tell() <= 200 * 1024 or quality <= 10:
            break
        quality -= 5
    
    output_bytes.seek(0)
    return output_bytes

if __name__ == "__main__":
    print("Bot started...")
    app.run()
