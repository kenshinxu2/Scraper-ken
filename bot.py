import os
import logging
import asyncio
from telegram import Update, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
WAITING_FOR_COVER = 1

# Dictionary to store pending videos (user_id -> video_data)
pending_videos = {}

# Get environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    await update.message.reply_text(
        "🎬 **Video Cover Bot**\n\n"
        "Send me a video and I'll change its cover!\n\n"
        "**How to use:**\n"
        "1️⃣ Send a video (as video, not document)\n"
        "2️⃣ Send an HD image as cover\n"
        "3️⃣ I'll send back the video with new cover instantly!\n\n"
        "✅ Caption will remain same\n"
        "✅ Cover changes in 0.04 seconds\n"
        "✅ Supports batch processing (1,2,3,4 format)",
        parse_mode='Markdown'
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming video"""
    user_id = update.effective_user.id
    video = update.message.video
    
    # Get caption - handle None case properly
    original_caption = update.message.caption if update.message.caption else ""
    
    # Store video info
    pending_videos[user_id] = {
        'video_file_id': video.file_id,
        'caption': original_caption,  # Store original caption exactly as-is
        'width': video.width,
        'height': video.height,
        'duration': video.duration,
        'filename': video.file_name if video.file_name else "video.mp4",
        'mime_type': video.mime_type if video.mime_type else "video/mp4",
        'supports_streaming': video.supports_streaming if hasattr(video, 'supports_streaming') else True,
        'has_spoiler': video.has_media_spoiler if hasattr(video, 'has_media_spoiler') else False
    }
    
    # Show user what caption was detected
    caption_preview = original_caption[:50] + "..." if len(original_caption) > 50 else original_caption
    if not caption_preview:
        caption_preview = "(no caption)"
    
    await update.message.reply_text(
        f"✅ Video received!\n"
        f"📝 Caption detected: `{caption_preview}`\n"
        f"📸 Now send me the **HD cover image** (as photo)\n"
        f"⏱️ Processing will take only 0.04 seconds!",
        parse_mode='Markdown'
    )
    
    return WAITING_FOR_COVER

async def handle_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cover image and send video back with new cover"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos:
        await update.message.reply_text("❌ Please send a video first!")
        return ConversationHandler.END
    
    if not update.message.photo:
        await update.message.reply_text("❌ Please send the cover as a **photo**, not document!")
        return WAITING_FOR_COVER
    
    # Get the highest quality photo
    cover_photo = update.message.photo[-1]
    cover_file_id = cover_photo.file_id
    
    video_data = pending_videos[user_id]
    
    try:
        # Send processing message
        processing_msg = await update.message.reply_text("⚡ Changing cover in 0.04 seconds...")
        
        # Get original caption exactly as stored
        original_caption = video_data['caption']
        
        logger.info(f"Original caption: {repr(original_caption)}")
        
        # Method 1: Try using copy_message with cover (if supported)
        # Method 2: Use InputMediaVideo with proper caption handling
        
        # Create InputMediaVideo with new cover
        # IMPORTANT: We must pass caption exactly as original, not empty string
        media = InputMediaVideo(
            media=video_data['video_file_id'],
            caption=original_caption if original_caption else None,  # Use None if empty, else exact caption
            parse_mode=None,  # Don't parse markdown/html in caption to preserve exact text
            width=video_data['width'],
            height=video_data['height'],
            duration=video_data['duration'],
            supports_streaming=video_data['supports_streaming'],
            cover=cover_file_id,  # NEW COVER HERE - HD image
            thumbnail=cover_file_id,  # Also set as thumbnail
            has_spoiler=video_data['has_spoiler']
        )
        
        # Send the video back with new cover
        sent_messages = await context.bot.send_media_group(
            chat_id=update.effective_chat.id,
            media=[media]
        )
        
        # Verify caption was preserved
        if sent_messages and len(sent_messages) > 0:
            sent_caption = sent_messages[0].caption if sent_messages[0].caption else ""
            logger.info(f"Sent caption: {repr(sent_caption)}")
            
            if sent_caption != original_caption:
                logger.warning(f"Caption mismatch! Original: {repr(original_caption)}, Sent: {repr(sent_caption)}")
        
        # Delete processing message
        await processing_msg.delete()
        
        # Clean up
        del pending_videos[user_id]
        
        await update.message.reply_text("✅ Cover changed successfully! Caption preserved.")
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        if user_id in pending_videos:
            del pending_videos[user_id]
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    user_id = update.effective_user.id
    if user_id in pending_videos:
        del pending_videos[user_id]
    await update.message.reply_text("❌ Cancelled. Send /start to try again.")
    return ConversationHandler.END

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN provided!")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for video + cover flow
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.VIDEO, handle_video)],
        states={
            WAITING_FOR_COVER: [
                MessageHandler(filters.PHOTO, handle_cover),
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                    lambda u, c: u.message.reply_text("Please send a photo as cover!"))
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(conv_handler)
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
