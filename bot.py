import os
import logging
import asyncio
from telegram import Update, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

COLLECTING_VIDEOS = 1
WAITING_FOR_COVER = 2

pending_videos = {}
user_cover = {}

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **Video Cover Bot V6 - Individual Videos**\n\n"
        "**Kaam ka tareeka:**\n"
        "1️⃣ Multiple videos ek saath bhejo\n"
        "2️⃣ Bot queue mein save karega\n"
        "3️⃣ Ek cover bhejo\n"
        "4️⃣ Bot **alag alag videos** bhejega\n"
        "   Har video ki **original caption** ke saath!\n\n"
        "✅ Group mein nahi, alag alag videos\n"
        "✅ Caption same rahegi\n"
        "✅ Same cover sab par\n\n"
        "🚀 **Videos bhejo shuru karo!**"
    )

async def handle_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle multiple videos - add to queue"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos:
        pending_videos[user_id] = []
        context.user_data['collecting'] = True
    
    # Handle media group (multiple videos at once)
    if update.message.media_group_id:
        if context.user_data.get('current_group') != update.message.media_group_id:
            context.user_data['current_group'] = update.message.media_group_id
            context.user_data['group_count'] = 0
        
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
        
        # Check if part of group
        if context.user_data.get('group_count', 0) > 1:
            count = context.user_data['group_count']
            await update.message.reply_text(
                f"✅ **{count} videos added!**\n"
                f"📊 Total: {total}\n\n"
                f"🎬 Aur videos bhejo ya\n"
                f"📸 **Ek cover bhejo to start processing!**"
            )
            context.user_data['group_count'] = 0
            context.user_data.pop('current_group', None)
        else:
            await update.message.reply_text(
                f"✅ Video #{total} added! Total: {total}\n\n"
                f"🎬 Aur videos bhejo ya\n"
                f"📸 **Cover bhejo!**"
            )
        
        return COLLECTING_VIDEOS
    
    return COLLECTING_VIDEOS

async def handle_cover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cover and send videos individually"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("❌ Pehle videos bhejo! /start")
        return COLLECTING_VIDEOS
    
    if not update.message.photo:
        await update.message.reply_text("❌ Photo bhejo cover ke liye!")
        return WAITING_FOR_COVER
    
    cover_file_id = update.message.photo[-1].file_id
    videos = pending_videos[user_id]
    total = len(videos)
    
    await update.message.reply_text(
        f"🎬 **{total} videos queue mein!**\n"
        f"📸 Cover mil gaya!\n"
        f"⚡ Ab alag alag videos bhej raha hu...\n"
        f"⏱️ ~{total * 0.04:.1f} seconds"
    )
    
    # Send videos one by one (INDIVIDUALLY - NOT IN GROUP)
    sent = 0
    for video_data in videos:
        try:
            # Send individual video with cover
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_data['video_file_id'],
                caption=video_data['caption'] if video_data['caption'] else None,
                caption_entities=video_data['caption_entities'] if video_data['caption_entities'] else None,
                parse_mode=None,  # Don't parse, use entities
                duration=video_data['duration'],
                width=video_data['width'],
                height=video_data['height'],
                thumbnail=cover_file_id,
                cover=cover_file_id,  # SAME COVER FOR ALL
                supports_streaming=video_data['supports_streaming'],
                has_spoiler=video_data['has_spoiler']
            )
            sent += 1
            
            # Small delay to avoid flood limits
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error sending video {video_data['index']}: {e}")
            await update.message.reply_text(f"❌ Video #{video_data['index']} failed: {str(e)}")
    
    # Cleanup
    del pending_videos[user_id]
    context.user_data.clear()
    
    # Success message
    await update.message.reply_text(
        f"✅ **{sent}/{total} videos sent!**\n"
        f"🎬 Sab par same cover lag gaya\n"
        f"📝 Har video ki original caption same hai\n"
        f"⚡ Alag alag format mein bhej diya!\n\n"
        f"🔄 /start for new batch"
    )
    
    return ConversationHandler.END

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish collecting"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("❌ Koi videos nahi!")
        return ConversationHandler.END
    
    total = len(pending_videos[user_id])
    await update.message.reply_text(
        f"🎬 **{total} videos ready!**\n\n"
        f"📸 **Ab ek cover bhejo**\n"
        f"Bot alag alag videos bhejega!"
    )
    
    return WAITING_FOR_COVER

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel"""
    user_id = update.effective_user.id
    
    count = 0
    if user_id in pending_videos:
        count = len(pending_videos[user_id])
        del pending_videos[user_id]
    
    context.user_data.clear()
    await update.message.reply_text(f"❌ {count} videos cancelled!")

def main():
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.VIDEO, handle_videos)],
        states={
            COLLECTING_VIDEOS: [
                MessageHandler(filters.VIDEO, handle_videos),
                MessageHandler(filters.PHOTO, handle_cover),
                CommandHandler('done', done_command),
            ],
            WAITING_FOR_COVER: [
                MessageHandler(filters.PHOTO, handle_cover),
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(conv_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
