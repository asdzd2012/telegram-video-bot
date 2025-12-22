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


# Placeholder function for import compatibility
def set_user_cookies(user_id: int, cookies_content: str) -> bool:
    """This function is handled by bot.py now."""
    pass


# ==================== TikTok - TikWM API (FREE & UNLIMITED) ====================

async def download_tiktok_tikwm(url: str) -> dict | None:
    """Download TikTok video using TikWM API."""
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


# ==================== Shared Download Function ====================

async def download_file(download_url: str, original_url: str, title: str, uploader: str, platform: str) -> dict | None:
    """Download file from direct URL."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            async with session.get(download_url, headers=headers, timeout=180) as response:
                if response.status == 200:
                    file_id = hashlib.md5(original_url.encode()).hexdigest()[:12]
                    file_path = os.path.join(TEMP_DIR, f"{file_id}.mp4")
                    
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
        print(f"Download error: {e}")
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


# ==================== Instagram - Free API (No Login Required) ====================

async def download_instagram_api(url: str) -> dict | None:
    """Download Instagram video using free APIs (no login/cookies required)."""
    
    # Try multiple free Instagram APIs
    apis = [
        _try_instagram_saveig,
        _try_instagram_snapinsta,
        _try_instagram_igdownloader,
    ]
    
    for api_func in apis:
        try:
            result = await api_func(url)
            if result and 'file_path' in result:
                return result
        except Exception as e:
            print(f"Instagram API error: {e}")
            continue
    
    return None


async def _try_instagram_saveig(url: str) -> dict | None:
    """Try saveig.app API."""
    try:
        async with aiohttp.ClientSession() as session:
            # First, get the page to extract any needed tokens
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://saveig.app",
                "Referer": "https://saveig.app/en",
            }
            
            api_url = "https://saveig.app/api/ajaxSearch"
            data = {
                "q": url,
                "t": "media",
                "lang": "en",
            }
            
            async with session.post(api_url, data=data, headers=headers, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('status') == 'ok':
                        html_content = result.get('data', '')
                        
                        # Parse the HTML to extract video URL and info
                        import re
                        
                        # Extract video download link
                        video_match = re.search(r'href="([^"]*)"[^>]*class="[^"]*download-media[^"]*"', html_content)
                        if not video_match:
                            # Try alternative pattern
                            video_match = re.search(r'<a[^>]*href="(https://[^"]+\.mp4[^"]*)"', html_content)
                        
                        if video_match:
                            video_url = video_match.group(1)
                            
                            # Extract title/description
                            title = "Instagram Video"
                            desc_match = re.search(r'<p[^>]*class="[^"]*desc[^"]*"[^>]*>([^<]+)</p>', html_content)
                            if desc_match:
                                title = desc_match.group(1).strip()[:200]
                            
                            # Download the video
                            return await download_file(
                                video_url, url,
                                title=title if title else "Instagram Video",
                                uploader="",
                                platform='instagram'
                            )
    except Exception as e:
        print(f"saveig error: {e}")
    return None


async def _try_instagram_snapinsta(url: str) -> dict | None:
    """Try snapinsta.app API."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://snapinsta.app",
                "Referer": "https://snapinsta.app/",
            }
            
            api_url = "https://snapinsta.app/api/ajaxSearch"
            data = {
                "q": url,
                "t": "media",
                "lang": "en",
            }
            
            async with session.post(api_url, data=data, headers=headers, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('status') == 'ok':
                        html_content = result.get('data', '')
                        
                        import re
                        
                        # Extract video download link
                        video_match = re.search(r'href="(https://[^"]+)"[^>]*>.*?Download', html_content, re.DOTALL)
                        if not video_match:
                            video_match = re.search(r'<a[^>]*href="(https://[^"]+\.mp4[^"]*)"', html_content)
                        
                        if video_match:
                            video_url = video_match.group(1)
                            
                            # Extract caption
                            title = "Instagram Video"
                            caption_match = re.search(r'class="[^"]*caption[^"]*"[^>]*>([^<]+)</div>', html_content)
                            if caption_match:
                                title = caption_match.group(1).strip()[:200]
                            
                            return await download_file(
                                video_url, url,
                                title=title if title else "Instagram Video",
                                uploader="",
                                platform='instagram'
                            )
    except Exception as e:
        print(f"snapinsta error: {e}")
    return None


async def _try_instagram_igdownloader(url: str) -> dict | None:
    """Try igdownloader.app API."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            # Try using a direct approach by parsing Instagram's embed
            # Get the embed URL which often works without login
            shortcode_match = re.search(r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
            if shortcode_match:
                shortcode = shortcode_match.group(1)
                embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
                
                async with session.get(embed_url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Try to find video URL in embed page
                        video_patterns = [
                            r'"video_url":"([^"]+)"',
                            r'class="Content"[^>]*>.*?src="([^"]+\.mp4[^"]*)"',
                            r'"contentUrl":\s*"([^"]+)"',
                        ]
                        
                        for pattern in video_patterns:
                            match = re.search(pattern, html, re.DOTALL)
                            if match:
                                video_url = match.group(1).replace('\\u0026', '&').replace('\\/', '/')
                                
                                # Get caption
                                title = "Instagram Video"
                                caption_match = re.search(r'"caption":\s*"([^"]*)"', html)
                                if caption_match:
                                    title = caption_match.group(1)[:200]
                                
                                # Get author
                                author = ""
                                author_match = re.search(r'"username":\s*"([^"]+)"', html)
                                if author_match:
                                    author = "@" + author_match.group(1)
                                
                                return await download_file(
                                    video_url, url,
                                    title=title if title else "Instagram Video",
                                    uploader=author,
                                    platform='instagram'
                                )
    except Exception as e:
        print(f"igdownloader error: {e}")
    return None


def download_instagram_sync(url: str) -> dict | None:
    """Sync wrapper for Instagram download."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(download_instagram_api(url))
        loop.close()
        return result
    except Exception as e:
        print(f"Instagram sync error: {e}")
        return None


# ==================== yt-dlp for YouTube & Instagram ====================

def download_with_ytdlp(url: str, user_cookies_path: str = None) -> dict | None:
    """Download using yt-dlp with optional user cookies."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    output_template = os.path.join(TEMP_DIR, '%(id)s.%(ext)s')
    
    platform = detect_platform(url)
    
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best',
        'outtmpl': output_template,
        'quiet': False,
        'no_warnings': False,
        'nocheckcertificate': True,
        'retries': 3,
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
    }
    
    # YouTube settings
    if platform == 'youtube':
        # Use 'tv' client - it works better with PO Token plugin
        # The bgutil-ytdlp-pot-provider plugin will handle PO Token automatically
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['tv', 'web'],
            }
        }
        # Flexible format selection
        ydl_opts['format'] = 'best[height<=720]/bestvideo[height<=720]+bestaudio/best'
        
        # Use user's cookies if provided
        if user_cookies_path:
            print(f"[DEBUG] Cookies path provided: {user_cookies_path}")
            if os.path.exists(user_cookies_path):
                # Check cookies file size
                file_size = os.path.getsize(user_cookies_path)
                print(f"[DEBUG] Cookies file exists, size: {file_size} bytes")
                
                # Read first line to verify format
                with open(user_cookies_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    print(f"[DEBUG] Cookies first line: {first_line[:50]}...")
                
                ydl_opts['cookiefile'] = user_cookies_path
                print(f"[DEBUG] Cookies file set in yt-dlp options")
            else:
                print(f"[DEBUG] Cookies file NOT FOUND at: {user_cookies_path}")
        else:
            print(f"[DEBUG] No cookies path provided")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            file_path = None
            if info.get('requested_downloads'):
                file_path = info['requested_downloads'][0].get('filepath')
            if not file_path:
                file_path = os.path.join(TEMP_DIR, f"{info.get('id', 'video')}.{info.get('ext', 'mp4')}")
            
            # Find file
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
        error = str(e).lower()
        print(f"yt-dlp error: {e}")
        
        if 'sign in' in error or 'age' in error or 'confirm' in error:
            if platform == 'youtube':
                return {'error': '⚠️ الـ Cookies منتهية الصلاحية أو غير صالحة.\n\nاستخدم /setcookies لتحديثها.'}
        elif 'private' in error:
            return {'error': 'الفيديو خاص'}
        elif 'unavailable' in error:
            return {'error': 'الفيديو غير متاح'}
            
        return {'error': 'فشل التحميل'}
    except Exception as e:
        print(f"Error: {e}")
    return None


# ==================== Main Download Function ====================

def download_video(url: str, user_cookies_path: str = None) -> dict | None:
    """Main download function with user cookies support."""
    platform = detect_platform(url)
    
    # TikTok: TikWM API (free & unlimited)
    if platform == 'tiktok':
        print("TikTok → TikWM API")
        result = download_tiktok_sync(url)
        if result and 'file_path' in result:
            return result
        
        # Fallback to yt-dlp
        result = download_with_ytdlp(url)
        if result:
            return result
        return {'error': 'فشل تحميل TikTok - جرب رابط تاني'}
    
    # YouTube: yt-dlp with user cookies
    elif platform == 'youtube':
        print(f"YouTube → yt-dlp (cookies: {user_cookies_path})")
        result = download_with_ytdlp(url, user_cookies_path)
        if result:
            return result
        return {'error': 'فشل تحميل YouTube'}
    
    # Instagram: Free API first, then yt-dlp fallback
    else:
        print("Instagram → Free API (no login required)")
        result = download_instagram_sync(url)
        if result and 'file_path' in result:
            return result
        
        # Fallback to yt-dlp (may fail without cookies)
        print("Instagram → Fallback to yt-dlp")
        result = download_with_ytdlp(url)
        if result:
            return result
        return {'error': 'فشل تحميل Instagram - قد يكون الفيديو خاص أو غير متاح'}


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
