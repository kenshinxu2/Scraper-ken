"""Configuration file for Anime Bot"""
import os

# Telegram Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")
API_ID = int(os.getenv("API_ID", "your_api_id_here"))
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
ADMIN_ID = int(os.getenv("ADMIN_ID", "your_admin_id_here"))

# Bot Settings
BOT_NAME = "@KENSHIN_ANIME"
BASE_URL = "https://aniwaves.ru"

# Quality Options
QUALITIES = ["360p", "480p", "720p", "1080p", "2160p"]

# Messages
START_MSG = """
👋 **Welcome to {bot_name}!**

I'm your anime streaming companion! 🎌

**How to use:**
Just send me any anime name like:
• `jjk season 3`
• `demon slayer`
• `attack on titan`
• `one piece episode 1000`

I'll find it for you and let you choose:
✅ Sub or Dub
✅ Episode selection
✅ Video quality (360p to 4K)

**Commands:**
/start - Start the bot
/help - Show help message

Enjoy watching! 🍿
"""

HELP_MSG = """
📖 **Help - {bot_name}**

**Available Commands:**
/start - Start the bot
/help - Show this help message

**How to search:**
Simply type any anime name:
• `jjk season 2`
• `naruto shippuden`
• `demon slayer season 3`
• `attack on titan final season`

**Features:**
🔍 Search any anime
🌐 Choose Subbed or Dubbed
📺 Select specific episodes or all
🎥 Choose video quality (360p - 4K)
📩 Direct video delivery

**Need help?** Contact: {admin}
"""

SEARCHING_MSG = "🔍 Searching for your anime..."
NOT_FOUND_MSG = "❌ Sorry, I couldn't find that anime. Please try a different name."
ERROR_MSG = "❌ An error occurred. Please try again later."
SELECT_TYPE_MSG = "🎌 **{title}**\n\nPlease select your preferred version:"
SELECT_EPISODE_MSG = "📺 **{title}** ({type})\n\nTotal Episodes: {total}\n\nSend episode number (1-{total}) or type 'all' for all episodes:"
SELECT_QUALITY_MSG = "🎥 **{title}** - Episode {episode}\n\nSelect video quality:"
DOWNLOADING_MSG = "⬇️ Downloading Episode {episode} in {quality}..."
SENDING_MSG = "📤 Sending your video..."
COMPLETED_MSG = "✅ **All episodes sent successfully!**"
