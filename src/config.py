import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables (from .env file for local development)
load_dotenv()

class Config:
    # YouTube API Configuration - reads from environment variables
    YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
    YOUTUBE_CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID')
    YOUTUBE_CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET')
    YOUTUBE_REFRESH_TOKEN = os.getenv('YOUTUBE_REFRESH_TOKEN')
    
    # Target channel
    TARGET_CHANNEL_ID = os.getenv('TARGET_CHANNEL_ID', 'UCWsDFcIhY2DBi3GB5uykGXA')
    
    # Gemini Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
    
    # Upload settings
    UPLOAD_PRIVACY = os.getenv('UPLOAD_PRIVACY', 'public')
    UPLOAD_CATEGORY = os.getenv('UPLOAD_CATEGORY', '22')
    
    # Processing settings
    VIDEO_DURATION_LIMIT = int(os.getenv('VIDEO_DURATION_LIMIT', '60'))
    MAX_VIDEOS_TO_PROCESS = int(os.getenv('MAX_VIDEOS_TO_PROCESS', '1'))
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / 'data'
    DOWNLOADS_DIR = BASE_DIR / 'downloads'
    OUTPUTS_DIR = BASE_DIR / 'outputs'
    LOGS_DIR = BASE_DIR / 'logs'
    
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
            'GEMINI_API_KEY'
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
