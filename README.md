# Telegram Video Downloader Bot 🎬

بوت تليجرام لتحميل الفيديوهات من YouTube, TikTok, و Instagram.

## المميزات

- ✅ تحميل فيديوهات YouTube (عادي + Shorts)
- ✅ تحميل فيديوهات TikTok (بدون Watermark)
- ✅ تحميل فيديوهات Instagram (Reels & Posts)
- ✅ عرض العنوان والوصف
- ✅ تحويل تلقائي لصيغة MP4

## التشغيل المحلي

```bash
# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل البوت
python bot.py
```

## النشر على Koyeb (مجاني)

### الخطوة 1: ارفع الكود على GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/telegram-video-bot.git
git push -u origin main
```

### الخطوة 2: انشر على Koyeb
1. اذهب إلى [app.koyeb.com](https://app.koyeb.com)
2. سجل دخول بـ GitHub
3. اضغط **"Create App"**
4. اختر **"GitHub"**
5. اختر الـ Repository
6. **Builder:** Docker
7. **Instance type:** Free
8. اضغط **"Deploy"**

## الملفات

- `bot.py` - الملف الرئيسي للبوت
- `downloader.py` - منطق التحميل
- `config.py` - الإعدادات
- `Dockerfile` - إعدادات Docker لـ Koyeb

## الأوامر

- `/start` - رسالة الترحيب
- `/help` - المساعدة
- أرسل أي رابط فيديو للتحميل

