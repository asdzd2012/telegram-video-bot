import os
import re
import aiohttp
import asyncio
import hashlib
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


async def download_tiktok_tikwm(url: str) -> dict | None:
    """
    Download TikTok video using TikWM API (FREE & UNLIMITED).
    API: https://tikwm.com/api/
    """
    try:
        async with aiohttp.ClientSession() as session:
            # TikWM API endpoint
            api_url = "https://tikwm.com/api/"
            
            # POST request with video URL
            data = {"url": url, "hd": 1}
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            
            async with session.post(api_url, data=data, headers=headers, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get('code') == 0:
                        video_data = result.get('data', {})
                        
                        # Get video URL (HD first, then normal play)
                        video_url = video_data.get('hdplay') or video_data.get('play')
                        
                        if video_url:
                            # Download the actual video file
                            file_result = await download_file(
                                video_url,
                                url,
                                title=video_data.get('title', 'TikTok Video'),
                                uploader=video_data.get('author', {}).get('nickname', '')
                            )
                            return file_result
                        else:
                            print("TikWM: No video URL found in response")
                    else:
                        print(f"TikWM API error: {result.get('msg', 'Unknown error')}")
                else:
                    print(f"TikWM API returned status {response.status}")
                    
    except asyncio.TimeoutError:
        print("TikWM API timeout")
    except Exception as e:
        print(f"TikWM error: {e}")
    
    return None


async def download_file(download_url: str, original_url: str, title: str = 'Video', uploader: str = '') -> dict | None:
    """Download file from direct URL."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://tikwm.com/",
            }
            
            async with session.get(download_url, headers=headers, timeout=120) as response:
                if response.status == 200:
                    # Generate unique filename
                    file_id = hashlib.md5(original_url.encode()).hexdigest()[:12]
                    file_path = os.path.join(TEMP_DIR, f"{file_id}.mp4")
                    
                    # Download content
                    content = await response.read()
                    
                    # Check size
                    if len(content) > MAX_FILE_SIZE:
                        return {'error': 'الفيديو كبير جداً (أكثر من 50MB)'}
                    
                    # Save file
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    return {
                        'file_path': file_path,
                        'title': title[:200] if title else 'TikTok Video',
                        'description': '',
                        'uploader': uploader,
                        'platform': 'tiktok',
                    }
                else:
                    print(f"Download failed with status {response.status}")
                    
    except Exception as e:
        print(f"Download file error: {e}")
    
    return None


def download_tiktok_sync(url: str) -> dict | None:
    """Synchronous wrapper for async TikTok download."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(download_tiktok_tikwm(url))
        loop.close()
        return result
    except Exception as e:
        print(f"Async error: {e}")
        return None


def download_with_ytdlp(url: str) -> dict | None:
    """Download video using yt-dlp (for YouTube/Instagram)."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    output_template = os.path.join(TEMP_DIR, '%(id)s.%(ext)s')
    
    platform = detect_platform(url)
    
    ydl_opts = {
        'format': 'best[ext=mp4][height<=720]/best[height<=720]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'retries': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
        },
    }
    
    # YouTube specific options
    if platform == 'youtube':
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
            }
        }
        # Check for cookies
        cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
    
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
            
            # Find file if not exists
            if not os.path.exists(file_path):
                base = os.path.splitext(file_path)[0]
                for ext in ['.mp4', '.webm', '.mkv']:
                    if os.path.exists(base + ext):
                        file_path = base + ext
                        break
            
            if not os.path.exists(file_path):
                return {'error': 'فشل حفظ الفيديو'}
            
            # Check size
            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                os.remove(file_path)
                return {'error': 'الفيديو كبير جداً (أكثر من 50MB)'}
            
            return {
                'file_path': file_path,
                'title': info.get('title', 'Video'),
                'description': (info.get('description') or '')[:400],
                'uploader': info.get('uploader') or '',
                'platform': platform,
            }
            
    except yt_dlp.utils.DownloadError as e:
        error = str(e).lower()
        print(f"yt-dlp error: {e}")
        
        if 'sign in' in error or 'age' in error or 'confirm' in error:
            return {'error': 'YouTube يحتاج cookies.txt - راجع README'}
        elif 'private' in error:
            return {'error': 'الفيديو خاص'}
        elif 'unavailable' in error:
            return {'error': 'الفيديو غير متاح'}
        else:
            return {'error': 'فشل التحميل'}
    except Exception as e:
        print(f"Error: {e}")
        return {'error': 'حصل خطأ'}


def download_video(url: str) -> dict | None:
    """
    Main download function.
    - TikTok: Uses TikWM API (FREE & UNLIMITED)
    - YouTube/Instagram: Uses yt-dlp
    """
    platform = detect_platform(url)
    
    # TikTok: Use TikWM API (free, unlimited, no API key needed!)
    if platform == 'tiktok':
        print("TikTok detected - using TikWM API (free & unlimited)")
        result = download_tiktok_sync(url)
        
        if result and 'file_path' in result:
            return result
        
        # Fallback to yt-dlp if TikWM fails
        print("TikWM failed, trying yt-dlp...")
        result = download_with_ytdlp(url)
        if result:
            return result
        
        return {'error': 'فشل تحميل فيديو TikTok - جرب رابط تاني'}
    
    # YouTube and Instagram: Use yt-dlp
    else:
        result = download_with_ytdlp(url)
        if result:
            return result
        return {'error': 'فشل التحميل'}


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
