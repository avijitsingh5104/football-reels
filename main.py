"""
Football Faceless Reels — Auto Generator
Niche: Football (Mix of facts, legends, moments, tactics)
Voice: Hype & energetic
Pipeline: Gemini → Edge TTS → Pexels (smart search) → FFmpeg → YouTube
"""

import os
import re
import json
import time
import random
import asyncio
import requests
import subprocess
from pathlib import Path
from datetime import datetime

from google import genai as google_genai
import edge_tts
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

# ─── CONFIG ───────────────────────────────────────────────────────────────────

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
YOUTUBE_TOKEN  = os.environ["YOUTUBE_TOKEN"]

NICHE          = "Football"
REEL_DURATION  = 45
VOICE          = "en-US-TonyNeural"      # hype & energetic male voice
MUSIC_VOLUME   = 0.15
OUTPUT_DIR     = Path("output")
ASSETS_DIR     = Path("assets")
TOPICS_FILE    = Path("topics.txt")

OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

# ─── SMART FOOTAGE KEYWORDS ───────────────────────────────────────────────────
# Maps topic keywords to the best Pexels search queries for relevant footage

FOOTAGE_MAP = {
    # Players / legends
    "messi":       ["football dribbling skills", "soccer player celebration", "football crowd stadium"],
    "ronaldo":     ["football player running", "soccer goal celebration", "football stadium night"],
    "ronaldinho":  ["football skills tricks", "soccer dribbling", "football crowd cheering"],
    "pele":        ["football vintage", "soccer match crowd", "football trophy celebration"],
    "maradona":    ["football match stadium", "soccer player skills", "football crowd vintage"],
    "mbappe":      ["football sprinting speed", "soccer player fast", "football match action"],
    "neymar":      ["football skills dribbling", "soccer tricks", "football crowd brazil"],

    # Clubs
    "barcelona":   ["football stadium barcelona", "soccer match crowd", "football tiki taka"],
    "real madrid": ["football stadium night lights", "soccer match action", "football trophy"],
    "manchester":  ["football stadium england", "soccer match premier league", "football crowd"],
    "liverpool":   ["football stadium anfield", "soccer match crowd", "football celebration"],
    "juventus":    ["football stadium italy", "soccer match serie a", "football action"],
    "chelsea":     ["football stadium england", "soccer match action", "football players"],
    "arsenal":     ["football stadium london", "soccer match action", "football crowd"],
    "psg":         ["football stadium paris", "soccer match action", "football celebration"],
    "bayern":      ["football stadium germany", "soccer match bundesliga", "football action"],

    # Competitions
    "world cup":   ["world cup football stadium", "soccer crowd celebration", "football trophy"],
    "champions league": ["football stadium night", "soccer match action", "football champions"],
    "premier league":   ["football england stadium", "soccer match crowd", "football action"],
    "la liga":     ["football spain stadium", "soccer match action", "football crowd"],
    "serie a":     ["football italy stadium", "soccer match action", "football players"],

    # Topics
    "goal":        ["football goal celebration", "soccer goal scored", "football crowd eruption"],
    "record":      ["football trophy collection", "soccer celebration", "football stadium crowd"],
    "transfer":    ["football player signing", "soccer contract", "football stadium"],
    "tactics":     ["football training tactics", "soccer team formation", "football coach"],
    "history":     ["football vintage match", "soccer history classic", "football old stadium"],
    "legend":      ["football legend celebration", "soccer trophy", "football crowd cheering"],
    "fact":        ["football stadium aerial", "soccer match action", "football crowd"],
    "skill":       ["football skills freestyle", "soccer tricks", "football dribbling"],
    "speed":       ["football player sprinting", "soccer fast player", "football match speed"],
    "penalty":     ["football penalty kick", "soccer penalty shootout", "football goalkeeper"],
    "goalkeeper":  ["football goalkeeper save", "soccer goalie", "football goal kick"],
    "free kick":   ["football free kick", "soccer free kick goal", "football wall"],
    "header":      ["football header goal", "soccer aerial ball", "football corner kick"],
    "injury":      ["football player injured", "soccer medical staff", "football stretcher"],
    "comeback":    ["football comeback celebration", "soccer crowd cheering", "football match"],
    "debut":       ["football young player", "soccer debut match", "football crowd"],
    "hat trick":   ["football hat trick celebration", "soccer three goals", "football crowd"],
    "coach":       ["football coach sideline", "soccer manager tactics", "football team huddle"],
    "team":        ["football team celebration", "soccer squad", "football training"],
    "stadium":     ["football stadium aerial", "soccer crowd stadium", "football pitch"],
}

DEFAULT_FOOTBALL_QUERIES = [
    "football stadium crowd",
    "soccer match action",
    "football player celebration",
    "soccer skills dribbling",
    "football goal scored",
]

def get_smart_queries(topic: str) -> list[str]:
    """Match topic keywords to best footage queries."""
    topic_lower = topic.lower()
    matched = []
    for keyword, queries in FOOTAGE_MAP.items():
        if keyword in topic_lower:
            matched.extend(queries)
    if not matched:
        matched = DEFAULT_FOOTBALL_QUERIES
    # pick 5 unique queries
    seen, result = set(), []
    for q in matched:
        if q not in seen:
            seen.add(q)
            result.append(q)
        if len(result) == 5:
            break
    while len(result) < 5:
        result.append(random.choice(DEFAULT_FOOTBALL_QUERIES))
    return result

# ─── STEP 1 — PICK TODAY'S TOPIC ─────────────────────────────────────────────

def get_todays_topic() -> str:
    lines = [l.strip() for l in TOPICS_FILE.read_text().splitlines() if l.strip()]
    if not lines:
        raise ValueError("topics.txt is empty!")
    idx = datetime.now().timetuple().tm_yday % len(lines)
    topic = lines[idx]
    print(f"[1/6] Today's topic: {topic}")
    return topic

# ─── STEP 2 — GENERATE SCRIPT ────────────────────────────────────────────────

def generate_script(topic: str) -> str:
    print("[2/6] Generating script with Gemini...")
    client = google_genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""You are a hype scriptwriter for viral football faceless reels.

Write a {REEL_DURATION}-second voiceover script about:
"{topic}"

Rules:
- Open with a SHOCKING or jaw-dropping statement — no "Did you know"
- High energy, punchy sentences. Use "..." for dramatic pauses
- Build hype and tension throughout
- Drop the mind-blowing fact or story at the peak
- End with a powerful one-liner that hits hard
- Plain text ONLY. No asterisks, no markdown, no stage directions
- Aim for ~110 words

Return ONLY the script."""

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=prompt
    )
    script = response.text.strip()
    print(f"    Script ({len(script.split())} words): {script[:80]}...")
    return script

# ─── STEP 3 — VOICEOVER ──────────────────────────────────────────────────────

async def _tts(script: str, out: Path):
    communicate = edge_tts.Communicate(script, VOICE, rate="+8%", volume="+15%")
    await communicate.save(str(out))

def generate_voiceover(script: str) -> Path:
    print("[3/6] Generating voiceover with Edge TTS...")
    out = OUTPUT_DIR / "voiceover.mp3"
    asyncio.run(_tts(script, out))
    print(f"    Saved: {out}")
    return out

# ─── STEP 4 — FETCH SMART FOOTAGE ────────────────────────────────────────────

def fetch_pexels_videos(topic: str, n_clips: int = 5) -> list[Path]:
    print("[4/6] Fetching smart football footage from Pexels...")
    headers = {"Authorization": PEXELS_API_KEY}
    queries = get_smart_queries(topic)
    print(f"    Using queries: {queries}")
    clips = []

    for i, query in enumerate(queries[:n_clips]):
        url = f"https://api.pexels.com/videos/search?query={query}&per_page=8&orientation=portrait&size=medium"
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        videos = r.json().get("videos", [])
        if not videos:
            # fallback to landscape if no portrait
            url = f"https://api.pexels.com/videos/search?query={query}&per_page=8&size=medium"
            r = requests.get(url, headers=headers, timeout=15)
            videos = r.json().get("videos", [])
        if not videos:
            continue

        video = random.choice(videos[:5])
        files = sorted(video["video_files"], key=lambda x: x.get("width", 0))
        vfile = next((f for f in files if f.get("width", 0) >= 720), files[-1])

        clip_path = ASSETS_DIR / f"clip_{i}.mp4"
        with requests.get(vfile["link"], stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(clip_path, "wb") as f:
                for chunk in resp.iter_content(65536):
                    f.write(chunk)
        clips.append(clip_path)
        print(f"    Clip {i+1}: '{query}'")
        time.sleep(0.3)

    return clips

# ─── STEP 5 — BUILD VIDEO ─────────────────────────────────────────────────────

def get_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

def download_lofi_music() -> Path:
    music_path = ASSETS_DIR / "music.mp3"
    if music_path.exists():
        return music_path
    try:
        url = "https://archive.org/download/lofi_20231231/lofi_chill.mp3"
        r = requests.get(url, timeout=30, stream=True)
        r.raise_for_status()
        with open(music_path, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
    except Exception:
        subprocess.run([
            "ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "120", "-q:a", "9", "-acodec", "libmp3lame",
            str(music_path), "-y"
        ], check=True, capture_output=True)
    return music_path

def build_video(clips: list[Path], voiceover: Path, script: str, topic: str) -> Path:
    print("[5/6] Assembling video with FFmpeg...")
    audio_dur = get_audio_duration(voiceover)
    clip_dur  = audio_dur / max(len(clips), 1)

    # 1. Scale & crop each clip to 1080x1920
    scaled = []
    for i, clip in enumerate(clips):
        out = ASSETS_DIR / f"scaled_{i}.mp4"
        subprocess.run([
            "ffmpeg", "-i", str(clip), "-t", str(clip_dur),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                   "crop=1080:1920,setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-an", str(out), "-y"
        ], check=True, capture_output=True)
        scaled.append(out)

    # 2. Concatenate
    concat_list = ASSETS_DIR / "concat.txt"
    concat_list.write_text("\n".join(f"file '{p.resolve()}'" for p in scaled))
    concat_out = ASSETS_DIR / "concat.mp4"
    subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(concat_out), "-y"
    ], check=True, capture_output=True)

    # 3. Music
    music = download_lofi_music()

    # 4. SRT captions
    srt_path = ASSETS_DIR / "captions.srt"
    words = script.split()
    words_per_sec = len(words) / audio_dur
    chunk_size = 6
    chunks = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)]
    srt_lines = []
    for idx, chunk in enumerate(chunks):
        word_start = idx * chunk_size
        t_start = word_start / words_per_sec
        t_end   = min((word_start + len(chunk)) / words_per_sec, audio_dur)
        def fmt(s):
            h=int(s//3600); m=int((s%3600)//60); sec=int(s%60); ms=int((s-int(s))*1000)
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
        srt_lines.append(f"{idx+1}\n{fmt(t_start)} --> {fmt(t_end)}\n{' '.join(chunk)}\n")
    srt_path.write_text("\n".join(srt_lines))

    # 5. Final render
    final_out = OUTPUT_DIR / "final_reel.mp4"
    srt_escaped = str(srt_path).replace("\\", "/")
    subtitle_filter = (
        f"subtitles={srt_escaped}:force_style='"
        "FontName=Arial,FontSize=22,PrimaryColour=&HFFFFFF,"
        "OutlineColour=&H000000,Outline=3,Bold=1,Alignment=2'"
    )
    subprocess.run([
        "ffmpeg",
        "-i", str(concat_out),
        "-i", str(voiceover),
        "-i", str(music),
        "-filter_complex",
        f"[0:v]{subtitle_filter}[v];"
        f"[1:a]volume=1.0[voice];"
        f"[2:a]volume={MUSIC_VOLUME},aloop=loop=-1:size=44100*120[bg];"
        f"[voice][bg]amix=inputs=2:duration=first[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(audio_dur),
        "-movflags", "+faststart",
        str(final_out), "-y"
    ], check=True)
    print(f"    Final video: {final_out}")
    return final_out

# ─── STEP 6 — UPLOAD TO YOUTUBE ──────────────────────────────────────────────

def upload_to_youtube(video_path: Path, topic: str, script: str):
    print("[6/6] Uploading to YouTube Shorts...")
    creds_data = json.loads(YOUTUBE_TOKEN)
    creds = Credentials(
        token=creds_data["token"],
        refresh_token=creds_data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
    )
    youtube = build("youtube", "v3", credentials=creds)

    sentences = re.split(r'(?<=[.!?])\s+', script)
    description = " ".join(sentences[:2]) + "\n\n#Shorts #Football #Soccer #FootballFacts #FootballHistory"

    body = {
        "snippet": {
            "title": topic[:95] + (" #Shorts" if len(topic) < 88 else ""),
            "description": description,
            "tags": ["shorts", "football", "soccer", "football facts", "football history", "football legends"],
            "categoryId": "17",  # Sports
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"    Uploading... {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"    ✓ Uploaded! https://youtube.com/shorts/{video_id}")
    return video_id

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*50}")
    print(f"  Football Reels — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    topic     = get_todays_topic()
    script    = generate_script(topic)
    voiceover = generate_voiceover(script)
    clips     = fetch_pexels_videos(topic, n_clips=5)
    video     = build_video(clips, voiceover, script, topic)
    video_id  = upload_to_youtube(video, topic, script)

    print(f"\n✓ Done! Reel posted: {topic}")
    print(f"  Watch: https://youtube.com/shorts/{video_id}\n")

if __name__ == "__main__":
    main()
