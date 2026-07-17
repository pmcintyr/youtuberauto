import google.genai as genai
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time
import hashlib
import json
from pathlib import Path
from src.logger import log
from src.config import Config

class MetadataGenerator:
    def __init__(self):
        # Initialize the new Gemini client
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model = "gemini-flash-latest"  # Use stable model
        self.cache_dir = Config.DATA_DIR / 'metadata_cache'
        self.cache_dir.mkdir(exist_ok=True)
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests
        
    def _get_cache_key(self, video_title: str, video_description: str) -> str:
        """Generate a cache key from video metadata"""
        content = f"{video_title}|{video_description[:100]}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_metadata(self, cache_key: str) -> Optional[Dict]:
        """Get cached metadata if it exists and is fresh"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                # Check if cache is less than 30 days old
                cached_date = datetime.fromisoformat(data.get('generated_at', '2000-01-01'))
                if datetime.now() - cached_date < timedelta(days=30):
                    log.info("✅ Using cached metadata")
                    return data
            except Exception as e:
                log.warning(f"Cache read error: {e}")
        return None
    
    def _cache_metadata(self, cache_key: str, metadata: Dict):
        """Cache metadata to disk"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            with open(cache_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            log.info("✅ Metadata cached")
        except Exception as e:
            log.warning(f"Cache write error: {e}")
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting to avoid quota issues"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            log.info(f"Rate limiting: waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        self.last_request_time = time.time()
    
    def generate_metadata(self, video_title: str, video_description: str) -> Dict:
        """Generate enhanced metadata with caching and rate limiting"""
        # Check cache first
        cache_key = self._get_cache_key(video_title, video_description)
        cached = self._get_cached_metadata(cache_key)
        if cached:
            return cached
        
        try:
            # Rate limit
            self._wait_for_rate_limit()
            
            # Generate title
            title_prompt = f"""Create a viral, engaging title for this YouTube Short. Make it clickable. Original: "{video_title}"
Rules:
- MUST be under 100 characters
- Use emojis (max 2)
- Make it exciting and curiosity-driven
- Include a call to action
- Don't use ALL CAPS
- Make it unique

Return ONLY the title, nothing else."""
            
            title_response = self.client.models.generate_content(
                model=self.model,
                contents=title_prompt
            )
            enhanced_title = title_response.text.strip()[:100]
            if not enhanced_title:
                enhanced_title = video_title[:100]
            
            # Rate limit
            self._wait_for_rate_limit()
            
            # Generate description
            desc_prompt = f"""Create an engaging description with optimized hashtags for this YouTube Short.
Original: {video_description}
Rules:
- Start with the most interesting hook
- Include 3-5 relevant hashtags
- Keep under 500 characters
- Add a call to action
- Use emojis (max 3)

Return ONLY the description."""
            
            desc_response = self.client.models.generate_content(
                model=self.model,
                contents=desc_prompt
            )
            enhanced_description = desc_response.text.strip()[:5000]
            if not enhanced_description:
                enhanced_description = video_description[:5000] if video_description else "Check out this awesome short! 🔥"
            
            # Rate limit
            self._wait_for_rate_limit()
            
            # Generate tags
            tags_prompt = f"""Generate 10-15 relevant tags for this YouTube Short.
Title: {video_title}
Rules:
- Include main keywords
- Mix of broad and specific tags
- Include trending tags
- Return as comma-separated list"""
            
            tags_response = self.client.models.generate_content(
                model=self.model,
                contents=tags_prompt
            )
            tags = [tag.strip() for tag in tags_response.text.split(',') if tag.strip()][:500]
            if not tags:
                tags = ['shorts', 'youtube', 'viral', 'trending']
            
            metadata = {
                'enhanced_title': enhanced_title,
                'enhanced_description': enhanced_description,
                'tags': tags,
                'generated_at': datetime.now().isoformat(),
                'model_used': self.model
            }
            
            # Cache the result
            self._cache_metadata(cache_key, metadata)
            
            return metadata
            
        except Exception as e:
            log.error(f"Error generating metadata with Gemini: {e}")
            # Return fallback metadata
            fallback = {
                'enhanced_title': video_title[:100],
                'enhanced_description': video_description[:5000] if video_description else "Check out this awesome short! 🔥",
                'tags': ['shorts', 'youtube', 'viral', 'trending'],
                'generated_at': datetime.now().isoformat(),
                'model_used': 'fallback'
            }
            # Cache the fallback to avoid repeated failures
            self._cache_metadata(cache_key, fallback)
            return fallback
