import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# A local .env overrides; everything else comes from Qualivio's .env so secrets are not duplicated.
load_dotenv(ROOT / ".env")
load_dotenv(Path(os.getenv("CI_SHARED_ENV", ROOT.parent / "caller-qa-py" / ".env")), override=False)

# Postgres (same database and schema as Qualivio; call-insights tables are prefixed ci_)
DATABASE_URL = os.getenv("DATABASE_URL", "")
DB_SCHEMA = os.getenv("DB_SCHEMA", "callerqa")
# Timezone of the hub's calls: dates, 'days since' and promise due dates are computed in it.
CALL_TIMEZONE = os.getenv("CI_CALL_TIMEZONE", "America/New_York")

# Azure Blob
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_RECORDING_CONTAINER_NAME = os.getenv("AZURE_RECORDING_CONTAINER_NAME", "")
CI_BLOB_PREFIX = os.getenv("CI_BLOB_PREFIX", "call-insights").strip("/")

# Azure Speech batch transcription
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "")
AZURE_SPEECH_BATCH_ENDPOINT = os.getenv("AZURE_SPEECH_BATCH_ENDPOINT", "")
TRANSCRIPTION_LOCALE = os.getenv("CI_TRANSCRIPTION_LOCALE", "en-US")
TRANSCRIPTION_TIMEOUT_S = int(os.getenv("CI_TRANSCRIPTION_TIMEOUT_S", "1200"))

# Vertex AI (Gemini)
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")
GCP_CLIENT_EMAIL = os.getenv("GCP_CLIENT_EMAIL", "")
GCP_PRIVATE_KEY = os.getenv("GCP_PRIVATE_KEY", "").replace("\\n", "\n")
GEMINI_MODEL_VERSION = os.getenv("GEMINI_MODEL_VERSION", "gemini-3.8-flash")
GEMINI_MODEL_EXTRACT = os.getenv("GEMINI_MODEL_EXTRACT", GEMINI_MODEL_VERSION)
GEMINI_THINKING_EXTRACT = os.getenv("GEMINI_THINKING_EXTRACT", "HIGH")

# Local working files (uploaded audio, converted audio)
DATA_DIR = Path(os.getenv("CI_DATA_DIR", ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
