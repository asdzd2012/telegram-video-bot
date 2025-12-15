import os
import re
import yt_dlp
from config import MAX_FILE_SIZE, TEMP_DIR


def detect_platform(url: str) -> str | None:
    """Detect the platform from URL."""
    url_lower = url.lower()
    
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "tiktok.com" in url_lower:
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
    
    ydl_opts = {
        'format': 'best[filesize<50M]/best[height<=720]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
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
                'platform': detect_platform(url),
            }
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Private video" in error_msg:
            return {'error': 'الفيديو خاص ومش متاح للتحميل'}
        elif "Video unavailable" in error_msg:
            return {'error': 'الفيديو مش موجود أو تم حذفه'}
        elif "Sign in" in error_msg:
            return {'error': 'الفيديو يحتاج تسجيل دخول'}
        else:
            return {'error': f'فشل التحميل: {error_msg[:100]}'}
    except Exception as e:
        return {'error': f'حصل خطأ: {str(e)[:100]}'}


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
