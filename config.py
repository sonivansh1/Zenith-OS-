import json
import os

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".dynamic_island_settings.json")

LEGACY_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".zenith_settings.json")

DEFAULT_CONFIG = {
    "groq_api_key": os.environ.get("GROQ_API_KEY", ""),
    "alignment": "Center",
    "roundness": 1.0,
    "display_mode": "Only Emo Eyes",
    "voice": "Emo",
    "compact_width": 110,
    "auto_collapse": False,
    "companion_eyes": True,
    "auto_capture_workspaces": True,
    "enable_hotkey": True,
    "music_ambient_glow": True,
    "focus_duration": 25,
    "break_duration": 5,
    "tasks_list": [],
    "quick_apps": [
        "notepad",
        "calc"
    ],
    "quick_commands": [
        "What is my battery level?",
        "Lock the PC"
    ],
    "quick_buttons": ["music", "timer", "clipboard"],
    "clipboard_history": [],
    "pinned_dashboard": False
}

def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(LEGACY_CONFIG_FILE):
        config.update(_read_json(LEGACY_CONFIG_FILE))
    if os.path.exists(CONFIG_FILE):
        config.update(_read_json(CONFIG_FILE))
    return config

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
