# Docker command to run this server (from the project root):
# docker run --rm -d -p 8000:8000 -v "$PWD:/app" -w /app/player python:3.9-slim python server.py

import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
from datetime import datetime

# Configuration
PORT = 8000
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'downloads')
PLAYER_DIR = os.path.dirname(os.path.abspath(__file__))

print(f"Scanning downloads directory: {DOWNLOADS_DIR}")

def get_video_files():
    """Scans the downloads directory and groups video files with their subtitles."""
    videos = []
    
    if not os.path.exists(DOWNLOADS_DIR):
        print("Downloads directory not found!")
        return videos

    # Look through all channel folders inside downloads/
    for root, _, files in os.walk(DOWNLOADS_DIR):
        # We process files grouped by their base name (excluding extension)
        file_groups = {}
        
        for file in files:
            # Simple grouping strategy: anything before the last dot is the base name
            # However, yt-dlp might output .f137.mp4, etc.
            # Let's group by the unique video ID in the bracket: [VideoID]
            import re
            match = re.search(r'\[(.*?)\]', file)
            if not match:
                continue
                
            video_id = match.group(1)
            
            if video_id not in file_groups:
                file_groups[video_id] = {
                    'id': video_id,
                    'title': file.split('[')[0].strip(),
                    'video_file': None,
                    'ext': None,
                    'en_sub': None,
                    'ur_sub': None,
                    'channel_path': root
                }
                
            group = file_groups[video_id]
            
            # Check for video files (mp4, webm, mkv)
            if file.endswith('.mp4') or file.endswith('.webm') or file.endswith('.mkv'):
                # Prefer .mp4 if multiple exist, or just take the first video file found
                if not group['video_file'] or file.endswith('.mp4'):
                    group['video_file'] = file
                    group['ext'] = file.split('.')[-1]
                    
            # Check for english subtitles
            elif file.endswith('.en.srt') or file.endswith('.en.vtt'):
                group['en_sub'] = file
                
            # Check for urdu subtitles
            elif file.endswith('.ur.srt') or file.endswith('.ur.vtt'):
                group['ur_sub'] = file

        # Now that we've grouped them, add the valid ones to our list
        for vid_id, data in file_groups.items():
            if data['video_file']:
                # Construct the relative path from the downloads dir for serving
                rel_dir = os.path.relpath(data['channel_path'], DOWNLOADS_DIR)
                if rel_dir == '.':
                    rel_dir = ''
                
                vid_path = os.path.join(rel_dir, data['video_file']).replace('\\', '/')
                en_path = os.path.join(rel_dir, data['en_sub']).replace('\\', '/') if data['en_sub'] else None
                ur_path = os.path.join(rel_dir, data['ur_sub']).replace('\\', '/') if data['ur_sub'] else None
                
                videos.append({
                    'id': data['id'],
                    'title': data['title'],
                    'filename': vid_path,
                    'ext': data['ext'],
                    'has_en_sub': bool(data['en_sub']),
                    'en_sub_file': en_path,
                    'has_ur_sub': bool(data['ur_sub']),
                    'ur_sub_file': ur_path
                })
                
    return videos

class VideoPlayerHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        # Prevent caching for development
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        return super().end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        # 1. API endpoint to get videos
        if path == '/api/videos':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            videos = get_video_files()
            response = {
                'status': 'success',
                'count': len(videos),
                'videos': videos
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return

        # 2. Serve files from the downloads directory under /files/
        elif path.startswith('/files/'):
            # Strip '/files' but keep the leading slash, leaving the rest URL-encoded
            self.path = self.path[6:]
            
            # Temporarily change directory to serve the file
            original_dir = os.getcwd()
            os.chdir(DOWNLOADS_DIR)
            
            # Let simple HTTP request handler serve the file (handles range requests and decoding!)
            result = super().do_GET()
            
            # Restore directory
            os.chdir(original_dir)
            return result

        # 3. Serve the player UI (index.html) from the player directory
        elif path == '/' or path == '/index.html':
            self.path = '/index.html'
            # Temporarily change to player directory
            original_dir = os.getcwd()
            os.chdir(PLAYER_DIR)
            result = super().do_GET()
            os.chdir(original_dir)
            return result
            
        # 4. 404 for anything else
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')
            return

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, VideoPlayerHandler)
    print(f"\n=======================================================")
    print(f"Server is running! Open your browser to:")
    print(f"http://localhost:{PORT}")
    print(f"=======================================================\n")
    print(f"Press Ctrl+C to stop the server.")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == '__main__':
    run_server()
