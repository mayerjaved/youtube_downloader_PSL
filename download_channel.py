"""
# Docker commands to run this script (from the project root):
# 1. Build the image: docker build -t yt-downloader .
docker build -t yt-downloader .

# 2. Run the container to download videos to your D: drive: 
docker run --rm -it -v "D:\PSL_Downloads:/app/downloads" yt-downloader
docker run --rm -it -v "D:\PSL_Downloads:/app/downloads" yt-downloader

"""
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

def download_channel(channel_url, output_path="downloads"):
    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)
    
    # Configure yt-dlp options
    ydl_opts = {
        'ffmpeg_location': get_ffmpeg_path(),
        # Download all videos in the playlist/channel
        
        # Format selection: Best video + best audio, matched together
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        
        # Subtitle settings
        'writesubtitles': True,          # Download official subtitles
        'writeautomaticsubtitles': True, # Fallback to auto-generated subtitles
        'subtitleslangs': ['en', 'ur', 'ur-en', 'en.*', 'ur.*'], # Match English, Urdu, and YouTube's specific auto-translated 'ur-en' (Urdu from English) variant
        'subtitlesformat': 'srt',        # Prefer SRT format
        # Disable embedding so the individual .srt files remain on disk for the web player
        'embedsubtitles': False,          
        
        # Post-processors for robust subtitle handling
        'postprocessors': [
            {'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'}, # Convert all to SRT
        ],
        
        # Workarounds for YouTube's 403 Forbidden / bot detection
        'extractor_args': {
            'youtube': {'player_client': ['android', 'ios', 'web']}
        },
        
        # Output template (e.g., downloads/Channel Name/Video Title [ID].mp4)
        'outtmpl': os.path.join(output_path, '%(uploader)s', '%(title)s [%(id)s].%(ext)s'),
        
        # Keep track of downloaded videos so we only download new ones
        'download_archive': os.path.join(output_path, 'downloaded.txt'),
        
        # Ignore errors for individual videos and continue downloading the rest
        'ignoreerrors': True,
        
        # Restrict sleep between requests to avoid rate limits (be gentle)
        'sleep_interval': 5,
        'max_sleep_interval': 15,
        'sleep_subtitles': 3, # Wait 3 seconds before requesting subtitle data to avoid HTTP 429 Too Many Requests
    }

    print(f"Starting download process for: {channel_url}")
    print(f"Videos will be saved to: {os.path.abspath(output_path)}")
    print("Warning: Embedding subtitles and merging best video/audio quality requires 'ffmpeg' to be installed.")

    # Start the downloading process
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([channel_url])
            print("\nDownload process completed!")
            
            # Since YouTube is currently blocking/withholding urdu subtitles due to rate-limiting requests
            # on auto-translated captions, we will translate the freshly downloaded english captions locally.
            print("\nTranslating downloaded English subtitles to Urdu...")
            _translate_subtitles_to_urdu(output_path)
            
    except Exception as e:
        print(f"\nAn error occurred during the download process: {e}")

def _translate_subtitles_to_urdu(output_path):
    """Finds all .en.srt files in the output path and translates them to .ur.srt using googletrans."""
    try:
        from googletrans import Translator
    except ImportError:
        print("googletrans is not installed. Skipping local Urdu subtitle generation.")
        return

    translator = Translator()
    
    # Recursively find all .en.srt files in the output path
    for root, _, files in os.walk(output_path):
        for file in files:
            if file.endswith('.en.srt'):
                en_path = os.path.join(root, file)
                ur_path = en_path.replace('.en.srt', '.ur.srt')
                
                # Skip if already translated
                if os.path.exists(ur_path):
                    continue
                    
                print(f"Translating: {file} -> Urdu...")
                try:
                    with open(en_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    translated_lines = []
                    # SRT files have structure: Index \n Timecode \n Subtitle Text \n\n
                    for i, line in enumerate(lines):
                        line_stripped = line.strip()
                        # If it's empty, an index number, or a timecode, keep it as is
                        if not line_stripped or line_stripped.isdigit() or '-->' in line_stripped:
                            translated_lines.append(line)
                        else:
                            # It's actual subtitle text, translate it
                            try:
                                result = translator.translate(line_stripped, src='en', dest='ur')
                                translated_lines.append(result.text + '\n')
                            except Exception as e:
                                # Fallback to original text if translation fails
                                print(f"  Warning: Translation failed for line '{line_stripped}': {e}")
                                translated_lines.append(line)
                                
                    with open(ur_path, 'w', encoding='utf-8') as f:
                        f.writelines(translated_lines)
                        
                    print(f"Successfully created: {os.path.basename(ur_path)}")
                except Exception as e:
                    print(f"Failed to translate {en_path}: {e}")

if __name__ == "__main__":
    # Channel URL provided
    url = "https://www.youtube.com/@pslhamzafoundationacademyf7624/videos"
    
    import os
    # If running normally on Windows, use D: drive. 
    # If running inside Linux Docker container, use the 'downloads' folder which Docker maps to the D: drive.
    dest_path = r"D:\PSL_Downloads" if os.name == 'nt' else "downloads"
    
    download_channel(url, output_path=dest_path)
