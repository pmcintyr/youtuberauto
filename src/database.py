import json
from pathlib import Path
from datetime import datetime, timedelta
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
                'channel_id': Config.TARGET_CHANNEL_ID,
                'uploaded_videos': [],  # Track uploaded videos separately
                'failed_attempts': [],  # Track failed attempts to avoid retrying
                'video_history': {}  # Store full history of each video
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
            return {
                'processed_videos': [], 
                'last_run': None,
                'uploaded_videos': [],
                'failed_attempts': [],
                'video_history': {}
            }
        except Exception as e:
            log.error(f"Error loading data: {e}")
            return {
                'processed_videos': [], 
                'last_run': None,
                'uploaded_videos': [],
                'failed_attempts': [],
                'video_history': {}
            }
    
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
        
        # Check if already processed
        if video_id in data.get('processed_videos', []):
            log.info(f"Video {video_id} already processed")
            return True
        
        # Check if already uploaded
        if video_id in data.get('uploaded_videos', []):
            log.info(f"Video {video_id} already uploaded")
            return True
        
        # Check if failed recently (within last 24 hours)
        if video_id in data.get('failed_attempts', []):
            failed_videos = data.get('failed_attempts', [])
            for entry in failed_videos:
                if entry.get('video_id') == video_id:
                    failed_time = datetime.fromisoformat(entry.get('timestamp', '2000-01-01'))
                    if datetime.now() - failed_time < timedelta(hours=24):
                        log.info(f"Video {video_id} failed recently, skipping")
                        return True
        
        return False
    
    def mark_video_processed(self, video_id: str, metadata: Dict):
        """Mark a video as successfully processed and uploaded"""
        data = self.load_data()
        
        # Add to processed videos
        if video_id not in data.get('processed_videos', []):
            data.setdefault('processed_videos', []).append(video_id)
        
        # Add to uploaded videos
        if video_id not in data.get('uploaded_videos', []):
            data.setdefault('uploaded_videos', []).append(video_id)
        
        # Update last run
        data['last_run'] = datetime.now().isoformat()
        
        # Add to history
        if 'video_history' not in data:
            data['video_history'] = {}
        data['video_history'][video_id] = {
            'processed_at': datetime.now().isoformat(),
            'metadata': metadata,
            'status': 'uploaded'
        }
        
        # Remove from failed attempts if present
        if 'failed_attempts' in data:
            data['failed_attempts'] = [f for f in data['failed_attempts'] if f.get('video_id') != video_id]
        
        self.save_data(data)
        log.info(f"✅ Marked video {video_id} as processed and uploaded")
    
    def mark_video_failed(self, video_id: str, error: str):
        """Mark a video as failed (to avoid retrying too soon)"""
        data = self.load_data()
        
        if 'failed_attempts' not in data:
            data['failed_attempts'] = []
        
        # Remove old entries for this video
        data['failed_attempts'] = [f for f in data['failed_attempts'] if f.get('video_id') != video_id]
        
        # Add new failure
        data['failed_attempts'].append({
            'video_id': video_id,
            'timestamp': datetime.now().isoformat(),
            'error': str(error)[:200]  # Truncate error message
        })
        
        # Update history if exists
        if 'video_history' in data and video_id in data['video_history']:
            data['video_history'][video_id]['status'] = 'failed'
            data['video_history'][video_id]['error'] = str(error)[:200]
        
        self.save_data(data)
        log.warning(f"Marked video {video_id} as failed: {error[:100]}...")
    
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
    
    def get_uploaded_count(self) -> int:
        """Get the number of uploaded videos"""
        data = self.load_data()
        return len(data.get('uploaded_videos', []))
    
    def get_recently_processed(self, days: int = 7) -> List[str]:
        """Get videos processed in the last N days"""
        data = self.load_data()
        recent = []
        cutoff = datetime.now() - timedelta(days=days)
        
        for video_id, info in data.get('video_history', {}).items():
            processed_at = info.get('processed_at')
            if processed_at:
                try:
                    processed_time = datetime.fromisoformat(processed_at)
                    if processed_time > cutoff:
                        recent.append(video_id)
                except ValueError:
                    pass
        
        return recent
    
    def clear_failed_attempts(self, older_than_days: int = 7):
        """Clear failed attempts older than N days"""
        data = self.load_data()
        cutoff = datetime.now() - timedelta(days=older_than_days)
        
        if 'failed_attempts' in data:
            data['failed_attempts'] = [
                f for f in data['failed_attempts']
                if datetime.fromisoformat(f.get('timestamp', '2000-01-01')) > cutoff
            ]
            self.save_data(data)
    
    def get_duplicates(self) -> List[str]:
        """Find any duplicate entries in the database"""
        data = self.load_data()
        all_videos = []
        
        # Check processed_videos
        all_videos.extend(data.get('processed_videos', []))
        
        # Check uploaded_videos
        all_videos.extend(data.get('uploaded_videos', []))
        
        # Find duplicates
        seen = set()
        duplicates = []
        for video_id in all_videos:
            if video_id in seen:
                duplicates.append(video_id)
            seen.add(video_id)
        
        return duplicates
    
    def repair_duplicates(self):
        """Remove duplicate entries from the database"""
        data = self.load_data()
        
        # Remove duplicates from processed_videos
        if 'processed_videos' in data:
            data['processed_videos'] = list(set(data['processed_videos']))
        
        # Remove duplicates from uploaded_videos
        if 'uploaded_videos' in data:
            data['uploaded_videos'] = list(set(data['uploaded_videos']))
        
        self.save_data(data)
        log.info("Repaired duplicate entries")
