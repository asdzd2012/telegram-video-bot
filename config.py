import os

# Bot Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')

# Telegram limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max for Telegram bots

# Temp directory for downloads
TEMP_DIR = "downloads"

# Supported platforms
SUPPORTED_PLATFORMS = ["youtube", "tiktok", "instagram"]
