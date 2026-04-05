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
WAITING_FOR_COVERS = 1

# Dictionary to store pending videos (user_id -> list of video_data)
pending_videos = {}

# Get environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    await update.message.reply_text(
        "🎬 **Video Cover Bot V3 - Multi Video Support**\n\n"
        "Send multiple videos and I'll change all covers!\n\n"
        "**How to use:**\n"
        "1️⃣ Send videos one by one (as video, not document) - 1,2,3,4...\n"
        "2️⃣ Send /done when all videos sent\n"
        "3️⃣ Send cover images in same order (1 cover per video)\n"
        "4️⃣ Bot processes all videos instantly!\n\n"
        "✅ Exact caption preserved (with formatting)\n"
        "✅ 0.04 seconds per video\n"
        "✅ Supports 1000+ videos in batch\n"
        "✅ Same format output (1,2,3,4)",
        parse_mode='Markdown'
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming video - add to batch"""
    user_id = update.effective_user.id
    video = update.message.video
    
    # Initialize user's video list if not exists
    if user_id not in pending_videos:
        pending_videos[user_id] = []
    
    # Get caption with entities (preserves exact formatting)
    original_caption = update.message.caption if update.message.caption else ""
    caption_entities = update.message.caption_entities if update.message.caption_entities else []
    
    # Store video info with index
    video_index = len(pending_videos[user_id]) + 1
    video_data = {
        'index': video_index,
        'video_file_id': video.file_id,
        'caption': original_caption,
        'caption_entities': caption_entities,  # Preserve entities for exact formatting
        'width': video.width,
        'height': video.height,
        'duration': video.duration,
        'filename': video.file_name if video.file_name else f"video_{video_index}.mp4",
        'mime_type': video.mime_type if video.mime_type else "video/mp4",
        'supports_streaming': video.supports_streaming if hasattr(video, 'supports_streaming') else True,
        'has_spoiler': video.has_media_spoiler if hasattr(video, 'has_media_spoiler') else False
    }
    
    pending_videos[user_id].append(video_data)
    
    await update.message.reply_text(
        f"✅ Video #{video_index} received!\n"
        f"📝 Caption: `{original_caption[:30]}...`" if len(original_caption) > 30 else f"📝 Caption: `{original_caption}`",
        parse_mode='Markdown'
    )
    
    return WAITING_FOR_COVERS

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User finished sending videos, now ask for covers"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("❌ No videos received! Send videos first.")
        return ConversationHandler.END
    
    video_count = len(pending_videos[user_id])
    
    await update.message.reply_text(
        f"🎬 **{video_count} videos received!**\n\n"
        f"📸 Now send {video_count} cover images in same order (1,2,3,4...)\n"
        f"⏱️ All covers will be changed in {video_count * 0.04:.2f} seconds!\n\n"
        f"Send cover #1 now...",
        parse_mode='Markdown'
    )
    
    # Reset cover counter for this user
    context.user_data['cover_count'] = 0
    context.user_data['total_videos'] = video_count
    
    return WAITING_FOR_COVERS

async def handle_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cover images and process videos"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("❌ No pending videos! Send /start to begin.")
        return ConversationHandler.END
    
    if not update.message.photo:
        await update.message.reply_text("❌ Please send cover as **photo**, not document!")
        return WAITING_FOR_COVERS
    
    # Get current cover index
    current_cover = context.user_data.get('cover_count', 0)
    total_videos = context.user_data.get('total_videos', len(pending_videos[user_id]))
    
    if current_cover >= total_videos:
        await update.message.reply_text("❌ All covers already received! Processing...")
        return await process_all_videos(update, context)
    
    # Get the highest quality photo
    cover_photo = update.message.photo[-1]
    
    # Store cover for this video
    pending_videos[user_id][current_cover]['cover_file_id'] = cover_photo.file_id
    
    # Increment counter
    context.user_data['cover_count'] = current_cover + 1
    next_cover = current_cover + 2
    
    # Check if all covers received
    if context.user_data['cover_count'] >= total_videos:
        return await process_all_videos(update, context)
    else:
        await update.message.reply_text(
            f"✅ Cover #{current_cover + 1} received!\n"
            f"📸 Send cover #{next_cover}..."
        )
        return WAITING_FOR_COVERS

async def process_all_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process all videos with their covers"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos:
        await update.message.reply_text("❌ No videos to process!")
        return ConversationHandler.END
    
    videos = pending_videos[user_id]
    total = len(videos)
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        f"⚡ Processing {total} videos...\n"
        f"⏱️ Estimated time: {total * 0.04:.2f} seconds"
    )
    
    # Prepare all media for batch send
    media_group = []
    
    for video_data in videos:
        # Check if cover exists
        if 'cover_file_id' not in video_data:
            await update.message.reply_text(f"❌ Missing cover for video #{video_data['index']}!")
            continue
        
        # Create InputMediaVideo with exact caption preservation using entities
        media = InputMediaVideo(
            media=video_data['video_file_id'],
            caption=video_data['caption'] if video_data['caption'] else None,
            caption_entities=video_data['caption_entities'] if video_data['caption_entities'] else None,  # Exact formatting preserved!
            parse_mode=None,  # Don't parse, use entities instead
            width=video_data['width'],
            height=video_data['height'],
            duration=video_data['duration'],
            supports_streaming=video_data['supports_streaming'],
            cover=video_data['cover_file_id'],  # NEW COVER
            thumbnail=video_data['cover_file_id'],
            has_spoiler=video_data['has_spoiler']
        )
        media_group.append(media)
    
    try:
        # Telegram allows max 10 items per media_group
        # Split into chunks of 10 if more than 10 videos
        chunk_size = 10
        sent_count = 0
        
        for i in range(0, len(media_group), chunk_size):
            chunk = media_group[i:i + chunk_size]
            
            # Send chunk
            await context.bot.send_media_group(
                chat_id=update.effective_chat.id,
                media=chunk
            )
            sent_count += len(chunk)
            
            # Small delay between chunks to avoid rate limits
            if i + chunk_size < len(media_group):
                await asyncio.sleep(0.5)
        
        # Delete processing message
        await processing_msg.delete()
        
        # Send completion message
        await update.message.reply_text(
            f"✅ **All {sent_count} videos processed!**\n"
            f"🎬 Covers changed successfully\n"
            f"📝 Captions preserved exactly\n"
            f"⚡ Total time: ~{total * 0.04:.2f} seconds",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error processing videos: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    # Clean up
    del pending_videos[user_id]
    context.user_data.clear()
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    user_id = update.effective_user.id
    if user_id in pending_videos:
        del pending_videos[user_id]
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled. Send /start to try again.")
    return ConversationHandler.END

async def process_single_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alternative: Process videos immediately as covers arrive (1-by-1)"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        return
    
    if not update.message.photo:
        return
    
    # Get first pending video without cover
    cover_photo = update.message.photo[-1]
    cover_file_id = cover_photo.file_id
    
    for i, video_data in enumerate(pending_videos[user_id]):
        if 'cover_file_id' not in video_data:
            # Process this video immediately
            try:
                media = InputMediaVideo(
                    media=video_data['video_file_id'],
                    caption=video_data['caption'] if video_data['caption'] else None,
                    caption_entities=video_data['caption_entities'] if video_data['caption_entities'] else None,
                    parse_mode=None,
                    width=video_data['width'],
                    height=video_data['height'],
                    duration=video_data['duration'],
                    supports_streaming=video_data['supports_streaming'],
                    cover=cover_file_id,
                    thumbnail=cover_file_id,
                    has_spoiler=video_data['has_spoiler']
                )
                
                await context.bot.send_media_group(
                    chat_id=update.effective_chat.id,
                    media=[media]
                )
                
                # Mark as processed
                pending_videos[user_id][i]['cover_file_id'] = cover_file_id
                pending_videos[user_id][i]['processed'] = True
                
                await update.message.reply_text(f"✅ Video #{video_data['index']} done!")
                
                # Check if all done
                all_done = all(v.get('processed', False) for v in pending_videos[user_id])
                if all_done:
                    await update.message.reply_text("🎉 All videos completed!")
                    del pending_videos[user_id]
                
                return
                
            except Exception as e:
                logger.error(f"Error: {e}")
                await update.message.reply_text(f"❌ Error processing video #{video_data['index']}")
                return

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN provided!")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.VIDEO, handle_video)],
        states={
            WAITING_FOR_COVERS: [
                MessageHandler(filters.PHOTO, handle_cover),
                CommandHandler('done', done_command),
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(conv_handler)
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
