def download_video(self, video_id: str, output_path: str) -> bool:
    """Download a video using yt-dlp"""
    try:
        import yt_dlp
        
        # Try different format options
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # More flexible format
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'prefer_insecure': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Try to download
            try:
                ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
                log.info(f"Downloaded video {video_id} to {output_path}")
                return True
            except Exception as e:
                log.warning(f"First download attempt failed: {e}")
                
                # Try alternative format
                ydl_opts['format'] = 'best'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                    ydl2.download([f'https://www.youtube.com/watch?v={video_id}'])
                    log.info(f"Downloaded video {video_id} with alternative format")
                    return True
        
    except Exception as e:
        log.error(f"Error downloading video: {e}")
        return False
