import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
AUDIO_SAMPLERATE = 16000
AUDIO_CHANNELS = 1
MAX_AUDIO_CHUNK_MB = 19  # Gemini 인라인 데이터 제한 ~20MB

# ── 사용자 설정 파일 ──
_SETTINGS_PATH = Path(__file__).parent / "settings.json"


def _load_settings():
    if _SETTINGS_PATH.exists():
        try:
            return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_settings(data):
    _SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_save_folder():
    """저장 폴더 경로 반환. 미설정 시 바탕화면."""
    settings = _load_settings()
    folder = settings.get("save_folder", "")
    if folder and Path(folder).is_dir():
        return folder
    return str(Path.home() / "Desktop")


def set_save_folder(folder_path):
    """저장 폴더 경로 설정."""
    settings = _load_settings()
    settings["save_folder"] = folder_path
    _save_settings(settings)


def get_language():
    """현재 언어 코드 반환. 기본: 'ko'."""
    settings = _load_settings()
    return settings.get("language", "ko")


def set_language(lang_code):
    """언어 코드 설정 ('ko', 'en', 'ja')."""
    settings = _load_settings()
    settings["language"] = lang_code
    _save_settings(settings)
