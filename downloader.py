import os
import re
import aiohttp
import asyncio
import hashlib
import json
import yt_dlp
from config import MAX_FILE_SIZE, TEMP_DIR, RAPIDAPI_KEY


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


# ==================== Instagram - RapidAPI + Fallbacks ====================

async def download_instagram_api(url: str) -> dict | None:
    """Download Instagram video using RapidAPI (primary) or fallback methods."""
    
    # Build methods list - RapidAPI first if key is configured
    methods = []
    
    if RAPIDAPI_KEY:
        methods.append(_try_instagram_rapidapi)
    
    # Fallback methods
    methods.extend([
        _try_instagram_embed_scrape,
        _try_instagram_igram,
        _try_instagram_saveig,
    ])
    
    for method in methods:
        try:
            print(f"Trying Instagram method: {method.__name__}")
            result = await method(url)
            if result and 'file_path' in result:
                print(f"Success with {method.__name__}")
                return result
            elif result and 'error' in result:
                print(f"{method.__name__} returned error: {result.get('error')}")
        except Exception as e:
            print(f"Instagram method {method.__name__} error: {e}")
            continue
    
    return None


async def _try_instagram_rapidapi(url: str) -> dict | None:
    """Try RapidAPI Instagram Scrapper (500 free requests/month)."""
    if not RAPIDAPI_KEY:
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "instagram-scrapper-api-posts-reels-stories-downloader.p.rapidapi.com"
            }
            
            api_url = "https://instagram-scrapper-api-posts-reels-stories-downloader.p.rapidapi.com/instagram/"
            params = {"url": url}
            
            async with session.get(api_url, headers=headers, params=params, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Extract video URL from response
                    video_url = None
                    caption = "Instagram Video"
                    author = ""
                    
                    # Try different response structures
                    if isinstance(result, dict):
                        # Direct video_url field
                        video_url = result.get('video_url') or result.get('download_url') or result.get('url')
                        
                        # Check in data/media fields
                        if not video_url and result.get('data'):
                            data = result['data']
                            if isinstance(data, dict):
                                video_url = data.get('video_url') or data.get('download_url')
                                caption = data.get('caption', caption)[:200] if data.get('caption') else caption
                                author = data.get('username', '')
                            elif isinstance(data, list) and data:
                                video_url = data[0].get('video_url') or data[0].get('download_url')
                        
                        # Check media array
                        if not video_url and result.get('media'):
                            media = result['media']
                            if isinstance(media, list) and media:
                                for m in media:
                                    if m.get('type') == 'video' or 'video' in str(m.get('url', '')).lower():
                                        video_url = m.get('url') or m.get('video_url')
                                        break
                                if not video_url and media:
                                    video_url = media[0].get('url')
                        
                        # Get caption and author
                        if not author:
                            author = result.get('username', '') or result.get('author', '')
                        if caption == "Instagram Video":
                            caption = (result.get('caption') or result.get('title') or 'Instagram Video')[:200]
                    
                    if video_url:
                        if author and not author.startswith('@'):
                            author = '@' + author
                        
                        return await download_file(
                            video_url, url,
                            title=caption,
                            uploader=author,
                            platform='instagram'
                        )
                elif response.status == 429:
                    print("RapidAPI rate limit reached")
                    return None
                else:
                    print(f"RapidAPI returned status: {response.status}")
    except Exception as e:
        print(f"RapidAPI error: {e}")
    return None


async def _try_instagram_embed_scrape(url: str) -> dict | None:
    """Try scraping Instagram's public embed page - most reliable method."""
    try:
        # Extract shortcode from URL
        shortcode_match = re.search(r'instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)', url)
        if not shortcode_match:
            return None
        
        shortcode = shortcode_match.group(1)
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            
            # Try Instagram's embed endpoint
            embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/captioned/"
            
            async with session.get(embed_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for video URL in various formats
                    video_patterns = [
                        r'"video_url"\s*:\s*"([^"]+)"',
                        r'"contentUrl"\s*:\s*"([^"]+)"',
                        r'property="og:video"\s+content="([^"]+)"',
                        r'"src"\s*:\s*"([^"]*?\.mp4[^"]*)"',
                    ]
                    
                    for pattern in video_patterns:
                        match = re.search(pattern, html)
                        if match:
                            video_url = match.group(1)
                            # Decode unicode escapes
                            video_url = video_url.replace('\\u0026', '&').replace('\\/', '/')
                            video_url = video_url.encode().decode('unicode_escape') if '\\u' in video_url else video_url
                            
                            # Get caption
                            caption = "Instagram Video"
                            caption_match = re.search(r'"caption"\s*:\s*\{[^}]*"text"\s*:\s*"([^"]*)"', html)
                            if not caption_match:
                                caption_match = re.search(r'"edge_media_to_caption".*?"text"\s*:\s*"([^"]*)"', html, re.DOTALL)
                            if caption_match:
                                try:
                                    caption = caption_match.group(1)[:200]
                                    caption = caption.encode().decode('unicode_escape') if '\\u' in caption else caption
                                except:
                                    caption = "Instagram Video"
                            
                            # Get author
                            author = ""
                            author_match = re.search(r'"username"\s*:\s*"([^"]+)"', html)
                            if author_match:
                                author = "@" + author_match.group(1)
                            
                            return await download_file(
                                video_url, url,
                                title=caption if caption else "Instagram Video",
                                uploader=author,
                                platform='instagram'
                            )
            
            # Try regular page with embed
            page_url = f"https://www.instagram.com/p/{shortcode}/embed/"
            async with session.get(page_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    for pattern in video_patterns:
                        match = re.search(pattern, html)
                        if match:
                            video_url = match.group(1).replace('\\u0026', '&').replace('\\/', '/')
                            
                            return await download_file(
                                video_url, url,
                                title="Instagram Video",
                                uploader="",
                                platform='instagram'
                            )
                            
    except Exception as e:
        print(f"embed scrape error: {e}")
    return None


async def _try_instagram_igram(url: str) -> dict | None:
    """Try iGram.io API."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://igram.io",
                "Referer": "https://igram.io/",
            }
            
            api_url = "https://api.igram.io/api/convert"
            import json
            payload = {"url": url}
            
            async with session.post(api_url, data=json.dumps(payload), headers=headers, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Parse response
                    items = result.get('result', []) or result.get('data', [])
                    if isinstance(items, list) and items:
                        for item in items:
                            item_url = item.get('url') or item.get('download_url')
                            if item_url:
                                return await download_file(
                                    item_url, url,
                                    title="Instagram Video",
                                    uploader="",
                                    platform='instagram'
                                )
    except Exception as e:
        print(f"igram error: {e}")
    return None


async def _try_instagram_saveig(url: str) -> dict | None:
    """Try SaveIG API."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
            }
            
            # Try saveig API
            api_url = "https://v3.saveig.app/api/ajaxSearch"
            data = {"q": url, "t": "media", "lang": "en"}
            
            async with session.post(api_url, data=data, headers=headers, timeout=30) as response:
                if response.status == 200:
                    try:
                        result = await response.json()
                        if result.get('status') == 'ok' and result.get('data'):
                            html_data = result.get('data', '')
                            
                            # Look for video download links
                            video_match = re.search(r'href="(https://[^"]+)"[^>]*class="[^"]*btn[^"]*"', html_data)
                            if not video_match:
                                video_match = re.search(r'<a[^>]*href="(https://[^"]+\.mp4[^"]*)"', html_data)
                            if not video_match:
                                video_match = re.search(r'href="(https://[^"]+)"[^>]*>.*?Download', html_data, re.DOTALL)
                            
                            if video_match:
                                video_url = video_match.group(1)
                                
                                # Get caption
                                caption = "Instagram Video"
                                caption_match = re.search(r'class="[^"]*text[^"]*"[^>]*>([^<]+)<', html_data)
                                if caption_match:
                                    caption = caption_match.group(1).strip()[:200]
                                
                                return await download_file(
                                    video_url, url,
                                    title=caption,
                                    uploader="",
                                    platform='instagram'
                                )
                    except:
                        pass
    except Exception as e:
        print(f"saveig error: {e}")
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
    
    # Instagram: RapidAPI + Free APIs (no yt-dlp - requires login)
    else:
        print(f"Instagram → RapidAPI + Free APIs (RAPIDAPI_KEY configured: {bool(RAPIDAPI_KEY)})")
        result = download_instagram_sync(url)
        print(f"Instagram download result: {type(result)} - has file_path: {'file_path' in result if result else 'None'}")
        if result and 'file_path' in result:
            return result
        elif result and 'error' in result:
            return result
        return {'error': 'فشل تحميل Instagram - جرب تاني بعد شوية'}


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
