import openai
from typing import Dict, List, Tuple
from datetime import datetime
from src.logger import log
from src.config import Config

class MetadataGenerator:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
    
    def generate_metadata(self, video_title: str, video_description: str) -> Dict:
        """Generate enhanced metadata for the video"""
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
            
            title_response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a viral video title expert for YouTube Shorts."},
                    {"role": "user", "content": title_prompt}
                ],
                max_tokens=100,
                temperature=0.8
            )
            enhanced_title = title_response.choices[0].message.content.strip()
            
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
            
            desc_response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a YouTube Shorts description expert."},
                    {"role": "user", "content": desc_prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            enhanced_description = desc_response.choices[0].message.content.strip()
            
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
            
            tags_response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a YouTube SEO expert."},
                    {"role": "user", "content": tags_prompt}
                ],
                max_tokens=150,
                temperature=0.6
            )
            tags = [tag.strip() for tag in tags_response.choices[0].message.content.split(',')]
            
            return {
                'enhanced_title': enhanced_title,
                'enhanced_description': enhanced_description,
                'tags': tags,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            log.error(f"Error generating metadata: {e}")
            # Fallback to original content
            return {
                'enhanced_title': video_title,
                'enhanced_description': video_description,
                'tags': ['shorts', 'youtube', 'viral'],
                'generated_at': datetime.now().isoformat()
            }
    
    def generate_thumbnail_ideas(self, video_title: str) -> List[str]:
        """Generate thumbnail ideas for the video"""
        try:
            prompt = f"""Generate 3 specific thumbnail ideas for this YouTube Short. Be very specific about what elements to include.

Video title: {video_title}

Rules:
- Keep each idea under 50 words
- Be specific about expressions, text overlays, and colors
- Focus on YouTube Shorts thumbnail best practices
- Mention specific elements that should be visible

Return each idea on a new line prefixed with a number."""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a YouTube thumbnail design expert."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            ideas = [idea.strip() for idea in response.choices[0].message.content.split('\n') if idea.strip()]
            return ideas
            
        except Exception as e:
            log.error(f"Error generating thumbnail ideas: {e}")
            return ["Surprised face reaction thumbnail with text overlay"]
