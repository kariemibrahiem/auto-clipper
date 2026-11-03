"""Automatically cut a licensed video into narrated vertical highlights.

Requires no application API keys. Clip selection uses speech, not computer vision.
"""

import argparse
import asyncio
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
OUT = ROOT / "outputs"
WIDTH, HEIGHT, FPS = 720, 1280, 30
MAX_SOURCE_BYTES = 1_500_000_000
MAX_SOURCE_SECONDS = 3 * 60 * 60
DEFAULT_ANALYSIS_SECONDS = 30 * 60


def cmd(*args):
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"{args[0]} failed:\n{p.stderr[-3000:]}")


def media_info(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def duration(path):
    return float(media_info(path)["format"]["duration"])


def has_audio(path):
    return any(s.get("codec_type") == "audio" for s in media_info(path)["streams"])


def validate_media_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Source video must be a public HTTPS URL")
    host = parsed.hostname.lower()
    if host in ("localhost", "::1") or host.endswith((".local", ".internal")):
        raise ValueError("Local URLs are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("Only public media hosts are allowed")
    return host


def download_direct_video(url):
    target = WORK / "source.mp4"
    req = Request(url, headers={"User-Agent": "AutoClipper/2.0", "Accept": "video/*,*/*"})
    try:
        with urlopen(req, timeout=90) as response:
            validate_media_url(response.geturl())
            content_type = response.headers.get_content_type().lower()
            if not (content_type.startswith("video/") or content_type in
                    {"application/octet-stream", "binary/octet-stream"}):
                raise ValueError(f"Media URL returned {content_type}, not a video file. "
                                 "Use a direct downloadable MP4 link, not a web page.")
            with target.open("wb") as dest:
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > MAX_SOURCE_BYTES:
                        raise ValueError("Source exceeds 1.5 GB; provide a shorter or compressed MP4")
                    dest.write(block)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if target.stat().st_size < 1000:
        raise ValueError("Downloaded media file is empty")
    return target


def download_video(url, prefer_direct=False):
    host = validate_media_url(url)
    # Direct public media files are fetched without involving YouTube extraction.
    if prefer_direct or not (host == "youtu.be" or
                            host.endswith((".youtube.com", ".youtube-nocookie.com")) or
                            host == "youtube.com"):
        if prefer_direct or urlsplit(url).path.lower().endswith(
                (".mp4", ".mov", ".mkv", ".webm", ".m4v")):
            return download_direct_video(url)
    import yt_dlp

    opts = {"outtmpl": str(WORK / "source.%(ext)s"), "noplaylist": True,
            "format": "bv*[height<=720]+ba/b[height<=720]/best",
            "merge_output_format": "mp4", "quiet": True, "socket_timeout": 45,
            "retries": 3, "fragment_retries": 3, "max_filesize": MAX_SOURCE_BYTES,
            "js_runtimes": {"node": {}}, "remote_components": {"ejs:github"}}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as exc:
        if "Sign in to confirm" in str(exc) or "not a bot" in str(exc):
            raise RuntimeError("YouTube blocked this GitHub runner (bot verification). "
                               "Add an authorized HTTPS direct MP4 URL in the "
                               "Google Sheet media_url column, or use MP4 as source_url. "
                               "Changing JavaScript runtime alone cannot fix this.") from exc
        raise
    files = [f for f in WORK.glob("source.*")
             if f.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov", ".m4v")]
    if not files:
        raise RuntimeError("Unable to download source. Try a direct MP4 URL.")
    result = max(files, key=lambda f: f.stat().st_size)
    if result.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Source exceeds 1.5 GB")
    return result


def prepare_analysis_video(source, start_seconds, analysis_seconds):
    total = duration(source)
    if total < 5 or total > MAX_SOURCE_SECONDS:
        raise ValueError("Video duration must be from 5 seconds to 3 hours")
    if start_seconds >= total - 5:
        raise ValueError("start_seconds is after the end of the video")
    available = total - start_seconds
    if start_seconds == 0 and available <= analysis_seconds:
        return source, 0.0
    segment = WORK / "analysis.mp4"
    # Copy an MP4 window before speech analysis, so long videos do not exhaust
    # the 105-minute GitHub Actions job limit. No re-encoding is required here.
    cmd("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", start_seconds,
        "-i", source, "-t", min(analysis_seconds, available), "-map", "0:v:0",
        "-map", "0:a?", "-c", "copy", "-avoid_negative_ts", "make_zero", segment)
    return segment, start_seconds


@dataclass(frozen=True)
class Speech:
    start: float
    end: float
    text: str


def transcribe(video):
    if not has_audio(video):
        return [], "en"
    wav = WORK / "transcript.wav"
    cmd("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video,
        "-vn", "-ac", "1", "-ar", "16000", wav)
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=2)
    segments, info = model.transcribe(str(wav), beam_size=2, vad_filter=True)
    return ([Speech(float(s.start), float(s.end), s.text.strip())
             for s in segments if s.text and s.text.strip()], info.language or "en")


def score(lines, start, end):
    rows = [s for s in lines if s.end > start and s.start < end]
    words = re.findall(r"\w+", " ".join(s.text for s in rows), flags=re.UNICODE)
    excitement = len(re.findall(r"[!?؟]|\b(wow|wait|look|amazing|secret|how|why)\b|"
                                 r"\b(استنى|بص|شوف|مفاجأة|سر|ليه|ازاي)\b",
                                 " ".join(s.text for s in rows), re.IGNORECASE))
    spoken = sum(max(0, min(end, s.end) - max(start, s.start)) for s in rows)
    return len(words) * .13 + excitement * 2 + spoken * .18


def choose_windows(video_length, lines, wanted, clip_length):
    if video_length <= 0:
        raise ValueError("Invalid video duration")
    clip_length = min(video_length, clip_length)
    count = min(wanted, max(1, int(video_length // clip_length)))
    last_start = max(0.0, video_length - clip_length)
    candidates = {0.0, last_start}
    candidates.update(round(min(max(s.start - 1.5, 0), last_start), 2) for s in lines)
    candidates.update(round(last_start * i / max(1, count * 10 - 1), 2)
                      for i in range(count * 10))
    best_first = sorted(candidates,
                        key=lambda s: (score(lines, s, s + clip_length), -s), reverse=True)
    picked = []
    for start in best_first:
        if all(abs(start - old) >= clip_length - .25 for old in picked):
            picked.append(start)
        if len(picked) == count:
            break
    for i in range(count):
        start = min(last_start, i * clip_length)
        if len(picked) < count and all(abs(start - old) >= clip_length - .25 for old in picked):
            picked.append(start)
    return sorted((round(s, 2), round(clip_length, 2)) for s in picked)


def hook_text(lines, start, length, language):
    selection = " ".join(s.text for s in lines
                         if s.end > start and s.start < start + length)
    excerpt = " ".join(re.findall(r"\S+", selection)[:8]).rstrip(" .!؟")
    if language == "ar":
        return (f"بص، ركز معايا في اللحظة دي! {excerpt}. كمل للآخر!" if excerpt
                else "بص، ركز في اللحظة دي، واستنى اللي جاي!")
    return (f"Wait for this moment! {excerpt}. Watch until the end!" if excerpt
            else "Wait for this moment! Watch what happens next!")


async def edge_voice(text, file, language):
    import edge_tts
    name = "ar-EG-SalmaNeural" if language == "ar" else "en-US-AriaNeural"
    await edge_tts.Communicate(text, voice=name, rate="+10%").save(str(file))


def make_voice(text, number, language):
    speech_file = WORK / f"voice_{number:02}.mp3"
    try:
        asyncio.run(edge_voice(text, speech_file, language))
        if speech_file.is_file() and speech_file.stat().st_size > 1000:
            return speech_file
    except Exception as error:
        print(f"Online voice unavailable; trying local fallback: {error}", file=sys.stderr)
    fallback = WORK / f"voice_{number:02}.wav"
    try:
        cmd("espeak-ng", "-v", "ar" if language == "ar" else "en-us", "-s", "150",
            "-w", fallback, text)
        return fallback if fallback.is_file() and fallback.stat().st_size > 1000 else None
    except (RuntimeError, FileNotFoundError):
        print(f"Narrator failed for clip {number}; original audio will remain.", file=sys.stderr)
        return None


def vertical_segment(video, target, start, length, audio):
    visual = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
              f"crop={WIDTH}:{HEIGHT},fps={FPS},setsar=1,format=yuv420p")
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", start, "-i", video]
    if not audio:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    args += ["-t", length, "-map", "0:v:0", "-map", "0:a:0" if audio else "1:a:0",
             "-vf", visual, "-r", FPS, "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "26", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
             "-ar", "44100", "-ac", "2", "-movflags", "+faststart", "-shortest", target]
    cmd(*args)


def overlay_narrator(visual, narrator, final, length):
    if narrator is None:
        shutil.copy2(visual, final)
        return
    duck_until = min(length - .5, duration(narrator) + .4)
    filtergraph = (f"[0:a]volume='if(lt(t,{duck_until:.2f}),0.23,1.0)':eval=frame[bg];"
                   "[1:a]adelay=350|350,volume=1.12[voice];"
                   "[bg][voice]amix=inputs=2:duration=first:normalize=0,"
                   "alimiter=limit=0.94[a]")
    cmd("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", visual,
        "-i", narrator, "-filter_complex", filtergraph, "-map", "0:v:0",
        "-map", "[a]", "-t", length, "-c:v", "copy", "-c:a", "aac",
        "-b:a", "128k", "-movflags", "+faststart", final)


def render(source, opts, source_offset=0.0):
    length = duration(source)
    if length < 5 or length > MAX_SOURCE_SECONDS:
        raise ValueError("Video duration must be from 5 seconds to 3 hours")
    if not any(s.get("codec_type") == "video" for s in media_info(source)["streams"]):
        raise ValueError("Source has no video track")
    lines, detected = [], "en"
    if not opts.skip_transcription:
        try:
            lines, detected = transcribe(source)
        except Exception as exc:
            print(f"Transcription unavailable, using spaced clips: {exc}", file=sys.stderr)
    language = opts.language if opts.language != "auto" else ("ar" if detected == "ar" else "en")
    spans = choose_windows(length, lines, opts.clip_count, opts.clip_seconds)
    manifest = {"job_id": opts.job_id, "language": language,
                "source_offset_seconds": source_offset,
                "selection": "spoken highlights" if lines else "spaced fallback", "clips": []}
    for i, (start, seconds) in enumerate(spans, 1):
        print(f"Clip {i}/{len(spans)}: {start}s to {start + seconds:.2f}s", flush=True)
        raw, final = WORK / f"raw_{i:02}.mp4", OUT / f"clip_{i:02}.mp4"
        vertical_segment(source, raw, start, seconds, has_audio(source))
        hook = hook_text(lines, start, seconds, language)
        voice = make_voice(hook, i, language) if opts.narration else None
        overlay_narrator(raw, voice, final, seconds)
        info = media_info(final)
        video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        if (int(video_stream["width"]), int(video_stream["height"])) != (WIDTH, HEIGHT):
            raise RuntimeError("Rendered dimensions are not 720x1280")
        if abs(float(info["format"]["duration"]) - seconds) > 1.5:
            raise RuntimeError("Unexpected rendered MP4 duration")
        manifest["clips"].append({"number": i, "start": round(start + source_offset, 2),
                                  "duration": seconds,
                                  "file": final.name, "voice_added": bool(voice), "hook": hook})
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print(f"SUCCESS: {len(spans)} short-form MP4s created", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-video", type=Path, help="Use local input for a dry-run")
    parser.add_argument("--skip-transcription", action="store_true")
    args = parser.parse_args()
    config = argparse.Namespace(
        clip_count=int(os.getenv("CLIP_COUNT", "3")),
        clip_seconds=float(os.getenv("CLIP_SECONDS", "35")),
        language=os.getenv("LANGUAGE", "auto").lower().strip(),
        narration=os.getenv("NARRATION", "on").lower().strip() == "on",
        job_id=os.getenv("JOB_ID", "manual"), skip_transcription=args.skip_transcription,
        start_seconds=float(os.getenv("START_SECONDS", "0")),
        analysis_seconds=float(os.getenv("ANALYSIS_SECONDS", str(DEFAULT_ANALYSIS_SECONDS))),
    )
    if not 1 <= config.clip_count <= 5 or not 15 <= config.clip_seconds <= 55:
        raise ValueError("Valid settings: 1–5 clips, each 15–55 seconds")
    if config.language not in {"auto", "ar", "en"}:
        raise ValueError("LANGUAGE must be auto, ar or en")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", config.job_id):
        raise ValueError("Invalid job ID")
    if not (0 <= config.start_seconds < MAX_SOURCE_SECONDS):
        raise ValueError("START_SECONDS must be between 0 and 10800")
    if not (60 <= config.analysis_seconds <= 45 * 60):
        raise ValueError("ANALYSIS_SECONDS must be between 60 and 2700")
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    video = args.local_video if args.local_video else download_video(
        os.getenv("SOURCE_URL", ""),
        prefer_direct=os.getenv("SOURCE_IS_DIRECT", "false").lower() == "true")
    if not video.is_file():
        raise FileNotFoundError(video)
    prepared, offset = prepare_analysis_video(video, config.start_seconds,
                                              config.analysis_seconds)
    render(prepared, config, source_offset=offset)


if __name__ == "__main__":
    main()
