import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InputMediaVideo
from PIL import Image

# Railway Environment Variables
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# Pyrofork Client
app = Client("video_cover_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_queues = {}

# Telegram ke rules ke hisaab se Thumbnail ko resize karne ka function
def prepare_thumbnail(photo_path):
    try:
        img = Image.open(photo_path)
        img.thumbnail((320, 320)) # Telegram API rule: thumb must be max 320x320
        thumb_path = f"{photo_path}_thumb.jpg"
        img.convert("RGB").save(thumb_path, "JPEG", quality=85) # Convert to strict JPEG
        return thumb_path
    except Exception as e:
        print(f"Thumbnail resize error: {e}")
        return photo_path

@app.on_message(filters.command("start") & filters.user(ADMIN_ID))
async def start_cmd(client, message):
    await message.reply_text("Bot Ready! ⚡\n1. Videos bhejo (caption aur formatting save rahegi).\n2. Cover image bhejo.\n3. Main order me cover lagakar wapis bhejunga.")

@app.on_message(filters.command("clear") & filters.user(ADMIN_ID))
async def clear_queue(client, message):
    user_queues[message.from_user.id] = []
    await message.reply_text("🗑️ Queue clear kar di gayi hai!")

# Step 1: Videos Save Karna
@app.on_message(filters.video & filters.user(ADMIN_ID))
async def handle_video(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_queues:
        user_queues[user_id] = []
        
    user_queues[user_id].append({
        "msg_id": message.id, # Yeh ID order ko 1,2,3,4 me lagane ke kaam aayegi
        "file_id": message.video.file_id,
        "caption": message.caption, 
        "entities": message.caption_entities # Yeh aapki fonts, emojis, links bachayega
    })
    
    await message.reply_text(f"✅ Video Added! Total in queue: {len(user_queues[user_id])}", quote=True)

# Step 2: Cover lagana aur wapis bhejna
@app.on_message(filters.photo & filters.user(ADMIN_ID))
async def handle_photo(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_queues or len(user_queues[user_id]) == 0:
        await message.reply_text("⚠️ Queue khali hai! Pehle videos bhejo.")
        return
        
    status_msg = await message.reply_text("⏳ Processing started... Thumbnail set kar raha hu aur line se bhej raha hu!")
    
    # Image download karo aur Telegram ke hisaab se resize karo
    raw_photo = await message.download()
    final_thumb = prepare_thumbnail(raw_photo)
    
    try:
        # MAIN FIX: Videos ko unke bheje gaye order (Message ID) ke hisaab se sort karo
        sorted_videos = sorted(user_queues[user_id], key=lambda x: x["msg_id"])
        
        for video_data in sorted_videos:
            # Puraani file_id + naya thumbnail + exactly same caption bhejna
            await client.send_video(
                chat_id=message.chat.id,
                video=video_data["file_id"],
                thumb=final_thumb, # Resized thumbnail
                caption=video_data["caption"], 
                caption_entities=video_data["entities"] # Formatting intact rahegi
            )
            await asyncio.sleep(1.5) # FloodWait error se bachne ke liye thoda wait
            
        await status_msg.edit_text("🎉 Kaam Ho Gaya! Saare videos naye cover ke sath, original caption ke sath, aur bilkul sahi order me bhej diye gaye hain!")
        
    except Exception as e:
        await message.reply_text(f"❌ Error aagaya: {e}")
    finally:
        # Server se kachra saaf karo aur queue zero karo
        if os.path.exists(raw_photo):
            os.remove(raw_photo)
        if os.path.exists(final_thumb):
            os.remove(final_thumb)
        user_queues[user_id] = []

print("Pyrofork Bot is starting...")
app.run()
