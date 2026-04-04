"""Configuration file for Anime Bot"""
import os

# Telegram Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Bot Settings
BOT_NAME = "@KENSHIN_ANIME"
BASE_URL = "https://aniwaves.ru"

# Quality Options
QUALITIES = ["360p", "480p", "720p", "1080p", "2160p"]

# Messages - Using HTML instead of Markdown to avoid parsing errors
START_MSG = """<b>👋 Welcome to {bot_name}!</b>

I'm your anime streaming companion! 🎌

<b>How to use:</b>
Just send me any anime name like:
• jjk season 3
• demon slayer
• attack on titan
• one piece episode 1000

I'll find it for you and let you choose:
✅ Sub or Dub
✅ Episode selection
✅ Video quality (360p to 4K)

<b>Commands:</b>
/start - Start the bot
/help - Show help message
/caption - Set custom caption for videos
/thumb - View your current thumbnail
/delthumb - Delete your thumbnail

Enjoy watching! 🍿"""

HELP_MSG = """<b>📖 Help - {bot_name}</b>

<b>Available Commands:</b>
/start - Start the bot
/help - Show this help message
/caption - Set custom caption for videos
/thumb - View your current thumbnail
/delthumb - Delete your thumbnail

<b>How to search:</b>
Simply type any anime name:
• jjk season 2
• naruto shippuden
• demon slayer season 3
• attack on titan final season

<b>Features:</b>
🔍 Search any anime
🌐 Choose Subbed or Dubbed
📺 Select specific episodes or all
🎥 Choose video quality (360p - 4K)
📩 Direct video delivery
🏷️ Custom captions for videos
🖼️ Custom thumbnail support

<b>Need help?</b> Contact: {admin}"""

CAPTION_MSG = """<b>🏷️ Caption Settings</b>

Current caption: {current}

Send me your custom caption text.
Use these placeholders:
• {title} - Anime title
• {episode} - Episode number
• {quality} - Video quality
• {type} - SUB or DUB

Example:
<code>{title} - Ep {episode} [{quality}] {type}</code>

Send /delcaption to remove custom caption."""

CAPTION_SET_MSG = "✅ Caption set successfully!"
CAPTION_DEL_MSG = "✅ Caption removed! Using default caption."
THUMB_SET_MSG = "✅ Thumbnail set successfully!"
THUMB_DEL_MSG = "✅ Thumbnail removed!"
NO_THUMB_MSG = "❌ No thumbnail set. Send me an image to set as thumbnail."

SEARCHING_MSG = "🔍 Searching for your anime..."
NOT_FOUND_MSG = "❌ Sorry, I couldn't find that anime. Please try a different name."
ERROR_MSG = "❌ An error occurred. Please try again later."
SELECT_TYPE_MSG = "🎌 <b>{title}</b>\n\nPlease select your preferred version:"
SELECT_QUALITY_MSG = "🎥 <b>{title}</b> - {episode}\n\nSelect video quality:"
