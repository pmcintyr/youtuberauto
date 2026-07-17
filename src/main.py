#!/usr/bin/env python3
"""
YouTube Automation Pipeline
Main entry point for the application
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logger import log
from src.config import Config
from src.youtube import YouTubeClient
from src.database import Database
from src.uploader import VideoUploader
from src.metadata import MetadataGenerator

def main():
    """Main execution function"""
    log.info("=" * 60)
    log.info("Starting YouTube Automation Pipeline")
    log.info(f"Run started at: {datetime.now().isoformat()}")
    log.info("=" * 60)
    
    try:
        # Validate configuration
        Config.validate()
        log.info("Configuration validated successfully")
        
        # Initialize components
        youtube_client = YouTubeClient()
        database = Database()
        uploader = VideoUploader()
        metadata_generator = MetadataGenerator()
        
        # Get target channel ID
        channel_id = Config.TARGET_CHANNEL_ID
        log.info(f"Target channel: {channel_id}")
        
        # Get recent videos from channel
        log.info("Fetching recent videos...")
        videos = youtube_client.get_channel_videos(channel_id, max_results=5)
        
        if not videos:
            log.warning("No videos found for the channel")
            return
        
        log.info(f"Found {len(videos)} recent videos")
        
        # Process videos (only most recent that hasn't been processed)
        processed_count = 0
        for video in videos:
            video_id = video['id']
            
            # Check if already processed
            if database.is_video_processed(video_id):
                log.info(f"Video {video_id} already processed, skipping")
                continue
            
            # Check if it's a short (based on duration)
            if not youtube_client.is_short(video['duration']):
                log.info(f"Video {video_id} is not a short, skipping")
                continue
            
            # Process and upload the video
            log.info(f"Processing video: {video['title']} ({video_id})")
            success = uploader.process_and_upload_video(video)
            
            if success:
                processed_count += 1
                # Only process one video per run (the most recent)
                break
            else:
                log.error(f"Failed to process video {video_id}")
        
        log.info(f"Pipeline completed. Processed {processed_count} new videos")
        
    except Exception as e:
        log.error(f"Pipeline failed with error: {e}")
        import traceback
        log.error(traceback.format_exc())
        sys.exit(1)
    finally:
        log.info("=" * 60)
        log.info("Pipeline execution finished")
        log.info("=" * 60)

if __name__ == "__main__":
    main()
