import os
import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN
from downloader import detect_platform, download_video, cleanup_file, extract_url

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get port from environment (Koyeb sets this)
PORT = int(os.environ.get('PORT', 8000))

# Platform emojis
PLATFORM_EMOJI = {
    'youtube': '🔴 YouTube',
    'tiktok': '🎵 TikTok',
    'instagram': '📸 Instagram',
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_message = """
🎬 **مرحباً بك في بوت تحميل الفيديوهات!**

أرسل لي رابط فيديو من:
• 🔴 YouTube (فيديوهات عادية + Shorts)
• 🎵 TikTok
• 📸 Instagram (Reels & Posts)

وهحمله لك مع العنوان والوصف! 🚀

⚠️ **ملاحظة:** الحد الأقصى لحجم الفيديو 50MB
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
📖 **كيفية الاستخدام:**

1️⃣ انسخ رابط الفيديو
2️⃣ الصقه هنا وأرسله
3️⃣ استنى ثواني وهيوصلك الفيديو

**المنصات المدعومة:**
• YouTube: روابط youtube.com أو youtu.be
• TikTok: روابط tiktok.com
• Instagram: روابط instagram.com/reel أو /p/

**الأوامر:**
/start - رسالة الترحيب
/help - المساعدة
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages with URLs."""
    text = update.message.text
    
    # Extract URL from message
    url = extract_url(text)
    
    if not url:
        await update.message.reply_text("❌ مفيش رابط في الرسالة. ابعت رابط فيديو صحيح.")
        return
    
    # Detect platform
    platform = detect_platform(url)
    
    if not platform:
        await update.message.reply_text(
            "❌ الرابط ده مش مدعوم.\n"
            "المنصات المدعومة: YouTube, TikTok, Instagram"
        )
        return
    
    platform_name = PLATFORM_EMOJI.get(platform, platform)
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        f"⏳ جاري تحميل الفيديو من {platform_name}...\n"
        "ممكن ياخد شوية وقت حسب حجم الفيديو 🎬"
    )
    
    try:
        # Download video in executor to not block
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_video, url)
        
        if not result:
            await processing_msg.edit_text("❌ فشل تحميل الفيديو. جرب تاني.")
            return
        
        if 'error' in result:
            await processing_msg.edit_text(f"❌ {result['error']}")
            return
        
        # Prepare caption
        title = result.get('title', 'No Title')
        description = result.get('description', '')
        uploader = result.get('uploader', '')
        
        caption = f"🎬 **{title}**\n\n"
        if uploader:
            caption += f"👤 {uploader}\n\n"
        if description and description != 'No Description':
            # Truncate description to fit Telegram caption limit
            max_desc_len = 800 - len(caption)
            if len(description) > max_desc_len:
                description = description[:max_desc_len] + "..."
            caption += f"📝 {description}\n\n"
        caption += f"📥 تم التحميل بواسطة @YourBotName"
        
        # Update processing message
        await processing_msg.edit_text("📤 جاري إرسال الفيديو...")
        
        # Send video
        file_path = result.get('file_path')
        if file_path:
            with open(file_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=caption[:1024],  # Telegram caption limit
                    parse_mode='Markdown',
                    supports_streaming=True
                )
            
            # Cleanup
            cleanup_file(file_path)
        
        # Delete processing message
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await processing_msg.edit_text(
            "❌ حصل خطأ أثناء التحميل.\n"
            "تأكد إن الرابط صحيح وجرب تاني."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")


# Health check endpoint for Koyeb
async def health_check(request):
    return web.Response(text="OK")


async def main():
    """Start the bot with webhook."""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Initialize application
    await application.initialize()
    await application.start()
    
    # Set up aiohttp web server for health checks
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    # Create webhook handler
    async def telegram_webhook(request):
        """Handle incoming Telegram updates."""
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return web.Response(text="Error", status=500)
    
    app.router.add_post('/webhook', telegram_webhook)
    
    # Get the public URL from environment (set by Koyeb)
    webhook_url = os.environ.get('KOYEB_PUBLIC_DOMAIN', '')
    
    if webhook_url:
        # Set webhook
        full_webhook_url = f"https://{webhook_url}/webhook"
        await application.bot.set_webhook(url=full_webhook_url)
        logger.info(f"Webhook set to: {full_webhook_url}")
    else:
        # Fallback to polling for local development
        logger.info("No KOYEB_PUBLIC_DOMAIN found, starting in polling mode...")
        await application.stop()
        application2 = Application.builder().token(BOT_TOKEN).build()
        application2.add_handler(CommandHandler("start", start))
        application2.add_handler(CommandHandler("help", help_command))
        application2.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application2.add_error_handler(error_handler)
        application2.run_polling(allowed_updates=Update.ALL_TYPES)
        return
    
    # Start web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"Bot started on port {PORT}!")
    
    # Keep running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
