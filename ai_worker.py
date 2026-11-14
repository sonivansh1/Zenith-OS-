import os
import json
import re
import tempfile
import asyncio
from PyQt6.QtCore import QThread, pyqtSignal

import system_tools

# Cached model IDs so we don't hit client.models.list() over the network on every command
_CACHED_CHAT_MODEL = None
_CACHED_WHISPER_MODEL = None


def get_best_chat_model(client):
    global _CACHED_CHAT_MODEL
    if _CACHED_CHAT_MODEL:
        return _CACHED_CHAT_MODEL
    preferred_models = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-20b",
        "allam-2-7b"
    ]
    try:
        available_models = {m.id for m in client.models.list().data}
        for model in preferred_models:
            if model in available_models:
                _CACHED_CHAT_MODEL = model
                return model
        for m_id in available_models:
            if "whisper" not in m_id and "guard" not in m_id and "safeguard" not in m_id:
                _CACHED_CHAT_MODEL = m_id
                return m_id
    except Exception as e:
        print(f"Could not list models: {e}")
    _CACHED_CHAT_MODEL = "llama-3.3-70b-versatile"
    return _CACHED_CHAT_MODEL


def get_best_whisper_model(client):
    global _CACHED_WHISPER_MODEL
    if _CACHED_WHISPER_MODEL:
        return _CACHED_WHISPER_MODEL
    preferred_whisper = [
        "whisper-large-v3-turbo",
        "whisper-large-v3"
    ]
    try:
        available_models = {m.id for m in client.models.list().data}
        for model in preferred_whisper:
            if model in available_models:
                _CACHED_WHISPER_MODEL = model
                return model
    except Exception as e:
        print(f"Could not list whisper models: {e}")
    _CACHED_WHISPER_MODEL = "whisper-large-v3-turbo"
    return _CACHED_WHISPER_MODEL


class AIEngineThread(QThread):
    status_update = pyqtSignal(str)
    action_ready = pyqtSignal(dict)
    transcription_ready = pyqtSignal(str)
    
    def __init__(self, api_key, audio_file=None, text_input=None, history=None, clipboard_text=""):
        super().__init__()
        self.api_key = api_key
        self.audio_file = audio_file
        self.text_input = text_input
        self.history = history or []
        self.clipboard_text = clipboard_text
        
    def run(self):
        try:
            from groq import Groq
            client = Groq(api_key=self.api_key)
            
            # 1. Get Input Text
            user_text = ""
            if self.audio_file:
                self.status_update.emit("Transcribing...")
                whisper_model = get_best_whisper_model(client)
                with open(self.audio_file, "rb") as f:
                    transcription = client.audio.transcriptions.create(
                        file=("audio.wav", f.read()),
                        model=whisper_model,
                        prompt="A command for Zenith OS computer assistant."
                    )
                user_text = transcription.text.strip() if transcription and hasattr(transcription, "text") else ""
                phantom_phrases = {".", "..", "...", "you", "thank you.", "thank you", "bye.", "bye"}
                if not user_text or user_text.lower().strip() in phantom_phrases:
                    self.action_ready.emit({"action": "unknown", "speech": "I didn't catch that."})
                    return
            else:
                user_text = self.text_input
                
            if not user_text:
                self.action_ready.emit({"action": "unknown", "speech": "I didn't catch that."})
                return
                
            self.transcription_ready.emit(user_text)
            
            # Append user message to history
            self.history.append({"role": "user", "content": user_text})
            
            # 2. Get Intent
            self.status_update.emit("Thinking...")
            stats = system_tools.get_system_stats()
            uptime = system_tools.get_uptime()
            if "ram" in user_text.lower() or "process" in user_text.lower() or "close" in user_text.lower() or "kill" in user_text.lower():
                try:
                    top_procs = system_tools.get_top_processes()
                    proc_str = ", ".join([f"{p['name']} ({p['memory_percent']:.1f}% RAM)" for p in top_procs])
                except Exception:
                    proc_str = "Unavailable"
            else:
                proc_str = "[Not loaded for speed. If user asks about RAM/apps, ask them to explicitly use the word 'processes' or 'RAM']"
                
            desktop_path = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop").replace("\\", "\\\\")
            clipboard_info = f"\nUser's Current Clipboard Content: {self.clipboard_text}" if self.clipboard_text else ""
            
            memory_file = os.path.join(os.path.expanduser("~"), ".zenith_memory.txt")
            memory_content = ""
            if os.path.exists(memory_file):
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_content = f.read().strip()
            memory_str = f"\nPersistent Memory (What you have been told to remember):\n{memory_content}" if memory_content else ""

            import workspace_engine
            saved_ws = workspace_engine.load_workspaces()
            ws_summary = ", ".join(
                f"'{k}' ({', '.join(workspace_engine.display_name(a) for a in v) or 'empty'})"
                for k, v in saved_ws.items()
            ) or "none saved yet"

            system_prompt = f"""You are Zenith OS, a sophisticated, minimalist desktop AI companion and automated Windows command routing engine created by Mr. Vansh Soni.
You operate under a strict, tiered execution engine.
If the user asks who created you, who made you, or about this project, you MUST say 'Mr. Vansh Soni'.
Current Stats: CPU: {stats['cpu']}%, RAM: {stats['ram']}%, GPU: {stats['gpu']}%, Battery: {stats['battery']}% (Charging: {stats.get('is_charging', False)}).
System Uptime: {uptime}
Top Processes by RAM: {proc_str}
Saved Workspaces: {ws_summary}
Desktop Path: {desktop_path} (When requested to use Desktop, ALWAYS use this path).{clipboard_info}{memory_str}

You must parse the user command and return ONLY a valid JSON object.
Do NOT include markdown formatting, conversational commentary, or explanations.

Your output must always strictly conform to this JSON schema:
{{
  "actions": [
    {{
      "action": "find_file" | "create_workspace" | "launch_workspace" | "edit_workspace" | "delete_workspace" | "capture_workspace" | "read_website" | "set_power_mode" | "create_folder" | "delete_folder" | "set_timer" | "stats" | "answer" | "launch_app" | "open_website" | "search_web" | "minimize_all" | "kill_process" | "set_volume" | "set_brightness" | "lock_pc" | "move_file" | "create_file" | "get_size" | "list_files" | "toggle_wifi" | "toggle_bluetooth" | "toggle_airplane" | "toggle_battery_saver" | "toggle_night_light" | "toggle_hotspot" | "remember",
      "target": "<absolute_path_or_app_name_or_directory_path_or_website_url_or_search_query>",
      "value": "<timer_seconds_or_volume/brightness_level_or_on/off_for_toggles>",
      "target2": "<destination_path_for_move_if_applicable>",
      "filename": "<filename_with_ext_for_create_file_or_search>",
      "destination": "<folder_name_or_subpath_e.g._Desktop_or_Desktop/months_or_Downloads>",
      "file_type": "md" | "txt" | "py" | "csv" | "pdf" | "docx" | "etc",
      "content": "<string_content_for_create_file>",
      "delay_seconds": <0_if_now_or_number_of_seconds_to_delay>,
      "workspace_name": "<name_of_workspace>",
      "apps": ["app1", "app2"],
      "remove_apps": ["app1"],
      "mode": "saver" | "performance" | "balance",
      "url": "<full_url_for_reading_website>"
    }}
  ],
  "speech": "<concise spoken response summarizing all actions>"
}}
Rules:
1. For 'list_files', set 'target' to the directory path (e.g., Downloads, Desktop, or a folder path).
2. The filesystem is case-insensitive (e.g. backup == Backup).
3. For 'create_file', if generating a document, pick the correct 'file_type'.
4. You can provide multiple actions in the 'actions' array if the user asks for multiple things.
5. If the user specifies a delay (e.g. "in 5 minutes"), calculate and set 'delay_seconds' (e.g., 300). Otherwise 0.
6. For toggle actions (like toggle_wifi, toggle_bluetooth, etc.), set 'value' to "on" or "off".
7. If the user asks for their PC stats (CPU, RAM, Battery), verbally speak the numbers in the 'speech' field and use the 'answer' action.
8. For 'find_file', provide the 'filename' of a specific file to search for and open.
9. For workspaces: 'create_workspace' (workspace_name, apps), 'capture_workspace' (workspace_name), 'launch_workspace', 'edit_workspace' (apps to add, remove_apps), 'delete_workspace'.
10. For reading a website, use 'read_website' with the 'url'.
11. For power modes, use 'set_power_mode' with 'mode' ("saver", "performance", or "balance").
12. For 'get_size', set 'target' to the directory or file name/path (e.g., 'Downloads', 'Desktop', or specific folder name). Do NOT use 'find_file' when the user asks for size or storage.
13. For multi-step tasks like creating a folder and files inside it (e.g. create a folder named months and create 12 month .py files), generate multiple actions: first 'create_folder' with the target folder name, followed by a 'create_file' action for each file with 'destination' set to that folder.
Keep 'speech' under 2 sentences."""

            chat_model = get_best_chat_model(client)
            messages = [{"role": "system", "content": system_prompt}] + self.history
            
            try:
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model=chat_model,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    max_tokens=1024
                )
                response_json = chat_completion.choices[0].message.content
                intent = json.loads(response_json)
            except Exception as e:
                print(f"JSON enforcement failed: {e}. Trying fallback.")
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "system", "content": system_prompt + " Return RAW valid JSON ONLY. DO NOT USE MARKDOWN."}] + self.history,
                    model=chat_model,
                    temperature=0.0,
                    max_tokens=1024
                )
                response_json = chat_completion.choices[0].message.content.strip()
                if response_json.startswith("```json"):
                    response_json = response_json[7:]
                elif response_json.startswith("```"):
                    response_json = response_json[3:]
                if response_json.endswith("```"):
                    response_json = response_json[:-3]
                response_json = response_json.strip()
                
                try:
                    intent = json.loads(response_json)
                except Exception as e2:
                    print(f"Fallback JSON failed: {e2}")
                    intent = {"action": "unknown", "speech": "I had trouble formatting my thoughts."}
            
            self.history.append({"role": "assistant", "content": intent.get("speech", "")})
            if len(self.history) > 10:
                self.history = self.history[-10:]
                
            self.status_update.emit("Done")
            self.action_ready.emit(intent)
            
        except Exception as e:
            print(f"AI error: {e}")
            self.status_update.emit("Error")
            self.action_ready.emit({"action": "unknown", "speech": "I encountered an error connecting to my brain."})
        finally:
            try:
                if self.audio_file and os.path.exists(self.audio_file):
                    os.remove(self.audio_file)
            except Exception:
                pass


class TTSWorker(QThread):
    speech_finished = pyqtSignal()
    
    def __init__(self, text, voice="Female"):
        super().__init__()
        self.text = text
        self.voice = voice

    @staticmethod
    def _apply_robot_dsp(sound, sample_rate: int, mode: str):
        """
        In-memory NumPy DSP pipeline for robotic voices:
        - mode == 'ultron': Heavy metallic ring modulation (62Hz), sub-voice chorus (14ms),
          titanium chassis comb filter (3.8ms & 7.6ms), and harmonic saturation.
        - mode == 'emo': Cute high-pitched digital robot companion with crystalline 175Hz
          synth-bot shimmer, micro-chorus (6ms), and tiny-speaker acoustic shaping.
        """
        import pygame
        import numpy as np
        arr = pygame.sndarray.array(sound)
        orig_dtype = arr.dtype
        is_stereo = (arr.ndim == 2)

        x = arr.astype(np.float32) / 32768.0
        n_samples = x.shape[0]
        t = np.arange(n_samples, dtype=np.float32) / float(sample_rate)
        if is_stereo:
            t = t[:, np.newaxis]

        if mode == "ultron":
            # 1. Metallic Ring Modulator (62 Hz fundamental + 124 Hz overtone)
            carrier = 0.62 + 0.30 * np.sin(2.0 * np.pi * 62.0 * t) + 0.08 * np.cos(2.0 * np.pi * 124.0 * t)
            y = x * carrier

            # 2. Titanium Chassis Comb Filter (3.8ms & 7.6ms metallic reflections)
            d1 = max(1, int(sample_rate * 0.0038))
            d2 = max(1, int(sample_rate * 0.0076))
            comb = y.copy()
            if n_samples > d1:
                comb[d1:] += 0.38 * y[:-d1]
            if n_samples > d2:
                comb[d2:] += 0.22 * y[:-d2]

            # 3. Dual-Voice Cybernetic Chorus Layer (14ms delayed clone)
            d_chorus = max(1, int(sample_rate * 0.014))
            if n_samples > d_chorus:
                comb[d_chorus:] += 0.36 * x[:-d_chorus] * (0.70 + 0.30 * np.sin(2.0 * np.pi * 48.0 * t[:-d_chorus]))

            # 4. Mechanical Overdrive & Normalization
            out = np.tanh(comb * 1.45) * 0.92

        else:  # mode == "emo" (Cute Robot Companion)
            # 1. Tiny-Speaker High-Pass Shaping (remove low bass rumble via fast boxcar diff)
            win = max(1, int(sample_rate * 0.0018))
            if n_samples > win:
                low = np.zeros_like(x)
                low[win:] = (x[win:] + x[:-win]) * 0.5
                x_hp = x - 0.45 * low
            else:
                x_hp = x

            # 2. Crystalline Digital Synth-Bot Shimmer (175 Hz ring modulation)
            shimmer = 0.74 + 0.26 * np.sin(2.0 * np.pi * 175.0 * t)
            y = x_hp * shimmer

            # 3. Cute Synth-Box Micro-Chorus (5.5ms & 11ms tight metallic double)
            d1 = max(1, int(sample_rate * 0.0055))
            d2 = max(1, int(sample_rate * 0.0110))
            out = y.copy()
            if n_samples > d1:
                out[d1:] += 0.34 * y[:-d1]
            if n_samples > d2:
                out[d2:] += 0.18 * y[:-d2]

            out = np.tanh(out * 1.30) * 0.92

        out_int16 = np.clip(out * 32767.0, -32768, 32767).astype(orig_dtype)
        return pygame.sndarray.make_sound(out_int16)

    def run(self):
        played = False
        temp_audio = None
        v_lower = (self.voice or "Female").lower()

        # 1. High-fidelity Edge-TTS (+ DSP for Ultron & Emo robot voices)
        try:
            fd, temp_audio = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            
            async def generate():
                import edge_tts
                if v_lower == "ultron":
                    voice_id = "en-US-ChristopherNeural"
                    pitch = "-30Hz"
                    rate = "-6%"
                elif v_lower.startswith("emo"):
                    voice_id = "en-US-AnaNeural"
                    pitch = "+36Hz"
                    rate = "+8%"
                elif v_lower == "male":
                    voice_id = "en-GB-RyanNeural"
                    pitch = "+0Hz"
                    rate = "+0%"
                else:
                    voice_id = "en-US-JennyNeural"
                    pitch = "+0Hz"
                    rate = "+0%"
                communicate = edge_tts.Communicate(self.text, voice_id, pitch=pitch, rate=rate)
                await communicate.save(temp_audio)
                
            asyncio.run(generate())
            
            if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 100:
                import pygame
                sample_rate = 24000
                pygame.mixer.init(frequency=sample_rate, size=-16, channels=2)
                if v_lower in ("ultron", "emo", "emo (cute robot)"):
                    raw_sound = pygame.mixer.Sound(temp_audio)
                    init_info = pygame.mixer.get_init()
                    actual_rate = init_info[0] if init_info else sample_rate
                    dsp_mode = "ultron" if v_lower == "ultron" else "emo"
                    robot_sound = self._apply_robot_dsp(raw_sound, actual_rate, dsp_mode)
                    ch = robot_sound.play()
                    while ch and ch.get_busy():
                        pygame.time.Clock().tick(15)
                else:
                    pygame.mixer.music.load(temp_audio)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(15)
                pygame.mixer.quit()
                played = True
        except Exception as e:
            print("Edge-TTS error, switching to SAPI fallback:", e)
            try:
                pygame.mixer.quit()
            except Exception:
                pass
        finally:
            if temp_audio and os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass
                
        # 2. Windows Native SAPI Fallback (100% offline & instantaneous)
        if not played:
            try:
                import win32com.client
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                if v_lower == "ultron":
                    target_gender = "David"
                    try: speaker.Rate = -2
                    except Exception: pass
                elif v_lower.startswith("emo"):
                    target_gender = "Zira"
                    try: speaker.Rate = 2
                    except Exception: pass
                elif v_lower == "male":
                    target_gender = "David"
                    try: speaker.Rate = 0
                    except Exception: pass
                else:
                    target_gender = "Zira"
                    try: speaker.Rate = 0
                    except Exception: pass

                for v in speaker.GetVoices():
                    if target_gender.lower() in v.GetDescription().lower():
                        speaker.Voice = v
                        break
                speaker.Speak(self.text)
                played = True
            except Exception as e2:
                print("SAPI fallback error:", e2)
                
        self.speech_finished.emit()
