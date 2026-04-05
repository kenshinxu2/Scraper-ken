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

# States
COLLECTING_VIDEOS = 1
WAITING_FOR_COVER = 2

# Storage
pending_videos = {}  # user_id -> list of videos
user_cover = {}      # user_id -> cover_file_id

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    await update.message.reply_text(
        "🎬 **Video Cover Bot V5 - One Cover for All**\n\n"
        "**Kaam ka tareeka:**\n"
        "1️⃣ Multiple videos ek saath bhejo (100 bhi bhejo!)\n"
        "2️⃣ Bot queue mein save karega\n"
        "3️⃣ Ek HD cover image bhejo\n"
        "4️⃣ Bot sab videos par wahi cover laga ke bhej dega!\n\n"
        "✅ Caption same rahega\n"
        "✅ 0.04 sec per video\n"
        "✅ Same format (1,2,3,4...)\n\n"
        "🚀 **Shuru karo - Videos bhejo!**"
    )

async def handle_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle multiple videos - add to queue"""
    user_id = update.effective_user.id
    
    # Initialize storage
    if user_id not in pending_videos:
        pending_videos[user_id] = []
        context.user_data['collecting'] = True
    
    # Handle media group (multiple videos at once)
    if update.message.media_group_id:
        # First video of group
        if context.user_data.get('current_group') != update.message.media_group_id:
            context.user_data['current_group'] = update.message.media_group_id
            context.user_data['group_count'] = 0
            context.user_data['group_videos'] = []
        
        if update.message.video:
            video = update.message.video
            video_data = {
                'index': len(pending_videos[user_id]) + 1,
                'video_file_id': video.file_id,
                'caption': update.message.caption if update.message.caption else "",
                'caption_entities': update.message.caption_entities if update.message.caption_entities else [],
                'width': video.width,
                'height': video.height,
                'duration': video.duration,
                'supports_streaming': getattr(video, 'supports_streaming', True),
                'has_spoiler': getattr(video, 'has_media_spoiler', False)
            }
            pending_videos[user_id].append(video_data)
            context.user_data['group_count'] += 1
            context.user_data['group_videos'].append(video_data['index'])
        
        # Don't reply for every video, wait for last
        return COLLECTING_VIDEOS
    
    # Single video
    if update.message.video:
        video = update.message.video
        video_data = {
            'index': len(pending_videos[user_id]) + 1,
            'video_file_id': video.file_id,
            'caption': update.message.caption if update.message.caption else "",
            'caption_entities': update.message.caption_entities if update.message.caption_entities else [],
            'width': video.width,
            'height': video.height,
            'duration': video.duration,
            'supports_streaming': getattr(video, 'supports_streaming', True),
            'has_spoiler': getattr(video, 'has_media_spoiler', False)
        }
        pending_videos[user_id].append(video_data)
        
        total = len(pending_videos[user_id])
        
        # Check if this was part of a group
        if context.user_data.get('group_count', 0) > 1:
            count = context.user_data['group_count']
            await update.message.reply_text(
                f"✅ **{count} videos added!**\n"
                f"📊 Total in queue: {total}\n\n"
                f"🎬 Aur videos bhejo ya\n"
                f"📸 **Ek cover bhejo sab par lagane ke liye!**"
            )
            context.user_data['group_count'] = 0
            context.user_data.pop('current_group', None)
        else:
            await update.message.reply_text(
                f"✅ Video #{total} added! Total: {total}\n\n"
                f"🎬 Aur videos bhejo ya\n"
                f"📸 **Cover bhejo to process!**"
            )
        
        return COLLECTING_VIDEOS
    
    return COLLECTING_VIDEOS

async def handle_single_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle one cover for all videos"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("❌ Pehle videos bhejo! /start")
        return COLLECTING_VIDEOS
    
    if not update.message.photo:
        await update.message.reply_text("❌ Photo bhejo cover ke liye!")
        return WAITING_FOR_COVER
    
    # Get highest quality cover
    cover_file_id = update.message.photo[-1].file_id
    user_cover[user_id] = cover_file_id
    
    videos = pending_videos[user_id]
    total = len(videos)
    
    await update.message.reply_text(
        f"🎬 **{total} videos mil gayi!**\n"
        f"📸 Cover mil gaya!\n"
        f"⚡ Processing shuru... {total * 0.04:.1f} seconds lagega"
    )
    
    # Process all videos with same cover
    return await process_all_videos_with_one_cover(update, context, user_id, cover_file_id)

async def process_all_videos_with_one_cover(update, context, user_id, cover_file_id):
    """Process all videos with the single cover"""
    videos = pending_videos[user_id]
    total = len(videos)
    
    # Prepare media groups (max 10 per group)
    media_groups = []
    current_group = []
    
    for video_data in videos:
        media = InputMediaVideo(
            media=video_data['video_file_id'],
            caption=video_data['caption'] if video_data['caption'] else None,
            caption_entities=video_data['caption_entities'] if video_data['caption_entities'] else None,
            parse_mode=None,
            width=video_data['width'],
            height=video_data['height'],
            duration=video_data['duration'],
            supports_streaming=video_data['supports_streaming'],
            cover=cover_file_id,  # SAME COVER FOR ALL
            thumbnail=cover_file_id,
            has_spoiler=video_data['has_spoiler']
        )
        current_group.append(media)
        
        if len(current_group) == 10:
            media_groups.append(current_group)
            current_group = []
    
    if current_group:
        media_groups.append(current_group)
    
    # Send processing message
    processing_msg = await update.message.reply_text(f"⚡ 0/{total} videos processed...")
    
    # Send all groups
    sent_count = 0
    try:
        for i, group in enumerate(media_groups):
            await context.bot.send_media_group(
                chat_id=update.effective_chat.id,
                media=group
            )
            sent_count += len(group)
            
            # Update progress every 2 groups
            if i % 2 == 0 or sent_count == total:
                await processing_msg.edit_text(f"⚡ {sent_count}/{total} videos sent...")
            
            # Rate limit protection
            if i < len(media_groups) - 1:
                await asyncio.sleep(0.5)
        
        await processing_msg.delete()
        
        # Success message
        await update.message.reply_text(
            f"✅ **{sent_count} videos ready!**\n"
            f"🎬 Sab par same cover lag gaya\n"
            f"📝 Captions same hain\n"
            f"⚡ Total time: ~{total * 0.04:.1f} sec\n\n"
            f"🔄 /start for new batch"
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit_text(f"❌ Error: {str(e)}")
    
    # Cleanup
    del pending_videos[user_id]
    if user_id in user_cover:
        del user_cover[user_id]
    context.user_data.clear()
    
    return ConversationHandler.END

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish collecting, ask for cover"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("❌ Koi videos nahi hain!")
        return ConversationHandler.END
    
    total = len(pending_videos[user_id])
    await update.message.reply_text(
        f"🎬 **{total} videos queue mein hain!**\n\n"
        f"📸 **Ab ek cover bhejo**\n"
        f"Ye cover sab videos par lagega!"
    )
    
    return WAITING_FOR_COVER

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show queue status"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("📭 Queue khali hai!")
        return
    
    total = len(pending_videos[user_id])
    await update.message.reply_text(
        f"📊 **Queue Status:**\n"
        f"🎬 Videos: {total}\n"
        f"⏳ Cover ka intezaar...\n\n"
        f"📸 Ek cover bhejo sab par lagane ke liye!"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel everything"""
    user_id = update.effective_user.id
    
    count = 0
    if user_id in pending_videos:
        count = len(pending_videos[user_id])
        del pending_videos[user_id]
    if user_id in user_cover:
        del user_cover[user_id]
    
    context.user_data.clear()
    
    if count > 0:
        await update.message.reply_text(f"❌ {count} videos clear kar diye!")
    else:
        await update.message.reply_text("❌ Cancelled!")

def main():
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.VIDEO, handle_videos)],
        states={
            COLLECTING_VIDEOS: [
                MessageHandler(filters.VIDEO, handle_videos),
                MessageHandler(filters.PHOTO, handle_single_cover),  # Can send cover anytime
                CommandHandler('done', done_command),
            ],
            WAITING_FOR_COVER: [
                MessageHandler(filters.PHOTO, handle_single_cover),
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(conv_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
