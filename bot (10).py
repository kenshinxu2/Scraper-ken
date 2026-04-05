import os
import asyncio
import logging
from collections import deque
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image
import io

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Environment variables for bot token, API ID, and API Hash
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Validate environment variables
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("Missing one or more environment variables: API_ID, API_HASH, BOT_TOKEN")
    exit(1)

# Initialize the bot client
app = Client("video_cover_bot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

# Dictionaries to store state per user
user_video_queues = {}  # user_id -> deque of video messages
user_photo_queues = {}  # user_id -> deque of photo messages
user_processing_lock = {}  # user_id -> asyncio.Lock to ensure sequential processing

async def process_thumbnail_image(image_path: str) -> io.BytesIO:
    """Processes an image to meet Telegram thumbnail requirements (JPEG, max 320x320, < 200KB)."""
    try:
        img = Image.open(image_path)

        # Resize to max 320x320 while maintaining aspect ratio
        img.thumbnail((320, 320), Image.Resampling.LANCZOS)

        # Convert to JPEG and compress to less than 200KB
        output_bytes = io.BytesIO()
        quality = 95  # Start with high quality
        while True:
            output_bytes.seek(0)
            img.save(output_bytes, format="JPEG", quality=quality)
            if output_bytes.tell() <= 200 * 1024 or quality <= 10:
                break
            quality -= 5
            if quality < 0: # Prevent infinite loop if image cannot be compressed enough
                logger.warning(f"Could not compress image {image_path} to under 200KB. Sending with best possible quality.")
                break
        
        output_bytes.seek(0)
        return output_bytes
    except Exception as e:
        logger.error(f"Error processing thumbnail image {image_path}: {e}")
        raise

async def process_user_queue(client: Client, user_id: int, chat_id: int):
    """Processes video and photo pairs from a user's queue in order."""
    if user_id not in user_processing_lock:
        user_processing_lock[user_id] = asyncio.Lock()
    
    # If another task is already processing for this user, return
    if user_processing_lock[user_id].locked():
        return

    async with user_processing_lock[user_id]:
        while user_id in user_video_queues and user_video_queues[user_id] and \
              user_id in user_photo_queues and user_photo_queues[user_id]:
            
            video_message = user_video_queues[user_id].popleft()
            photo_message = user_photo_queues[user_id].popleft()
            
            original_caption = video_message.caption if video_message.caption else ""
            
            photo_path = None
            video_path = None
            try:
                logger.info(f"User {user_id}: Processing video {video_message.id} with photo {photo_message.id}")
                status_msg = await client.send_message(chat_id, "Processing your video... Please wait.")

                # Download and process image for thumbnail
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
                await status_msg.edit_text("Video sent with new cover!")
                logger.info(f"User {user_id}: Successfully sent video {video_message.id} with new cover.")

            except Exception as e:
                logger.error(f"User {user_id}: Error processing video {video_message.id}: {e}")
                await client.send_message(chat_id, f"An error occurred while processing your video: {e}")
            finally:
                # Clean up downloaded files
                if photo_path and os.path.exists(photo_path):
                    os.remove(photo_path)
                    logger.debug(f"Cleaned up photo file: {photo_path}")
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)
                    logger.debug(f"Cleaned up video file: {video_path}")
                if status_msg:
                    await status_msg.delete()

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    logger.info(f"User {message.from_user.id} started the bot.")
    await message.reply_text(
        "Hello! Send me a video, and then send me an image to use as its cover/thumbnail. "
        "I will send the video back with the new cover, preserving its caption. "
        "You can send multiple videos and images; I will process them in the order received."
    )

@app.on_message(filters.video & filters.private)
async def handle_video(client: Client, message: Message):
    user_id = message.from_user.id
    logger.info(f"User {user_id} sent a video (ID: {message.id}).")
    if user_id not in user_video_queues:
        user_video_queues[user_id] = deque()
    
    user_video_queues[user_id].append(message)
    await message.reply_text("Video received! Now send me the image you want to use as its cover/thumbnail.")
    asyncio.create_task(process_user_queue(client, user_id, message.chat.id))

@app.on_message(filters.photo & filters.private)
async def handle_photo(client: Client, message: Message):
    user_id = message.from_user.id
    logger.info(f"User {user_id} sent a photo (ID: {message.id}).")
    if user_id not in user_photo_queues:
        user_photo_queues[user_id] = deque()
    
    user_photo_queues[user_id].append(message)
    await message.reply_text("Image received! I will process it with the next available video.")
    asyncio.create_task(process_user_queue(client, user_id, message.chat.id))

if __name__ == "__main__":
    logger.info("Bot started...")
    app.run()
