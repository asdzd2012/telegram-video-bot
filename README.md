# 🚀 Facebook Webhooks Server

سيرفر للرد التلقائي على التعليقات والرسائل باستخدام Facebook Webhooks - **بدون حدود أو حظر!**

## 📋 المتطلبات

1. **Python 3.8+**
2. **Facebook App** مع صلاحيات:
   - `pages_manage_metadata`
   - `pages_read_engagement`
   - `pages_messaging`
   - `pages_manage_posts`
3. **سيرفر مع SSL** (أو ngrok للتجربة)

---

## ⚙️ الإعداد

### 1. تثبيت المتطلبات
```bash
cd webhooks_server
pip install -r requirements.txt
```

### 2. تعديل الإعدادات

#### ملف `.env`:
```
VERIFY_TOKEN=اختر_توكن_سري_خاص_بك
PORT=5000
```

#### ملف `config.json`:
```json
{
  "page_tokens": {
    "PAGE_ID": "PAGE_ACCESS_TOKEN"
  },
  "comment_templates": ["قوالب الردود..."],
  "message_templates": ["قوالب الرسائل..."]
}
```

### 3. تشغيل السيرفر محلياً
```bash
python server.py
```

### 4. استخدام ngrok للتجربة
```bash
ngrok http 5000
```
سيعطيك رابط مثل: `https://abc123.ngrok.io`

---

## 🔗 إعداد Facebook Webhooks

### 1. اذهب لـ [Facebook Developers](https://developers.facebook.com)

### 2. اختر تطبيقك → Webhooks

### 3. أضف Webhook:
- **Callback URL:** `https://YOUR_SERVER/webhook`
- **Verify Token:** نفس القيمة في `.env`

### 4. اشترك في الأحداث:
- ✅ `feed` (للتعليقات)
- ✅ `messages` (للرسائل)

### 5. اختر الصفحات التي تريد مراقبتها

---

## 📁 هيكل الملفات

```
webhooks_server/
├── server.py              # السيرفر الرئيسي
├── config.json            # إعدادات الصفحات والقوالب
├── requirements.txt       # المتطلبات
├── .env                   # المتغيرات البيئية
├── processed_comments.json # التعليقات المردود عليها
└── README.md              # هذا الملف
```

---

## 🌐 النشر على سيرفر

### Railway (مجاني):
1. ارفع الملفات على GitHub
2. اذهب لـ [railway.app](https://railway.app)
3. اربط الـ repo
4. أضف المتغيرات البيئية
5. انشر!

### Render (مجاني):
1. [render.com](https://render.com) → New Web Service
2. اربط الـ repo
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn server:app`

---

## ✅ المميزات

- 📩 استقبال التعليقات فور حدوثها
- 💬 رد تلقائي على التعليقات
- 📨 رسائل خاصة تلقائية
- 🔀 دعم Spintax
- 🛡️ **بدون Rate Limits!**

---

## ⚠️ ملاحظات

- Facebook يتطلب **HTTPS** للـ Webhooks
- استخدم `ngrok` للتجربة المحلية
- تأكد من صلاحيات الـ Page Access Token
