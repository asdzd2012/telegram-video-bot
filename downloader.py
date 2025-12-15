import os
import re
import aiohttp
import asyncio
import yt_dlp
from config import MAX_FILE_SIZE, TEMP_DIR


# Cobalt API endpoints (public instances)
COBALT_APIS = [
    "https://api.cobalt.tools",
    "https://cobalt-api.kwiatekmiki.com",
]


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


async def download_with_cobalt(url: str) -> dict | None:
    """Download video using Cobalt API."""
    
    for api_base in COBALT_APIS:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                }
                
                payload = {
                    'url': url,
                    'vQuality': '720',
                    'filenamePattern': 'basic',
                    'isAudioOnly': False,
                }
                
                async with session.post(
                    f"{api_base}/api/json",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('status') == 'stream' or data.get('status') == 'redirect':
                            download_url = data.get('url')
                            if download_url:
                                return await download_file_from_url(download_url, url)
                        
                        elif data.get('status') == 'picker':
                            # Multiple options available, take the first video
                            picker = data.get('picker', [])
                            for item in picker:
                                if item.get('type') == 'video':
                                    download_url = item.get('url')
                                    if download_url:
                                        return await download_file_from_url(download_url, url)
                        
                        elif data.get('status') == 'error':
                            error_text = data.get('text', 'Unknown error')
                            print(f"Cobalt error: {error_text}")
                            continue
                    else:
                        print(f"Cobalt API {api_base} returned status {response.status}")
                        continue
                        
        except asyncio.TimeoutError:
            print(f"Cobalt API {api_base} timeout")
            continue
        except Exception as e:
            print(f"Cobalt API {api_base} error: {e}")
            continue
    
    return None


async def download_file_from_url(download_url: str, original_url: str) -> dict | None:
    """Download file from direct URL."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                download_url,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status == 200:
                    # Generate filename
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > MAX_FILE_SIZE:
                        return {'error': f'الفيديو كبير جداً. الحد الأقصى 50MB'}
                    
                    # Get filename from headers or generate one
                    import hashlib
                    file_id = hashlib.md5(original_url.encode()).hexdigest()[:12]
                    file_path = os.path.join(TEMP_DIR, f"{file_id}.mp4")
                    
                    # Download file
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    # Check file size
                    file_size = os.path.getsize(file_path)
                    if file_size > MAX_FILE_SIZE:
                        os.remove(file_path)
                        return {'error': f'الفيديو كبير جداً ({file_size / (1024*1024):.1f}MB). الحد الأقصى 50MB'}
                    
                    return {
                        'file_path': file_path,
                        'title': 'Video',
                        'description': '',
                        'duration': 0,
                        'uploader': '',
                        'platform': detect_platform(original_url),
                    }
    except Exception as e:
        print(f"Download error: {e}")
        return None
    
    return None


def download_video_sync(url: str) -> dict | None:
    """Synchronous wrapper for async download with Cobalt."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(download_with_cobalt(url))
        loop.close()
        return result
    except Exception as e:
        print(f"Async wrapper error: {e}")
        return None


def download_with_ytdlp(url: str) -> dict | None:
    """Fallback download using yt-dlp."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    output_template = os.path.join(TEMP_DIR, '%(id)s.%(ext)s')
    
    platform = detect_platform(url)
    
    ydl_opts = {
        'format': 'best[height<=720][ext=mp4]/best[height<=720]/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        },
        'nocheckcertificate': True,
        'retries': 3,
    }
    
    if platform == 'youtube':
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['ios', 'android'],
            }
        }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if info.get('requested_downloads'):
                file_path = info['requested_downloads'][0]['filepath']
            else:
                video_id = info.get('id', 'video')
                ext = info.get('ext', 'mp4')
                file_path = os.path.join(TEMP_DIR, f"{video_id}.{ext}")
            
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > MAX_FILE_SIZE:
                    os.remove(file_path)
                    return {'error': f'الفيديو كبير جداً ({file_size / (1024*1024):.1f}MB). الحد الأقصى 50MB'}
                
                return {
                    'file_path': file_path,
                    'title': info.get('title', 'No Title'),
                    'description': info.get('description', '')[:500] if info.get('description') else '',
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                    'platform': platform,
                }
    except Exception as e:
        print(f"yt-dlp error: {e}")
        return None
    
    return None


def download_video(url: str) -> dict | None:
    """
    Download video from URL.
    First tries Cobalt API, then falls back to yt-dlp.
    """
    platform = detect_platform(url)
    
    # Try Cobalt API first (works better for YouTube and TikTok on servers)
    print(f"Trying Cobalt API for {platform}...")
    result = download_video_sync(url)
    
    if result and 'file_path' in result:
        # Get video info using yt-dlp (without downloading)
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                result['title'] = info.get('title', 'Video')
                result['description'] = info.get('description', '')[:500] if info.get('description') else ''
                result['uploader'] = info.get('uploader', info.get('creator', ''))
        except:
            pass
        return result
    
    # Fallback to yt-dlp
    print("Cobalt failed, trying yt-dlp...")
    result = download_with_ytdlp(url)
    
    if result:
        return result
    
    return {'error': 'فشل تحميل الفيديو. الرابط قد يكون غير صحيح أو الفيديو محمي.'}


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
