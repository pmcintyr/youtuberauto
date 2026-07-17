import google.genai as genai
from typing import Dict, List
from datetime import datetime
from src.logger import log
from src.config import Config

class MetadataGenerator:
    def __init__(self):
        # Initialize the new Gemini client
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model = "gemini-flash-latest"  # Stable, free model
    
    def generate_metadata(self, video_title: str, video_description: str) -> Dict:
        """Generate enhanced metadata for the video using Gemini"""
        try:
            # Generate a viral-style title
            title_prompt = f"""Create a viral, engaging title for this YouTube Short. Make it clickable and exciting. The original title was: "{video_title}"

Rules:
- MUST be under 100 characters
- Use emojis for engagement (max 2)
- Make it exciting and curiosity-driven
- Include a call to action if possible
- Don't use ALL CAPS
- Make it unique and different from the original

Return ONLY the title, nothing else."""
            
            title_response = self.client.models.generate_content(
                model=self.model,
                contents=title_prompt
            )
            enhanced_title = title_response.text.strip()
            if not enhanced_title:
                enhanced_title = video_title[:100]
            
            # Generate a description with hashtags
            desc_prompt = f"""Create an engaging description for this YouTube Short with optimized hashtags.

Original description: {video_description}

Rules:
- Start with the most interesting hook
- Include 3-5 relevant hashtags at the end
- Keep it under 500 characters
- Add a call to action (like, comment, subscribe)
- Make it engaging and conversational
- Include relevant emojis (max 3)

Return ONLY the description, nothing else."""
            
            desc_response = self.client.models.generate_content(
                model=self.model,
                contents=desc_prompt
            )
            enhanced_description = desc_response.text.strip()
            if not enhanced_description:
                enhanced_description = video_description[:5000]
            
            # Generate tags
            tags_prompt = f"""Generate 10-15 highly relevant and searchable tags for this YouTube Short.

Original title: {video_title}
Original description: {video_description}

Rules:
- Include the most important keywords first
- Use a mix of broad and specific tags
- Include trending relevant tags
- Focus on the main topics and personalities
- Maximum 500 characters total

Return ONLY the tags as a comma-separated list, nothing else."""
            
            tags_response = self.client.models.generate_content(
                model=self.model,
                contents=tags_prompt
            )
            tags = [tag.strip() for tag in tags_response.text.split(',') if tag.strip()]
            
            # Ensure we have at least some tags
            if not tags:
                tags = ['shorts', 'youtube', 'viral', 'trending']
            
            return {
                'enhanced_title': enhanced_title[:100],
                'enhanced_description': enhanced_description[:5000],
                'tags': tags[:500],
                'generated_at': datetime.now().isoformat(),
                'model_used': self.model
            }
            
        except Exception as e:
            log.error(f"Error generating metadata with Gemini: {e}")
            # Fallback to original content
            return {
                'enhanced_title': video_title[:100],
                'enhanced_description': video_description[:5000] if video_description else "Check out this awesome short! 🔥",
                'tags': ['shorts', 'youtube', 'viral', 'trending'],
                'generated_at': datetime.now().isoformat(),
                'model_used': 'fallback'
            }
