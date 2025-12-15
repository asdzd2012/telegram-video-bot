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

## النشر على Render.com

1. ارفع الكود على GitHub
2. اذهب إلى [Render Dashboard](https://dashboard.render.com)
3. اضغط "New +" → "Background Worker"
4. اختر الـ Repository
5. **Build Command:** `pip install -r requirements.txt`
6. **Start Command:** `python bot.py`
7. اضغط "Create Background Worker"

## الملفات

- `bot.py` - الملف الرئيسي للبوت
- `downloader.py` - منطق التحميل
- `config.py` - الإعدادات
- `requirements.txt` - المتطلبات

## الأوامر

- `/start` - رسالة الترحيب
- `/help` - المساعدة
- أرسل أي رابط فيديو للتحميل
