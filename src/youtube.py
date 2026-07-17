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
        """Download a video using yt-dlp with tv_embedded client"""
        try:
            import yt_dlp
            
            # Ensure the downloads directory exists
            os.makedirs('downloads', exist_ok=True)
            
            # Get the directory and base filename
            output_dir = os.path.dirname(output_path)
            base_name = os.path.splitext(os.path.basename(output_path))[0]
            
            # Try with tv_embedded client (works without PO token)
            try:
                log.info(f"Attempting download with tv_embedded client...")
                
                ydl_opts = {
                    'outtmpl': os.path.join(output_dir, f'{base_name}.%(ext)s'),
                    'format': 'bestvideo+bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'ignoreerrors': True,
                    'no_check_certificate': True,
                    'prefer_insecure': True,
                    'merge_output_format': 'webm',  # YouTube often outputs webm
                    'extractor_args': {
                        'youtube': {
                            'player-client': ['tv_embedded'],
                        }
                    }
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
                
                # Check for downloaded files (could be .mp4 or .webm)
                possible_extensions = ['.mp4', '.webm', '.mkv', '.avi']
                downloaded_files = []
                for ext in possible_extensions:
                    downloaded_files.extend(glob.glob(os.path.join(output_dir, f'{base_name}*{ext}')))
                
                if downloaded_files:
                    downloaded_file = downloaded_files[0]
                    # If the file doesn't have .mp4 extension, rename it
                    if not downloaded_file.endswith('.mp4') and not output_path.endswith('.webm'):
                        # Rename to .webm (YouTube accepts it)
                        new_path = output_path.replace('.mp4', '.webm')
                        if downloaded_file != new_path:
                            os.rename(downloaded_file, new_path)
                            log.info(f"Renamed {downloaded_file} to {new_path}")
                        else:
                            log.info(f"Downloaded video {video_id} to {downloaded_file}")
                    else:
                        log.info(f"Downloaded video {video_id} to {downloaded_file}")
                    return True
                else:
                    log.error(f"No downloaded file found for {video_id}")
                    return False
                    
            except Exception as e:
                log.warning(f"Download with tv_embedded failed: {e}")
                # Fallback to default client
                log.info("Falling back to default client...")
                ydl_opts = {
                    'outtmpl': os.path.join(output_dir, f'{base_name}.%(ext)s'),
                    'format': 'bestvideo+bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'ignoreerrors': True,
                    'no_check_certificate': True,
                    'prefer_insecure': True,
                    'merge_output_format': 'webm',
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
                
                # Check for downloaded files
                downloaded_files = glob.glob(os.path.join(output_dir, f'{base_name}.*'))
                if downloaded_files:
                    downloaded_file = downloaded_files[0]
                    # Rename to expected path if needed
                    if downloaded_file != output_path:
                        # If output_path expects .mp4 but file is .webm, update output_path
                        if output_path.endswith('.mp4') and downloaded_file.endswith('.webm'):
                            output_path = output_path.replace('.mp4', '.webm')
                        os.rename(downloaded_file, output_path)
                        log.info(f"Renamed {downloaded_file} to {output_path}")
                    log.info(f"Downloaded video {video_id} to {output_path}")
                    return True
                
                log.error(f"All download attempts failed for {video_id}")
                return False
            
        except ImportError as e:
            log.error(f"yt-dlp not installed: {e}")
            return False
        except Exception as e:
            log.error(f"Error downloading video: {e}")
            return False
    
    def download_video_pytube(self, video_id: str, output_path: str) -> bool:
        """Fallback: Download a video using pytube"""
        try:
            from pytube import YouTube
            
            url = f'https://www.youtube.com/watch?v={video_id}'
            yt = YouTube(url)
            
            # Try to get a progressive stream first (video+audio combined)
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            if not stream:
                # If no progressive stream, get the highest resolution stream
                stream = yt.streams.get_highest_resolution()
            
            if not stream:
                log.error("No streams available for this video")
                return False
            
            # Download with the correct filename
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            stream.download(output_path=output_dir, filename=os.path.basename(output_path))
            
            if os.path.exists(output_path):
                log.info(f"Downloaded video {video_id} to {output_path} using pytube")
                return True
            else:
                log.error(f"Download failed - file not found: {output_path}")
                return False
                
        except ImportError as e:
            log.error(f"pytube not installed: {e}")
            return False
        except Exception as e:
            log.error(f"Error downloading with pytube: {e}")
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
                    'title': title[:100],  # YouTube title limit
                    'description': description[:5000],  # YouTube description limit
                    'tags': tags[:500],  # YouTube limits to 500 tags
                    'categoryId': Config.UPLOAD_CATEGORY
                },
                'status': {
                    'privacyStatus': Config.UPLOAD_PRIVACY
                }
            }
            
            # Upload video - determine correct mimetype
            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                if video_path.endswith('.webm'):
                    mime_type = 'video/webm'
                elif video_path.endswith('.mp4'):
                    mime_type = 'video/mp4'
                elif video_path.endswith('.mkv'):
                    mime_type = 'video/x-matroska'
                else:
                    mime_type = 'video/*'
            
            media = MediaFileUpload(
                video_path,
                mimetype=mime_type,
                resumable=True,
                chunksize=-1  # Use default chunk size
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
                log.info(f"Successfully uploaded video: {video_id}")
                
                # Upload thumbnail if provided
                if thumbnail_path and os.path.exists(thumbnail_path):
                    self._upload_thumbnail(video_id, thumbnail_path)
                
                return video_id
            else:
                log.error("Upload response did not contain video ID")
                return None
            
        except HttpError as e:
            log.error(f"YouTube upload error: {e}")
            if e.resp.status == 403:
                log.error("Quota exceeded or permissions issue")
            elif e.resp.status == 400:
                log.error("Bad request - check video format and metadata")
            return None
        except Exception as e:
            log.error(f"Unexpected upload error: {e}")
            return None
    
    def _upload_thumbnail(self, video_id: str, thumbnail_path: str):
        """Upload thumbnail for a video"""
        try:
            if not os.path.exists(thumbnail_path):
                log.error(f"Thumbnail file not found: {thumbnail_path}")
                return
            
            media = MediaFileUpload(
                thumbnail_path,
                mimetype='image/png'
            )
            
            request = self.auth_client.thumbnails().set(
                videoId=video_id,
                media_body=media
            )
            response = request.execute()
            
            log.info(f"Uploaded thumbnail for video {video_id}")
        except HttpError as e:
            log.error(f"Failed to upload thumbnail: {e}")
        except Exception as e:
            log.error(f"Error uploading thumbnail: {e}")
    
    def get_subscribers(self, channel_id: str) -> int:
        """Get subscriber count for a channel"""
        try:
            request = self.public_client.channels().list(
                part='statistics',
                id=channel_id
            )
            response = request.execute()
            
            if response.get('items'):
                return int(response['items'][0]['statistics'].get('subscriberCount', 0))
            return 0
        except HttpError as e:
            log.error(f"Error getting subscribers: {e}")
            return 0
    
    def get_video_comments(self, video_id: str, max_results: int = 10) -> List[Dict]:
        """Get comments for a video"""
        try:
            request = self.public_client.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=max_results,
                order='relevance'
            )
            response = request.execute()
            
            comments = []
            for item in response.get('items', []):
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'author': comment.get('authorDisplayName', ''),
                    'text': comment.get('textDisplay', ''),
                    'likes': comment.get('likeCount', 0),
                    'published_at': comment.get('publishedAt', '')
                })
            return comments
        except HttpError as e:
            log.error(f"Error getting comments: {e}")
            return []
