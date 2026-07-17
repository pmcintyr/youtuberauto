import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from src.logger import log
from src.config import Config

class Database:
    def __init__(self):
        self.data_file = Config.DATA_DIR / 'processed.json'
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """Create data file if it doesn't exist"""
        if not self.data_file.exists():
            initial_data = {
                'processed_videos': [],
                'last_run': None,
                'channel_id': Config.TARGET_CHANNEL_ID
            }
            with open(self.data_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    def load_data(self) -> Dict:
        """Load processed data from JSON file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            log.error("Corrupted data file, resetting")
            return {'processed_videos': [], 'last_run': None}
        except Exception as e:
            log.error(f"Error loading data: {e}")
            return {'processed_videos': [], 'last_run': None}
    
    def save_data(self, data: Dict):
        """Save data to JSON file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
            log.info("Data saved successfully")
        except Exception as e:
            log.error(f"Error saving data: {e}")
    
    def is_video_processed(self, video_id: str) -> bool:
        """Check if a video has been processed before"""
        data = self.load_data()
        processed_videos = data.get('processed_videos', [])
        return video_id in processed_videos
    
    def mark_video_processed(self, video_id: str, metadata: Dict):
        """Mark a video as processed"""
        data = self.load_data()
        if video_id not in data.get('processed_videos', []):
            data.setdefault('processed_videos', []).append(video_id)
            data['last_run'] = datetime.now().isoformat()
            
            # Add processing metadata
            if 'processed_metadata' not in data:
                data['processed_metadata'] = {}
            data['processed_metadata'][video_id] = {
                'processed_at': datetime.now().isoformat(),
                'metadata': metadata
            }
            
            self.save_data(data)
            log.info(f"Marked video {video_id} as processed")
    
    def get_last_run_time(self) -> Optional[datetime]:
        """Get the timestamp of the last successful run"""
        data = self.load_data()
        last_run = data.get('last_run')
        if last_run:
            try:
                return datetime.fromisoformat(last_run)
            except ValueError:
                return None
        return None
    
    def get_processed_count(self) -> int:
        """Get the number of processed videos"""
        data = self.load_data()
        return len(data.get('processed_videos', []))
    
    def clear_processed_cache(self):
        """Clear the processed videos cache (for testing)"""
        data = {'processed_videos': [], 'last_run': None}
        self.save_data(data)
        log.info("Cleared processed cache")
