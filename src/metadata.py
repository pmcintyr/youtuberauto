import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from src.logger import log
from src.config import Config

class MetadataGenerator:
    def __init__(self):
        self.model = "gemini-flash-latest"  # Your model
        self.cache_dir = Config.DATA_DIR / 'metadata_cache'
        self.cache_dir.mkdir(exist_ok=True)
        
        # Track quota usage
        self.quota_file = self.cache_dir / 'quota_usage.json'
        self._load_quota_data()
    
    def _load_quota_data(self):
        """Load quota usage data"""
        if self.quota_file.exists():
            try:
                with open(self.quota_file, 'r') as f:
                    self.quota_data = json.load(f)
                return
            except:
                pass
        self.quota_data = {
            'requests_today': 0,
            'last_reset': datetime.now().isoformat()
        }
    
    def _save_quota_data(self):
        """Save quota usage data"""
        try:
            with open(self.quota_file, 'w') as f:
                json.dump(self.quota_data, f)
        except:
            pass
    
    def _check_quota(self) -> bool:
        """Check if we have quota available (free tier: 20/day)"""
        # Reset if new day
        last_reset = datetime.fromisoformat(self.quota_data['last_reset'])
        if datetime.now().date() > last_reset.date():
            self.quota_data['requests_today'] = 0
            self.quota_data['last_reset'] = datetime.now().isoformat()
            self._save_quota_data()
        
        # Check if we've hit the limit
        if self.quota_data['requests_today'] >= 18:  # Leave 2 for safety
            log.warning("⚠️ Gemini quota almost exhausted, using cached/fallback metadata")
            return False
        
        return True
    
    def _increment_quota(self):
        """Increment quota usage counter"""
        self.quota_data['requests_today'] += 1
        self._save_quota_data()
    
    def _get_cache_key(self, video_title: str) -> str:
        """Generate a cache key from video title"""
        return hashlib.md5(video_title.encode()).hexdigest()
    
    def _get_cached_metadata(self, cache_key: str) -> Optional[Dict]:
        """Get cached metadata if it exists"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                log.info("✅ Using cached metadata")
                return data
            except:
                pass
        return None
    
    def _cache_metadata(self, cache_key: str, metadata: Dict):
        """Cache metadata to disk"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            with open(cache_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except:
            pass
    
    def generate_metadata(self, video_title: str, video_description: str) -> Dict:
        """Generate metadata with caching and quota management"""
        cache_key = self._get_cache_key(video_title)
        
        # Check cache first
        cached = self._get_cached_metadata(cache_key)
        if cached:
            return cached
        
        # Check if we have quota
        if not self._check_quota():
            return self._generate_fallback_metadata(video_title, video_description)
        
        try:
            # Try to generate with Gemini
            import google.genai as genai
            
            client = genai.Client(api_key=Config.GEMINI_API_KEY)
            
            # Generate title
            title_response = client.models.generate_content(
                model=self.model,
                contents=f"Create a viral YouTube Short title. Original: '{video_title}'. Make it exciting and clickable."
            )
            enhanced_title = title_response.text.strip()[:100]
            
            # Generate description
            desc_response = client.models.generate_content(
                model=self.model,
                contents=f"Create a short description for this YouTube Short with hashtags. Original: '{video_description}'"
            )
            enhanced_description = desc_response.text.strip()[:5000]
            
            # Generate tags
            tags_response = client.models.generate_content(
                model=self.model,
                contents=f"Generate 10 relevant tags for this YouTube Short. Title: '{video_title}'"
            )
            tags = [tag.strip() for tag in tags_response.text.split(',') if tag.strip()][:500]
            
            if not tags:
                tags = ['shorts', 'youtube', 'viral', 'trending']
            
            # Increment quota
            self._increment_quota()
            
            metadata = {
                'enhanced_title': enhanced_title or video_title[:100],
                'enhanced_description': enhanced_description or video_description[:5000],
                'tags': tags,
                'generated_at': datetime.now().isoformat(),
                'model_used': self.model
            }
            
            self._cache_metadata(cache_key, metadata)
            return metadata
            
        except Exception as e:
            log.warning(f"Gemini generation failed: {e}")
            return self._generate_fallback_metadata(video_title, video_description)
    
    def _generate_fallback_metadata(self, video_title: str, video_description: str) -> Dict:
        """Generate metadata without Gemini"""
        # Simple title enhancement
        title = video_title[:100]
        if "|" in title:
            title = title.split("|")[0].strip()
        if not title:
            title = "🔥 Check out this awesome short!"
        
        # Simple description
        desc = video_description[:5000] if video_description else "🔥 Check out this awesome short! Like, comment, and subscribe for more! #shorts #youtube #viral"
        
        # Simple tags
        tags = ['shorts', 'youtube', 'viral', 'trending', 'video']
        if "world cup" in video_title.lower():
            tags.extend(['worldcup', 'football', 'soccer'])
        if "speed" in video_title.lower() or "ishowspeed" in video_title.lower():
            tags.extend(['ishowspeed', 'speed'])
        
        metadata = {
            'enhanced_title': title,
            'enhanced_description': desc,
            'tags': list(set(tags))[:500],
            'generated_at': datetime.now().isoformat(),
            'model_used': 'fallback'
        }
        
        cache_key = self._get_cache_key(video_title)
        self._cache_metadata(cache_key, metadata)
        return metadata
