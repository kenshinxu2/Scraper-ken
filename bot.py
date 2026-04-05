import os
import asyncio
from pyrogram import Client, filters

# Environment Variables se credentials lena
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# Pyrogram Client Initialize karna
app = Client("video_cover_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Memory mein videos store karne ke liye dictionary
user_queues = {}

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("Sorry, this bot is only for the Admin.")
        return
    await message.reply_text("Hello Admin! 👑\n\n1. Mujhe ek-ek karke videos bhejo.\n2. Phir ek Image bhejo.\n3. Main us image ko sabhi videos ka cover banakar, same caption aur same order me wapis bhej dunga.\n\nQueue clear karne ke liye /clear type karein.")

@app.on_message(filters.command("clear") & filters.user(ADMIN_ID))
async def clear_queue(client, message):
    user_id = message.from_user.id
    user_queues[user_id] = []
    await message.reply_text("Queue bilkul clear ho chuki hai! Ab naye videos bhejo.")

# Jab Admin video bheje
@app.on_message(filters.video & filters.user(ADMIN_ID))
async def handle_video(client, message):
    user_id = message.from_user.id
    
    # Agar user pehli baar bhej raha hai, toh list create karo
    if user_id not in user_queues:
        user_queues[user_id] = []
        
    # Video aur uska original caption queue mein save karo
    user_queues[user_id].append({
        "file_id": message.video.file_id,
        "caption": message.caption if message.caption else "" # Caption jo tha wahi rahega
    })
    
    await message.reply_text(f"✅ Video {len(user_queues[user_id])} saved in queue! Aur videos bhejo ya cover image bhejo.")

# Jab Admin Image bheje (Cover change karne ke liye)
@app.on_message(filters.photo & filters.user(ADMIN_ID))
async def handle_photo(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_queues or len(user_queues[user_id]) == 0:
        await message.reply_text("⚠️ Pehle mujhe videos bhejo jinka cover change karna hai!")
        return
        
    status_msg = await message.reply_text("⏳ Processing started... Videos same order me wapis aa rahe hain!")
    
    # Image ko download karo
    photo_path = await message.download()
    
    try:
        # Loop chala kar ek-ek video same order (1,2,3,4) mein send karo
        for video_data in user_queues[user_id]:
            await client.send_video(
                chat_id=message.chat.id,
                video=video_data["file_id"],
                thumb=photo_path, # Yeh cover/thumbnail set karega
                caption=video_data["caption"] # Original caption
            )
            # 2 second ka sleep taaki Telegram bot ko block na kare (FloodWait Error se bachne ke liye)
            await asyncio.sleep(2) 
            
        await status_msg.edit_text("🎉 All videos sent successfully with the new cover!")
        
    except Exception as e:
        await message.reply_text(f"❌ Error aagaya: {e}")
    finally:
        # Kaam hone ke baad photo delete kardo server se aur queue empty kardo
        if os.path.exists(photo_path):
            os.remove(photo_path)
        user_queues[user_id] = [] # Queue reset

print("Bot is starting...")
app.run()
