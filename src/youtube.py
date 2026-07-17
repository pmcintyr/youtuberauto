import os
import re
import glob
import mimetypes
import requests
from typing import Dict, List, Optional, Tuple
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from src.logger import log
from src.config import Config

class YouTubeClient:
    def __init__(self):
        self.api_key = Config.YOUTUBE_API_KEY
        self.client_id = Config.YOUTUBE_CLIENT_ID
        self.client_secret = Config.YOUTUBE_CLIENT_SECRET
        self.refresh_token = Config.YOUTUBE_REFRESH_TOKEN
        
        self.public_client = build('youtube', 'v3', developerKey=self.api_key)
        self.auth_client = self._get_authenticated_client()
    
    def _get_authenticated_client(self):
        try:
            credentials = Credentials(
                token=None,
                refresh_token=self.refresh_token,
                client_id=self.client_id,
                client_secret=self.client_secret,
                token_uri='https://oauth2.googleapis.com/token'
            )
            if credentials.expired:
                credentials.refresh(Request())
            return build('youtube', 'v3', credentials=credentials)
        except Exception as e:
            log.error(f"Failed to get authenticated client: {e}")
            return None
    
    def get_channel_videos(self, channel_id: str, max_results: int = 5) -> List[Dict]:
        try:
            request = self.public_client.search().list(
                part='snippet',
                channelId=channel_id,
                maxResults=max_results,
                order='date',
                type='video'
            )
            response = request.execute()
            
            videos = []
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                video_details = self.get_video_details(video_id)
                if video_details:
                    videos.append({
                        'id': video_id,
                        'title': item['snippet']['title'],
                        'description': item['snippet']['description'],
                        'published_at': item['snippet']['publishedAt'],
                        'thumbnail': item['snippet']['thumbnails']['default']['url'],
                        'channel_id': channel_id,
                        'channel_title': item['snippet']['channelTitle'],
                        'duration': video_details.get('duration', ''),
                        'view_count': video_details.get('viewCount', 0),
                        'like_count': video_details.get('likeCount', 0),
                        'comment_count': video_details.get('commentCount', 0)
                    })
            return videos
        except HttpError as e:
            log.error(f"YouTube API error: {e}")
            return []
        except Exception as e:
            log.error(f"Error getting channel videos: {e}")
            return []
    
    def get_video_details(self, video_id: str) -> Dict:
        try:
            request = self.public_client.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            )
            response = request.execute()
            if not response.get('items'):
                return {}
            item = response['items'][0]
            return {
                'duration': item['contentDetails']['duration'],
                'viewCount': item['statistics'].get('viewCount', 0),
                'likeCount': item['statistics'].get('likeCount', 0),
                'commentCount': item['statistics'].get('commentCount', 0),
                'categoryId': item['snippet'].get('categoryId', ''),
                'tags': item['snippet'].get('tags', [])
            }
        except HttpError as e:
            log.error(f"YouTube API error getting video details: {e}")
            return {}
    
    def is_short(self, video_duration: str) -> bool:
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, video_duration)
        if not match:
            return False
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds <= Config.VIDEO_DURATION_LIMIT
    
    def download_video(self, video_id: str, output_path: str) -> bool:
        """
        Download video using pytube (with cookies if available) first,
        then fallback to yt-dlp.
        """
        # First, try pytube with cookies
        if self._download_with_pytube(video_id, output_path):
            return True
        
        # Fallback to yt-dlp
        log.info("Pytube failed, trying yt-dlp...")
        return self._download_with_ytdlp(video_id, output_path)
    
    def _download_with_pytube(self, video_id: str, output_path: str) -> bool:
        """Use pytube to download the video, optionally with cookies."""
        try:
            from pytube import YouTube
            
            url = f'https://www.youtube.com/watch?v={video_id}'
            # Check for cookies file
            cookies_file = os.getenv('YOUTUBE_COOKIES_FILE')
            yt = YouTube(url, cookies=cookies_file) if cookies_file and os.path.exists(cookies_file) else YouTube(url)
            
            # Get highest resolution stream
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            if not stream:
                stream = yt.streams.get_highest_resolution()
            if not stream:
                log.error("No streams available for this video via pytube")
                return False
            
            # Download
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            stream.download(output_path=output_dir, filename=os.path.basename(output_path))
            
            if os.path.exists(output_path):
                log.info(f"✅ Downloaded video {video_id} to {output_path} using pytube")
                return True
            else:
                log.error("Download completed but file not found")
                return False
                
        except Exception as e:
            log.warning(f"Pytube download failed: {e}")
            return False
    
    def _download_with_ytdlp(self, video_id: str, output_path: str) -> bool:
        """Fallback: use yt-dlp with multiple client attempts and cookies."""
        try:
            import yt_dlp
            
            os.makedirs('downloads', exist_ok=True)
            output_dir = os.path.dirname(output_path)
            base_name = os.path.splitext(os.path.basename(output_path))[0]
            
            # Get cookies file if available
            cookies_file = os.getenv('YOUTUBE_COOKIES_FILE')
            has_cookies = cookies_file and os.path.exists(cookies_file)
            
            # Different client options to try
            clients = ['tv_embedded', 'web_creator', 'mweb', 'android', 'ios']
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            ]
            
            for client in clients:
                for ua in user_agents:
                    try:
                        ydl_opts = {
                            'outtmpl': os.path.join(output_dir, f'{base_name}.%(ext)s'),
                            'format': 'best[ext=mp4]/best',
                            'quiet': True,
                            'no_warnings': True,
                            'ignoreerrors': True,
                            'no_check_certificate': True,
                            'prefer_insecure': True,
                            'merge_output_format': 'mp4',
                            'user_agent': ua,
                            'extractor_args': {
                                'youtube': {
                                    'player-client': [client],
                                    'skip': ['dash', 'hls']  # Skip problematic formats
                                }
                            }
                        }
                        if has_cookies:
                            ydl_opts['cookiefile'] = cookies_file
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
                        
                        # Check for downloaded file
                        downloaded_files = glob.glob(os.path.join(output_dir, f'{base_name}.*'))
                        if downloaded_files:
                            downloaded_file = downloaded_files[0]
                            if downloaded_file != output_path:
                                os.rename(downloaded_file, output_path)
                            log.info(f"✅ Downloaded video {video_id} to {output_path} using yt-dlp (client={client})")
                            return True
                    except Exception as e:
                        log.warning(f"yt-dlp attempt with client {client} failed: {str(e)[:100]}")
                        continue
            
            log.error("All yt-dlp attempts failed")
            return False
            
        except ImportError:
            log.error("yt-dlp not installed")
            return False
        except Exception as e:
            log.error(f"Error with yt-dlp: {e}")
            return False
    
    def upload_video(self, video_path: str, title: str, description: str, 
                     tags: List[str], thumbnail_path: Optional[str] = None) -> Optional[str]:
        if not self.auth_client:
            log.error("No authenticated client available")
            return None
        
        if not os.path.exists(video_path):
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            for ext in ['.mp4', '.webm', '.mkv']:
                found = glob.glob(os.path.join('downloads', f'{base_name}{ext}'))
                if found:
                    video_path = found[0]
                    log.info(f"Found video file: {video_path}")
                    break
            else:
                log.error(f"Could not find video file for {base_name}")
                return None
        
        try:
            body = {
                'snippet': {
                    'title': title[:100],
                    'description': description[:5000],
                    'tags': tags[:500],
                    'categoryId': Config.UPLOAD_CATEGORY
                },
                'status': {
                    'privacyStatus': Config.UPLOAD_PRIVACY
                }
            }
            
            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                if video_path.endswith('.webm'):
                    mime_type = 'video/webm'
                elif video_path.endswith('.mp4'):
                    mime_type = 'video/mp4'
                else:
                    mime_type = 'video/*'
            
            media = MediaFileUpload(video_path, mimetype=mime_type, resumable=True)
            request = self.auth_client.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            log.info(f"Uploading video: {title[:50]}...")
            response = request.execute()
            video_id = response.get('id')
            
            if video_id:
                log.info(f"✅ Successfully uploaded video: {video_id}")
                if thumbnail_path and os.path.exists(thumbnail_path):
                    self._upload_thumbnail(video_id, thumbnail_path)
                return video_id
            return None
            
        except HttpError as e:
            log.error(f"YouTube upload error: {e}")
            return None
        except Exception as e:
            log.error(f"Upload error: {e}")
            return None
    
    def _upload_thumbnail(self, video_id: str, thumbnail_path: str):
        try:
            media = MediaFileUpload(thumbnail_path, mimetype='image/png')
            self.auth_client.thumbnails().set(videoId=video_id, media_body=media).execute()
            log.info(f"✅ Uploaded thumbnail for video {video_id}")
        except Exception as e:
            log.error(f"Failed to upload thumbnail: {e}")
