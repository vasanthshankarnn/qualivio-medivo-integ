"""Parse an optional, caller-supplied transcript.

Accepted line format:  [mm:ss] Speaker label: text      (e.g. "[00:12] Hub agent (Jessica): Hi Denise ...")
Every line that does not start with a [mm:ss] timestamp is dropped, so header / reference metadata in a
transcript file never reaches the AI. Bracketed events such as "[00:13] [on hold ~4 s]" are kept as events.
"""
import re

LINE_RE = re.compile(r"^\[(\d{1,2}):(\d{2})\]\s*(.*)$")


def parse_transcript(text: str) -> list[dict]:
    segments = []
    for raw in text.splitlines():
        m = LINE_RE.match(raw.strip())
        if not m:
            continue
        start = int(m.group(1)) * 60 + int(m.group(2))
        rest = m.group(3).strip()
        if rest.startswith("["):
            label, body = "event", rest.strip("[] ")
        elif ":" in rest:
            label, body = (part.strip() for part in rest.split(":", 1))
        else:
            label, body = "unknown", rest
        if body:
            segments.append({"start_s": float(start), "end_s": None, "channel": None, "speaker_label": label, "text": body})
    for i, seg in enumerate(segments):
        seg["end_s"] = segments[i + 1]["start_s"] if i + 1 < len(segments) else seg["start_s"]
    return segments
