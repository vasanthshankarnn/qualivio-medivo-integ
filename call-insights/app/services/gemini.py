"""Vertex AI Gemini client, same setup as caller-qa-py/app/llm/client_factory.py."""
import threading
from typing import Optional

from google import genai
from google.genai import types
from google.oauth2 import service_account

from app.config import GCP_CLIENT_EMAIL, GCP_LOCATION, GCP_PRIVATE_KEY, GCP_PROJECT_ID

_client = None
_lock = threading.Lock()  # parallel calls must share one client: a discarded duplicate closes its connection


def get_client() -> genai.Client:
    global _client
    with _lock:
        return _client or _create()


def _create() -> genai.Client:
    global _client
    if not (GCP_CLIENT_EMAIL and GCP_PRIVATE_KEY and GCP_PROJECT_ID):
        raise ValueError("Missing Vertex AI credentials")
    creds = service_account.Credentials.from_service_account_info(
        {"type": "service_account", "project_id": GCP_PROJECT_ID, "private_key": GCP_PRIVATE_KEY,
         "client_email": GCP_CLIENT_EMAIL, "token_uri": "https://oauth2.googleapis.com/token"},
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    _client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=GCP_LOCATION, credentials=creds)
    return _client


def build_config(model: str, thinking_level: Optional[str] = None, temperature: Optional[float] = None,
                 **kwargs) -> types.GenerateContentConfig:
    """Gemini 3.x: keep the default temperature and apply thinking_level. Older models: use temperature."""
    if model.startswith("gemini-3"):
        if thinking_level:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level.upper())
    elif temperature is not None:
        kwargs["temperature"] = temperature
    return types.GenerateContentConfig(**kwargs)
