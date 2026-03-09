"""
Extract labeled video clips from downloaded YouTube videos for sign language model training.

For each video that has an .en.srt subtitle file, this script:
1. Parses the SRT file to find all subtitle entries (timestamp + text).
2. Uses ffmpeg to cut the video into one clip per subtitle entry.
3. Saves each clip as a numbered .mp4 with a corresponding .txt label file.
4. If a .ur.srt file exists, includes the Urdu translation in the label file.

Output structure:
  Training_Dataset_Clips/
    <video_name>/
      001.mp4    # clip for subtitle entry 1
      001.txt    # "en: <english text>\nur: <urdu text>"
      002.mp4
      002.txt
      ...

Usage:
  python extract_clips.py
  python extract_clips.py --input "D:\PSL_Downloads\PSL Hamza Foundation Academy for the Deaf" --output "D:\PSL_Downloads\Training_Dataset_Clips"
  python extract_clips.py --max-videos 5   # process only 5 videos (for testing)
"""

import os
import re
import subprocess
import shutil
import glob
import argparse


def get_ffmpeg_path():
    """Find ffmpeg on the system."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    # Check Winget default installation path (Windows)
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    winget_paths = glob.glob(os.path.join(local_app_data, r'Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg*\bin\ffmpeg.exe'))
    if winget_paths:
        return winget_paths[0]
    return "ffmpeg"  # hope it's on PATH


def parse_srt(srt_path):
    """
    Parse an SRT subtitle file and return a list of entries.
    Each entry is a dict: {'index': int, 'start': float, 'end': float, 'text': str}
    Times are in seconds.
    """
    # Try multiple encodings since some translated subtitle files may not be UTF-8
    for encoding in ['utf-8', 'utf-8-sig', 'latin-1']:
        try:
            with open(srt_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        # Last resort: read with replacement characters
        with open(srt_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

    # Split into blocks separated by blank lines
    blocks = re.split(r'\n\s*\n', content.strip())
    entries = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        # Line 1: index number
        try:
            index = int(lines[0].strip())
        except ValueError:
            continue

        # Line 2: timecodes  "HH:MM:SS,mmm --> HH:MM:SS,mmm"
        time_match = re.match(
            r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})',
            lines[1].strip()
        )
        if not time_match:
            continue

        g = time_match.groups()
        start_sec = int(g[0]) * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000.0
        end_sec = int(g[4]) * 3600 + int(g[5]) * 60 + int(g[6]) + int(g[7]) / 1000.0

        # Lines 3+: subtitle text (may span multiple lines)
        text = ' '.join(line.strip() for line in lines[2:] if line.strip())

        if text:
            entries.append({
                'index': index,
                'start': start_sec,
                'end': end_sec,
                'text': text,
            })

    return entries


def parse_srt_as_dict(srt_path):
    """Parse SRT and return a dict mapping index -> text for quick lookup."""
    entries = parse_srt(srt_path)
    return {e['index']: e['text'] for e in entries}


def extract_clip(ffmpeg_path, video_path, start_sec, end_sec, output_path):
    """
    Use ffmpeg to extract a clip from the video.
    Uses re-encoding for frame-accurate cuts.
    """
    duration = end_sec - start_sec
    if duration <= 0:
        return False

    cmd = [
        ffmpeg_path,
        '-y',                           # overwrite output
        '-ss', f'{start_sec:.3f}',      # seek to start (before -i for fast seek)
        '-i', video_path,
        '-t', f'{duration:.3f}',        # duration of clip
        '-c:v', 'libx264',             # re-encode video for accurate cuts
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',                 # re-encode audio
        '-b:a', '128k',
        '-avoid_negative_ts', 'make_zero',
        '-loglevel', 'error',
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"    ffmpeg error: {result.stderr.strip()}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"    ffmpeg timed out for clip at {start_sec:.1f}s")
        return False


def process_video(ffmpeg_path, video_path, en_srt_path, ur_srt_path, output_dir):
    """
    Process a single video: parse its SRT, extract clips, save labels.
    Returns the number of clips successfully extracted.
    """
    # Parse English subtitles
    en_entries = parse_srt(en_srt_path)
    if not en_entries:
        print(f"  No subtitle entries found, skipping.")
        return 0

    # Parse Urdu subtitles if available (matched by index)
    ur_texts = {}
    if ur_srt_path and os.path.exists(ur_srt_path):
        ur_texts = parse_srt_as_dict(ur_srt_path)

    os.makedirs(output_dir, exist_ok=True)

    clips_created = 0
    for entry in en_entries:
        clip_num = f"{entry['index']:03d}"
        clip_path = os.path.join(output_dir, f"{clip_num}.mp4")
        label_path = os.path.join(output_dir, f"{clip_num}.txt")

        # Skip if clip already exists (resume support)
        if os.path.exists(clip_path) and os.path.exists(label_path):
            clips_created += 1
            continue

        # Extract the clip
        success = extract_clip(ffmpeg_path, video_path, entry['start'], entry['end'], clip_path)
        if not success:
            continue

        # Write the label file
        label_lines = [f"en: {entry['text']}"]
        ur_text = ur_texts.get(entry['index'])
        if ur_text:
            label_lines.append(f"ur: {ur_text}")
        label_lines.append(f"start: {entry['start']:.3f}")
        label_lines.append(f"end: {entry['end']:.3f}")

        with open(label_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(label_lines) + '\n')

        clips_created += 1

    return clips_created


def main():
    parser = argparse.ArgumentParser(description='Extract labeled video clips from downloaded YouTube videos.')
    parser.add_argument('--input', default=None,
                        help='Input directory containing .mp4 and .srt files. '
                             'Defaults to D:\\PSL_Downloads\\PSL Hamza Foundation Academy for the Deaf (Windows) '
                             'or downloads/ (Linux/Docker).')
    parser.add_argument('--output', default=None,
                        help='Output directory for training clips. '
                             'Defaults to D:\\PSL_Downloads\\Training_Dataset_Clips (Windows) '
                             'or downloads/Training_Dataset_Clips (Linux/Docker).')
    parser.add_argument('--max-videos', type=int, default=None,
                        help='Maximum number of videos to process (for testing).')
    args = parser.parse_args()

    # Smart defaults based on OS
    if os.name == 'nt':
        default_input = r"D:\PSL_Downloads\PSL Hamza Foundation Academy for the Deaf"
        default_output = r"D:\PSL_Downloads\Training_Dataset_Clips"
    else:
        default_input = "downloads"
        default_output = os.path.join("downloads", "Training_Dataset_Clips")

    input_dir = args.input or default_input
    output_dir = args.output or default_output

    ffmpeg_path = get_ffmpeg_path()
    print(f"Using ffmpeg: {ffmpeg_path}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    if not os.path.isdir(input_dir):
        print(f"ERROR: Input directory not found: {input_dir}")
        return

    # Find all .mp4 files that have a matching .en.srt file
    video_files = []
    for f in os.listdir(input_dir):
        if f.endswith('.mp4'):
            base = f[:-4]  # strip .mp4
            en_srt = os.path.join(input_dir, base + '.en.srt')
            if os.path.exists(en_srt):
                video_files.append(f)

    video_files.sort()
    total = len(video_files)
    print(f"\nFound {total} videos with English subtitles.")

    if args.max_videos:
        video_files = video_files[:args.max_videos]
        print(f"Processing only the first {args.max_videos} videos.")

    total_clips = 0
    for i, video_file in enumerate(video_files, 1):
        base = video_file[:-4]
        video_path = os.path.join(input_dir, video_file)
        en_srt_path = os.path.join(input_dir, base + '.en.srt')
        ur_srt_path = os.path.join(input_dir, base + '.ur.srt')

        # Create a subdirectory for this video's clips
        # Use the video filename (without extension) as the folder name
        clip_dir = os.path.join(output_dir, base)

        print(f"\n[{i}/{len(video_files)}] Processing: {video_file}")
        print(f"  Output: {clip_dir}")

        clips = process_video(ffmpeg_path, video_path, en_srt_path, ur_srt_path, clip_dir)
        total_clips += clips
        print(f"  Created {clips} clips.")

    print(f"\n{'='*60}")
    print(f"Done! Total clips extracted: {total_clips}")
    print(f"Clips saved to: {output_dir}")


if __name__ == "__main__":
    main()
