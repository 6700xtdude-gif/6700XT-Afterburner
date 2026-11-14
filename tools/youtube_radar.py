"""
YouTube Idea Radar for 6700XT-Afterburner / Strata
==================================================
Tracks YouTube videos watched in Google Chrome / Microsoft Edge,
fetches transcripts via youtube-transcript-api, and extracts actionable
silicon & software optimization ideas for the AMD Radeon RX 6700 XT.
"""

import os
import sys
import json
import shutil
import sqlite3
import tempfile
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi

ROOT_DIR = Path(__file__).resolve().parent.parent
RADAR_MD = ROOT_DIR / "docs" / "YOUTUBE_IDEA_RADAR.md"
LEDGER_JSONL = ROOT_DIR / "MEMORY" / "watched_youtube_ledger.jsonl"


def extract_video_id(url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(url)
        if "youtube.com" in parsed.netloc:
            qs = urllib.parse.parse_qs(parsed.query)
            return qs.get("v", [None])[0]
        elif "youtu.be" in parsed.netloc:
            return parsed.path.lstrip("/").split("?")[0]
    except Exception:
        pass
    return None


def get_browser_history(browser="chrome", limit=15):
    if browser == "chrome":
        hist_path = Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\History"))
    elif browser == "edge":
        hist_path = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\History"))
    else:
        return []

    if not hist_path.exists():
        return []

    temp_path = Path(tempfile.gettempdir()) / f"{browser}_history_temp.db"
    try:
        shutil.copy2(hist_path, temp_path)
    except Exception as e:
        print(f"[!] Could not copy {browser} history: {e}")
        return []

    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()
    query = """
    SELECT url, title, last_visit_time
    FROM urls
    WHERE url LIKE '%youtube.com/watch?v=%' OR url LIKE '%youtu.be/%'
    ORDER BY last_visit_time DESC
    LIMIT ?
    """
    records = []
    try:
        cursor.execute(query, (limit,))
        epoch_start = datetime(1601, 1, 1)
        for url, title, visit_time in cursor.fetchall():
            vid = extract_video_id(url)
            if not vid:
                continue
            visit_dt = epoch_start + timedelta(microseconds=visit_time)
            clean_title = (title or "").replace(" - YouTube", "").strip()
            records.append({
                "video_id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "title": clean_title,
                "visited_at": visit_dt.strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        print(f"[!] Error querying SQLite: {e}")
    finally:
        conn.close()
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Deduplicate by video_id
    seen = set()
    deduped = []
    for r in records:
        if r["video_id"] not in seen:
            seen.add(r["video_id"])
            deduped.append(r)
    return deduped


def get_logged_video_ids() -> set:
    if not LEDGER_JSONL.exists():
        return set()
    logged = set()
    with open(LEDGER_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                logged.add(data.get("video_id"))
            except Exception:
                pass
    return logged


def fetch_transcript_text(video_id: str) -> str | None:
    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=["en", "en-US", "en-GB"])
        lines = []
        for item in transcript:
            if isinstance(item, dict):
                lines.append(item.get("text", ""))
            else:
                lines.append(getattr(item, "text", ""))
        return " ".join(lines)
    except Exception as e:
        # Try any available transcript
        try:
            tl = YouTubeTranscriptApi().list(video_id)
            for t in tl:
                tr = t.fetch()
                return " ".join([x.get("text", "") if isinstance(x, dict) else getattr(x, "text", "") for x in tr])
        except Exception:
            return None


def extract_ideas_heuristic(title: str, text: str) -> dict:
    """
    Analyzes transcript text against 6700XT / Strata hardware invariants.
    """
    text_lower = text.lower() if text else ""
    
    tags = []
    if any(k in text_lower for k in ["moe", "mixture of experts", "expert", "ncmoe"]):
        tags.append("MoE-Architecture")
    if any(k in text_lower for k in ["speculative", "speculation", "draft", "mtp", "eagle"]):
        tags.append("Speculative-Decoding")
    if any(k in text_lower for k in ["cache", "infinity cache", "l3", "sram", "kv cache"]):
        tags.append("Cache-Hierarchy")
    if any(k in text_lower for k in ["bandwidth", "192-bit", "gddr6", "ddr4", "pcie", "offload"]):
        tags.append("Memory-Bandwidth")
    if any(k in text_lower for k in ["quantization", "gguf", "imatrix", "iq2", "q4_k"]):
        tags.append("Quantization")
    if any(k in text_lower for k in ["vulkan", "rocm", "amd", "navi", "rdna"]):
        tags.append("AMD-Vulkan-ROCm")
    if any(k in text_lower for k in ["context", "prompt caching", "chunking", "kv shift"]):
        tags.append("Context-Engineering")

    # Word count and status
    word_count = len(text.split()) if text else 0

    return {
        "tags": tags or ["General-AI-Engineering"],
        "word_count": word_count,
        "has_transcript": bool(text)
    }


def record_video(video: dict, transcript: str | None, ideas_meta: dict):
    # 1. Append to JSONL ledger
    LEDGER_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "video_id": video["video_id"],
            "url": video["url"],
            "title": video["title"],
            "visited_at": video["visited_at"],
            "tags": ideas_meta["tags"],
            "word_count": ideas_meta["word_count"],
            "logged_at": datetime.now().isoformat()
        }) + "\n")

    # 2. Append to Markdown Radar
    RADAR_MD.parent.mkdir(parents=True, exist_ok=True)
    if not RADAR_MD.exists():
        with open(RADAR_MD, "w", encoding="utf-8") as f:
            f.write("# 📡 6700XT YouTube Idea Radar & Inspiration Log\n\n")
            f.write("> **System Mission:** Automatically monitor technical YouTube viewing, capture transcripts, and extract actionable hardware/inference optimizations for the AMD Radeon RX 6700 XT (Navi 22 Vulkan + 96 MB Infinity Cache) and Strata architecture.\n\n---\n\n")

    tags_str = " ".join([f"`#{t}`" for t in ideas_meta["tags"]])
    entry = f"""
### 🎥 [{video['title']}]({video['url']})
* **Recorded:** {video['visited_at']} | **Tags:** {tags_str} | **Transcript Length:** {ideas_meta['word_count']} words
* **Video ID:** `{video['video_id']}`

#### Key Technical Context:
- **Source:** Automatically tracked from user viewing session.
- **Hardware Relevance:** {', '.join(ideas_meta['tags'])}

---
"""
    with open(RADAR_MD, "a", encoding="utf-8") as f:
        f.write(entry)


def scan_and_process(browser="chrome", limit=10):
    print(f"[*] Scanning {browser} history for recent YouTube videos...")
    videos = get_browser_history(browser, limit=limit)
    if not videos:
        print(f"[!] No YouTube history found in {browser}.")
        return

    logged_ids = get_logged_video_ids()
    new_count = 0
    for v in videos:
        vid = v["video_id"]
        if vid in logged_ids:
            continue
        print(f"[+] Processing new video: '{v['title']}' ({vid})")
        transcript = fetch_transcript_text(vid)
        ideas = extract_ideas_heuristic(v["title"], transcript)
        record_video(v, transcript, ideas)
        new_count += 1
        print(f"    -> Saved with tags: {ideas['tags']}")

    print(f"[*] Done. {new_count} new video(s) logged to {RADAR_MD}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Idea Radar for Strata / 6700XT")
    parser.add_argument("--scan", action="store_true", help="Scan browser history")
    parser.add_argument("--browser", choices=["chrome", "edge"], default="chrome")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--url", type=str, help="Manually ingest a specific YouTube URL")

    args = parser.parse_args()

    if args.url:
        vid = extract_video_id(args.url)
        if not vid:
            print("[!] Invalid YouTube URL")
            sys.exit(1)
        
        # Try fetching official title via oEmbed
        title = f"YouTube Video ({vid})"
        try:
            import urllib.request
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
            req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                title = data.get("title", title)
        except Exception:
            pass

        transcript = fetch_transcript_text(vid)
        video_info = {
            "video_id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": title,
            "visited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        ideas = extract_ideas_heuristic(video_info["title"], transcript)
        record_video(video_info, transcript, ideas)
        print(f"[+] Logged '{title}' ({vid}) to Radar.")
    else:
        scan_and_process(browser=args.browser, limit=args.limit)
