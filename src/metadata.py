import google.generativeai as genai
from typing import Dict, List, Tuple
from datetime import datetime
from src.logger import log
from src.config import Config

class MetadataGenerator:
    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
        
        # Set up generation config for consistent outputs
        self.generation_config = {
            "temperature": 0.8,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 200,
        }
    
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
            
            title_response = self.model.generate_content(title_prompt)
            enhanced_title = title_response.text.strip()
            
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
            
            desc_response = self.model.generate_content(desc_prompt)
            enhanced_description = desc_response.text.strip()
            
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
            
            tags_response = self.model.generate_content(tags_prompt)
            tags = [tag.strip() for tag in tags_response.text.split(',') if tag.strip()]
            
            # Ensure we have at least some tags
            if not tags:
                tags = ['shorts', 'youtube', 'viral', 'trending']
            
            return {
                'enhanced_title': enhanced_title[:100],  # YouTube limit
                'enhanced_description': enhanced_description[:5000],  # YouTube limit
                'tags': tags[:500],  # YouTube limits to 500 tags
                'generated_at': datetime.now().isoformat(),
                'model_used': 'gemini-pro'
            }
            
        except Exception as e:
            log.error(f"Error generating metadata with Gemini: {e}")
            # Fallback to original content
            return {
                'enhanced_title': video_title[:100],
                'enhanced_description': video_description[:5000],
                'tags': ['shorts', 'youtube', 'viral', 'trending'],
                'generated_at': datetime.now().isoformat(),
                'model_used': 'fallback'
            }
    
    def generate_thumbnail_ideas(self, video_title: str) -> List[str]:
        """Generate thumbnail ideas for the video using Gemini"""
        try:
            prompt = f"""Generate 3 specific thumbnail ideas for this YouTube Short. Be very specific about what elements to include.

Video title: {video_title}

Rules:
- Keep each idea under 50 words
- Be specific about expressions, text overlays, and colors
- Focus on YouTube Shorts thumbnail best practices
- Mention specific elements that should be visible

Return each idea on a new line prefixed with a number."""
            
            response = self.model.generate_content(prompt)
            ideas = [idea.strip() for idea in response.text.split('\n') if idea.strip() and any(c.isdigit() for c in idea[:2])]
            
            if not ideas:
                ideas = ["Surprised face reaction thumbnail with bold text overlay"]
            
            return ideas[:3]  # Limit to 3 ideas
            
        except Exception as e:
            log.error(f"Error generating thumbnail ideas: {e}")
            return ["Surprised face reaction thumbnail with text overlay"]
    
    def generate_hashtags(self, video_title: str, video_description: str) -> List[str]:
        """Generate optimized hashtags using Gemini"""
        try:
            prompt = f"""Generate 10 highly relevant and trending hashtags for this YouTube Short.

Video title: {video_title}
Video description: {video_description}

Rules:
- Start with the most relevant hashtags
- Include a mix of broad and specific tags
- Include trending hashtags when relevant
- Keep each hashtag under 30 characters
- No spaces in hashtags
- Include the channel name or personality if relevant

Return ONLY the hashtags as a space-separated list, nothing else."""
            
            response = self.model.generate_content(prompt)
            hashtags = response.text.strip().split()
            # Clean up hashtags
            hashtags = [tag if tag.startswith('#') else f'#{tag}' for tag in hashtags]
            return hashtags[:10]  # Limit to 10 hashtags
            
        except Exception as e:
            log.error(f"Error generating hashtags: {e}")
            return ['#shorts', '#youtube', '#viral', '#trending', '#video']
