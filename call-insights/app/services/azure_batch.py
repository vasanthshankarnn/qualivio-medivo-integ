"""Azure Speech batch transcription (REST v3.1), same service as caller-qa-py/app/services/azure_batch_service.py.

Difference: stereo calls are transcribed per channel ("channels": [0, 1]) instead of mono + diarization,
so each phrase is attributed to the exact party (left = hub staff, right = other party).
"""
import time

import requests

from app.config import (AZURE_SPEECH_BATCH_ENDPOINT, AZURE_SPEECH_KEY, AZURE_SPEECH_REGION,
                        TRANSCRIPTION_LOCALE, TRANSCRIPTION_TIMEOUT_S)
from app.logger import logger

TICKS_PER_SECOND = 10_000_000


class AzureBatchTranscriber:
    def __init__(self):
        if not AZURE_SPEECH_KEY:
            raise ValueError("AZURE_SPEECH_KEY is missing")
        base = AZURE_SPEECH_BATCH_ENDPOINT.rstrip("/") if AZURE_SPEECH_BATCH_ENDPOINT \
            else f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com"
        self.endpoint = f"{base}/speechtotext/v3.1/transcriptions"
        self.headers = {"Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY, "Content-Type": "application/json"}

    def transcribe(self, sas_url: str, job_name: str, stereo: bool) -> list[dict]:
        """Run a batch job to completion and return phrases sorted by start time."""
        props = {"wordLevelTimestampsEnabled": True, "punctuationMode": "DictatedAndAutomatic",
                 "profanityFilterMode": "None"}
        if stereo:
            props["channels"] = [0, 1]
        else:
            props["diarizationEnabled"] = True
        body = {"contentUrls": [sas_url], "locale": TRANSCRIPTION_LOCALE, "displayName": job_name, "properties": props}

        resp = requests.post(self.endpoint, headers=self.headers, json=body, timeout=60)
        if resp.status_code != 201:
            raise RuntimeError(f"Azure transcription job not created ({resp.status_code}): {resp.text[:300]}")
        job_url = resp.json()["self"]
        logger.info("Azure batch job created: %s", job_name)

        try:
            deadline = time.monotonic() + TRANSCRIPTION_TIMEOUT_S
            while True:
                status = requests.get(job_url, headers=self.headers, timeout=60).json()
                state = status.get("status")
                if state == "Succeeded":
                    break
                if state == "Failed":
                    raise RuntimeError(f"Azure transcription failed: {status.get('properties', {}).get('error')}")
                if time.monotonic() > deadline:
                    raise TimeoutError(f"Azure transcription not finished after {TRANSCRIPTION_TIMEOUT_S}s")
                time.sleep(10)

            files = requests.get(f"{job_url}/files", headers=self.headers, timeout=60).json().get("values", [])
            result = next((f for f in files if f.get("kind") == "Transcription"), None)
            if not result:
                raise RuntimeError("Azure transcription returned no result file")
            content = requests.get(result["links"]["contentUrl"], timeout=60).json()
        finally:
            # Jobs keep the audio reference and results on Azure's side; remove once read.
            try:
                requests.delete(job_url, headers=self.headers, timeout=60)
            except requests.RequestException:
                logger.warning("Could not delete Azure job %s", job_name)

        phrases = []
        for p in content.get("recognizedPhrases") or []:
            best = (p.get("nBest") or [{}])[0]
            text = (best.get("display") or "").strip()
            if not text:
                continue
            start = p.get("offsetInTicks", 0) / TICKS_PER_SECOND
            phrases.append({
                "start_s": round(start, 2),
                "end_s": round(start + p.get("durationInTicks", 0) / TICKS_PER_SECOND, 2),
                "channel": p.get("channel"),
                "speaker": p.get("speaker"),
                "text": text,
            })
        phrases.sort(key=lambda x: x["start_s"])
        return phrases
