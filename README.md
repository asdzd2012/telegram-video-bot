# Telegram Video Downloader Bot 🎬

بوت تليجرام لتحميل الفيديوهات من YouTube, TikTok, و Instagram.

## المميزات

- ✅ تحميل فيديوهات YouTube (يحتاج Cookies)
- ✅ تحميل فيديوهات TikTok (باستخدام RapidAPI)
- ✅ تحميل فيديوهات Instagram
- ✅ عرض العنوان والوصف

## ⚙️ الإعداد المطلوب

### 1️⃣ TikTok - احصل على RapidAPI Key (مجاني)

1. اذهب إلى [RapidAPI TikTok Downloader](https://rapidapi.com/tikwm-tikwm-default/api/tiktok-download-without-watermark)
2. سجل حساب مجاني
3. اشترك في الخطة المجانية (150 طلب/شهر)
4. انسخ الـ API Key
5. أضفه كـ Environment Variable في Koyeb:
   - **Key:** `RAPIDAPI_KEY`
   - **Value:** `your-api-key-here`

### 2️⃣ YouTube - أضف Cookies (اختياري لكن مهم)

YouTube يحظر السيرفرات، لذلك تحتاج cookies من حسابك:

1. ثبت إضافة [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) على Chrome
2. افتح YouTube وسجل دخول
3. اضغط على الإضافة → Export → حفظ كـ `cookies.txt`
4. ارفع الملف مع الكود على GitHub

## التشغيل المحلي

```bash
pip install -r requirements.txt
python bot.py
```

## النشر على Koyeb

1. ارفع الكود على GitHub
2. اذهب إلى [app.koyeb.com](https://app.koyeb.com)
3. أنشئ Web Service جديد
4. أضف Environment Variable:
   - `RAPIDAPI_KEY` = مفتاح RapidAPI
5. Deploy!

## الأوامر

- `/start` - رسالة الترحيب
- `/help` - المساعدة
- أرسل أي رابط فيديو للتحميل
