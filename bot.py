"""
Anime Bot - Telegram Bot for Streaming Anime
Scrapes from aniwaves.ru
@KENSHIN_ANIME
"""
import os
import asyncio
import tempfile
import logging
from typing import Dict, Any, Optional

from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, InputMediaPhoto
)
from pyrogram.enums import ParseMode

from config import (
    BOT_TOKEN, API_ID, API_HASH, ADMIN_ID,
    START_MSG, HELP_MSG, CAPTION_MSG, CAPTION_SET_MSG, CAPTION_DEL_MSG,
    THUMB_SET_MSG, THUMB_DEL_MSG, NO_THUMB_MSG,
    SEARCHING_MSG, NOT_FOUND_MSG, ERROR_MSG,
    SELECT_TYPE_MSG, SELECT_QUALITY_MSG,
    QUALITIES, BOT_NAME
)
from scraper import scraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

user_data: Dict[int, Dict[str, Any]] = {}
user_captions: Dict[int, str] = {}
user_thumbnails: Dict[int, str] = {}

app = Client(
    "anime_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.HTML
)


def get_user_data(user_id: int) -> Dict[str, Any]:
    if user_id not in user_data:
        user_data[user_id] = {}
    return user_data[user_id]


def clear_user_data(user_id: int):
    if user_id in user_data:
        del user_data[user_id]


def get_caption(user_id: int, title: str, episode: str, quality: str, vtype: str) -> str:
    if user_id in user_captions:
        template = user_captions[user_id]
        return template.format(title=title, episode=episode, quality=quality, type=vtype)
    return f"📺 <b>{title}</b>\n🎬 Episode {episode}\n🎥 {quality} | {vtype}"


def get_thumbnail(user_id: int) -> Optional[str]:
    return user_thumbnails.get(user_id)


@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text(
        START_MSG.format(bot_name=BOT_NAME),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔍 Search Anime", switch_inline_query_current_chat="")
        ]])
    )


@app.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    admin_mention = f"@{ADMIN_ID}" if ADMIN_ID else "Admin"
    await message.reply_text(HELP_MSG.format(bot_name=BOT_NAME, admin=admin_mention))


@app.on_message(filters.command("caption"))
async def caption_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    current = user_captions.get(user_id, "Default caption")
    await message.reply_text(CAPTION_MSG.format(current=current))


@app.on_message(filters.command("delcaption"))
async def delcaption_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_captions:
        del user_captions[user_id]
    await message.reply_text(CAPTION_DEL_MSG)


@app.on_message(filters.command("thumb"))
async def thumb_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    thumb_path = get_thumbnail(user_id)
    
    if thumb_path and os.path.exists(thumb_path):
        await message.reply_photo(thumb_path, caption="🖼️ Your current thumbnail")
    else:
        await message.reply_text(NO_THUMB_MSG)


@app.on_message(filters.command("delthumb"))
async def delthumb_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    thumb_path = get_thumbnail(user_id)
    
    if thumb_path and os.path.exists(thumb_path):
        os.remove(thumb_path)
    
    if user_id in user_thumbnails:
        del user_thumbnails[user_id]
    
    await message.reply_text(THUMB_DEL_MSG)


@app.on_message(filters.private & filters.text & ~filters.command([
    "start", "help", "caption", "delcaption", "thumb", "delthumb"
]))
async def handle_text(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    if "{title}" in text or "{episode}" in text or "{quality}" in text or "{type}" in text:
        user_captions[user_id] = text
        await message.reply_text(CAPTION_SET_MSG)
        return
    
    await search_anime(client, message)


@app.on_message(filters.private & filters.photo)
async def handle_photo(client: Client, message: Message):
    user_id = message.from_user.id
    
    try:
        thumb_dir = "/tmp/thumbnails"
        os.makedirs(thumb_dir, exist_ok=True)
        
        thumb_path = f"{thumb_dir}/{user_id}_thumb.jpg"
        
        if user_id in user_thumbnails and os.path.exists(user_thumbnails[user_id]):
            os.remove(user_thumbnails[user_id])
        
        await message.download(thumb_path)
        user_thumbnails[user_id] = thumb_path
        
        await message.reply_text(THUMB_SET_MSG)
        
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        await message.reply_text("❌ Failed to set thumbnail.")


async def search_anime(client: Client, message: Message):
    user_id = message.from_user.id
    query = message.text.strip()
    
    if len(query) < 2:
        await message.reply_text("❌ Please enter at least 2 characters to search.")
        return
    
    searching_msg = await message.reply_text(SEARCHING_MSG)
    
    try:
        results = scraper.search_anime(query)
        
        if not results:
            await searching_msg.edit_text(NOT_FOUND_MSG)
            return
        
        data = get_user_data(user_id)
        data['search_results'] = results
        
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
        
        await searching_msg.edit_text(
            f"🎯 <b>Search Results for:</b> <code>{query}</code>\n\nSelect an anime:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await searching_msg.edit_text(ERROR_MSG)


@app.on_callback_query()
async def handle_callback(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    
    try:
        if data == "cancel":
            clear_user_data(user_id)
            await callback.message.edit_text("❌ Search cancelled. Send me another anime name!")
            return
        
        if data.startswith("anime_"):
            await handle_anime_selection(client, callback, data)
        
        elif data.startswith("type_"):
            await handle_type_selection(client, callback, data)
        
        elif data.startswith("ep_"):
            await handle_episode_selection(client, callback, data)
        
        elif data.startswith("quality_"):
            await handle_quality_selection(client, callback, data)
        
        elif data == "all_episodes":
            await handle_all_episodes(client, callback)
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await callback.answer("❌ Error occurred!", show_alert=True)


async def handle_anime_selection(client: Client, callback: CallbackQuery, data: str):
    user_id = callback.from_user.id
    
    try:
        index = int(data.split("_")[1])
        user_data_dict = get_user_data(user_id)
        anime = user_data_dict['search_results'][index]
        
        await callback.message.edit_text("📋 Getting anime details...")
        
        details = scraper.get_anime_details(anime['url'])
        
        if not details or not details.get('episodes'):
            await callback.message.edit_text("❌ Could not fetch episodes. Please try again.")
            return
        
        user_data_dict['anime'] = details
        user_data_dict['anime_url'] = anime['url']
        
        keyboard = []
        
        if details.get('has_sub', True):
            keyboard.append([InlineKeyboardButton("🌐 SUBBED", callback_data="type_sub")])
        
        if details.get('has_dub', False):
            keyboard.append([InlineKeyboardButton("🔊 DUBBED", callback_data="type_dub")])
        
        if not keyboard:
            keyboard.append([InlineKeyboardButton("🌐 SUBBED", callback_data="type_sub")])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        await callback.message.edit_text(
            SELECT_TYPE_MSG.format(title=details['title']),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Anime selection error: {e}")
        await callback.message.edit_text(ERROR_MSG)


async def handle_type_selection(client: Client, callback: CallbackQuery, data: str):
    user_id = callback.from_user.id
    
    try:
        version = data.split("_")[1]
        user_data_dict = get_user_data(user_id)
        
        user_data_dict['version'] = version
        anime = user_data_dict['anime']
        episodes = anime['episodes']
        total_eps = len(episodes)
        
        keyboard = [
            [InlineKeyboardButton("📥 ALL EPISODES", callback_data="all_episodes")]
        ]
        
        ep_buttons = []
        for ep in episodes[:10]:
            ep_num = ep['number']
            ep_buttons.append(InlineKeyboardButton(
                str(ep_num),
                callback_data=f"ep_{ep_num}"
            ))
        
        for i in range(0, len(ep_buttons), 5):
            keyboard.append(ep_buttons[i:i+5])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        version_text = "SUBBED" if version == "sub" else "DUBBED"
        
        await callback.message.edit_text(
            f"📺 <b>{anime['title']}</b> ({version_text})\n"
            f"📊 Total Episodes: {total_eps}\n\n"
            f"Select an episode or choose 'ALL EPISODES':",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Type selection error: {e}")
        await callback.message.edit_text(ERROR_MSG)


async def handle_episode_selection(client: Client, callback: CallbackQuery, data: str):
    user_id = callback.from_user.id
    
    try:
        ep_num = data.split("_")[1]
        user_data_dict = get_user_data(user_id)
        
        user_data_dict['selected_episodes'] = [int(ep_num)]
        
        await show_quality_options(client, callback)
        
    except Exception as e:
        logger.error(f"Episode selection error: {e}")
        await callback.message.edit_text(ERROR_MSG)


async def handle_all_episodes(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        user_data_dict = get_user_data(user_id)
        anime = user_data_dict['anime']
        episodes = anime['episodes']
        
        user_data_dict['selected_episodes'] = [ep['number'] for ep in episodes]
        
        await show_quality_options(client, callback)
        
    except Exception as e:
        logger.error(f"All episodes error: {e}")
        await callback.message.edit_text(ERROR_MSG)


async def show_quality_options(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    
    user_data_dict = get_user_data(user_id)
    episodes = user_data_dict.get('selected_episodes', [1])
    
    keyboard = []
    quality_buttons = []
    
    for quality in QUALITIES:
        quality_buttons.append(InlineKeyboardButton(
            quality,
            callback_data=f"quality_{quality}"
        ))
    
    for i in range(0, len(quality_buttons), 3):
        keyboard.append(quality_buttons[i:i+3])
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    ep_text = f"Episode {episodes[0]}" if len(episodes) == 1 else f"{len(episodes)} Episodes"
    
    await callback.message.edit_text(
        SELECT_QUALITY_MSG.format(
            title=user_data_dict['anime']['title'],
            episode=ep_text
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_quality_selection(client: Client, callback: CallbackQuery, data: str):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    try:
        quality = data.split("_")[1]
        user_data_dict = get_user_data(user_id)
        
        user_data_dict['quality'] = quality
        anime = user_data_dict['anime']
        episodes = user_data_dict['selected_episodes']
        version = user_data_dict.get('version', 'sub')
        
        await callback.message.edit_text(
            f"⬇️ Starting download...\n"
            f"📺 <b>{anime['title']}</b>\n"
            f"🎬 Episodes: {len(episodes)}\n"
            f"🎥 Quality: {quality}\n"
            f"🌐 Version: {version.upper()}"
        )
        
        for i, ep_num in enumerate(episodes, 1):
            await process_episode(
                client, chat_id, user_id, ep_num,
                f"📥 Downloading: {i}/{len(episodes)}"
            )
        
        await client.send_message(
            chat_id,
            f"✅ <b>Completed!</b>\n\n"
            f"📺 <b>{anime['title']}</b>\n"
            f"🎬 Episodes sent: {len(episodes)}\n\n"
            f"Send me another anime name to search!"
        )
        
        clear_user_data(user_id)
        
    except Exception as e:
        logger.error(f"Quality selection error: {e}")
        await callback.message.edit_text(ERROR_MSG)


async def process_episode(client: Client, chat_id: int, user_id: int, ep_num: int, progress_text: str):
    user_data_dict = get_user_data(user_id)
    anime = user_data_dict['anime']
    quality = user_data_dict['quality']
    version = user_data_dict.get('version', 'sub')
    
    try:
        episode = None
        for ep in anime['episodes']:
            if ep['number'] == ep_num:
                episode = ep
                break
        
        if not episode:
            await client.send_message(
                chat_id,
                f"❌ Episode {ep_num} not found."
            )
            return
        
        progress_msg = await client.send_message(
            chat_id,
            f"{progress_text}\n⬇️ Episode {ep_num} - Getting video links..."
        )
        
        ep_url = episode.get('url', '')
        ep_id = episode.get('id')
        
        sources = scraper.get_video_sources(ep_url, ep_id, version)
        
        if not sources:
            await progress_msg.edit_text(f"❌ Episode {ep_num}: No video sources found.")
            return
        
        video_url = None
        selected_quality = quality
        
        if quality in sources:
            video_url = sources[quality]
        else:
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
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        success = scraper.download_video(video_url, tmp_path)
        
        if not success or not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1000:
            await progress_msg.edit_text(f"❌ Episode {ep_num}: Download failed.")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return
        
        await progress_msg.edit_text(f"{progress_text}\n📤 Episode {ep_num} - Sending...")
        
        version_text = "SUB" if version == "sub" else "DUB"
        caption = get_caption(user_id, anime['title'], str(ep_num), selected_quality, version_text)
        thumb_path = get_thumbnail(user_id)
        
        await client.send_video(
            chat_id=chat_id,
            video=tmp_path,
            caption=caption,
            thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            supports_streaming=True
        )
        
        os.remove(tmp_path)
        await progress_msg.delete()
        
        await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"Process episode error: {e}")
        await client.send_message(
            chat_id,
            f"❌ Error processing Episode {ep_num}."
        )


if __name__ == "__main__":
    logger.info("Starting Anime Bot...")
    app.run()
