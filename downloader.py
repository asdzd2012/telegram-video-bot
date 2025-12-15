import os
import re
import yt_dlp
from config import MAX_FILE_SIZE, TEMP_DIR


# User agent to bypass restrictions
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


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


def get_video_info(url: str) -> dict | None:
    """Get video information without downloading."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': USER_AGENT,
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'No Title'),
                'description': info.get('description', '')[:500] if info.get('description') else 'No Description',
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'platform': detect_platform(url),
            }
    except Exception as e:
        print(f"Error getting video info: {e}")
        return None


def download_video(url: str) -> dict | None:
    """
    Download video from URL.
    Returns dict with file_path, title, description or None on failure.
    """
    # Create temp directory if not exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Clean filename
    output_template = os.path.join(TEMP_DIR, '%(id)s.%(ext)s')
    
    # Base options that work for most platforms
    ydl_opts = {
        'format': 'best[filesize<50M]/best[height<=720]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        # Important for YouTube Shorts and age-restricted content
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls'],
            }
        },
        # Cookie handling
        'cookiebrowser': None,
        # Retry settings
        'retries': 3,
        'fragment_retries': 3,
        # Don't check certificates (helps with some servers)
        'nocheckcertificate': True,
    }
    
    # Detect platform for specific options
    platform = detect_platform(url)
    
    # TikTok specific options
    if platform == 'tiktok':
        ydl_opts['extractor_args'] = {
            'tiktok': {
                'api_hostname': 'api22-normal-c-useast2a.tiktokv.com',
            }
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Get the downloaded file path
            if info.get('requested_downloads'):
                file_path = info['requested_downloads'][0]['filepath']
            else:
                video_id = info.get('id', 'video')
                ext = info.get('ext', 'mp4')
                file_path = os.path.join(TEMP_DIR, f"{video_id}.{ext}")
            
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
                'uploader': info.get('uploader', 'Unknown'),
                'platform': platform,
            }
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        print(f"Download error: {error_msg}")
        
        if "Private video" in error_msg:
            return {'error': 'الفيديو خاص ومش متاح للتحميل'}
        elif "Video unavailable" in error_msg:
            return {'error': 'الفيديو مش موجود أو تم حذفه'}
        elif "Sign in" in error_msg or "age" in error_msg.lower():
            return {'error': 'الفيديو محظور أو يحتاج تسجيل دخول. جرب فيديو تاني.'}
        elif "geo" in error_msg.lower() or "country" in error_msg.lower():
            return {'error': 'الفيديو محظور في منطقتنا'}
        else:
            return {'error': f'فشل التحميل. تأكد إن الرابط صحيح وجرب تاني.'}
    except Exception as e:
        print(f"General error: {str(e)}")
        return {'error': f'حصل خطأ. جرب تاني أو استخدم رابط مختلف.'}


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
