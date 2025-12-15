import os
import re
import random
import yt_dlp
from config import MAX_FILE_SIZE, TEMP_DIR


# Multiple User Agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


def get_user_agent():
    return random.choice(USER_AGENTS)


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


def get_youtube_opts(output_template: str) -> dict:
    """Get yt-dlp options optimized for YouTube."""
    return {
        'format': 'best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web'],
                'player_skip': ['webpage', 'configs'],
            }
        },
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'retries': 5,
        'fragment_retries': 5,
        'skip_download': False,
        'merge_output_format': 'mp4',
        # Try to bypass age gate
        'age_limit': None,
    }


def get_tiktok_opts(output_template: str) -> dict:
    """Get yt-dlp options optimized for TikTok."""
    return {
        'format': 'best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.tiktok.com/',
        },
        'nocheckcertificate': True,
        'retries': 5,
        'fragment_retries': 5,
        'extractor_args': {
            'tiktok': {
                'api_hostname': 'api16-normal-c-useast1a.tiktokv.com',
            }
        },
    }


def get_instagram_opts(output_template: str) -> dict:
    """Get yt-dlp options for Instagram."""
    return {
        'format': 'best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': get_user_agent(),
        },
        'nocheckcertificate': True,
        'retries': 3,
    }


def get_default_opts(output_template: str) -> dict:
    """Get default yt-dlp options."""
    return {
        'format': 'best[filesize<50M]/best[height<=720]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': get_user_agent(),
        },
        'nocheckcertificate': True,
        'retries': 3,
    }


def download_video(url: str) -> dict | None:
    """
    Download video from URL.
    Returns dict with file_path, title, description or None on failure.
    """
    # Create temp directory if not exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Clean filename
    output_template = os.path.join(TEMP_DIR, '%(id)s.%(ext)s')
    
    # Detect platform
    platform = detect_platform(url)
    
    # Get platform-specific options
    if platform == 'youtube':
        ydl_opts = get_youtube_opts(output_template)
    elif platform == 'tiktok':
        ydl_opts = get_tiktok_opts(output_template)
    elif platform == 'instagram':
        ydl_opts = get_instagram_opts(output_template)
    else:
        ydl_opts = get_default_opts(output_template)
    
    # Try multiple times with different options
    last_error = None
    
    for attempt in range(3):
        try:
            # On retry, modify some options
            if attempt > 0:
                ydl_opts['http_headers']['User-Agent'] = get_user_agent()
                if platform == 'youtube' and attempt == 1:
                    # Try different player clients
                    ydl_opts['extractor_args']['youtube']['player_client'] = ['android', 'web']
                elif platform == 'youtube' and attempt == 2:
                    # Last resort - try tv_embedded
                    ydl_opts['extractor_args']['youtube']['player_client'] = ['tv_embedded', 'android']
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Get the downloaded file path
                if info.get('requested_downloads'):
                    file_path = info['requested_downloads'][0]['filepath']
                elif info.get('_filename'):
                    file_path = info['_filename']
                else:
                    video_id = info.get('id', 'video')
                    ext = info.get('ext', 'mp4')
                    file_path = os.path.join(TEMP_DIR, f"{video_id}.{ext}")
                
                # Try to find the file with mp4 extension
                if not os.path.exists(file_path):
                    base_path = os.path.splitext(file_path)[0]
                    for ext in ['.mp4', '.webm', '.mkv']:
                        if os.path.exists(base_path + ext):
                            file_path = base_path + ext
                            break
                
                # Check file size
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    if file_size > MAX_FILE_SIZE:
                        os.remove(file_path)
                        return {
                            'error': f'الفيديو كبير جداً ({file_size / (1024*1024):.1f}MB). الحد الأقصى 50MB'
                        }
                    
                    return {
                        'file_path': file_path,
                        'title': info.get('title', 'No Title'),
                        'description': info.get('description', '')[:500] if info.get('description') else 'No Description',
                        'duration': info.get('duration', 0),
                        'uploader': info.get('uploader', info.get('creator', 'Unknown')),
                        'platform': platform,
                    }
                else:
                    last_error = "الملف لم يتم تحميله"
                    continue
                    
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            print(f"Attempt {attempt + 1} failed: {error_msg}")
            last_error = error_msg
            continue
        except Exception as e:
            print(f"Attempt {attempt + 1} general error: {str(e)}")
            last_error = str(e)
            continue
    
    # All attempts failed
    if last_error:
        error_lower = last_error.lower()
        if "private" in error_lower:
            return {'error': 'الفيديو خاص ومش متاح للتحميل'}
        elif "unavailable" in error_lower or "not available" in error_lower:
            return {'error': 'الفيديو مش موجود أو تم حذفه'}
        elif "sign in" in error_lower or "login" in error_lower:
            return {'error': 'الفيديو يحتاج تسجيل دخول'}
        elif "age" in error_lower or "confirm" in error_lower:
            return {'error': 'الفيديو محظور للأعمار أو يحتاج تأكيد'}
        elif "geo" in error_lower or "country" in error_lower:
            return {'error': 'الفيديو محظور في منطقتنا'}
        elif "copyright" in error_lower:
            return {'error': 'الفيديو محذوف بسبب حقوق الملكية'}
    
    return {'error': 'فشل تحميل الفيديو بعد عدة محاولات. جرب رابط تاني.'}


def cleanup_file(file_path: str):
    """Remove downloaded file after sending."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error cleaning up file: {e}")


def extract_url(text: str) -> str | None:
    """Extract URL from message text."""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None
