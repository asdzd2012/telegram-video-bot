"""
Facebook Webhooks Server with Web Dashboard
============================================
سيرفر للرد التلقائي على التعليقات والرسائل
مع واجهة ويب لإدارة الصفحات والقوالب
"""

from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
import requests
import os
import json
import random
import re
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-this")

# ============ الإعدادات ============
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_fb_webhook_verify_2024")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "0452218374")

# البيانات (ستُحفظ في ملفات JSON)
DATA_FILE = "data.json"
HISTORY_FILE = "history.json"

data = {
    "pages": [],  # [{"id": "...", "name": "...", "token": "..."}]
    "comment_templates": [],
    "message_templates": [],
    "settings": {
        "auto_reply_comments": True,
        "auto_reply_messages": True,
        "send_private_reply": True,
        # Scheduling
        "schedule_enabled": False,
        "schedule_start": "09:00",
        "schedule_end": "22:00",
        "schedule_days": [0, 1, 2, 3, 4, 5, 6],  # 0=Monday, 6=Sunday
        # Filtering
        "filter_enabled": False,
        "blocked_words": [],  # تجاهل تعليقات تحتوي هذه الكلمات
        "required_words": [],  # رد فقط إذا احتوى التعليق على هذه الكلمات
        # Images
        "comment_image_url": "",
        "message_image_url": "",
        # AI Settings
        "ai_enabled": False,
        "ai_provider": "keywords",  # "keywords" or "gemini"
        "ai_api_key": "",
        "keyword_rules": []  # [{"keywords": ["سعر", "كم"], "reply": "السعر..."}]
    },
    # Statistics
    "stats": {
        "total_replies": 0,
        "successful_replies": 0,
        "failed_replies": 0,
        "private_messages": 0,
        "daily_stats": {}  # {"2025-12-13": {"replies": 10, "messages": 5}}
    }
}
history = []
processed_comments = set()

# ============ تحميل وحفظ البيانات ============
def load_data():
    global data, history, processed_comments
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        save_data()
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            processed_comments = set(h.get("comment_id", "") for h in history)
    except:
        history = []

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        # Keep last 1000 entries
        json.dump(history[-1000:], f, ensure_ascii=False, indent=2)

PROCESSED_FILE = "processed.json"

def load_processed():
    global processed_comments
    try:
        with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
            processed_comments = set(json.load(f))
    except:
        processed_comments = set()

def save_processed():
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        # Keep last 500 only to prevent file from growing too large
        comments_list = list(processed_comments)[-500:]
        json.dump(comments_list, f)

def add_history(page_name, action, status, details=""):
    history.append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "page": page_name,
        "action": action,
        "status": status,
        "details": details,
        "comment_id": details if "comment" in action.lower() else ""
    })
    save_history()

# ============ جدولة العمل ============
def is_within_schedule():
    """Check if current time is within work schedule"""
    settings = data.get("settings", {})
    if not settings.get("schedule_enabled", False):
        return True  # If scheduling disabled, always work
    
    now = datetime.now()
    current_day = now.weekday()  # 0=Monday, 6=Sunday
    
    # Check if today is a work day
    allowed_days = settings.get("schedule_days", [0, 1, 2, 3, 4, 5, 6])
    if current_day not in allowed_days:
        return False
    
    # Check time range
    start_str = settings.get("schedule_start", "09:00")
    end_str = settings.get("schedule_end", "22:00")
    
    try:
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        current_time = now.time()
        
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:  # Overnight schedule (e.g., 22:00 to 06:00)
            return current_time >= start_time or current_time <= end_time
    except:
        return True

# ============ فلترة الكلمات ============
def should_reply_to_comment(comment_text):
    """Check if we should reply based on word filters"""
    settings = data.get("settings", {})
    if not settings.get("filter_enabled", False):
        return True
    
    comment_lower = comment_text.lower() if comment_text else ""
    
    # Check blocked words
    blocked_words = settings.get("blocked_words", [])
    for word in blocked_words:
        if word.lower() in comment_lower:
            print(f"⏭️ تجاهل: التعليق يحتوي كلمة محظورة '{word}'")
            return False
    
    # Check required words
    required_words = settings.get("required_words", [])
    if required_words:
        found = any(word.lower() in comment_lower for word in required_words)
        if not found:
            print(f"⏭️ تجاهل: التعليق لا يحتوي كلمات مطلوبة")
            return False
    
    return True

# ============ ردود AI ذكية ============
def get_ai_reply(comment_text, template_type="comment"):
    """Get AI-generated or keyword-based reply"""
    settings = data.get("settings", {})
    
    if not settings.get("ai_enabled", False):
        return None  # Use normal templates
    
    provider = settings.get("ai_provider", "keywords")
    
    if provider == "keywords":
        return get_keyword_based_reply(comment_text)
    elif provider == "gemini":
        return get_gemini_reply(comment_text, template_type)
    
    return None

def get_keyword_based_reply(comment_text):
    """Match comment against keyword rules"""
    settings = data.get("settings", {})
    rules = settings.get("keyword_rules", [])
    
    comment_lower = comment_text.lower() if comment_text else ""
    
    for rule in rules:
        keywords = rule.get("keywords", [])
        reply = rule.get("reply", "")
        
        if any(kw.lower() in comment_lower for kw in keywords):
            return process_spintax(reply)
    
    return None  # No match, use normal templates

def get_gemini_reply(comment_text, template_type):
    """Generate reply using Gemini AI"""
    settings = data.get("settings", {})
    api_key = settings.get("ai_api_key", "")
    
    if not api_key:
        return None
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
        
        if template_type == "comment":
            prompt = f"اكتب رد قصير ومحترف على هذا التعليق على فيسبوك: '{comment_text}'. الرد يجب أن يكون جملة أو جملتين فقط بالعربية."
        else:
            prompt = f"اكتب رسالة ترحيب قصيرة ومحترفة رداً على هذا التعليق: '{comment_text}'. الرسالة للمحادثة الخاصة."
        
        response = requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip() if text else None
    except Exception as e:
        print(f"❌ خطأ Gemini AI: {e}")
    
    return None

# ============ الإحصائيات ============
def update_stats(stat_type, success=True):
    """Update statistics counters"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Ensure stats structure exists
    if "stats" not in data:
        data["stats"] = {"total_replies": 0, "successful_replies": 0, "failed_replies": 0, "private_messages": 0, "daily_stats": {}}
    
    stats = data["stats"]
    
    # Update totals
    if stat_type == "reply":
        stats["total_replies"] = stats.get("total_replies", 0) + 1
        if success:
            stats["successful_replies"] = stats.get("successful_replies", 0) + 1
        else:
            stats["failed_replies"] = stats.get("failed_replies", 0) + 1
    elif stat_type == "message":
        stats["private_messages"] = stats.get("private_messages", 0) + 1
    
    # Update daily stats
    if "daily_stats" not in stats:
        stats["daily_stats"] = {}
    if today not in stats["daily_stats"]:
        stats["daily_stats"][today] = {"replies": 0, "messages": 0, "successful": 0, "failed": 0}
    
    daily = stats["daily_stats"][today]
    if stat_type == "reply":
        daily["replies"] = daily.get("replies", 0) + 1
        if success:
            daily["successful"] = daily.get("successful", 0) + 1
        else:
            daily["failed"] = daily.get("failed", 0) + 1
    elif stat_type == "message":
        daily["messages"] = daily.get("messages", 0) + 1
    
    save_data()

# ============ المصادقة ============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ============ Spintax ============
def process_spintax(text):
    pattern = r'\{([^{}]+)\}'
    def replace(match):
        options = match.group(1).split('|')
        return random.choice(options)
    while re.search(pattern, text):
        text = re.sub(pattern, replace, text, count=1)
    return text

# ============ الرد على التعليقات ============
def get_page_token(page_id):
    for page in data.get("pages", []):
        if page["id"] == page_id:
            return page.get("token"), page.get("name", "Unknown")
    return None, None

def reply_to_comment(comment_id, page_id, user_name, comment_text=""):
    # Check if already processed FIRST to prevent duplicates
    if comment_id in processed_comments:
        print(f"⏭️ تعليق معالج مسبقاً: {comment_id}")
        return False
    
    # Add to processed IMMEDIATELY to prevent duplicates from webhook retries
    processed_comments.add(comment_id)
    save_processed()  # Save to file immediately
    
    # Check scheduling
    if not is_within_schedule():
        print("⏭️ خارج أوقات العمل - تخطي الرد")
        return False
    
    # Check word filters
    if not should_reply_to_comment(comment_text):
        return False
    
    if not data["settings"].get("auto_reply_comments", True):
        return False
    
    token, page_name = get_page_token(page_id)
    if not token:
        add_history("Unknown", "خطأ", "فشل", f"لا يوجد توكن للصفحة {page_id}")
        update_stats("reply", False)
        return False
    
    # Try AI reply first
    reply_text = get_ai_reply(comment_text, "comment")
    
    # Fall back to templates if no AI reply
    if not reply_text:
        templates = data.get("comment_templates", [])
        if not templates:
            return False
        template = random.choice(templates)
        reply_text = process_spintax(template)
    
    url = f"https://graph.facebook.com/v19.0/{comment_id}/comments"
    try:
        post_data = {
            "message": reply_text,
            "access_token": token
        }
        
        # Add image if configured
        image_url = data.get("settings", {}).get("comment_image_url", "")
        if image_url:
            post_data["attachment_url"] = image_url
        
        response = requests.post(url, data=post_data, timeout=10)
        
        if response.status_code == 200:
            img_text = " + صورة" if image_url else ""
            add_history(page_name, "رد على تعليق", "نجاح", f"الرد على {user_name}: {reply_text[:50]}...{img_text}")
            update_stats("reply", True)
            return True
        else:
            error_text = response.text[:100]
            print(f"❌ فشل الرد: {error_text}")
            add_history(page_name, "رد على تعليق", "فشل", error_text)
            update_stats("reply", False)
            return False
    except Exception as e:
        print(f"❌ استثناء: {e}")
        add_history(page_name, "رد على تعليق", "خطأ", str(e)[:100])
        update_stats("reply", False)
        return False

def send_private_reply(comment_id, page_id, user_name, comment_text=""):
    if not data["settings"].get("send_private_reply", True):
        return False
    
    token, page_name = get_page_token(page_id)
    if not token:
        print(f"⚠️ رسالة خاصة: لا يوجد توكن للصفحة {page_id}")
        return False
    
    # Try AI reply first
    message_text = get_ai_reply(comment_text, "message")
    
    # Fall back to templates if no AI reply
    if not message_text:
        templates = data.get("message_templates", [])
        if not templates:
            print("⚠️ رسالة خاصة: لا يوجد قوالب رسائل")
            return False
        template = random.choice(templates)
        message_text = process_spintax(template)
    
    # Use the correct API: POST to /{page_id}/messages with recipient.comment_id
    url = f"https://graph.facebook.com/v19.0/{page_id}/messages"
    try:
        payload = {
            'recipient': json.dumps({'comment_id': comment_id}),
            'message': json.dumps({'text': message_text}),
            'access_token': token
        }
        
        print(f"📨 إرسال رسالة خاصة لـ {user_name}...")
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            add_history(page_name, "رسالة خاصة", "نجاح", f"رسالة لـ {user_name}")
            print(f"✅ تم إرسال رسالة خاصة لـ {user_name}")
            update_stats("message", True)
            
            # Send image in separate message if configured
            image_url = data.get("settings", {}).get("message_image_url", "")
            if image_url:
                img_payload = {
                    'recipient': json.dumps({'comment_id': comment_id}),
                    'message': json.dumps({
                        'attachment': {
                            'type': 'image',
                            'payload': {'url': image_url}
                        }
                    }),
                    'access_token': token
                }
                requests.post(url, data=img_payload, timeout=10)
            
            return True
        else:
            error_text = response.text[:150]
            print(f"❌ فشل الرسالة الخاصة: {error_text}")
            add_history(page_name, "رسالة خاصة", "فشل", error_text[:80])
            return False
    except Exception as e:
        print(f"❌ استثناء رسالة خاصة: {e}")
        return False

def reply_to_message(sender_id, page_id):
    if not data["settings"].get("auto_reply_messages", True):
        return False
    
    token, page_name = get_page_token(page_id)
    if not token:
        return False
    
    templates = data.get("message_templates", [])
    if not templates:
        return False
    
    template = random.choice(templates)
    message_text = process_spintax(template)
    
    url = f"https://graph.facebook.com/v19.0/{page_id}/messages"
    try:
        response = requests.post(url, json={
            "recipient": {"id": sender_id},
            "message": {"text": message_text},
            "access_token": token
        }, timeout=10)
        
        if response.status_code == 200:
            add_history(page_name, "رد على رسالة", "نجاح", "")
            return True
        else:
            add_history(page_name, "رد على رسالة", "فشل", response.text[:100])
            return False
    except Exception as e:
        add_history(page_name, "رد على رسالة", "خطأ", str(e)[:100])
        return False

# ============ HTML Templates ============
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة تحكم Webhooks</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Cairo', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        /* Header */
        .header {
            background: rgba(0,0,0,0.3);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { color: #00e5ff; font-size: 1.8em; }
        .header .status {
            background: #00c853;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
        }
        .logout-btn {
            background: #ff5252;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            text-decoration: none;
        }
        
        /* Stats */
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        .stat-card h3 { font-size: 2em; color: #00e5ff; }
        .stat-card p { color: #aaa; }
        
        /* Grid */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        
        /* Mobile Responsive */
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .header { flex-direction: column; gap: 10px; text-align: center; }
            .header h1 { font-size: 1.4em; }
            .stats { grid-template-columns: repeat(2, 1fr); }
            .stat-card { padding: 15px; }
            .stat-card h3 { font-size: 1.5em; }
            .grid { grid-template-columns: 1fr; }
            .card { padding: 15px; }
            .btn { padding: 12px 16px; font-size: 0.9em; }
            input, textarea, select { padding: 10px; font-size: 14px; }
            .list-item { flex-direction: column; gap: 10px; text-align: center; }
            .toggle-group { flex-direction: column; }
        }
        
        @media (max-width: 480px) {
            .stats { grid-template-columns: 1fr; }
            .header h1 { font-size: 1.2em; }
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .tab {
            background: rgba(255,255,255,0.1);
            padding: 12px 25px;
            border-radius: 8px;
            cursor: pointer;
            border: none;
            color: #fff;
            font-family: inherit;
            transition: all 0.3s;
        }
        .tab.active, .tab:hover { background: #00e5ff; color: #1a1a2e; }
        
        /* Tab Content */
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Cards */
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .card-title { color: #00e5ff; font-size: 1.2em; }
        
        /* Forms */
        input, textarea, select {
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            margin-bottom: 10px;
            font-family: inherit;
        }
        textarea { min-height: 100px; resize: vertical; }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
        }
        .btn-primary { background: linear-gradient(45deg, #00e5ff, #00b8d4); color: #000; }
        .btn-danger { background: #ff5252; color: #fff; }
        .btn-success { background: #00c853; color: #fff; }
        .btn:hover { transform: translateY(-2px); opacity: 0.9; }
        
        /* List */
        .list-item {
            background: rgba(0,0,0,0.2);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .list-item:hover { background: rgba(0,0,0,0.3); }
        
        /* Table */
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: right; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: #00e5ff; }
        .status-success { color: #00c853; }
        .status-error { color: #ff5252; }
        
        /* Toggle */
        .toggle-container { display: flex; align-items: center; gap: 10px; margin: 10px 0; }
        .toggle {
            width: 50px; height: 26px;
            background: #555;
            border-radius: 13px;
            position: relative;
            cursor: pointer;
            transition: 0.3s;
        }
        .toggle.active { background: #00c853; }
        .toggle::after {
            content: '';
            position: absolute;
            width: 22px; height: 22px;
            background: #fff;
            border-radius: 50%;
            top: 2px; left: 2px;
            transition: 0.3s;
        }
        .toggle.active::after { left: 26px; }
        
        /* Responsive */
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .header { flex-direction: column; gap: 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🚀 لوحة تحكم Webhooks</h1>
            <div class="status">🟢 السيرفر يعمل</div>
            <a href="/logout" class="logout-btn">تسجيل الخروج</a>
        </div>
        
        <!-- Stats -->
        <div class="stats">
            <div class="stat-card">
                <h3 id="pages-count">{{ pages_count }}</h3>
                <p>الصفحات</p>
            </div>
            <div class="stat-card">
                <h3 id="total-replies">{{ stats.get('total_replies', 0) }}</h3>
                <p>إجمالي الردود</p>
            </div>
            <div class="stat-card" style="border: 2px solid #00c853;">
                <h3 id="success-count" style="color: #00c853;">{{ stats.get('successful_replies', 0) }}</h3>
                <p>ناجحة ✅</p>
            </div>
            <div class="stat-card" style="border: 2px solid #ff5252;">
                <h3 id="fail-count" style="color: #ff5252;">{{ stats.get('failed_replies', 0) }}</h3>
                <p>فاشلة ❌</p>
            </div>
            <div class="stat-card">
                <h3 id="messages-count">{{ stats.get('private_messages', 0) }}</h3>
                <p>رسائل خاصة 📨</p>
            </div>
        </div>
        
        <!-- Tabs Navigation -->
        <div class="tabs">
            <button class="tab active" onclick="showTab('main')">🏠 الرئيسية</button>
            <button class="tab" onclick="showTab('settings')">⚙️ الإعدادات المتقدمة</button>
            <button class="tab" onclick="showTab('ai')">🤖 الذكاء الاصطناعي</button>
            <button class="tab" onclick="showTab('history')">📜 السجل</button>
        </div>
        
        <!-- Main Tab Content -->
        <div id="tab-main" class="tab-content active">
        <div class="grid">
            <!-- Pages -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">📄 الصفحات</span>
                    <button class="btn btn-danger" onclick="deleteAllPages()" style="font-size: 0.8em;">🗑️ حذف الكل</button>
                </div>
                
                <!-- Fetch Pages Section -->
                <div style="margin-bottom: 15px; padding: 15px; background: rgba(0,0,0,0.2); border-radius: 10px;">
                    <p style="color: #00e5ff; margin-bottom: 10px;">🔄 جلب الصفحات تلقائياً</p>
                    <input type="text" id="user-token" placeholder="أدخل Access Token للحساب">
                    <button class="btn btn-primary" onclick="fetchPages()" id="fetch-btn">📥 جلب الصفحات</button>
                </div>
                
                <!-- Fetched Pages (hidden initially) -->
                <div id="fetched-pages-container" style="display: none; margin-bottom: 15px; padding: 15px; background: rgba(0,100,0,0.2); border-radius: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span style="color: #00c853;">📋 الصفحات المتاحة:</span>
                        <button class="btn btn-success" onclick="addSelectedPages()">➕ إضافة المحددة</button>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <label style="cursor: pointer;">
                            <input type="checkbox" id="select-all-fetched" onchange="toggleAllFetched()"> 
                            تحديد الكل
                        </label>
                    </div>
                    <div id="fetched-pages-list" style="max-height: 200px; overflow-y: auto;"></div>
                </div>
                
                <!-- Current Pages List -->
                <p style="color: #aaa; margin-bottom: 10px;">الصفحات المضافة ({{ pages|length }}):</p>
                <div id="pages-list" style="max-height: 300px; overflow-y: auto;">
                    {% for page in pages %}
                    <div class="list-item">
                        <span>{{ page.name }}</span>
                        <button class="btn btn-danger" onclick="deletePage('{{ page.id }}')" style="padding: 5px 10px;">🗑️</button>
                    </div>
                    {% endfor %}
                </div>
                
                <!-- Subscribe All Button -->
                {% if pages %}
                <div style="margin-top: 15px; padding: 15px; background: rgba(0,150,0,0.2); border-radius: 10px;">
                    <button class="btn btn-success" onclick="subscribeAllPages()" style="width: 100%;">
                        🔔 تفعيل Webhooks لكل الصفحات
                    </button>
                    <p style="color: #aaa; font-size: 0.85em; margin-top: 8px; text-align: center;">
                        اضغط هنا بعد إضافة الصفحات لتفعيل الإشعارات
                    </p>
                </div>
                {% endif %}
            </div>
            
            <!-- Comment Templates -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">💬 قوالب التعليقات</span>
                </div>
                <form id="add-comment-template-form">
                    <textarea id="comment-template" placeholder="اكتب قالب الرد هنا... يمكنك استخدام {خيار1|خيار2}"></textarea>
                    <button type="submit" class="btn btn-primary">➕ إضافة قالب</button>
                </form>
                <div id="comment-templates-list" style="margin-top: 15px; max-height: 200px; overflow-y: auto;">
                    {% for template in comment_templates %}
                    <div class="list-item">
                        <span>{{ template[:50] }}...</span>
                        <button class="btn btn-danger" onclick="deleteCommentTemplate({{ loop.index0 }})">🗑️</button>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <!-- Message Templates -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">📨 قوالب الرسائل</span>
                </div>
                <form id="add-message-template-form">
                    <textarea id="message-template" placeholder="اكتب قالب الرسالة هنا..."></textarea>
                    <button type="submit" class="btn btn-primary">➕ إضافة قالب</button>
                </form>
                <div id="message-templates-list" style="margin-top: 15px; max-height: 200px; overflow-y: auto;">
                    {% for template in message_templates %}
                    <div class="list-item">
                        <span>{{ template[:50] }}...</span>
                        <button class="btn btn-danger" onclick="deleteMessageTemplate({{ loop.index0 }})">🗑️</button>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <!-- Settings -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">⚙️ الإعدادات</span>
                </div>
                <div class="toggle-container">
                    <div class="toggle {{ 'active' if settings.auto_reply_comments else '' }}" 
                         onclick="toggleSetting('auto_reply_comments', this)"></div>
                    <span>الرد على التعليقات تلقائياً</span>
                </div>
                <div class="toggle-container">
                    <div class="toggle {{ 'active' if settings.auto_reply_messages else '' }}" 
                         onclick="toggleSetting('auto_reply_messages', this)"></div>
                    <span>الرد على الرسائل تلقائياً</span>
                </div>
                <div class="toggle-container">
                    <div class="toggle {{ 'active' if settings.send_private_reply else '' }}" 
                         onclick="toggleSetting('send_private_reply', this)"></div>
                    <span>إرسال رسالة خاصة مع الرد</span>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background: rgba(0,0,0,0.2); border-radius: 8px;">
                    <p style="color: #aaa; margin-bottom: 10px;">🔗 Webhook URL:</p>
                    <code style="color: #00e5ff; word-break: break-all;">{{ webhook_url }}</code>
                </div>
            </div>
            
                </div>
            </div>
        </div>
        </div><!-- End Main Tab -->
        
        <!-- Settings Tab -->
        <div id="tab-settings" class="tab-content">
            <div class="grid">
                <!-- Scheduling -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">⏰ جدولة العمل</span>
                        <div class="toggle {{ 'active' if settings.get('schedule_enabled') }}" 
                             onclick="toggleSetting('schedule_enabled', this)">
                            {{ 'تشغيل' if settings.get('schedule_enabled') else 'إيقاف' }}
                        </div>
                    </div>
                    <div style="display: grid; gap: 15px;">
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <label>من:</label>
                            <input type="time" id="schedule-start" value="{{ settings.get('schedule_start', '09:00') }}" 
                                   onchange="updateSchedule()">
                            <label>إلى:</label>
                            <input type="time" id="schedule-end" value="{{ settings.get('schedule_end', '22:00') }}"
                                   onchange="updateSchedule()">
                        </div>
                        <p style="color: #aaa; font-size: 0.9em;">الرد فقط في الأوقات المحددة</p>
                    </div>
                </div>
                
                <!-- Word Filtering -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">🔍 فلترة الكلمات</span>
                        <div class="toggle {{ 'active' if settings.get('filter_enabled') }}" 
                             onclick="toggleSetting('filter_enabled', this)">
                            {{ 'تشغيل' if settings.get('filter_enabled') else 'إيقاف' }}
                        </div>
                    </div>
                    <div style="display: grid; gap: 15px;">
                        <div>
                            <label style="color: #ff5252;">❌ كلمات محظورة (تجاهل التعليق):</label>
                            <input type="text" id="blocked-words" 
                                   placeholder="كلمة1, كلمة2, كلمة3"
                                   value="{{ ', '.join(settings.get('blocked_words', [])) }}"
                                   onchange="updateFilterWords('blocked')">
                        </div>
                        <div>
                            <label style="color: #00c853;">✅ كلمات مطلوبة (رد فقط إذا وُجدت):</label>
                            <input type="text" id="required-words" 
                                   placeholder="كلمة1, كلمة2"
                                   value="{{ ', '.join(settings.get('required_words', [])) }}"
                                   onchange="updateFilterWords('required')">
                        </div>
                    </div>
                </div>
                
                <!-- Images -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">🖼️ إرفاق صور</span>
                    </div>
                    <div style="display: grid; gap: 15px;">
                        <div>
                            <label>صورة مع رد التعليق:</label>
                            <input type="text" id="comment-image" 
                                   placeholder="رابط الصورة (URL)"
                                   value="{{ settings.get('comment_image_url', '') }}"
                                   onchange="updateSetting('comment_image_url', this.value)">
                        </div>
                        <div>
                            <label>صورة مع الرسالة الخاصة:</label>
                            <input type="text" id="message-image" 
                                   placeholder="رابط الصورة (URL)"
                                   value="{{ settings.get('message_image_url', '') }}"
                                   onchange="updateSetting('message_image_url', this.value)">
                        </div>
                    </div>
                </div>
            </div>
        </div><!-- End Settings Tab -->
        
        <!-- AI Tab -->
        <div id="tab-ai" class="tab-content">
            <div class="grid">
                <!-- AI Provider -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">🤖 الذكاء الاصطناعي</span>
                        <div class="toggle {{ 'active' if settings.get('ai_enabled') }}" 
                             onclick="toggleSetting('ai_enabled', this)">
                            {{ 'تشغيل' if settings.get('ai_enabled') else 'إيقاف' }}
                        </div>
                    </div>
                    <div style="display: grid; gap: 15px;">
                        <div>
                            <label>نوع الـ AI:</label>
                            <select id="ai-provider" onchange="updateSetting('ai_provider', this.value)">
                                <option value="keywords" {{ 'selected' if settings.get('ai_provider') == 'keywords' }}>كلمات مفتاحية</option>
                                <option value="gemini" {{ 'selected' if settings.get('ai_provider') == 'gemini' }}>Gemini AI (يحتاج API Key)</option>
                            </select>
                        </div>
                        <div id="gemini-key-section" style="{{ '' if settings.get('ai_provider') == 'gemini' else 'display: none;' }}">
                            <label>Gemini API Key:</label>
                            <input type="password" id="ai-api-key" 
                                   placeholder="أدخل API Key"
                                   value="{{ settings.get('ai_api_key', '') }}"
                                   onchange="updateSetting('ai_api_key', this.value)">
                            <a href="https://makersuite.google.com/app/apikey" target="_blank" style="color: #00e5ff; font-size: 0.8em;">
                                احصل على API Key مجاناً
                            </a>
                        </div>
                    </div>
                </div>
                
                <!-- Keyword Rules -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">📝 قواعد الكلمات المفتاحية</span>
                    </div>
                    <div style="display: grid; gap: 10px;">
                        <div style="display: flex; gap: 10px;">
                            <input type="text" id="new-keywords" placeholder="الكلمات (مفصولة بفاصلة): سعر, كم, ثمن">
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <input type="text" id="new-reply" placeholder="الرد عند وجود الكلمات">
                            <button class="btn btn-success" onclick="addKeywordRule()">➕</button>
                        </div>
                        <div id="keyword-rules-list" style="max-height: 200px; overflow-y: auto;">
                            {% for rule in settings.get('keyword_rules', []) %}
                            <div class="list-item">
                                <span><strong>{{ ', '.join(rule.keywords) }}</strong> → {{ rule.reply[:30] }}...</span>
                                <button class="btn btn-danger" onclick="deleteKeywordRule({{ loop.index0 }})" style="padding: 5px 10px;">🗑️</button>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
            </div>
        </div><!-- End AI Tab -->
        
        <!-- History Tab -->
        <div id="tab-history" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">📜 سجل الردود</span>
                    <div style="display: flex; gap: 10px;">
                        <a href="/api/export" class="btn btn-primary" style="text-decoration: none;">📥 تصدير CSV</a>
                        <button class="btn btn-danger" onclick="clearHistory()">🗑️ مسح</button>
                    </div>
                </div>
                <div style="max-height: 500px; overflow-y: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>الوقت</th>
                                <th>الصفحة</th>
                                <th>الإجراء</th>
                                <th>الحالة</th>
                                <th>التفاصيل</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for item in history[-100:]|reverse %}
                            <tr>
                                <td>{{ item.time }}</td>
                                <td>{{ item.page }}</td>
                                <td>{{ item.action }}</td>
                                <td class="{{ 'status-success' if item.status == 'نجاح' else 'status-error' }}">
                                    {{ item.status }}
                                </td>
                                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">
                                    {{ item.details[:50] }}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div><!-- End History Tab -->
    </div>
    
    <script>
        // Tab Switching
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(btn => btn.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            event.target.classList.add('active');
        }
        
        // Update single setting
        async function updateSetting(setting, value) {
            await fetch('/api/settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({setting, value})
            });
            
            // Show/hide Gemini key section
            if (setting === 'ai_provider') {
                document.getElementById('gemini-key-section').style.display = 
                    value === 'gemini' ? 'block' : 'none';
            }
        }
        
        // Update schedule
        async function updateSchedule() {
            const start = document.getElementById('schedule-start').value;
            const end = document.getElementById('schedule-end').value;
            await updateSetting('schedule_start', start);
            await updateSetting('schedule_end', end);
        }
        
        // Update filter words
        async function updateFilterWords(type) {
            const inputId = type === 'blocked' ? 'blocked-words' : 'required-words';
            const words = document.getElementById(inputId).value
                .split(',')
                .map(w => w.trim())
                .filter(w => w);
            
            await fetch('/api/filter-words', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({type, words})
            });
        }
        
        // Add keyword rule
        async function addKeywordRule() {
            const keywordsInput = document.getElementById('new-keywords');
            const replyInput = document.getElementById('new-reply');
            
            const keywords = keywordsInput.value.split(',').map(k => k.trim()).filter(k => k);
            const reply = replyInput.value.trim();
            
            if (keywords.length && reply) {
                await fetch('/api/keyword-rules', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({keywords, reply})
                });
                location.reload();
            }
        }
        
        // Delete keyword rule
        async function deleteKeywordRule(index) {
            await fetch('/api/keyword-rules/' + index, {method: 'DELETE'});
            location.reload();
        }
        
        // Global variable to store fetched pages
        let fetchedPages = [];
        
        // Fetch Pages from Token
        async function fetchPages() {
            const token = document.getElementById('user-token').value;
            if (!token) {
                alert('يرجى إدخال Access Token');
                return;
            }
            
            const btn = document.getElementById('fetch-btn');
            btn.textContent = '⏳ جاري الجلب...';
            btn.disabled = true;
            
            try {
                const response = await fetch('/api/fetch-pages', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({token: token})
                });
                const result = await response.json();
                
                if (result.success) {
                    fetchedPages = result.pages;
                    displayFetchedPages(result.pages);
                } else {
                    alert('خطأ: ' + (result.error || 'فشل جلب الصفحات'));
                }
            } catch (e) {
                alert('خطأ في الاتصال');
            }
            
            btn.textContent = '📥 جلب الصفحات';
            btn.disabled = false;
        }
        
        // Display fetched pages with checkboxes
        function displayFetchedPages(pages) {
            const container = document.getElementById('fetched-pages-container');
            const list = document.getElementById('fetched-pages-list');
            
            if (pages.length === 0) {
                list.innerHTML = '<p style="color: #aaa;">لم يتم العثور على صفحات</p>';
            } else {
                list.innerHTML = pages.map((p, i) => `
                    <div class="list-item">
                        <label style="cursor: pointer; flex: 1;">
                            <input type="checkbox" class="page-checkbox" data-index="${i}" checked>
                            ${p.name}
                        </label>
                    </div>
                `).join('');
            }
            
            container.style.display = 'block';
        }
        
        // Toggle all checkboxes
        function toggleAllFetched() {
            const checked = document.getElementById('select-all-fetched').checked;
            document.querySelectorAll('.page-checkbox').forEach(cb => cb.checked = checked);
        }
        
        // Add selected pages
        async function addSelectedPages() {
            const selected = [];
            document.querySelectorAll('.page-checkbox:checked').forEach(cb => {
                const index = parseInt(cb.dataset.index);
                selected.push(fetchedPages[index]);
            });
            
            if (selected.length === 0) {
                alert('يرجى تحديد صفحة واحدة على الأقل');
                return;
            }
            
            const response = await fetch('/api/pages/bulk', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({pages: selected})
            });
            const result = await response.json();
            
            alert(`تمت إضافة ${result.added} صفحة جديدة`);
            location.reload();
        }
        
        // Subscribe all pages to webhooks
        async function subscribeAllPages() {
            if (!confirm('هل تريد تفعيل Webhooks لكل الصفحات المضافة؟')) {
                return;
            }
            
            try {
                const response = await fetch('/api/pages/subscribe-all', {method: 'POST'});
                const result = await response.json();
                
                if (result.success) {
                    let message = `تم تفعيل ${result.subscribed} من ${result.total} صفحة\n\n`;
                    result.results.forEach(r => {
                        message += r.success ? `✅ ${r.page}\n` : `❌ ${r.page}: ${r.error}\n`;
                    });
                    alert(message);
                    location.reload();
                } else {
                    alert('حدث خطأ أثناء التفعيل');
                }
            } catch (e) {
                alert('خطأ في الاتصال');
            }
        }
        
        // Delete Page
        async function deletePage(id) {
            if (confirm('هل أنت متأكد من حذف هذه الصفحة؟')) {
                await fetch('/api/pages/' + id, {method: 'DELETE'});
                location.reload();
            }
        }
        
        // Delete All Pages
        async function deleteAllPages() {
            if (confirm('هل أنت متأكد من حذف جميع الصفحات؟')) {
                const pages = {{ pages | tojson }};
                for (const p of pages) {
                    await fetch('/api/pages/' + p.id, {method: 'DELETE'});
                }
                location.reload();
            }
        }
        
        // Add Comment Template
        document.getElementById('add-comment-template-form').onsubmit = async (e) => {
            e.preventDefault();
            await fetch('/api/templates/comment', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({template: document.getElementById('comment-template').value})
            });
            location.reload();
        };
        
        // Add Message Template
        document.getElementById('add-message-template-form').onsubmit = async (e) => {
            e.preventDefault();
            await fetch('/api/templates/message', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({template: document.getElementById('message-template').value})
            });
            location.reload();
        };
        
        // Delete Templates
        async function deleteCommentTemplate(index) {
            await fetch('/api/templates/comment/' + index, {method: 'DELETE'});
            location.reload();
        }
        
        async function deleteMessageTemplate(index) {
            await fetch('/api/templates/message/' + index, {method: 'DELETE'});
            location.reload();
        }
        
        // Toggle Setting
        async function toggleSetting(setting, el) {
            el.classList.toggle('active');
            await fetch('/api/settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({setting: setting, value: el.classList.contains('active')})
            });
        }
        
        // Clear History
        async function clearHistory() {
            if (confirm('هل أنت متأكد من مسح السجل؟')) {
                await fetch('/api/history', {method: 'DELETE'});
                location.reload();
            }
        }
        
        // Auto-refresh disabled to prevent losing data while working
        // setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
'''

LOGIN_HTML = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Cairo', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #fff;
        }
        .login-box {
            background: rgba(255,255,255,0.05);
            padding: 40px;
            border-radius: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            width: 100%;
            max-width: 400px;
            text-align: center;
        }
        h1 { color: #00e5ff; margin-bottom: 30px; font-size: 1.8em; }
        input {
            width: 100%;
            padding: 15px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 10px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            margin-bottom: 15px;
            font-size: 1em;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(45deg, #00e5ff, #00b8d4);
            border: none;
            border-radius: 10px;
            color: #000;
            font-weight: bold;
            font-size: 1.1em;
            cursor: pointer;
            transition: 0.3s;
        }
        button:hover { transform: translateY(-2px); }
        .error { color: #ff5252; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🔒 تسجيل الدخول</h1>
        {% if error %}
        <p class="error">{{ error }}</p>
        {% endif %}
        <form method="POST">
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول</button>
        </form>
    </div>
</body>
</html>
'''

# ============ Routes ============
@app.route("/")
@login_required
def dashboard():
    today = datetime.now().strftime("%Y-%m-%d")
    replies_today = len([h for h in history if h.get("time", "").startswith(today) and h.get("status") == "نجاح"])
    
    return render_template_string(DASHBOARD_HTML,
        pages=data.get("pages", []),
        comment_templates=data.get("comment_templates", []),
        message_templates=data.get("message_templates", []),
        settings=data.get("settings", {}),
        stats=data.get("stats", {}),
        history=history,
        pages_count=len(data.get("pages", [])),
        replies_count=replies_today,
        templates_count=len(data.get("comment_templates", [])) + len(data.get("message_templates", [])),
        webhook_url=request.host_url + "webhook"
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            error = "كلمة المرور غير صحيحة"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ============ API Routes ============
@app.route("/api/pages", methods=["POST"])
@login_required
def add_page():
    page_data = request.json
    data.setdefault("pages", []).append(page_data)
    save_data()
    return jsonify({"success": True})

@app.route("/api/fetch-pages", methods=["POST"])
@login_required
def fetch_pages():
    """Fetch all pages from a user access token"""
    user_token = request.json.get("token")
    if not user_token:
        return jsonify({"success": False, "error": "Token required"}), 400
    
    try:
        # Get all pages for this user
        url = f"https://graph.facebook.com/v19.0/me/accounts?fields=id,name,access_token&limit=100&access_token={user_token}"
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            return jsonify({"success": False, "error": response.text}), 400
        
        pages_data = response.json().get("data", [])
        
        # Format pages
        pages = []
        for p in pages_data:
            pages.append({
                "id": p["id"],
                "name": p["name"],
                "token": p["access_token"]
            })
        
        return jsonify({"success": True, "pages": pages})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/pages/bulk", methods=["POST"])
@login_required
def add_pages_bulk():
    """Add multiple pages at once"""
    pages_to_add = request.json.get("pages", [])
    existing_ids = {p["id"] for p in data.get("pages", [])}
    
    added = 0
    for page in pages_to_add:
        if page["id"] not in existing_ids:
            data.setdefault("pages", []).append(page)
            added += 1
    
    save_data()
    return jsonify({"success": True, "added": added})

@app.route("/api/pages/subscribe-all", methods=["POST"])
@login_required
def subscribe_all_pages():
    """Subscribe all pages to webhooks at once"""
    results = []
    pages = data.get("pages", [])
    
    for page in pages:
        page_id = page.get("id")
        page_token = page.get("token")
        page_name = page.get("name", "Unknown")
        
        if not page_id or not page_token:
            results.append({"page": page_name, "success": False, "error": "Missing ID or token"})
            continue
        
        try:
            url = f"https://graph.facebook.com/v19.0/{page_id}/subscribed_apps"
            response = requests.post(url, data={
                "subscribed_fields": "feed,messages",
                "access_token": page_token
            }, timeout=10)
            
            if response.status_code == 200:
                results.append({"page": page_name, "success": True})
                add_history(page_name, "اشتراك Webhook", "نجاح", "")
            else:
                error_msg = response.json().get("error", {}).get("message", "Unknown error")
                results.append({"page": page_name, "success": False, "error": error_msg[:50]})
                add_history(page_name, "اشتراك Webhook", "فشل", error_msg[:50])
        except Exception as e:
            results.append({"page": page_name, "success": False, "error": str(e)[:50]})
    
    success_count = len([r for r in results if r["success"]])
    return jsonify({
        "success": True,
        "total": len(pages),
        "subscribed": success_count,
        "results": results
    })

@app.route("/api/pages/<page_id>", methods=["DELETE"])
@login_required
def delete_page(page_id):
    data["pages"] = [p for p in data.get("pages", []) if p["id"] != page_id]
    save_data()
    return jsonify({"success": True})

@app.route("/api/templates/comment", methods=["POST"])
@login_required
def add_comment_template():
    template = request.json.get("template")
    if template:
        data.setdefault("comment_templates", []).append(template)
        save_data()
    return jsonify({"success": True})

@app.route("/api/templates/comment/<int:index>", methods=["DELETE"])
@login_required
def delete_comment_template(index):
    if 0 <= index < len(data.get("comment_templates", [])):
        data["comment_templates"].pop(index)
        save_data()
    return jsonify({"success": True})

@app.route("/api/templates/message", methods=["POST"])
@login_required
def add_message_template():
    template = request.json.get("template")
    if template:
        data.setdefault("message_templates", []).append(template)
        save_data()
    return jsonify({"success": True})

@app.route("/api/templates/message/<int:index>", methods=["DELETE"])
@login_required
def delete_message_template(index):
    if 0 <= index < len(data.get("message_templates", [])):
        data["message_templates"].pop(index)
        save_data()
    return jsonify({"success": True})

@app.route("/api/settings", methods=["POST"])
@login_required
def update_setting():
    setting = request.json.get("setting")
    value = request.json.get("value")
    data.setdefault("settings", {})[setting] = value
    save_data()
    return jsonify({"success": True})

@app.route("/api/history", methods=["DELETE"])
@login_required
def clear_history():
    global history
    history = []
    save_history()
    return jsonify({"success": True})

@app.route("/api/stats")
@login_required
def get_stats():
    """Return statistics for dashboard"""
    stats = data.get("stats", {})
    return jsonify(stats)

@app.route("/api/export")
@login_required
def export_logs():
    """Export history as CSV"""
    import io
    output = io.StringIO()
    output.write("الوقت,الصفحة,الإجراء,الحالة,التفاصيل\n")
    for h in history:
        output.write(f"{h.get('time','')},{h.get('page','')},{h.get('action','')},{h.get('status','')},{h.get('details','')}\n")
    
    response = app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=history.csv'}
    )
    return response

@app.route("/api/keyword-rules", methods=["GET"])
@login_required
def get_keyword_rules():
    """Get keyword rules for AI"""
    rules = data.get("settings", {}).get("keyword_rules", [])
    return jsonify({"rules": rules})

@app.route("/api/keyword-rules", methods=["POST"])
@login_required
def add_keyword_rule():
    """Add a keyword rule"""
    keywords = request.json.get("keywords", [])
    reply = request.json.get("reply", "")
    if keywords and reply:
        data.setdefault("settings", {}).setdefault("keyword_rules", []).append({
            "keywords": keywords,
            "reply": reply
        })
        save_data()
    return jsonify({"success": True})

@app.route("/api/keyword-rules/<int:index>", methods=["DELETE"])
@login_required
def delete_keyword_rule(index):
    """Delete a keyword rule"""
    rules = data.get("settings", {}).get("keyword_rules", [])
    if 0 <= index < len(rules):
        rules.pop(index)
        save_data()
    return jsonify({"success": True})

@app.route("/api/filter-words", methods=["POST"])
@login_required
def update_filter_words():
    """Update blocked/required words"""
    word_type = request.json.get("type")  # "blocked" or "required"
    words = request.json.get("words", [])
    
    if word_type == "blocked":
        data.setdefault("settings", {})["blocked_words"] = words
    elif word_type == "required":
        data.setdefault("settings", {})["required_words"] = words
    
    save_data()
    return jsonify({"success": True})

# ============ Webhook ============
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("✅ Webhook verified!")
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook_handler():
    webhook_data = request.get_json()
    print(f"📩 Webhook: {json.dumps(webhook_data, indent=2)}")
    
    if webhook_data.get("object") == "page":
        for entry in webhook_data.get("entry", []):
            page_id = entry.get("id")
            
            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    value = change.get("value", {})
                    if value.get("item") == "comment" and value.get("verb") == "add":
                        comment_id = value.get("comment_id")
                        from_data = value.get("from", {})
                        user_id = from_data.get("id")
                        user_name = from_data.get("name", "Unknown")
                        post_id = value.get("post_id")
                        parent_id = value.get("parent_id")
                        comment_text = value.get("message", "")  # Get comment text for filtering/AI
                        
                        # Skip comments from the page itself (to avoid infinite loop)
                        if user_id == page_id:
                            print(f"⏭️ تخطي: تعليق من الصفحة نفسها ({user_name})")
                            continue
                        
                        print(f"💬 New comment from {user_name}: {comment_text[:50]}...")
                        reply_to_comment(comment_id, page_id, user_name, comment_text)
                        
                        # Only send private reply for top-level comments (not replies to replies)
                        # Check if parent_id equals post_id (means it's a direct comment on the post)
                        if parent_id == post_id:
                            send_private_reply(comment_id, page_id, user_name, comment_text)
                        else:
                            print(f"⏭️ تخطي رسالة خاصة: تعليق على تعليق (ليس تعليق أساسي)")
            
            for messaging in entry.get("messaging", []):
                sender_id = messaging.get("sender", {}).get("id")
                message = messaging.get("message", {})
                
                if message and sender_id != page_id:
                    reply_to_message(sender_id, page_id)
    
    return "OK", 200

# ============ Run ============
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Facebook Webhooks Server with Dashboard")
    print("=" * 50)
    
    load_data()
    load_processed()  # Load processed comments to prevent duplicates
    
    port = int(os.getenv("PORT", 5000))
    print(f"🌐 Server running on port {port}")
    print(f"📊 Dashboard: http://localhost:{port}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
