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
        
        # Public API client (for searching and getting metadata)
        self.public_client = build('youtube', 'v3', developerKey=self.api_key)
        
        # Authenticated client (for uploading)
        self.auth_client = self._get_authenticated_client()
    
    def _get_authenticated_client(self):
        """Get authenticated YouTube client for uploads"""
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
        """Get recent videos from a channel"""
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
        """Get detailed information about a video"""
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
        """Check if a video is a short based on duration"""
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
        """Download a video using direct URL with yt-dlp"""
        try:
            import yt_dlp
            
            os.makedirs('downloads', exist_ok=True)
            output_dir = os.path.dirname(output_path)
            base_name = os.path.splitext(os.path.basename(output_path))[0]
            
            # Try multiple approaches
            approaches = [
                # Approach 1: Standard download
                lambda: self._download_with_ytdlp(video_id, base_name, output_dir, {}),
                
                # Approach 2: With TV client
                lambda: self._download_with_ytdlp(video_id, base_name, output_dir, 
                    {'extractor_args': {'youtube': {'player-client': ['tv']}}}),
                
                # Approach 3: With android client
                lambda: self._download_with_ytdlp(video_id, base_name, output_dir,
                    {'extractor_args': {'youtube': {'player-client': ['android']}}}),
                
                # Approach 4: Using yt-dlp without cookies
                lambda: self._download_with_ytdlp(video_id, base_name, output_dir,
                    {'extractor_args': {'youtube': {'player-client': ['default']}}}),
            ]
            
            for i, approach in enumerate(approaches, 1):
                try:
                    log.info(f"Download attempt {i}...")
                    result = approach()
                    if result:
                        return result
                except Exception as e:
                    log.warning(f"Attempt {i} failed: {str(e)[:100]}")
                    continue
            
            log.error(f"All download attempts failed for {video_id}")
            return False
            
        except ImportError:
            log.error("yt-dlp not installed")
            return False
        except Exception as e:
            log.error(f"Error downloading video: {e}")
            return False
    
    def _download_with_ytdlp(self, video_id: str, base_name: str, output_dir: str, extra_opts: Dict) -> bool:
        """Helper method for yt-dlp download"""
        try:
            import yt_dlp
            
            ydl_opts = {
                'outtmpl': os.path.join(output_dir, f'{base_name}.%(ext)s'),
                'format': 'best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'no_check_certificate': True,
                'prefer_insecure': True,
                'merge_output_format': 'mp4',
                **extra_opts
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
            
            # Check for downloaded files
            downloaded_files = glob.glob(os.path.join(output_dir, f'{base_name}.*'))
            if downloaded_files:
                downloaded_file = downloaded_files[0]
                if downloaded_file != os.path.join(output_dir, f'{base_name}.mp4'):
                    os.rename(downloaded_file, os.path.join(output_dir, f'{base_name}.mp4'))
                log.info(f"✅ Downloaded to: {downloaded_file}")
                return True
            return False
            
        except Exception as e:
            log.error(f"yt-dlp download failed: {e}")
            return False
    
    def upload_video(self, video_path: str, title: str, description: str, 
                     tags: List[str], thumbnail_path: Optional[str] = None) -> Optional[str]:
        """Upload a video to YouTube"""
        if not self.auth_client:
            log.error("No authenticated client available")
            return None
        
        if not os.path.exists(video_path):
            # Try to find the file with different extensions
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            for ext in ['.mp4', '.webm', '.mkv']:
                found_files = glob.glob(os.path.join('downloads', f'{base_name}{ext}'))
                if found_files:
                    video_path = found_files[0]
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
            
            media = MediaFileUpload(
                video_path,
                mimetype=mime_type,
                resumable=True
            )
            
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
        """Upload thumbnail for a video"""
        try:
            media = MediaFileUpload(thumbnail_path, mimetype='image/png')
            self.auth_client.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()
            log.info(f"✅ Uploaded thumbnail for video {video_id}")
        except Exception as e:
            log.error(f"Failed to upload thumbnail: {e}")
