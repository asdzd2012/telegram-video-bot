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


# ==================== TikTok - TikWM API ====================

async def download_tiktok_tikwm(url: str) -> dict | None:
    """Download TikTok video using TikWM API (FREE & UNLIMITED)."""
    try:
        async with aiohttp.ClientSession() as session:
            api_url = "https://tikwm.com/api/"
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
                        video_url = video_data.get('hdplay') or video_data.get('play')
                        if video_url:
                            return await download_file(
                                video_url, url,
                                title=video_data.get('title', 'TikTok Video'),
                                uploader=video_data.get('author', {}).get('nickname', ''),
                                platform='tiktok'
                            )
    except Exception as e:
        print(f"TikWM error: {e}")
    return None


# ==================== YouTube - Multiple Methods ====================

async def download_youtube_api(url: str) -> dict | None:
    """Try multiple free YouTube download APIs."""
    
    # Method 1: Try loader.to API (free, no API key)
    try:
        result = await try_loaderto_api(url)
        if result and 'file_path' in result:
            return result
    except Exception as e:
        print(f"Loader.to failed: {e}")
    
    # Method 2: Try ssyoutube API
    try:
        result = await try_ssyoutube_api(url)
        if result and 'file_path' in result:
            return result
    except Exception as e:
        print(f"SSYoutube failed: {e}")
    
    return None


async def try_loaderto_api(url: str) -> dict | None:
    """Try loader.to free API for YouTube."""
    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Get download link
            api_url = "https://loader.to/api/button/"
            params = {
                "url": url,
                "f": "mp4",  # format
                "q": "720"   # quality
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            
            async with session.get(api_url, params=params, headers=headers, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    download_url = data.get('download_url') or data.get('url')
                    if download_url:
                        return await download_file(
                            download_url, url,
                            title=data.get('title', 'YouTube Video'),
                            uploader='',
                            platform='youtube'
                        )
    except Exception as e:
        print(f"Loader.to error: {e}")
    return None


async def try_ssyoutube_api(url: str) -> dict | None:
    """Try ssyoutube.com style API."""
    # Extract video ID
    video_id = extract_youtube_id(url)
    if not video_id:
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            # Try to get video info from multiple sources
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
            }
            
            # Try api.vevioz.com (a working YouTube API)
            api_url = f"https://api.vevioz.com/api/button/videos?url={url}"
            
            async with session.get(api_url, headers=headers, timeout=30, allow_redirects=True) as response:
                if response.status == 200:
                    text = await response.text()
                    
                    # Parse the response for download links
                    # Look for MP4 links
                    import re
                    mp4_pattern = r'href="(https://[^"]+\.mp4[^"]*)"'
                    matches = re.findall(mp4_pattern, text)
                    
                    if matches:
                        download_url = matches[0]
                        return await download_file(
                            download_url, url,
                            title='YouTube Video',
                            uploader='',
                            platform='youtube'
                        )
    except Exception as e:
        print(f"SSYoutube API error: {e}")
    return None


def extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11})(?:[&?/]|$)',
        r'youtu\.be/([0-9A-Za-z_-]{11})',
        r'shorts/([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


# ==================== Shared Download Function ====================

async def download_file(download_url: str, original_url: str, title: str, uploader: str, platform: str) -> dict | None:
    """Download file from direct URL."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
            
            async with session.get(download_url, headers=headers, timeout=180) as response:
                if response.status == 200:
                    file_id = hashlib.md5(original_url.encode()).hexdigest()[:12]
                    file_path = os.path.join(TEMP_DIR, f"{file_id}.mp4")
                    
                    # Download in chunks
                    total_size = 0
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            total_size += len(chunk)
                            if total_size > MAX_FILE_SIZE:
                                f.close()
                                os.remove(file_path)
                                return {'error': 'الفيديو كبير جداً (أكثر من 50MB)'}
                            f.write(chunk)
                    
                    return {
                        'file_path': file_path,
                        'title': title[:200] if title else 'Video',
                        'description': '',
                        'uploader': uploader,
                        'platform': platform,
                    }
    except Exception as e:
        print(f"Download file error: {e}")
    return None


# ==================== Sync Wrappers ====================

def download_tiktok_sync(url: str) -> dict | None:
    """Sync wrapper for TikTok download."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(download_tiktok_tikwm(url))
        loop.close()
        return result
    except:
        return None


def download_youtube_sync(url: str) -> dict | None:
    """Sync wrapper for YouTube download."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(download_youtube_api(url))
        loop.close()
        return result
    except:
        return None


# ==================== yt-dlp Fallback ====================

def download_with_ytdlp(url: str) -> dict | None:
    """Fallback to yt-dlp for Instagram and failed downloads."""
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
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36',
        },
    }
    
    if platform == 'youtube':
        ydl_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'ios']}}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            file_path = None
            if info.get('requested_downloads'):
                file_path = info['requested_downloads'][0].get('filepath')
            if not file_path:
                file_path = os.path.join(TEMP_DIR, f"{info.get('id', 'video')}.{info.get('ext', 'mp4')}")
            
            if not os.path.exists(file_path):
                base = os.path.splitext(file_path)[0]
                for ext in ['.mp4', '.webm', '.mkv']:
                    if os.path.exists(base + ext):
                        file_path = base + ext
                        break
            
            if os.path.exists(file_path):
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    os.remove(file_path)
                    return {'error': 'الفيديو كبير جداً'}
                return {
                    'file_path': file_path,
                    'title': info.get('title', 'Video'),
                    'description': (info.get('description') or '')[:400],
                    'uploader': info.get('uploader') or '',
                    'platform': platform,
                }
    except yt_dlp.utils.DownloadError as e:
        if 'sign in' in str(e).lower():
            return {'error': 'الفيديو يحتاج تسجيل دخول'}
    except:
        pass
    return None


# ==================== Main Download Function ====================

def download_video(url: str) -> dict | None:
    """Main download function."""
    platform = detect_platform(url)
    
    # TikTok
    if platform == 'tiktok':
        print("TikTok → TikWM API")
        result = download_tiktok_sync(url)
        if result and 'file_path' in result:
            return result
        
        # Fallback
        result = download_with_ytdlp(url)
        if result:
            return result
        return {'error': 'فشل تحميل TikTok'}
    
    # YouTube
    elif platform == 'youtube':
        print("YouTube → Free APIs")
        result = download_youtube_sync(url)
        if result and 'file_path' in result:
            return result
        
        # Fallback to yt-dlp
        print("YouTube APIs failed, trying yt-dlp...")
        result = download_with_ytdlp(url)
        if result:
            return result
        return {'error': 'فشل تحميل YouTube. جرب رابط تاني.'}
    
    # Instagram & others
    else:
        result = download_with_ytdlp(url)
        if result:
            return result
        return {'error': 'فشل التحميل'}


def cleanup_file(file_path: str):
    """Remove downloaded file."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass


def extract_url(text: str) -> str | None:
    """Extract URL from message text."""
    match = re.search(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
    return match.group(0) if match else None
