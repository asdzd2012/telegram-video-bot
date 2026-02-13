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

# Bot password - users must login with this password
BOT_PASSWORD = "5123"

# Directory for user cookies and authenticated users
COOKIES_DIR = "user_cookies"
AUTH_FILE = "authenticated_users.json"
os.makedirs(COOKIES_DIR, exist_ok=True)

# Platform emojis
PLATFORM_EMOJI = {
    'youtube': '🔴 YouTube',
    'tiktok': '🎵 TikTok',
    'instagram': '📸 Instagram',
}

# Load authenticated users
def load_authenticated_users() -> set:
    """Load list of authenticated user IDs."""
    try:
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r') as f:
                return set(json.load(f))
    except:
        pass
    return set()

def save_authenticated_users(users: set):
    """Save authenticated user IDs."""
    with open(AUTH_FILE, 'w') as f:
        json.dump(list(users), f)

# Global set of authenticated users
authenticated_users = load_authenticated_users()

def is_authenticated(user_id: int) -> bool:
    """Check if user is authenticated."""
    return user_id in authenticated_users

def authenticate_user(user_id: int):
    """Add user to authenticated list."""
    authenticated_users.add(user_id)
    save_authenticated_users(authenticated_users)


def get_user_cookies_path(user_id: int) -> str:
    """Get the cookies file path for a user."""
    return os.path.join(COOKIES_DIR, f"{user_id}_cookies.txt")


def has_user_cookies(user_id: int) -> bool:
    """Check if user has saved cookies."""
    return os.path.exists(get_user_cookies_path(user_id))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id
    
    # Check if user is authenticated
    if not is_authenticated(user_id):
        await update.message.reply_text(
            "🔒 **هذا البوت محمي بكلمة سر**\n\n"
            "للاستخدام، أرسل كلمة السر مباشرة 👇",
            parse_mode='Markdown'
        )
        return
    
    has_cookies = has_user_cookies(user_id)
    cookies_status = "✅ لديك Cookies محفوظة" if has_cookies else "❌ لم تضف Cookies بعد"
    
    welcome_message = f"""
🎬 **مرحباً بك في بوت تحميل الفيديوهات!**

✅ أنت مسجل دخول

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
/logout - تسجيل الخروج

⚠️ الحد الأقصى لحجم الفيديو 50MB
"""
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /login command."""
    user_id = update.effective_user.id
    
    # Check if already logged in
    if is_authenticated(user_id):
        await update.message.reply_text("✅ أنت مسجل دخول بالفعل!")
        return
    
    # Check password
    if not context.args:
        await update.message.reply_text(
            "❌ أدخل كلمة السر:\n"
            "`/login كلمة_السر`",
            parse_mode='Markdown'
        )
        return
    
    password = context.args[0]
    
    if password == BOT_PASSWORD:
        authenticate_user(user_id)
        await update.message.reply_text(
            "✅ **تم تسجيل الدخول بنجاح!**\n\n"
            "يمكنك الآن استخدام البوت.\n"
            "أرسل /start للبدء.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ كلمة السر غير صحيحة!")


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /logout command."""
    user_id = update.effective_user.id
    
    if user_id in authenticated_users:
        authenticated_users.remove(user_id)
        save_authenticated_users(authenticated_users)
        await update.message.reply_text("👋 تم تسجيل الخروج. إلى اللقاء!")
    else:
        await update.message.reply_text("❌ أنت غير مسجل دخول.")



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

1️⃣ ثبت إضافة [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2️⃣ افتح YouTube وسجل دخول
3️⃣ اضغط على الإضافة واضغط على زر Copy
4️⃣ الصق المحتوى وارسله هنا

━━━━━━━━━━━━━━━━━━━━
📱 **من الموبايل (Android):**

1️⃣ حمّل [Lemur Browser](https://play.google.com/store/apps/details?id=com.lemurbrowser.exts) من Play Store
2️⃣ افتح المتصفح واضغط على أيقونة الإضافات (شكل شباك) في الأسفل → اضغط Chrome → حمّل إضافة [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
3️⃣ افتح YouTube وسجل دخول
4️⃣ اضغط على الإضافة واضغط على زر Copy
5️⃣ الصق المحتوى وارسله هنا

━━━━━━━━━━━━━━━━━━━━
⚠️ **ملاحظات مهمة:**
• استخدم حساب Google **ثانوي** (ليس الأساسي)
• الـ Cookies تنتهي صلاحيتها بعد فترة
• لا تشارك الـ Cookies مع أي شخص

📤 **الآن ارسل محتوى الـ Cookies:**
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
    
    # Check if user is trying to login with password directly
    if not is_authenticated(user_id):
        # Check if the message is the password
        if text.strip() == BOT_PASSWORD:
            authenticate_user(user_id)
            await update.message.reply_text(
                "✅ **تم تسجيل الدخول بنجاح!**\n\n"
                "يمكنك الآن استخدام البوت.\n"
                "أرسل رابط فيديو للتحميل!",
                parse_mode='Markdown'
            )
            return
        else:
            await update.message.reply_text(
                "🔒 **كلمة السر غير صحيحة**\n\n"
                "أرسل كلمة السر الصحيحة للدخول."
            )
            return
    
    # Check if user is sending cookies
    if context.user_data.get('awaiting_cookies'):
        context.user_data['awaiting_cookies'] = False
        
        # Validate cookies format (should start with # or contain cookie lines)
        if '# Netscape HTTP Cookie File' in text or '\t' in text:
            # Clean and fix cookies format
            lines = text.strip().split('\n')
            fixed_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Skip comment lines
                if line.startswith('#'):
                    fixed_lines.append(line)
                    continue
                
                # Fix tabs - Telegram might convert them to spaces
                # Cookie lines should have 6 or 7 tab-separated fields
                parts = line.split()
                if len(parts) >= 6:
                    # Reconstruct with proper tabs
                    # Format: domain, flag, path, secure, expiry, name, value
                    if len(parts) == 7:
                        fixed_line = '\t'.join(parts)
                    elif len(parts) > 7:
                        # Value might contain spaces, join the rest
                        fixed_line = '\t'.join(parts[:6]) + '\t' + ' '.join(parts[6:])
                    else:
                        fixed_line = '\t'.join(parts)
                    fixed_lines.append(fixed_line)
                else:
                    fixed_lines.append(line)
            
            # Ensure header exists
            if not any('# Netscape HTTP Cookie File' in l for l in fixed_lines):
                fixed_lines.insert(0, '# Netscape HTTP Cookie File')
                fixed_lines.insert(1, '# This is a generated file!')
            
            # Save cookies
            cookies_content = '\n'.join(fixed_lines)
            cookies_path = get_user_cookies_path(user_id)
            with open(cookies_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(cookies_content)
            
            # Verify saved file
            saved_size = os.path.getsize(cookies_path)
            
            await update.message.reply_text(
                f"✅ **تم حفظ الـ Cookies بنجاح!**\n\n"
                f"📁 حجم الملف: {saved_size} bytes\n"
                f"📝 عدد السطور: {len(fixed_lines)}\n\n"
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
    
    # Check for YouTube without cookies (User or Default)
    cookies_to_use = None
    user_cookies_path = get_user_cookies_path(user_id)
    
    if os.path.exists(user_cookies_path):
        cookies_to_use = user_cookies_path
    elif os.path.exists('default_cookies.txt'):
         cookies_to_use = 'default_cookies.txt'
         
    if platform == 'youtube' and not cookies_to_use:
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
        # Get cookies path (User > Default > None)
        user_cookies = cookies_to_use
        
        # Download video
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_video, url, user_cookies)
        
        if not result:
            await processing_msg.edit_text("❌ فشل تحميل الفيديو. جرب تاني.")
            return
        
        if 'error' in result:
            await processing_msg.edit_text(f"❌ {result['error']}")
            return
        
        # Prepare caption - escape special Markdown characters
        title = result.get('title', 'No Title')
        description = result.get('description', '')
        uploader = result.get('uploader', '')
        
        # Escape Markdown special characters
        def escape_markdown(text):
            if not text:
                return text
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = text.replace(char, '\\' + char)
            return text
        
        safe_title = escape_markdown(title)
        safe_uploader = escape_markdown(uploader)
        safe_description = escape_markdown(description)
        
        caption = f"🎬 *{safe_title}*\n\n"
        if safe_uploader:
            caption += f"👤 {safe_uploader}\n\n"
        if safe_description and safe_description != 'No Description':
            max_desc_len = 700 - len(caption)
            if len(safe_description) > max_desc_len:
                safe_description = safe_description[:max_desc_len] + "..."
            caption += f"📝 {safe_description}\n\n"
        caption += "📥 تم التحميل بواسطة @AHBOTDON_bot"
        
        # Update processing message
        await processing_msg.edit_text("📤 جاري إرسال الفيديو...")
        
        # Send video
        file_path = result.get('file_path')
        if file_path:
            try:
                with open(file_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=caption[:1024],
                        parse_mode='Markdown',
                        supports_streaming=True
                    )
            except Exception as send_error:
                # If Markdown fails, try without parse_mode
                logger.warning(f"Markdown failed, sending without: {send_error}")
                with open(file_path, 'rb') as video_file:
                    plain_caption = f"🎬 {title}\n\n"
                    if uploader:
                        plain_caption += f"👤 {uploader}\n\n"
                    plain_caption += "📥 تم التحميل بواسطة @AHBOTDON_bot"
                    await update.message.reply_video(
                        video=video_file,
                        caption=plain_caption[:1024],
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
    application.add_handler(CommandHandler("login", login_command))
    application.add_handler(CommandHandler("logout", logout_command))
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
        application2.add_handler(CommandHandler("login", login_command))
        application2.add_handler(CommandHandler("logout", logout_command))
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
