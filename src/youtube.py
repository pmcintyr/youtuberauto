import os
import re
import requests
from typing import Dict, List, Optional, Tuple
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
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
            
            # Refresh the token if needed
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
                
                # Get video details including duration
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
        # Parse ISO 8601 duration
        import re
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
        """Download a video using yt-dlp with robust file finding"""
        try:
            import yt_dlp
            import glob
            
            # Ensure the downloads directory exists
            os.makedirs('downloads', exist_ok=True)
            
            # Get the directory and base filename
            output_dir = os.path.dirname(output_path)
            base_name = os.path.splitext(os.path.basename(output_path))[0]
            
            # Try downloading with different format options
            formats_to_try = [
                'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'best[ext=mp4]',
                'best',
                'worst'  # Last resort
            ]
            
            for format_str in formats_to_try:
                try:
                    ydl_opts = {
                        'outtmpl': os.path.join(output_dir, f'{base_name}.%(ext)s'),
                        'format': format_str,
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': False,
                        'ignoreerrors': True,
                        'no_check_certificate': True,
                        'prefer_insecure': True,
                        'merge_output_format': 'mp4',
                    }
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
                    
                    # Find the downloaded file
                    downloaded_files = glob.glob(os.path.join(output_dir, f'{base_name}.*'))
                    
                    if downloaded_files:
                        # Rename to the expected path
                        downloaded_file = downloaded_files[0]
                        if downloaded_file != output_path:
                            os.rename(downloaded_file, output_path)
                            log.info(f"Renamed {downloaded_file} to {output_path}")
                        else:
                            log.info(f"Downloaded video {video_id} to {output_path}")
                        return True
                    else:
                        log.warning(f"No file found for {video_id} with format {format_str}")
                        continue
                        
                except Exception as e:
                    log.warning(f"Download attempt with format {format_str} failed: {e}")
                    continue
            
            log.error(f"All download attempts failed for {video_id}")
            return False
            
        except Exception as e:
            log.error(f"Error downloading video: {e}")
            return False
    
    def upload_video(self, video_path: str, title: str, description: str, 
                     tags: List[str], thumbnail_path: Optional[str] = None) -> Optional[str]:
        """Upload a video to YouTube"""
        if not self.auth_client:
            log.error("No authenticated client available")
            return None
        
        # Check if video file exists
        if not os.path.exists(video_path):
            log.error(f"Video file not found: {video_path}")
            # Try to find the file
            import glob
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            found_files = glob.glob(os.path.join('downloads', f'{base_name}.*'))
            if found_files:
                video_path = found_files[0]
                log.info(f"Found video file: {video_path}")
            else:
                return None
        
        try:
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags[:500],
                    'categoryId': Config.UPLOAD_CATEGORY
                },
                'status': {
                    'privacyStatus': Config.UPLOAD_PRIVACY
                }
            }
            
            # Upload video
            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(
                video_path,
                mimetype='video/mp4',
                resumable=True
            )
            
            request = self.auth_client.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = request.execute()
            video_id = response.get('id')
            
            if video_id and thumbnail_path and os.path.exists(thumbnail_path):
                # Upload thumbnail
                self._upload_thumbnail(video_id, thumbnail_path)
            
            log.info(f"Successfully uploaded video: {response.get('id')}")
            return video_id
            
        except HttpError as e:
            log.error(f"YouTube upload error: {e}")
            if e.resp.status == 403:
                log.error("Quota exceeded or permissions issue")
            return None
        except Exception as e:
            log.error(f"Unexpected upload error: {e}")
            return None
    
    def _upload_thumbnail(self, video_id: str, thumbnail_path: str):
        """Upload thumbnail for a video"""
        try:
            from googleapiclient.http import MediaFileUpload
            
            media = MediaFileUpload(
                thumbnail_path,
                mimetype='image/png'
            )
            
            self.auth_client.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()
            
            log.info(f"Uploaded thumbnail for video {video_id}")
        except Exception as e:
            log.error(f"Failed to upload thumbnail: {e}")
