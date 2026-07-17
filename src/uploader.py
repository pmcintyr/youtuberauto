import os
import subprocess
from pathlib import Path
from typing import Optional, Dict
from src.logger import log
from src.youtube import YouTubeClient
from src.metadata import MetadataGenerator
from src.database import Database

class VideoUploader:
    def __init__(self):
        self.youtube = YouTubeClient()
        self.metadata_generator = MetadataGenerator()
        self.db = Database()
    
    def process_and_upload_video(self, video_info: Dict) -> bool:
        """Process a video and upload it with enhanced metadata"""
        try:
            video_id = video_info['id']
            log.info(f"Processing video: {video_info['title']} ({video_id})")
            
            # Generate enhanced metadata
            log.info("Generating enhanced metadata...")
            metadata = self.metadata_generator.generate_metadata(
                video_info['title'],
                video_info['description']
            )
            
            # Download the video
            video_filename = f"{video_id}.mp4"
            video_path = Path('downloads') / video_filename
            log.info(f"Downloading video to {video_path}")
            
            if not self.youtube.download_video(video_id, str(video_path)):
                log.error("Failed to download video")
                return False
            
            # Generate thumbnail (simple version)
            thumbnail_path = self._generate_thumbnail(video_path)
            
            # Upload the video
            log.info(f"Uploading video with title: {metadata['enhanced_title']}")
            uploaded_video_id = self.youtube.upload_video(
                video_path=str(video_path),
                title=metadata['enhanced_title'],
                description=metadata['enhanced_description'],
                tags=metadata['tags'],
                thumbnail_path=thumbnail_path
            )
            
            if uploaded_video_id:
                # Mark as processed
                self.db.mark_video_processed(video_id, metadata)
                log.info(f"Successfully processed and uploaded video: {uploaded_video_id}")
                
                # Clean up
                self._cleanup_files(video_path, thumbnail_path)
                return True
            else:
                log.error("Failed to upload video")
                return False
                
        except Exception as e:
            log.error(f"Error processing video: {e}")
            return False
    
    def _generate_thumbnail(self, video_path: Path) -> Optional[str]:
        """Generate a simple thumbnail from the video"""
        try:
            thumbnail_path = Path('outputs') / f"{video_path.stem}_thumbnail.png"
            
            # Use ffmpeg to extract a frame from the middle of the video
            import cv2
            import numpy as np
            
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                log.warning("Could not open video for thumbnail generation")
                return None
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            middle_frame = total_frames // 2
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                # Resize for thumbnail
                frame_resized = cv2.resize(frame, (1280, 720))
                cv2.imwrite(str(thumbnail_path), frame_resized)
                log.info(f"Generated thumbnail at {thumbnail_path}")
                return str(thumbnail_path)
            else:
                log.warning("Could not extract frame for thumbnail")
                return None
                
        except ImportError:
            log.warning("OpenCV not available, skipping thumbnail generation")
            return None
        except Exception as e:
            log.error(f"Error generating thumbnail: {e}")
            return None
    
    def _cleanup_files(self, video_path: Path, thumbnail_path: Optional[str]):
        """Clean up temporary files"""
        try:
            if video_path.exists():
                os.remove(video_path)
                log.info(f"Removed video file: {video_path}")
            
            if thumbnail_path and Path(thumbnail_path).exists():
                os.remove(thumbnail_path)
                log.info(f"Removed thumbnail file: {thumbnail_path}")
        except Exception as e:
            log.error(f"Error cleaning up files: {e}")
