"""ffmpeg / ffprobe helpers (ffmpeg must be on PATH, as for caller-qa-py)."""
import json
import subprocess


def probe(path: str) -> dict:
    """Return {'channels': int, 'duration_s': float} for an audio file."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels:format=duration",
         "-of", "json", path],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr.strip()}")
    data = json.loads(out.stdout or "{}")
    streams = data.get("streams") or [{}]
    return {
        "channels": int(streams[0].get("channels") or 1),
        "duration_s": float((data.get("format") or {}).get("duration") or 0.0),
    }


def to_transcription_mp3(src: str, dst: str, keep_stereo: bool) -> str:
    """16 kHz 64 kbps MP3. Stereo is kept so Azure can transcribe each channel (= each party) separately."""
    cmd = ["ffmpeg", "-y", "-i", src, "-ac", "2" if keep_stereo else "1", "-ar", "16000", "-b:a", "64k", dst]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {out.stderr.strip()[-500:]}")
    return dst
