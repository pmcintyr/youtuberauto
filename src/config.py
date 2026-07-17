import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

class Config:
    # YouTube API Configuration
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
    YOUTUBE_CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
    YOUTUBE_CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')
    YOUTUBE_REFRESH_TOKEN = os.getenv('YOUTUBE_REFRESH_TOKEN')
    
    # Target channel (Ishowspeed's channel ID)
    TARGET_CHANNEL_ID = os.getenv('TARGET_CHANNEL_ID', 'UCWsPfpqE1AqF5_6JgI7rPXg')
    
    # Gemini API Configuration (FREE!)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-pro')  # Free tier model
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / 'data'
    DOWNLOADS_DIR = BASE_DIR / 'downloads'
    OUTPUTS_DIR = BASE_DIR / 'outputs'
    LOGS_DIR = BASE_DIR / 'logs'
    
    # Processing settings
    MAX_VIDEOS_TO_PROCESS = 1  # Only process the most recent short
    VIDEO_DURATION_LIMIT = 60  # Only process videos under 60 seconds (shorts)
    
    # Upload settings
    UPLOAD_CATEGORY = '22'  # People & Blogs
    UPLOAD_PRIVACY = 'public'  # or 'unlisted' or 'private'
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist"""
        for directory in [cls.DATA_DIR, cls.DOWNLOADS_DIR, cls.OUTPUTS_DIR, cls.LOGS_DIR]:
            directory.mkdir(exist_ok=True)
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required_vars = [
            'YOUTUBE_API_KEY',
            'YOUTUBE_CLIENT_ID', 
            'YOUTUBE_CLIENT_SECRET',
            'YOUTUBE_REFRESH_TOKEN',
            'GEMINI_API_KEY'  # Changed from OPENAI_API_KEY
        ]
        
        missing = []
        for var in required_vars:
            if not getattr(cls, var, None):
                missing.append(var)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True

# Initialize directories on import
Config.ensure_directories()
