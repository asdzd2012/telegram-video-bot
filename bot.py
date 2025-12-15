import os
import asyncio
import logging
import json
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN
from downloader import detect_platform, download_video, cleanup_file, extract_url, set_user_cookies

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get port from environment (Koyeb sets this)
PORT = int(os.environ.get('PORT', 8000))

# Directory for user cookies
COOKIES_DIR = "user_cookies"
os.makedirs(COOKIES_DIR, exist_ok=True)

# Platform emojis
PLATFORM_EMOJI = {
    'youtube': '🔴 YouTube',
    'tiktok': '🎵 TikTok',
    'instagram': '📸 Instagram',
}


def get_user_cookies_path(user_id: int) -> str:
    """Get the cookies file path for a user."""
    return os.path.join(COOKIES_DIR, f"{user_id}_cookies.txt")


def has_user_cookies(user_id: int) -> bool:
    """Check if user has saved cookies."""
    return os.path.exists(get_user_cookies_path(user_id))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id
    has_cookies = has_user_cookies(user_id)
    
    cookies_status = "✅ لديك Cookies محفوظة" if has_cookies else "❌ لم تضف Cookies بعد"
    
    welcome_message = f"""
🎬 **مرحباً بك في بوت تحميل الفيديوهات!**

أرسل لي رابط فيديو من:
• 🎵 TikTok ✅
• 📸 Instagram ✅
• 🔴 YouTube (يحتاج Cookies)

**حالة YouTube:** {cookies_status}

**الأوامر:**
/setcookies - إضافة YouTube Cookies
/mycookies - حالة الـ Cookies
/deletecookies - حذف الـ Cookies
/help - المساعدة

⚠️ الحد الأقصى لحجم الفيديو 50MB
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
• ✅ TikTok - يعمل مباشرة
• ✅ Instagram - يعمل مباشرة
• ⚠️ YouTube - يحتاج Cookies

**لتفعيل YouTube:**
استخدم أمر /setcookies واتبع التعليمات

**الأوامر:**
/start - رسالة الترحيب
/help - المساعدة
/setcookies - إضافة Cookies
/mycookies - حالة الـ Cookies
/deletecookies - حذف الـ Cookies
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def setcookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setcookies command - explain how to add cookies."""
    instructions = """
🍪 **كيفية إضافة YouTube Cookies:**

━━━━━━━━━━━━━━━━━━━━
💻 **من الكمبيوتر (Chrome):**

1️⃣ ثبت إضافة [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2️⃣ افتح YouTube وسجل دخول
3️⃣ اضغط على الإضافة → Export
4️⃣ انسخ المحتوى وارسله هنا

━━━━━━━━━━━━━━━━━━━━
📱 **من الموبايل (Android):**

1️⃣ حمّل **Kiwi Browser** من Play Store
2️⃣ افتح المتصفح واكتب: `kiwi://extensions`
3️⃣ فعّل "Developer mode"
4️⃣ ابحث عن "Get cookies.txt" وثبتها
5️⃣ افتح YouTube وسجل دخول
6️⃣ اضغط على الإضافة → Export
7️⃣ انسخ المحتوى وارسله هنا

━━━━━━━━━━━━━━━━━━━━
⚠️ **ملاحظات مهمة:**
• استخدم حساب Google **ثانوي** (ليس الأساسي)
• الـ Cookies تنتهي صلاحيتها بعد فترة
• لا تشارك الـ Cookies مع أي شخص

📤 **الآن ارسل محتوى ملف cookies.txt:**
"""
    await update.message.reply_text(instructions, parse_mode='Markdown', disable_web_page_preview=True)
    
    # Set state to expect cookies
    context.user_data['awaiting_cookies'] = True


async def mycookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mycookies command - check cookies status."""
    user_id = update.effective_user.id
    cookies_path = get_user_cookies_path(user_id)
    
    if os.path.exists(cookies_path):
        file_size = os.path.getsize(cookies_path)
        mod_time = os.path.getmtime(cookies_path)
        from datetime import datetime
        mod_date = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
        
        await update.message.reply_text(
            f"✅ **لديك Cookies محفوظة**\n\n"
            f"📁 الحجم: {file_size} bytes\n"
            f"📅 آخر تحديث: {mod_date}\n\n"
            f"YouTube يجب أن يعمل معك! 🎉",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ **لم تضف Cookies بعد**\n\n"
            "استخدم /setcookies لإضافة Cookies وتفعيل YouTube",
            parse_mode='Markdown'
        )


async def deletecookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /deletecookies command - delete user's cookies."""
    user_id = update.effective_user.id
    cookies_path = get_user_cookies_path(user_id)
    
    if os.path.exists(cookies_path):
        os.remove(cookies_path)
        await update.message.reply_text("✅ تم حذف الـ Cookies بنجاح")
    else:
        await update.message.reply_text("❌ لا توجد Cookies محفوظة لحذفها")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Check if user is sending cookies
    if context.user_data.get('awaiting_cookies'):
        context.user_data['awaiting_cookies'] = False
        
        # Validate cookies format (should start with # or contain cookie lines)
        if '# Netscape HTTP Cookie File' in text or '\t' in text:
            # Save cookies
            cookies_path = get_user_cookies_path(user_id)
            with open(cookies_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            await update.message.reply_text(
                "✅ **تم حفظ الـ Cookies بنجاح!**\n\n"
                "الآن يمكنك تحميل فيديوهات YouTube 🎉\n\n"
                "جرب ارسل رابط YouTube!",
                parse_mode='Markdown'
            )
            return
        else:
            await update.message.reply_text(
                "❌ **صيغة Cookies غير صحيحة**\n\n"
                "تأكد من نسخ كل محتوى ملف cookies.txt\n"
                "يجب أن يبدأ بـ: `# Netscape HTTP Cookie File`\n\n"
                "استخدم /setcookies للمحاولة مرة أخرى",
                parse_mode='Markdown'
            )
            return
    
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
    
    # Check for YouTube without cookies
    if platform == 'youtube' and not has_user_cookies(user_id):
        await update.message.reply_text(
            "⚠️ **YouTube يحتاج Cookies**\n\n"
            "لتحميل فيديوهات YouTube، تحتاج إضافة Cookies.\n\n"
            "استخدم /setcookies واتبع التعليمات.",
            parse_mode='Markdown'
        )
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        f"⏳ جاري تحميل الفيديو من {platform_name}...\n"
        "ممكن ياخد شوية وقت حسب حجم الفيديو 🎬"
    )
    
    try:
        # Get user's cookies path
        user_cookies = get_user_cookies_path(user_id) if has_user_cookies(user_id) else None
        
        # Download video
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_video, url, user_cookies)
        
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
            max_desc_len = 800 - len(caption)
            if len(description) > max_desc_len:
                description = description[:max_desc_len] + "..."
            caption += f"📝 {description}\n\n"
        caption += f"📥 تم التحميل بواسطة البوت"
        
        # Update processing message
        await processing_msg.edit_text("📤 جاري إرسال الفيديو...")
        
        # Send video
        file_path = result.get('file_path')
        if file_path:
            with open(file_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=caption[:1024],
                    parse_mode='Markdown',
                    supports_streaming=True
                )
            
            cleanup_file(file_path)
        
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
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setcookies", setcookies_command))
    application.add_handler(CommandHandler("mycookies", mycookies_command))
    application.add_handler(CommandHandler("deletecookies", deletecookies_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.add_error_handler(error_handler)
    
    await application.initialize()
    await application.start()
    
    # Web server setup
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    async def telegram_webhook(request):
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Error processing update: {e}")
            return web.Response(text="Error", status=500)
    
    app.router.add_post('/webhook', telegram_webhook)
    
    webhook_url = os.environ.get('KOYEB_PUBLIC_DOMAIN', '')
    
    if webhook_url:
        full_webhook_url = f"https://{webhook_url}/webhook"
        await application.bot.set_webhook(url=full_webhook_url)
        logger.info(f"Webhook set to: {full_webhook_url}")
    else:
        logger.info("No KOYEB_PUBLIC_DOMAIN found, starting in polling mode...")
        await application.stop()
        application2 = Application.builder().token(BOT_TOKEN).build()
        application2.add_handler(CommandHandler("start", start))
        application2.add_handler(CommandHandler("help", help_command))
        application2.add_handler(CommandHandler("setcookies", setcookies_command))
        application2.add_handler(CommandHandler("mycookies", mycookies_command))
        application2.add_handler(CommandHandler("deletecookies", deletecookies_command))
        application2.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application2.add_error_handler(error_handler)
        application2.run_polling(allowed_updates=Update.ALL_TYPES)
        return
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"Bot started on port {PORT}!")
    
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
