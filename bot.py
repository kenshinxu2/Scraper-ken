"""
Anime Bot - Telegram Bot for Streaming Anime
Scrapes from aniwaves.ru
@KENSHIN_ANIME
"""
import asyncio
import logging
import os
import tempfile
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from config import (
    BOT_TOKEN, API_ID, API_HASH, ADMIN_ID,
    START_MSG, HELP_MSG, SEARCHING_MSG, NOT_FOUND_MSG, ERROR_MSG,
    SELECT_TYPE_MSG, SELECT_EPISODE_MSG, SELECT_QUALITY_MSG,
    DOWNLOADING_MSG, SENDING_MSG, COMPLETED_MSG,
    QUALITIES, BOT_NAME
)
from scraper import scraper

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
SEARCHING, SELECTING_TYPE, SELECTING_EPISODE, SELECTING_QUALITY, DOWNLOADING = range(5)

# Store user data
user_data: Dict[int, Dict[str, Any]] = {}


def get_user_data(user_id: int) -> Dict[str, Any]:
    """Get or create user data"""
    if user_id not in user_data:
        user_data[user_id] = {}
    return user_data[user_id]


def clear_user_data(user_id: int):
    """Clear user data"""
    if user_id in user_data:
        del user_data[user_id]


# ============== COMMAND HANDLERS ==============

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    msg = START_MSG.format(bot_name=BOT_NAME)
    
    keyboard = [[InlineKeyboardButton("🔍 Search Anime", switch_inline_query_current_chat="")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        msg,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    msg = HELP_MSG.format(bot_name=BOT_NAME, admin=f"@{ADMIN_ID}" if ADMIN_ID else "Admin")
    await update.message.reply_text(msg, parse_mode='Markdown')


# ============== SEARCH HANDLERS ==============

async def search_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle anime search from user message"""
    user_id = update.effective_user.id
    query = update.message.text.strip()
    
    if not query or len(query) < 2:
        await update.message.reply_text("❌ Please enter at least 2 characters to search.")
        return
    
    # Send searching message
    searching_msg = await update.message.reply_text(SEARCHING_MSG)
    
    try:
        # Search for anime
        results = scraper.search_anime(query)
        
        if not results:
            await searching_msg.edit_text(NOT_FOUND_MSG)
            return
        
        # Store search results
        data = get_user_data(user_id)
        data['search_results'] = results
        
        # Show search results
        keyboard = []
        for i, anime in enumerate(results[:6], 1):
            title = anime['title'][:40] + "..." if len(anime['title']) > 40 else anime['title']
            sub_dub = []
            if anime.get('has_sub'):
                sub_dub.append('SUB')
            if anime.get('has_dub'):
                sub_dub.append('DUB')
            sub_dub_str = f" [{'/'.join(sub_dub)}]" if sub_dub else ""
            
            keyboard.append([InlineKeyboardButton(
                f"{i}. {title}{sub_dub_str}",
                callback_data=f"anime_{i-1}"
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await searching_msg.edit_text(
            f"🎯 **Search Results for:** `{query}`\n\nSelect an anime:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await searching_msg.edit_text(ERROR_MSG)


# ============== CALLBACK HANDLERS ==============

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "cancel":
        clear_user_data(user_id)
        await query.edit_message_text("❌ Search cancelled. Send me another anime name!")
        return
    
    # Handle anime selection
    if data.startswith("anime_"):
        await handle_anime_selection(update, context, data)
    
    # Handle type selection (sub/dub)
    elif data.startswith("type_"):
        await handle_type_selection(update, context, data)
    
    # Handle episode selection
    elif data.startswith("ep_"):
        await handle_episode_selection(update, context, data)
    
    # Handle quality selection
    elif data.startswith("quality_"):
        await handle_quality_selection(update, context, data)
    
    # Handle all episodes
    elif data == "all_episodes":
        await handle_all_episodes(update, context)


async def handle_anime_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle anime selection"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        index = int(data.split("_")[1])
        user_data_dict = get_user_data(user_id)
        anime = user_data_dict['search_results'][index]
        
        # Get anime details
        await query.edit_message_text("📋 Getting anime details...")
        
        details = scraper.get_anime_details(anime['url'])
        
        if not details or not details.get('episodes'):
            await query.edit_text("❌ Could not fetch episodes. Please try again.")
            return
        
        # Store anime details
        user_data_dict['anime'] = details
        user_data_dict['anime_url'] = anime['url']
        
        # Show sub/dub options
        keyboard = []
        
        if details.get('has_sub', True):
            keyboard.append([InlineKeyboardButton("🌐 SUBBED", callback_data="type_sub")])
        
        if details.get('has_dub', False):
            keyboard.append([InlineKeyboardButton("🔊 DUBBED", callback_data="type_dub")])
        
        if not keyboard:
            keyboard.append([InlineKeyboardButton("🌐 SUBBED", callback_data="type_sub")])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            SELECT_TYPE_MSG.format(title=details['title']),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Anime selection error: {e}")
        await query.edit_message_text(ERROR_MSG)


async def handle_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle sub/dub selection"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        version = data.split("_")[1]  # sub or dub
        user_data_dict = get_user_data(user_id)
        
        user_data_dict['version'] = version
        anime = user_data_dict['anime']
        episodes = anime['episodes']
        total_eps = len(episodes)
        
        # Show episode options
        keyboard = [
            [InlineKeyboardButton("📥 ALL EPISODES", callback_data="all_episodes")],
            [InlineKeyboardButton("📝 CUSTOM RANGE", callback_data="custom_range")]
        ]
        
        # Add quick episode buttons (first 10)
        ep_buttons = []
        for ep in episodes[:10]:
            ep_num = ep['number']
            ep_buttons.append(InlineKeyboardButton(
                str(ep_num),
                callback_data=f"ep_{ep_num}"
            ))
        
        # Group episode buttons in rows of 5
        for i in range(0, len(ep_buttons), 5):
            keyboard.append(ep_buttons[i:i+5])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        version_text = "SUBBED" if version == "sub" else "DUBBED"
        
        await query.edit_message_text(
            f"📺 **{anime['title']}** ({version_text})\n"
            f"📊 Total Episodes: {total_eps}\n\n"
            f"Select an episode or choose 'ALL EPISODES':",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Type selection error: {e}")
        await query.edit_message_text(ERROR_MSG)


async def handle_episode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle single episode selection"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        ep_num = data.split("_")[1]
        user_data_dict = get_user_data(user_id)
        
        user_data_dict['selected_episodes'] = [int(ep_num)]
        
        # Show quality options
        await show_quality_options(update, context)
        
    except Exception as e:
        logger.error(f"Episode selection error: {e}")
        await query.edit_message_text(ERROR_MSG)


async def handle_all_episodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all episodes selection"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    try:
        user_data_dict = get_user_data(user_id)
        anime = user_data_dict['anime']
        episodes = anime['episodes']
        
        # Store all episode numbers
        user_data_dict['selected_episodes'] = [ep['number'] for ep in episodes]
        
        # Show quality options
        await show_quality_options(update, context)
        
    except Exception as e:
        logger.error(f"All episodes error: {e}")
        await query.edit_message_text(ERROR_MSG)


async def show_quality_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quality selection options"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    user_data_dict = get_user_data(user_id)
    episodes = user_data_dict.get('selected_episodes', [1])
    
    keyboard = []
    quality_buttons = []
    
    for quality in QUALITIES:
        quality_buttons.append(InlineKeyboardButton(
            quality,
            callback_data=f"quality_{quality}"
        ))
    
    # Group in rows of 3
    for i in range(0, len(quality_buttons), 3):
        keyboard.append(quality_buttons[i:i+3])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    ep_text = f"Episode {episodes[0]}" if len(episodes) == 1 else f"{len(episodes)} Episodes"
    
    await query.edit_message_text(
        SELECT_QUALITY_MSG.format(
            title=user_data_dict['anime']['title'],
            episode=ep_text
        ),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_quality_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle quality selection and start download"""
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    try:
        quality = data.split("_")[1]
        user_data_dict = get_user_data(user_id)
        
        user_data_dict['quality'] = quality
        anime = user_data_dict['anime']
        episodes = user_data_dict['selected_episodes']
        version = user_data_dict.get('version', 'sub')
        
        await query.edit_message_text(
            f"⬇️ Starting download...\n"
            f"📺 **{anime['title']}**\n"
            f"🎬 Episodes: {len(episodes)}\n"
            f"🎥 Quality: {quality}\n"
            f"🌐 Version: {version.upper()}",
            parse_mode='Markdown'
        )
        
        # Process each episode
        for i, ep_num in enumerate(episodes, 1):
            await process_episode(
                context, chat_id, user_id, ep_num,
                f"📥 Downloading: {i}/{len(episodes)}"
            )
        
        # Send completion message
        await context.bot.send_message(
            chat_id,
            f"✅ **Completed!**\n\n"
            f"📺 **{anime['title']}**\n"
            f"🎬 Episodes sent: {len(episodes)}\n\n"
            f"Send me another anime name to search!",
            parse_mode='Markdown'
        )
        
        # Clear user data
        clear_user_data(user_id)
        
    except Exception as e:
        logger.error(f"Quality selection error: {e}")
        await query.edit_message_text(ERROR_MSG)


async def process_episode(context, chat_id, user_id, ep_num, progress_text):
    """Process a single episode download and send"""
    user_data_dict = get_user_data(user_id)
    anime = user_data_dict['anime']
    quality = user_data_dict['quality']
    version = user_data_dict.get('version', 'sub')
    
    try:
        # Find episode
        episode = None
        for ep in anime['episodes']:
            if ep['number'] == ep_num:
                episode = ep
                break
        
        if not episode:
            await context.bot.send_message(
                chat_id,
                f"❌ Episode {ep_num} not found."
            )
            return
        
        # Send progress
        progress_msg = await context.bot.send_message(
            chat_id,
            f"{progress_text}\n⬇️ Episode {ep_num} - Getting video links..."
        )
        
        # Get video sources
        ep_url = episode.get('url', '')
        ep_id = episode.get('id')
        
        sources = scraper.get_video_sources(ep_url, ep_id, version)
        
        if not sources:
            await progress_msg.edit_text(f"❌ Episode {ep_num}: No video sources found.")
            return
        
        # Find best quality
        video_url = None
        selected_quality = quality
        
        # Try requested quality first
        if quality in sources:
            video_url = sources[quality]
        else:
            # Find closest quality
            available_qualities = list(sources.keys())
            for q in ['720p', '1080p', '480p', '360p', '2160p']:
                if q in available_qualities:
                    video_url = sources[q]
                    selected_quality = q
                    break
        
        if not video_url:
            await progress_msg.edit_text(f"❌ Episode {ep_num}: Could not find suitable quality.")
            return
        
        await progress_msg.edit_text(
            f"{progress_text}\n📤 Episode {ep_num} - Downloading {selected_quality}..."
        )
        
        # Download video
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        success = scraper.download_video(video_url, tmp_path)
        
        if not success or not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1000:
            await progress_msg.edit_text(f"❌ Episode {ep_num}: Download failed.")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return
        
        await progress_msg.edit_text(f"{progress_text}\n📤 Episode {ep_num} - Sending...")
        
        # Send video
        version_text = "SUB" if version == "sub" else "DUB"
        caption = f"📺 **{anime['title']}**\n🎬 Episode {ep_num}\n🎥 {selected_quality} | {version_text}"
        
        with open(tmp_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=chat_id,
                video=video_file,
                caption=caption,
                parse_mode='Markdown',
                supports_streaming=True
            )
        
        # Cleanup
        os.remove(tmp_path)
        await progress_msg.delete()
        
        # Small delay between episodes
        await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"Process episode error: {e}")
        await context.bot.send_message(
            chat_id,
            f"❌ Error processing Episode {ep_num}."
        )


# ============== ERROR HANDLER ==============

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An unexpected error occurred. Please try again later."
        )


# ============== MAIN FUNCTION ==============

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Callback handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Message handler for anime search
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_anime))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Starting Anime Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
