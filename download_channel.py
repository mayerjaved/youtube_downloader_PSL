# Docker commands to run this script (from the project root):
# 1. Build the image: docker build -t yt-downloader .
# 2. Run the container to download videos: 
# docker run --rm -v "$PWD/downloads:/app/downloads" yt-downloader

import yt_dlp
import os
import shutil
import glob

def get_ffmpeg_path():
    # Check system PATH first
    path = shutil.which("ffmpeg")
    if path: return path
    
    # Check Winget default installation path
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    winget_paths = glob.glob(os.path.join(local_app_data, r'Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg*\bin\ffmpeg.exe'))
    if winget_paths: return winget_paths[0]
    
    return None

def download_channel(channel_url, output_path="downloads", max_videos=10):
    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)
    
    # Configure yt-dlp options
    ydl_opts = {
        'ffmpeg_location': get_ffmpeg_path(),
        # Limit to the first N videos (for testing)
        'playlistend': max_videos,
        
        # Format selection: Best video + best audio, matched together
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        
        # Subtitle settings
        'writesubtitles': True,          # Download official subtitles
        'writeautomaticsubtitles': True, # Fallback to auto-generated subtitles
        'subtitleslangs': ['en.*', 'ur.*'], # Match English and Urdu variants (including auto-translated ur-en)
        'subtitlesformat': 'srt',        # Prefer SRT format
        'embedsubtitles': True,          # Embed subtitles into the video file (requires ffmpeg)
        
        # Post-processors for robust subtitle handling
        'postprocessors': [
            {'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'}, # Convert all to SRT
            {'key': 'FFmpegEmbedSubtitle'},                       # Embed into video
        ],
        
        # Workarounds for YouTube's 403 Forbidden / bot detection
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios', 'web']}
        },
        
        # Output template (e.g., downloads/Channel Name/Video Title [ID].mp4)
        'outtmpl': os.path.join(output_path, '%(uploader)s', '%(title)s [%(id)s].%(ext)s'),
        
        # Ignore errors for individual videos and continue downloading the rest
        'ignoreerrors': True,
        
        # Restrict sleep between requests to avoid rate limits (be gentle)
        'sleep_interval': 3,
        'max_sleep_interval': 7,
    }

    print(f"Starting download process for: {channel_url}")
    print(f"Videos will be saved to: {os.path.abspath(output_path)}")
    print("Warning: Embedding subtitles and merging best video/audio quality requires 'ffmpeg' to be installed.")

    # Start the downloading process
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([channel_url])
            print("\nDownload process completed!")
    except Exception as e:
        print(f"\nAn error occurred during the download process: {e}")

if __name__ == "__main__":
    # Channel URL provided
    url = "https://www.youtube.com/@pslhamzafoundationacademyf7624/videos"
    download_channel(url, max_videos=5)
