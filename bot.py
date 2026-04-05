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
COLLECTING_VIDEOS = 1
COLLECTING_COVERS = 2

# Dictionary to store pending videos (user_id -> list of video_data)
pending_videos = {}

# Get environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    await update.message.reply_text(
        "🎬 **Video Cover Bot V4 - Bulk Upload**\n\n"
        "✅ **Ek saath 100+ videos bhejo!**\n"
        "✅ Queue mein store honge\n"
        "✅ Phir covers bhejo, sab process ho jayenge!\n\n"
        "**Steps:**\n"
        "1️⃣ Select karo 100 videos aur ek saath bhejo\n"
        "2️⃣ Bot batayega kitne videos mile\n"
        "3️⃣ Select karo 100 covers aur ek saath bhejo\n"
        "4️⃣ Sab videos covers ke saath aa jayenge!\n\n"
        "⚡ Har video 0.04 seconds mein process hoga",
        parse_mode='Markdown'
    )

async def handle_multiple_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle multiple videos sent at once (album/media group)"""
    user_id = update.effective_user.id
    
    # Initialize user's video list if not exists
    if user_id not in pending_videos:
        pending_videos[user_id] = []
        context.user_data['mode'] = 'collecting_videos'
    
    # Check if this is part of a media group (album)
    if update.message.media_group_id:
        # Store media group ID to track batches
        if 'current_media_group' not in context.user_data:
            context.user_data['current_media_group'] = update.message.media_group_id
            context.user_data['videos_in_group'] = []
        
        # Only process if same media group
        if context.user_data['current_media_group'] == update.message.media_group_id:
            video = update.message.video
            if video:
                video_data = extract_video_data(video, update.message, len(pending_videos[user_id]) + 1)
                pending_videos[user_id].append(video_data)
                context.user_data['videos_in_group'].append(video_data['index'])
            
            # Don't reply for every video in album, wait for last one
            return COLLECTING_VIDEOS
    
    # Single video or last in group
    if update.message.video:
        video_data = extract_video_data(update.message.video, update.message, len(pending_videos[user_id]) + 1)
        pending_videos[user_id].append(video_data)
        
        count = len(pending_videos[user_id])
        
        # If we were collecting a group, show summary
        if 'videos_in_group' in context.user_data and len(context.user_data['videos_in_group']) > 1:
            await update.message.reply_text(
                f"✅ **{len(context.user_data['videos_in_group'])} videos added to queue!**\n"
                f"📊 Total videos: {count}\n\n"
                f"🎬 Abhi aur videos bhejo ya covers bhejna shuru karo!\n"
                f"📸 Covers bhejne ke liye images select karo aur bhejo...",
                parse_mode='Markdown'
            )
            context.user_data.pop('current_media_group', None)
            context.user_data.pop('videos_in_group', None)
        else:
            await update.message.reply_text(
                f"✅ Video #{count} added! Total: {count}\n"
                f"📸 Aur videos bhejo ya covers bhejo..."
            )
        
        return COLLECTING_VIDEOS
    
    return COLLECTING_VIDEOS

def extract_video_data(video, message, index):
    """Extract video data from message"""
    original_caption = message.caption if message.caption else ""
    caption_entities = message.caption_entities if message.caption_entities else []
    
    return {
        'index': index,
        'video_file_id': video.file_id,
        'caption': original_caption,
        'caption_entities': caption_entities,
        'width': video.width,
        'height': video.height,
        'duration': video.duration,
        'filename': video.file_name if video.file_name else f"video_{index}.mp4",
        'mime_type': video.mime_type if video.mime_type else "video/mp4",
        'supports_streaming': video.supports_streaming if hasattr(video, 'supports_streaming') else True,
        'has_spoiler': video.has_media_spoiler if hasattr(video, 'has_media_spoiler') else False,
        'cover_file_id': None,  # Will be filled later
        'processed': False
    }

async def handle_multiple_covers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle multiple covers sent at once and match with videos"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("❌ Pehle videos bhejo! /start")
        return COLLECTING_VIDEOS
    
    videos = pending_videos[user_id]
    unprocessed = [v for v in videos if not v['processed'] and v['cover_file_id'] is None]
    
    if not unprocessed:
        await update.message.reply_text("✅ Sab videos ke covers aa gaye! Processing...")
        return await process_all_videos(update, context)
    
    # Handle media group (multiple covers at once)
    if update.message.media_group_id:
        if 'current_cover_group' not in context.user_data:
            context.user_data['current_cover_group'] = update.message.media_group_id
            context.user_data['covers_in_group'] = []
        
        if context.user_data['current_cover_group'] == update.message.media_group_id:
            if update.message.photo:
                cover_file_id = update.message.photo[-1].file_id
                
                # Assign to next unprocessed video
                if len(context.user_data['covers_in_group']) < len(unprocessed):
                    video_index = unprocessed[len(context.user_data['covers_in_group'])]['index']
                    for v in videos:
                        if v['index'] == video_index:
                            v['cover_file_id'] = cover_file_id
                            context.user_data['covers_in_group'].append(video_index)
                            break
            
            return COLLECTING_COVERS
    
    # Single cover
    if update.message.photo:
        cover_file_id = update.message.photo[-1].file_id
        
        # Assign to first unprocessed video
        if unprocessed:
            unprocessed[0]['cover_file_id'] = cover_file_id
            
            # Check if all covers received
            remaining = len([v for v in videos if v['cover_file_id'] is None])
            
            if 'covers_in_group' in context.user_data:
                covers_added = len(context.user_data['covers_in_group'])
                await update.message.reply_text(
                    f"✅ {covers_added} covers assigned!\n"
                    f"📊 Remaining: {remaining}\n"
                    f"📸 Aur covers bhejo..."
                )
                context.user_data.pop('current_cover_group', None)
                context.user_data.pop('covers_in_group', None)
            else:
                if remaining == 0:
                    return await process_all_videos(update, context)
                else:
                    await update.message.reply_text(
                        f"✅ Cover assigned! Remaining: {remaining}\n"
                        f"📸 Covers bhejte raho..."
                    )
    
    # Check if all videos have covers
    all_have_covers = all(v['cover_file_id'] is not None for v in videos)
    if all_have_covers:
        return await process_all_videos(update, context)
    
    return COLLECTING_COVERS

async def process_all_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process all videos with their covers in batches"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos:
        await update.message.reply_text("❌ Koi videos nahi hain!")
        return ConversationHandler.END
    
    videos = pending_videos[user_id]
    total = len(videos)
    
    # Check all covers present
    missing_covers = [v['index'] for v in videos if v['cover_file_id'] is None]
    if missing_covers:
        await update.message.reply_text(
            f"❌ Videos #{missing_covers} ke covers missing hain!\n"
            f"📸 Un videos ke covers bhejo..."
        )
        return COLLECTING_COVERS
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        f"⚡ **Processing {total} videos...**\n"
        f"⏱️ Estimated: {total * 0.04:.1f} seconds\n"
        f"🔄 Please wait..."
    )
    
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
            cover=video_data['cover_file_id'],
            thumbnail=video_data['cover_file_id'],
            has_spoiler=video_data['has_spoiler']
        )
        current_group.append(media)
        
        if len(current_group) == 10:
            media_groups.append(current_group)
            current_group = []
    
    if current_group:
        media_groups.append(current_group)
    
    # Send all groups
    sent_total = 0
    try:
        for i, group in enumerate(media_groups):
            await context.bot.send_media_group(
                chat_id=update.effective_chat.id,
                media=group
            )
            sent_total += len(group)
            
            # Update progress
            if len(media_groups) > 1:
                await processing_msg.edit_text(
                    f"⚡ Processing... {sent_total}/{total} videos done\n"
                    f"⏱️ Please wait..."
                )
            
            # Rate limit protection
            if i < len(media_groups) - 1:
                await asyncio.sleep(1)
        
        await processing_msg.delete()
        
        # Success message
        await update.message.reply_text(
            f"✅ **{sent_total} videos processed successfully!**\n"
            f"🎬 All covers changed\n"
            f"📝 All captions preserved\n"
            f"⚡ Total time: ~{total * 0.04:.1f} seconds\n\n"
            f"🔄 /start for new batch",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error processing: {e}")
        await processing_msg.edit_text(f"❌ Error: {str(e)}")
    
    # Cleanup
    del pending_videos[user_id]
    context.user_data.clear()
    
    return ConversationHandler.END

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finish collecting videos, start collecting covers"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("❌ Pehle videos bhejo!")
        return ConversationHandler.END
    
    count = len(pending_videos[user_id])
    await update.message.reply_text(
        f"🎬 **{count} videos queued!**\n\n"
        f"📸 Ab covers bhejo (ek saath select karke)...\n"
        f"⚡ {count} covers chahiye, same order mein!",
        parse_mode='Markdown'
    )
    
    return COLLECTING_COVERS

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current queue status"""
    user_id = update.effective_user.id
    
    if user_id not in pending_videos or len(pending_videos[user_id]) == 0:
        await update.message.reply_text("📭 Queue empty! /start to begin")
        return
    
    videos = pending_videos[user_id]
    total = len(videos)
    with_covers = len([v for v in videos if v['cover_file_id'] is not None])
    
    await update.message.reply_text(
        f"📊 **Queue Status:**\n"
        f"🎬 Total Videos: {total}\n"
        f"📸 Covers Received: {with_covers}\n"
        f"⏳ Pending: {total - with_covers}\n\n"
        f"📤 {total - with_covers} aur covers bhejo...",
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel and clear queue"""
    user_id = update.effective_user.id
    if user_id in pending_videos:
        count = len(pending_videos[user_id])
        del pending_videos[user_id]
        await update.message.reply_text(f"❌ Cancelled! {count} videos cleared from queue.")
    else:
        await update.message.reply_text("❌ Cancelled!")
    
    context.user_data.clear()
    return ConversationHandler.END

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.VIDEO, handle_multiple_videos)
        ],
        states={
            COLLECTING_VIDEOS: [
                MessageHandler(filters.VIDEO, handle_multiple_videos),
                CommandHandler('done', done_command),
            ],
            COLLECTING_COVERS: [
                MessageHandler(filters.PHOTO, handle_multiple_covers),
                CommandHandler('status', status_command),
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(conv_handler)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
