import os
import re
import yt_dlp
from config import MAX_FILE_SIZE, TEMP_DIR


def detect_platform(url: str) -> str | None:
    """Detect the platform from URL."""
    url_lower = url.lower()
    
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "tiktok.com" in url_lower or "vm.tiktok" in url_lower:
        return "tiktok"
    elif "instagram.com" in url_lower:
        return "instagram"
    
    return None


def download_video(url: str) -> dict | None:
    """
    Download video from URL.
    Returns dict with file_path, title, description or None on failure.
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    output_template = os.path.join(TEMP_DIR, '%(id)s.%(ext)s')
    
    platform = detect_platform(url)
    
    # Simple, tested options
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'retries': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36',
        },
    }
    
    # TikTok specific - don't use FFmpeg conversion
    if platform == 'tiktok':
        pass  # Default options work for TikTok
    
    # YouTube specific
    elif platform == 'youtube':
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'ios'],
            }
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Get file path
            file_path = None
            if info.get('requested_downloads'):
                file_path = info['requested_downloads'][0].get('filepath')
            
            if not file_path:
                video_id = info.get('id', 'video')
                ext = info.get('ext', 'mp4')
                file_path = os.path.join(TEMP_DIR, f"{video_id}.{ext}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                # Try to find with different extension
                base = os.path.splitext(file_path)[0]
                for ext in ['.mp4', '.webm', '.mkv', '.mov']:
                    test_path = base + ext
                    if os.path.exists(test_path):
                        file_path = test_path
                        break
            
            if not os.path.exists(file_path):
                return {'error': 'فشل حفظ الفيديو'}
            
            # Check size
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                os.remove(file_path)
                return {'error': f'الفيديو كبير ({file_size // (1024*1024)}MB). الحد 50MB'}
            
            return {
                'file_path': file_path,
                'title': info.get('title', 'Video'),
                'description': (info.get('description') or '')[:400],
                'uploader': info.get('uploader') or info.get('creator') or '',
                'platform': platform,
            }
            
    except yt_dlp.utils.DownloadError as e:
        error = str(e).lower()
        print(f"DownloadError: {e}")
        
        if 'private' in error:
            return {'error': 'الفيديو خاص'}
        elif 'unavailable' in error or 'not available' in error:
            return {'error': 'الفيديو غير متاح'}
        elif 'sign in' in error or 'login' in error or 'age' in error:
            return {'error': 'الفيديو يحتاج تسجيل دخول (YouTube بيحظر السيرفرات)'}
        elif 'geo' in error:
            return {'error': 'الفيديو محظور جغرافياً'}
        else:
            return {'error': 'فشل التحميل - جرب رابط تاني'}
            
    except Exception as e:
        print(f"General error: {e}")
        return {'error': 'حصل خطأ - جرب تاني'}


def cleanup_file(file_path: str):
    """Remove downloaded file after sending."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass


def extract_url(text: str) -> str | None:
    """Extract URL from message text."""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None
