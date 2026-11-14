import re
import sys
import os
import json

# --- LOGGING SETUP ---
log_path = os.path.join(os.path.expanduser("~"), ".dynamic_island.log")
class Logger:
    def __init__(self, filename):
        self.terminal = sys.__stdout__
        self.log = open(filename, "a", encoding="utf-8")
    def write(self, message):
        if self.terminal:
            try:
                self.terminal.write(message)
                self.terminal.flush()
            except Exception:
                pass
        self.log.write(message)
        self.log.flush()
    def flush(self):
        if self.terminal:
            try:
                self.terminal.flush()
            except Exception:
                pass
        self.log.flush()

sys.stdout = Logger(log_path)
sys.stderr = sys.stdout
def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller bundling."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# ---------------------
import time
import tempfile
import ctypes
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QLineEdit, QSlider, QFormLayout, 
                             QMessageBox, QButtonGroup, QRadioButton, QComboBox,
                             QMenu, QInputDialog, QProgressBar, QListWidget, QStackedWidget, QCheckBox, QFileDialog, QTabWidget,
                             QSystemTrayIcon)
from PyQt6.QtCore import (Qt, QPropertyAnimation, QRect, QRectF, QEasingCurve, 
                          QTimer, QPoint, QSize, QPointF, pyqtSignal, pyqtProperty, QParallelAnimationGroup)
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QFont, QRadialGradient, QConicalGradient, QBrush, QPen, QCursor, QAction, QPixmap, QIcon
import math

import config
import system_tools
from ai_worker import AIEngineThread, TTSWorker
from media_worker import MediaWorker
from island_eyes import DynamicIslandEyes, IslandEyes, EyeMood

class RotatingDisc(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.angle = 0
        self._is_playing = False
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.rotate)

    @property
    def is_playing(self):
        return self._is_playing

    @is_playing.setter
    def is_playing(self, val: bool):
        self._is_playing = bool(val)
        self._sync_timer()

    def _sync_timer(self):
        if self._is_playing and self.isVisible():
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()
        
    def rotate(self):
        if self._is_playing:
            self.angle = (self.angle + 8) % 360
            self.update()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width()/2, self.height()/2)
        painter.rotate(self.angle)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 30, 30))
        painter.drawEllipse(QRectF(-7.0, -7.0, 14.0, 14.0))
        
        painter.setPen(QPen(QColor(50, 50, 50), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(-5.0, -5.0, 10.0, 10.0))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 80, 80))
        painter.drawEllipse(QRectF(-2.5, -2.5, 5.0, 5.0))

class AudioVisualizer(QWidget):
    """
    Minimalistic, serene micro-wave indicator for idle music playback.
    Replaces violent jumping bars with a gentle, smooth flowing harmonic wave.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 16)
        self._is_playing = False
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.animate)

    @property
    def is_playing(self):
        return self._is_playing

    @is_playing.setter
    def is_playing(self, val: bool):
        changed = (self._is_playing != bool(val))
        self._is_playing = bool(val)
        if changed:
            self.update()
        self._sync_timer()

    def set_playing(self, val: bool):
        self.is_playing = val

    def _sync_timer(self):
        if self._is_playing and self.isVisible():
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.timer.stop()

    def animate(self):
        if not self._is_playing:
            self.timer.stop()
            return
        self.phase += 0.12
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        mid_y = h / 2.0

        if not self._is_playing:
            # Minimal calm flat hairline when paused
            painter.setPen(QPen(QColor(0, 255, 204, 75), 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(2.0, mid_y), QPointF(w - 2.0, mid_y))
            return

        # Smooth, minimalistic harmonic flowing wave
        path = QPainterPath()
        num_points = 18
        step = (w - 3.0) / float(num_points - 1)

        points = []
        for i in range(num_points):
            px = 1.5 + i * step
            norm_x = (px - 1.5) / (w - 3.0)
            # Bell curve window envelope: 0.0 at edges so wave stays perfectly anchored
            window = math.sin(norm_x * math.pi)
            wave = 0.75 * math.sin(norm_x * 2.8 * math.pi - self.phase) + 0.25 * math.sin(norm_x * 5.6 * math.pi + self.phase * 0.7)
            py = mid_y + (wave * 3.8 * window)
            points.append(QPointF(px, py))

        path.moveTo(points[0])
        for i in range(len(points) - 1):
            p0 = points[i]
            p1 = points[i + 1]
            c1 = QPointF(p0.x() + (p1.x() - p0.x()) / 2.0, p0.y())
            c2 = QPointF(p0.x() + (p1.x() - p0.x()) / 2.0, p1.y())
            path.cubicTo(c1, c2, p1)

        # Subtle soft glow stroke
        painter.setPen(QPen(QColor(0, 255, 204, 50), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)

        # Crisp core wave
        painter.setPen(QPen(QColor(0, 255, 204, 230), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)


import ctypes
from ctypes import wintypes
import sounddevice as sd
import numpy as np
import wave
import threading
from PyQt6.QtCore import pyqtSignal, QObject, QThread

class WindowsHotkeyThread(QThread):
    """
    Triple-Redundant Ctrl+Space Global Hotkey Listener for Windows:
    1. OS RegisterHotKey (MOD_CONTROL | MOD_NOREPEAT, VK_SPACE)
    2. Low-Level Keyboard Hook (WH_KEYBOARD_LL) on the same Win32 message loop
    3. 25ms GetAsyncKeyState edge-triggered hardware key-state monitor (catches Ctrl+Space
       even when another app/IME steals RegisterHotKey or an elevated window is active)
    """
    triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._thread_id = None
        self._last_emit = 0.0
        self._emit_lock = threading.Lock()
        self.registered = False
        self.hook_installed = False

    def _fire(self):
        now = time.time()
        with self._emit_lock:
            if now - self._last_emit < 0.35:
                return
            self._last_emit = now
        try:
            self.triggered.emit()
        except RuntimeError:
            pass

    def run(self):
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        u32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        u32.RegisterHotKey.restype = wintypes.BOOL
        u32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        u32.UnregisterHotKey.restype = wintypes.BOOL
        u32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        u32.GetMessageW.restype = wintypes.BOOL
        u32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        u32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        u32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        u32.GetAsyncKeyState.restype = ctypes.c_short
        k32.GetCurrentThreadId.restype = wintypes.DWORD

        self._thread_id = k32.GetCurrentThreadId()

        WM_HOTKEY = 0x0312
        WM_KEYDOWN = 0x0100
        WM_SYSKEYDOWN = 0x0104
        MOD_CONTROL = 0x0002
        MOD_NOREPEAT = 0x4000
        VK_SPACE = 0x20
        VK_CONTROL = 0x11
        VK_MENU = 0x12
        VK_LWIN = 0x5B
        VK_RWIN = 0x5C
        HOTKEY_ID = 8888
        WH_KEYBOARD_LL = 13

        # Layer 1: RegisterHotKey
        res = u32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_NOREPEAT, VK_SPACE)
        if not res:
            res = u32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL, VK_SPACE)
        self.registered = bool(res)

        # Layer 2: WH_KEYBOARD_LL hook
        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        u32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        u32.SetWindowsHookExW.restype = ctypes.c_void_p
        u32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        u32.CallNextHookEx.restype = LRESULT
        u32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        u32.UnhookWindowsHookEx.restype = wintypes.BOOL

        def _ll_keyboard_proc(nCode, wParam, lParam):
            if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN) and lParam:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if kb.vkCode == VK_SPACE:
                    ctrl_down = bool(u32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                    alt_down = bool(u32.GetAsyncKeyState(VK_MENU) & 0x8000)
                    win_down = bool((u32.GetAsyncKeyState(VK_LWIN) | u32.GetAsyncKeyState(VK_RWIN)) & 0x8000)
                    if ctrl_down and not alt_down and not win_down:
                        self._fire()
            return u32.CallNextHookEx(None, nCode, wParam, lParam)

        self._hook_cb_ref = HOOKPROC(_ll_keyboard_proc)
        hook_handle = u32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_cb_ref, None, 0)
        self.hook_installed = bool(hook_handle)

        # Layer 3: Lightweight 25ms GetAsyncKeyState edge detector (catches elevated/fullscreen windows)
        def _async_key_poll():
            was_combo = False
            while self._running:
                ctrl_down = bool(u32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                space_down = bool(u32.GetAsyncKeyState(VK_SPACE) & 0x8000)
                alt_down = bool(u32.GetAsyncKeyState(VK_MENU) & 0x8000)
                win_down = bool((u32.GetAsyncKeyState(VK_LWIN) | u32.GetAsyncKeyState(VK_RWIN)) & 0x8000)
                is_combo = ctrl_down and space_down and not alt_down and not win_down
                if is_combo and not was_combo:
                    self._fire()
                was_combo = is_combo
                time.sleep(0.025)

        threading.Thread(target=_async_key_poll, daemon=True).start()

        msg = wintypes.MSG()
        while self._running:
            ret = u32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self._fire()
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))

        if hook_handle:
            u32.UnhookWindowsHookEx(hook_handle)
        if self.registered:
            u32.UnregisterHotKey(None, HOTKEY_ID)

    def stop(self):
        self._running = False
        if self._thread_id:
            u32 = ctypes.WinDLL("user32", use_last_error=True)
            u32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            u32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
        self.wait(1000)

class SiriOrbWidget(QWidget):
    def __init__(self, size=18, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_orb)
        self.timer.setInterval(16)  # 60 FPS
        
    def start(self):
        self.phase = 0.0
        self.timer.start()
        self.show()
        
    def stop(self):
        self.timer.stop()
        self.update()
        
    def update_orb(self):
        self.phase += 0.05
        if self.phase > math.pi * 2:
            self.phase -= math.pi * 2
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = min(self.width(), self.height())
        center_x = self.width() / 2.0
        center_y = self.height() / 2.0
        
        # 1. Revolving Outer Glow
        glow_radius = w * 0.46
        angle = math.degrees(self.phase * 1.5)
        conical = QConicalGradient(center_x, center_y, angle)
        conical.setColorAt(0.0, QColor(0, 230, 255, 0))
        conical.setColorAt(0.3, QColor(255, 0, 128, 140))  # Magenta streak
        conical.setColorAt(0.5, QColor(0, 230, 255, 200))  # Cyan streak
        conical.setColorAt(0.7, QColor(138, 43, 226, 140)) # Violet streak
        conical.setColorAt(1.0, QColor(0, 230, 255, 0))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(conical)
        painter.drawEllipse(QPointF(center_x, center_y), glow_radius, glow_radius)
        
        # 2. Main Inner Swirling Orb
        base_radius = w * 0.32
        scale = 0.93 + 0.07 * math.sin(self.phase)
        active_radius = base_radius * scale
        
        fx = center_x + (active_radius * 0.35) * math.cos(self.phase)
        fy = center_y + (active_radius * 0.35) * math.sin(self.phase)
        
        gradient = QRadialGradient(QPointF(center_x, center_y), active_radius, QPointF(fx, fy))
        gradient.setColorAt(0.00, QColor(255, 255, 255, 255))
        gradient.setColorAt(0.25, QColor(0, 230, 255, 220))
        gradient.setColorAt(0.55, QColor(255, 0, 128, 190))
        gradient.setColorAt(0.80, QColor(138, 43, 226, 150))
        gradient.setColorAt(1.00, QColor(0, 0, 0, 0))
        
        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(center_x, center_y), active_radius, active_radius)

class SmartAudioRecorder(QObject):
    finished = pyqtSignal(str)
    level_changed = pyqtSignal(float)
    
    def __init__(self):
        super().__init__()
        self.temp_file = ""
        self.is_recording = False
        self.sample_rate = 16000
        self.channels = 1
        self._lock = threading.Lock()
        
    @staticmethod
    def get_best_input_device():
        """
        Finds the best active working input device, prioritizing physical microphones
        (WASAPI, DirectSound, MME Microphone Arrays) over disconnected/sleeping Bluetooth profiles,
        and completely excluding kernel-mode WDM-KS.
        """
        try:
            devs = sd.query_devices()
            default_in = sd.default.device[0] if sd.default.device else 0
            candidates = []
            for idx, d in enumerate(devs):
                if d.get('max_input_channels', 0) > 0:
                    api_info = sd.query_hostapis(d['hostapi'])
                    api_name = api_info['name'].lower()
                    if 'wdm-ks' in api_name:
                        continue  # Never use WDM-KS exclusive mode in desktop app
                    name_lower = d['name'].lower()
                    is_bt_headset = any(k in name_lower for k in ['hands-free', 'bthhfenum', 'headset', 'airdopes', 'bluetooth'])
                    is_array = any(k in name_lower for k in ['array', 'realtek', 'internal', 'built-in', 'microphone'])
                    
                    score = 100
                    if 'mme' in api_name and is_array: score = 10
                    elif 'directsound' in api_name and is_array: score = 20
                    elif 'wasapi' in api_name and is_array: score = 30
                    elif idx == default_in and not is_bt_headset: score = 40
                    elif not is_bt_headset: score = 50
                    elif idx == default_in: score = 60
                    else: score = 70
                    candidates.append((score, idx, d, api_name))
            candidates.sort(key=lambda x: x[0])
            if candidates:
                best_idx = candidates[0][1]
                best_dev = candidates[0][2]
                sr = int(best_dev.get('default_samplerate', 16000))
                # For MME / DirectSound, 16000 Hz is ideal for Whisper and low CPU
                if 'mme' in candidates[0][3] or 'directsound' in candidates[0][3]:
                    sr = 16000
                return best_idx, sr
        except Exception as e:
            print(f"Error querying input devices: {e}")
        return None, 16000

    def start(self):
        with self._lock:
            if self.is_recording:
                return
            self.is_recording = True
            
        fd, self.temp_file = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        self.frames = []
        self.has_spoken = False
        self.silent_chunks = 0
        self.noise_floor = 0.0005
        self.chunk_count = 0
        
        def record_thread():
            best_idx, best_sr = self.get_best_input_device()
            self.sample_rate = best_sr
            chunk_size = 1024 if self.sample_rate >= 44100 else 512
            chunks_per_sec = self.sample_rate / chunk_size
            min_speech_chunks = int(1.2 * chunks_per_sec)  # Enforce at least 1.2s before silence stop
            silence_chunks_needed = int(1.4 * chunks_per_sec)  # ~1.4s of silence after speech
            max_chunks = int(14.0 * chunks_per_sec)  # 14s safety timeout
            
            def callback(indata, frames, time_info, status):
                if not self.is_recording:
                    raise sd.CallbackStop()
                    
                self.frames.append(indata.copy())
                self.chunk_count += 1
                
                rms = float(np.sqrt(np.mean(indata**2)))
                norm_level = min(1.0, max(0.0, (rms - self.noise_floor) / 0.04))
                self.level_changed.emit(norm_level)
                
                # First 10 chunks (~320ms) calibrate noise floor without triggering speech on click pops
                if self.chunk_count <= 10:
                    self.noise_floor = max(0.0001, min(0.008, self.noise_floor * 0.7 + rms * 0.3))
                    return
                    
                speech_threshold = max(self.noise_floor * 2.2, 0.004)
                
                if rms > speech_threshold:
                    self.has_spoken = True
                    self.silent_chunks = 0
                else:
                    if self.has_spoken:
                        self.silent_chunks += 1
                        if self.silent_chunks >= silence_chunks_needed and self.chunk_count >= min_speech_chunks:
                            self.is_recording = False
                            raise sd.CallbackStop()
                    else:
                        # Auto-stop if no speech detected after 7 seconds
                        if self.chunk_count > int(7.0 * chunks_per_sec):
                            self.is_recording = False
                            raise sd.CallbackStop()
                            
                if self.chunk_count >= max_chunks:
                    self.is_recording = False
                    raise sd.CallbackStop()
                    
            try:
                with sd.InputStream(device=best_idx, samplerate=self.sample_rate, channels=self.channels,
                                    dtype='float32', blocksize=chunk_size, callback=callback):
                    while self.is_recording:
                        sd.sleep(50)
            except Exception as e:
                print(f"Recording error with device {best_idx}: {e}")
                # Fallback to system default if preferred device failed
                if best_idx is not None and self.is_recording:
                    try:
                        with sd.InputStream(device=None, samplerate=16000, channels=self.channels,
                                            dtype='float32', blocksize=512, callback=callback):
                            self.sample_rate = 16000
                            while self.is_recording:
                                sd.sleep(50)
                    except Exception as e2:
                        print(f"Fallback recording error: {e2}")
            finally:
                self.is_recording = False
                self._save_and_emit()
                
        threading.Thread(target=record_thread, daemon=True).start()
        
    def _save_and_emit(self):
        if not self.frames:
            self.finished.emit("")
            return
        try:
            raw_audio = np.concatenate(self.frames, axis=0)
            # Automatic Gain Normalization so Whisper hears clear speech even on quiet microphones
            peak = float(np.max(np.abs(raw_audio)))
            if peak > 0.0003 and peak < 0.4:
                gain = min(12.0, 0.8 / peak)
                raw_audio = raw_audio * gain
            audio_data = np.int16(np.clip(raw_audio, -1.0, 1.0) * 32767)
            with wave.open(self.temp_file, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            self.finished.emit(self.temp_file)
        except Exception as e:
            print(f"Error saving audio: {e}")
            self.finished.emit("")
            
    def stop_manually(self, cancel=False):
        self.is_recording = False

from enum import Enum, auto
class IslandState(Enum):
    MINIMAL = auto()
    COMPACT = auto()
    HOVER = auto()
    TIMER_HOVER = auto()
    MEDIA_ACTIVE = auto()
    MEDIA_HOVER = auto()
    BATTERY_ALERT = auto()
    TEXT = auto()
    VOICE = auto()
    SETTINGS = auto()
    FULL_DASHBOARD = auto()


class HotkeySignals(QObject):
    triggered = pyqtSignal()

class DynamicIsland(QWidget):
    @pyqtProperty(QRectF)
    def pill_rect(self):
        return getattr(self, '_pill_rect', QRectF(0, 0, 160, 32))
        
    @pill_rect.setter
    def pill_rect(self, val):
        self._pill_rect = val
        self.update_mask_and_layout()
        
    @pyqtProperty(QRectF)
    def circle_rect(self):
        return getattr(self, '_circle_rect', QRectF(0, 0, 0, 0))
        
    @circle_rect.setter
    def circle_rect(self, val):
        self._circle_rect = val
        self.update_mask_and_layout()
        
    def __init__(self):
        super().__init__()
        
        # Setup fixed host canvas (expanded for Full Dashboard)
        screen = QApplication.primaryScreen().geometry()
        canvas_w, canvas_h = 640, 460
        self.setGeometry((screen.width() - canvas_w) // 2, 0, canvas_w, canvas_h)
        self.setMouseTracking(True) # VERY IMPORTANT for hover tracking without focus!
        self.cfg = config.load_config()
        self.state = IslandState.MINIMAL if self.cfg.get("collapsible_mode", False) else IslandState.COMPACT
        self.is_recording = False
        self.ai_state = "idle"  # "idle" | "listening" | "thinking" | "responding"
        
        # Setup window properties
        self.setWindowTitle("Zenith OS")
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.audio_recorder = SmartAudioRecorder()
        self.audio_recorder.finished.connect(self.on_audio_finished)
        self.audio_recorder.level_changed.connect(self._on_mic_level)
        self.btn_mic = None
        
        self.last_hotkey_time = 0
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hotkey_thread = WindowsHotkeyThread()
        self.hotkey_thread.triggered.connect(self._safe_on_hotkey)
        self.hotkey_thread.start()
        self.messages = []

        # Background Clipboard Manager (saves last 10 copied texts)
        self.clipboard_history = list(self.cfg.get("clipboard_history", []))[:10]
        qapp = QApplication.instance()
        if qapp:
            self.clipboard = qapp.clipboard()
            self.clipboard.dataChanged.connect(self._on_clipboard_changed)
        
        self.media_worker = MediaWorker()
        self.media_worker.media_updated.connect(self.on_media_update)
        self.media_worker.start()
        # Initialize layout tracking variables
        self.active_media = None
        self._pill_rect = QRectF(220, 0, 160, 32) # Centered initially
        self._circle_rect = QRectF(0, 0, 0, 0)

        # --- 1. COMPACT STATE ---
        self.compact_widget = QWidget(self)
        self.compact_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        c_layout = QHBoxLayout(self.compact_widget)
        c_layout.setContentsMargins(6, 0, 6, 0)
        c_layout.setSpacing(6)
        
        self.island_eyes = DynamicIslandEyes(self)
        if not self.cfg.get("companion_eyes", True):
            self.island_eyes.hide()
        self._apply_voice_theme()
        
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: white; font-weight: bold; font-family: 'SF Pro Display', 'Segoe UI', sans-serif; font-size: 13px;")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Minimalistic flowing wave for music inside single pill
        self.compact_music_vis = AudioVisualizer(self.compact_widget)
        self.compact_music_vis.setFixedSize(22, 16)
        self.compact_music_vis.hide()

        c_layout.addStretch()
        c_layout.addWidget(self.compact_music_vis)
        c_layout.addSpacing(6)
        c_layout.addWidget(self.island_eyes)

        # Fast cursor bounds tracker for instant auto-collapse on mouse leave
        self.dash_leave_timer = QTimer(self)
        self.dash_leave_timer.setInterval(60)
        self.dash_leave_timer.timeout.connect(self._check_dashboard_leave)
        self.dash_leave_timer.start()

        # Background process tray icon
        self._setup_tray_icon()

        # Aggressive memory optimization: auto-trim working set
        QTimer.singleShot(1500, self.trim_memory)
        self.mem_trim_timer = QTimer(self)
        self.mem_trim_timer.setInterval(45000)
        self.mem_trim_timer.timeout.connect(self.trim_memory)
        self.mem_trim_timer.start()
        c_layout.addWidget(self.status_lbl)
        c_layout.addStretch()
        
        # --- BATTERY ALERT STATE ---
        self.battery_widget = QWidget(self)
        self.battery_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.battery_widget.hide()
        bat_layout = QHBoxLayout(self.battery_widget)
        self.lbl_bat = QLabel("")
        self.lbl_bat.setStyleSheet("color: black; font-weight: bold; font-family: 'SF Pro Display', 'Segoe UI', sans-serif; font-size: 16px;")
        self.lbl_bat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bat_layout.addWidget(self.lbl_bat)
        
        # --- DROP STATE ---
        self.drop_widget = QWidget(self)
        self.drop_widget.hide()
        self.drop_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        drop_layout = QHBoxLayout(self.drop_widget)
        self.lbl_drop = QLabel("Drop file to stash...")
        self.lbl_drop.setStyleSheet("color: #00ffcc; font-weight: bold; font-family: 'SF Pro Display', 'Segoe UI', sans-serif; font-size: 16px;")
        self.lbl_drop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.lbl_drop)
        
        # --- 2. HOVER STATE (Customizable 3 Quick Action Buttons) ---
        self.hover_widget = QWidget(self)
        self.hover_widget.hide()
        self.h_layout = QHBoxLayout(self.hover_widget)
        self.h_layout.setContentsMargins(6, 0, 6, 0)
        self.h_layout.setSpacing(6)
        self._setup_hover_buttons()
        
        # Timer Setup
        self.active_timer_seconds = 0
        
        # --- 3. TEXT INPUT STATE ---
        self.text_widget = QWidget(self)
        self.text_widget.hide()
        t_layout = QHBoxLayout(self.text_widget)
        t_layout.setContentsMargins(0, 0, 0, 0)
        
        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("Type a command...")
        self.txt_input.setStyleSheet("background: #222; color: white; border: 1px solid #444; border-radius: 8px; padding: 5px;")
        self.txt_input.returnPressed.connect(self.submit_text)
        
        self.btn_send = QPushButton("➤")
        self.btn_send.setStyleSheet("background: #00ffcc; color: black; border-radius: 8px; font-weight: bold; padding: 5px 10px;")
        self.btn_send.clicked.connect(self.submit_text)
        
        self.btn_close_txt = QPushButton("✕")
        self.btn_close_txt.setStyleSheet("background: transparent; color: #ff4444; font-weight: bold; border: none;")
        self.btn_close_txt.clicked.connect(lambda: self.animate_to(IslandState.COMPACT))
        
        for btn in [self.btn_send, self.btn_close_txt]:
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        t_layout.addWidget(self.txt_input)
        t_layout.addWidget(self.btn_send)
        t_layout.addWidget(self.btn_close_txt)
        
        # --- 3.5. LISTENING STATE (Compact Inline Dynamic Island Pill) ---
        self.listening_widget = QWidget(self)
        self.listening_widget.hide()
        if hasattr(self, "drop_widget"): self.drop_widget.hide()
        if hasattr(self, "battery_widget"): self.battery_widget.hide()
        l_layout = QHBoxLayout(self.listening_widget)
        l_layout.setContentsMargins(12, 0, 12, 0)
        l_layout.setSpacing(8)
        l_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.siri_orb = SiriOrbWidget(size=18)
        
        self.listening_text = QLabel("Listening...")
        self.listening_text.setStyleSheet("color: white; font-size: 13px; font-weight: 600; font-family: 'SF Pro Display', 'Segoe UI', sans-serif;")
        self.listening_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.listening_subtext = QLabel("")
        self.listening_subtext.hide()
        self.btn_stop_listen = QPushButton("Stop")
        self.btn_stop_listen.hide()
        
        l_layout.addWidget(self.siri_orb)
        l_layout.addWidget(self.listening_text)
        
        
        # --- 4. SETTINGS STATE ---
        self._init_settings_ui()
        
        # Set all as children of self (for absolute positioning)
        self.timer_hover_widget = QWidget(self)
        self.timer_hover_widget.hide()
        th_layout = QHBoxLayout(self.timer_hover_widget)
        th_layout.setContentsMargins(15, 0, 15, 0)
        th_layout.setSpacing(10)
        
        self.lbl_timer_hover = QLabel("Timer 00:00")
        self.lbl_timer_hover.setStyleSheet("color: #ffaa00; font-family: 'SF Pro Display', 'Segoe UI', sans-serif; font-size: 15px; font-weight: bold; border: none;")
        
        self.btn_pause_timer = QPushButton("⏸")
        self.btn_pause_timer.setToolTip("Pause Timer")
        self.btn_stop_timer = QPushButton("⏹")
        self.btn_stop_timer.setToolTip("Stop Timer")
        self.btn_timer_to_hover = QPushButton("›")
        self.btn_timer_to_hover.setToolTip("Quick Controls")
        
        btn_timer_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 170, 0, 0.22);
                border-color: #ffaa00;
                color: #ffaa00;
            }
        """
        btn_stop_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 68, 68, 0.22);
                border-color: #ff4444;
                color: #ff4444;
            }
        """
        btn_next_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(0, 255, 204, 0.22);
                border-color: #00ffcc;
                color: #00ffcc;
            }
        """
        self.btn_pause_timer.setStyleSheet(btn_timer_style)
        self.btn_stop_timer.setStyleSheet(btn_stop_style)
        self.btn_timer_to_hover.setStyleSheet(btn_next_style)

        for b in [self.btn_pause_timer, self.btn_stop_timer, self.btn_timer_to_hover]:
            b.setFixedSize(28, 28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            
        self.btn_pause_timer.clicked.connect(self.toggle_timer_pause)
        self.btn_stop_timer.clicked.connect(self.stop_timer)
        self.btn_timer_to_hover.clicked.connect(lambda: self.animate_to(IslandState.HOVER))
        
        th_layout.addWidget(self.lbl_timer_hover)
        th_layout.addStretch()
        th_layout.addWidget(self.btn_pause_timer)
        th_layout.addWidget(self.btn_stop_timer)
        th_layout.addWidget(self.btn_timer_to_hover)

        # --- 6. MEDIA HOVER STATE (Compact Safe-Zone Media Controls) ---
        self.media_hover_widget = QWidget(self)
        self.media_hover_widget.hide()
        mh_layout = QVBoxLayout(self.media_hover_widget)
        mh_layout.setContentsMargins(14, 6, 14, 6)
        mh_layout.setSpacing(4)
        
        # Row 1: Track Title + Source badge
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        self.lbl_media_title = QLabel("Midnight in motion")
        self.lbl_media_title.setStyleSheet("color: white; font-weight: bold; font-family: 'Segoe UI', sans-serif; font-size: 12px;")
        self.lbl_media_artist = QLabel(" · Smart Notch Sessions")
        self.lbl_media_artist.setStyleSheet("color: rgba(255,255,255,0.6); font-family: 'Segoe UI', sans-serif; font-size: 11px;")
        self.lbl_media_source_badge = QLabel("Spotify")
        self.lbl_media_source_badge.setStyleSheet("color: #00ffcc; background: rgba(0,255,204,0.12); border-radius: 4px; padding: 1px 6px; font-size: 10px; font-weight: bold;")
        self.media_vis = AudioVisualizer()
        self.media_vis.setFixedSize(22, 14)
        
        row1.addWidget(self.lbl_media_title)
        row1.addWidget(self.lbl_media_artist)
        row1.addStretch()
        row1.addWidget(self.media_vis)
        row1.addSpacing(6)
        row1.addWidget(self.lbl_media_source_badge)
        mh_layout.addLayout(row1)
        
        # Row 2: Progress timeline bar
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)
        self.lbl_media_pos = QLabel("00:00")
        self.lbl_media_pos.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 10px; font-family: 'Segoe UI', monospace;")
        self.media_progress_bar = QProgressBar()
        self.media_progress_bar.setFixedHeight(4)
        self.media_progress_bar.setTextVisible(False)
        self.media_progress_bar.setRange(0, 100)
        self.media_progress_bar.setValue(0)
        self.media_progress_bar.setStyleSheet("""
            QProgressBar {
                background: rgba(255,255,255,0.15);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #00ffcc;
                border-radius: 2px;
            }
        """)
        self.lbl_media_rem = QLabel("-00:00")
        self.lbl_media_rem.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 10px; font-family: 'Segoe UI', monospace;")
        row2.addWidget(self.lbl_media_pos)
        row2.addWidget(self.media_progress_bar, 1)
        row2.addWidget(self.lbl_media_rem)
        mh_layout.addLayout(row2)
        
        # Row 3: Prev, Play/Pause, Next controls with crisp vector graphics
        from dashboard_widget import VectorMediaButton
        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 0, 0, 0)
        self.btn_media_prev = VectorMediaButton(mode="prev", is_accent=False)
        self.btn_media_prev.setFixedSize(28, 28)
        self.btn_media_play = VectorMediaButton(mode="play", is_accent=True)
        self.btn_media_play.setFixedSize(32, 32)
        self.btn_media_next = VectorMediaButton(mode="next", is_accent=False)
        self.btn_media_next.setFixedSize(28, 28)

        self.btn_media_prev.clicked.connect(self.media_worker.prev_track)
        self.btn_media_play.clicked.connect(self.media_worker.toggle_play_pause)
        self.btn_media_next.clicked.connect(self.media_worker.next_track)
        row3.addStretch()
        row3.addWidget(self.btn_media_prev)
        row3.addSpacing(18)
        row3.addWidget(self.btn_media_play)
        row3.addSpacing(18)
        row3.addWidget(self.btn_media_next)
        row3.addStretch()
        mh_layout.addLayout(row3)
        
        # Set all as children of self (for absolute positioning)
        self.compact_widget.setParent(self)
        self.hover_widget.setParent(self)
        self.text_widget.setParent(self)
        self.listening_widget.setParent(self)
        self.settings_widget.setParent(self)
        self.timer_hover_widget.setParent(self)
        
        # Full Dashboard Card Widget
        from dashboard_widget import DashboardWidget
        self.dashboard_widget = DashboardWidget(self)
        self.dashboard_widget.hide()
        self.dashboard_widget.collapse_requested.connect(lambda: self.animate_to(IslandState.COMPACT))
        self.dashboard_widget.pin_toggled.connect(self._on_dashboard_pin_toggled)
        
        self.ai_thread = None
        self.tts_worker = None
        
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_telemetry)
        self.update_timer.start(3000)
        self.update_telemetry()

        # Auto-collapse: after a few idle seconds shrink to a thin bar, expand again on hover
        self.idle_collapse_timer = QTimer(self)
        self.idle_collapse_timer.setSingleShot(True)
        self.idle_collapse_timer.setInterval(8000)
        self.idle_collapse_timer.timeout.connect(self._auto_collapse_if_idle)
        
        # --- BATTERY MONITORING (Green/Red island tint disabled per user request) ---
        self.battery_alert = None
        self.last_power_plugged = None
        self.low_battery_warned = False
        
        # Trigger initial layout and animation
        QTimer.singleShot(50, lambda: self.animate_to(IslandState.COMPACT))
        
    def eventFilter(self, source, event):
        from PyQt6.QtCore import QEvent
        if source == getattr(self, 'quick_list', None):
            if event.type() == QEvent.Type.DragEnter:
                if event.mimeData().hasUrls():
                    event.acceptProposedAction()
                    event.accept()
                    return True
            elif event.type() == QEvent.Type.Drop:
                if event.mimeData().hasUrls():
                    import os
                    for url in event.mimeData().urls():
                        path = url.toLocalFile()
                        if path.lower().endswith('.exe'):
                            name = os.path.basename(path).replace('.exe', '')
                            # Add to config
                            if "quick_apps" not in self.cfg:
                                self.cfg["quick_apps"] = []
                            if name not in self.cfg["quick_apps"]:
                                self.cfg["quick_apps"].append(name)
                                self.quick_list.addItem(f"[APP] {name}")
                    event.acceptProposedAction()
                    event.accept()
                    return True
            # Allow items to be deleted by pressing DEL key
            elif event.type() == QEvent.Type.KeyPress:
                from PyQt6.QtCore import Qt
                if event.key() == Qt.Key.Key_Delete:
                    item = self.quick_list.takeItem(self.quick_list.currentRow())
                    if item:
                        name = item.text().replace('[APP] ', '').replace('[CMD] ', '')
                        if "quick_apps" in self.cfg and name in self.cfg["quick_apps"]:
                            self.cfg["quick_apps"].remove(name)
                        if "quick_commands" in self.cfg and name in self.cfg["quick_commands"]:
                            self.cfg["quick_commands"].remove(name)
                    return True
        return super().eventFilter(source, event)

    def mousePressEvent(self, event):
        if hasattr(super(), 'mousePressEvent'):
            super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        if hasattr(super(), 'mouseMoveEvent'):
            super().mouseMoveEvent(event)

    def get_target_rect(self, width, height):
        screen = QApplication.primaryScreen().geometry()
        y = 0 # Flush with top of monitor!
        align = self.cfg.get("alignment", "Center")
        
        if align == "Left":
            x = 100
        elif align == "Right":
            x = screen.width() - width - 100
        else:
            x = (screen.width() - width) // 2
            
        return QRect(x, y, width, height)

    def toggle_timer_pause(self):
        self.is_timer_paused = not getattr(self, 'is_timer_paused', False)
        if hasattr(self, 'btn_pause_timer'):
            self.btn_pause_timer.setText("▶" if self.is_timer_paused else "⏸")
            self.btn_pause_timer.setToolTip("Resume Timer" if self.is_timer_paused else "Pause Timer")

    def start_timer(self, seconds: int):
        self.active_timer_seconds = int(seconds)
        self.is_timer_paused = False
        if hasattr(self, 'btn_pause_timer'):
            self.btn_pause_timer.setText("⏸")
            self.btn_pause_timer.setToolTip("Pause Timer")
        self.update_telemetry()

    def stop_timer(self):
        self.active_timer_seconds = 0
        self.is_timer_paused = False
        self.update_telemetry()
        if self.state not in (IslandState.FULL_DASHBOARD, IslandState.SETTINGS):
            self.animate_to(IslandState.COMPACT)

    def on_media_update(self, data):
        self.active_media = data
        is_active = data.get("active", False)
        is_playing = data.get("playing", False)
        if hasattr(self, 'compact_music_vis'):
            self.compact_music_vis.is_playing = is_playing
            if is_active:
                self.compact_music_vis.show()
            else:
                self.compact_music_vis.hide()
        self.media_vis.is_playing = is_playing

        title = data.get("title", "Unknown")
        artist = data.get("artist", "")
        source_app = data.get("source_app", "Media Player")
        pos_str = data.get("pos_str", "00:00")
        rem_str = data.get("rem_str", "-00:00")
        prog = data.get("progress", 0)

        if hasattr(self, 'lbl_media_title'):
            self.lbl_media_title.setText(title)
            self.lbl_media_artist.setText(f" · {artist}" if artist else "")
            self.lbl_media_source_badge.setText(source_app)
            self.lbl_media_pos.setText(pos_str)
            self.lbl_media_rem.setText(rem_str)
            self.media_progress_bar.setValue(prog)
            if hasattr(self.btn_media_play, 'set_mode'):
                self.btn_media_play.set_mode("pause" if is_playing else "play")
            else:
                self.btn_media_play.setText("⏸" if is_playing else "▶")

        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.update_media_data(data)

        if not is_active and self.state in [IslandState.MEDIA_ACTIVE, IslandState.MEDIA_HOVER]:
            if hasattr(self, 'compact_music_vis'):
                self.compact_music_vis.hide()
            self.animate_to(IslandState.COMPACT)
        elif is_active and self.state == IslandState.COMPACT:
            if hasattr(self, 'compact_music_vis'):
                self.compact_music_vis.show()
            self.animate_to(IslandState.MEDIA_ACTIVE)

        self.update()

    def trim_memory(self):
        """Aggressively releases unreferenced objects and flushes process working set on Windows."""
        import gc
        gc.collect()
        try:
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
            psapi.EmptyWorkingSet(kernel32.GetCurrentProcess())
        except Exception:
            pass

    def _setup_tray_icon(self):
        try:
            icon_path = get_resource_path("icon.ico")
            tray_icon = QIcon(icon_path) if os.path.exists(icon_path) else self.windowIcon()
            
            self.tray = QSystemTrayIcon(tray_icon, self)
            self.tray.setToolTip("Zenith OS (Desktop Companion)")
            
            menu = QMenu()
            menu.setStyleSheet("""
                QMenu {
                    background-color: #1a1a1a;
                    color: #ffffff;
                    border: 1px solid #333333;
                    border-radius: 8px;
                    padding: 4px;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 12px;
                }
                QMenu::item {
                    padding: 6px 20px 6px 12px;
                    border-radius: 4px;
                }
                QMenu::item:selected {
                    background-color: #0078d4;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #333333;
                    margin: 4px 8px;
                }
            """)
            
            act_toggle = menu.addAction("Show / Minimize Island")
            act_toggle.triggered.connect(self._toggle_island_visibility)
            
            act_settings = menu.addAction("Settings...")
            act_settings.triggered.connect(self.show_apple_settings)
            
            act_trim = menu.addAction("Trim RAM Footprint")
            act_trim.triggered.connect(self.trim_memory)
            
            menu.addSeparator()
            
            act_exit = menu.addAction("Exit Zenith OS")
            act_exit.triggered.connect(self._safe_exit)
            
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._on_tray_activated)
            self.tray.show()
        except Exception as e:
            print("Tray setup warning:", e)

    def _toggle_island_visibility(self):
        if self.state == IslandState.MINIMAL:
            self._prevent_hover_expand = True
            if self.active_timer_seconds > 0:
                self.animate_to(IslandState.TIMER_HOVER)
            else:
                self.animate_to(IslandState.COMPACT)
            QTimer.singleShot(600, lambda: setattr(self, '_prevent_hover_expand', False))
        else:
            self.animate_to(IslandState.MINIMAL)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_island_visibility()

    def _safe_exit(self):
        try:
            if hasattr(self, 'tray'):
                self.tray.hide()
        except Exception:
            pass
        QApplication.quit()

    def _show_island_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 4px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QMenu::separator {
                height: 1px;
                background-color: #333333;
                margin: 4px 8px;
            }
        """)
        
        act_toggle = menu.addAction("Toggle Notch (Compact / Minimal)")
        act_toggle.triggered.connect(self._toggle_island_visibility)
        
        act_settings = menu.addAction("Settings...")
        act_settings.triggered.connect(self.show_apple_settings)
        
        act_trim = menu.addAction("Trim RAM Footprint")
        act_trim.triggered.connect(self.trim_memory)
        
        menu.addSeparator()
        
        act_exit = menu.addAction("Exit Zenith OS")
        act_exit.triggered.connect(self._safe_exit)
        
        menu.exec(global_pos)

    def _on_clipboard_changed(self):
        try:
            if not hasattr(self, 'clipboard') or not self.clipboard:
                return
            text = self.clipboard.text().strip()
            if text and (not self.clipboard_history or self.clipboard_history[0] != text):
                if text in self.clipboard_history:
                    self.clipboard_history.remove(text)
                self.clipboard_history.insert(0, text)
                self.clipboard_history = self.clipboard_history[:10]
                self.cfg["clipboard_history"] = self.clipboard_history
                if hasattr(self, 'dashboard_widget'):
                    self.dashboard_widget.refresh_clipboard()
        except Exception:
            pass

    def _on_dashboard_pin_toggled(self, is_pinned):
        self.cfg["pinned_dashboard"] = is_pinned

    def _open_dashboard_tab(self, tab_idx: int):
        import time
        self._dashboard_open_time = time.time()
        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.switch_tab(tab_idx)
        self.animate_to(IslandState.FULL_DASHBOARD)

    def _setup_hover_buttons(self, force=False):
        if not hasattr(self, 'h_layout'):
            return
        if getattr(self, '_hover_buttons_built', False) and not force:
            return
        while self.h_layout.count() > 0:
            item = self.h_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.h_layout.addStretch()
        selected_btns = self.cfg.get("quick_actions", self.cfg.get("quick_buttons", ["music", "timer", "clipboard"]))
        defaults = ["music", "timer", "clipboard"]
        if not isinstance(selected_btns, list) or len(selected_btns) < 3:
            selected_btns = defaults

        btn_base_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                color: white;
                font-size: 15px;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
            }
            QPushButton:hover {
                background: rgba(0, 255, 204, 0.2);
                border-color: #00ffcc;
                color: #00ffcc;
            }
        """

        for code in selected_btns[:3]:
            c = str(code).lower()
            if c == "music":
                b = QPushButton("🎵")
                b.setToolTip("Music Controls")
                b.clicked.connect(lambda ch: self._open_dashboard_tab(0))
            elif c == "timer":
                b = QPushButton("⏱️")
                b.setToolTip("Timer & Focus")
                b.clicked.connect(lambda ch: self._open_dashboard_tab(1))
            elif c == "system":
                b = QPushButton("⚙️")
                b.setToolTip("System & Memory")
                b.clicked.connect(lambda ch: self._open_dashboard_tab(2))
            elif c in ("workspace", "workspaces"):
                b = QPushButton("💼")
                b.setToolTip("App Workspaces")
                b.clicked.connect(lambda ch: self._open_dashboard_tab(3))
            elif c == "clipboard":
                b = QPushButton("📋")
                b.setToolTip("Clipboard History")
                b.clicked.connect(lambda ch: self._open_dashboard_tab(4))
            elif c in ("voice", "mic"):
                b = QPushButton("🎙️")
                b.setToolTip("AI Voice Assistant")
                b.clicked.connect(self.toggle_recording)
            else:
                b = QPushButton("○")
                b.clicked.connect(self.show_apple_settings)

            b.setFixedSize(28, 28)
            b.setStyleSheet(btn_base_style)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.h_layout.addWidget(b)
            self.h_layout.addSpacing(6)

        self.h_layout.addStretch()
        self._hover_buttons_built = True

    def _is_in_disc_zone(self, pos):
        if not (self.active_media and self.active_media.get("active")):
            return False
        pr = self.pill_rect
        # Safe zone spans the left 58px of the unified notch pill
        return QRectF(pr.left(), pr.top(), 58, max(pr.height(), 32)).contains(pos)

    def _check_dashboard_leave(self):
        if self.state == IslandState.FULL_DASHBOARD:
            if hasattr(self, 'dashboard_widget') and not getattr(self.dashboard_widget, 'is_pinned', False):
                import time
                if hasattr(self, '_dashboard_open_time') and (time.time() - self._dashboard_open_time < 0.6):
                    return
                if QApplication.activePopupWidget() or QApplication.activeModalWidget():
                    return
                cursor_global = QCursor.pos()
                cx = self.width() // 2
                full_card_local = QRect(cx - 260, 0, 520, 410)
                card_rect_global = QRect(self.mapToGlobal(full_card_local.topLeft()), full_card_local.size())
                # The moment cursor leaves the expanded island area (+15px buffer for smooth UX)
                if not card_rect_global.adjusted(-15, -15, 15, 15).contains(cursor_global):
                    self.animate_to(IslandState.COMPACT)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if getattr(self, 'ai_state', 'idle') != 'idle' or self.state == IslandState.VOICE:
                if getattr(self, 'is_recording', False):
                    self.toggle_recording()
                return
            if self.state in [IslandState.COMPACT, IslandState.MEDIA_ACTIVE, IslandState.HOVER, IslandState.MEDIA_HOVER]:
                # Single-click anywhere expands to the Full Dashboard Card!
                import time
                self._dashboard_open_time = time.time()
                self.animate_to(IslandState.FULL_DASHBOARD)
                return
            elif self.state == IslandState.FULL_DASHBOARD:
                if hasattr(self, 'dashboard_widget') and not self.dashboard_widget.is_pinned:
                    if not self.dashboard_widget.geometry().contains(event.position().toPoint()):
                        self.animate_to(IslandState.COMPACT)
                return
            elif self.state == IslandState.SETTINGS:
                self.animate_to(IslandState.COMPACT)
                return
        elif event.button() == Qt.MouseButton.RightButton:
            if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.dragging = True
                self.drag_offset_x = event.globalPosition().x() - self.x()
            else:
                self._show_island_context_menu(event.globalPosition().toPoint())
            
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.state == IslandState.MINIMAL:
                # Unhide the island on double click
                self._prevent_hover_expand = True
                if self.active_timer_seconds > 0:
                    self.animate_to(IslandState.TIMER_HOVER)
                else:
                    self.animate_to(IslandState.COMPACT)
                QTimer.singleShot(600, lambda: setattr(self, '_prevent_hover_expand', False))
            elif self.state in [IslandState.COMPACT, IslandState.HOVER, IslandState.TIMER_HOVER, IslandState.SETTINGS, IslandState.FULL_DASHBOARD]:
                # Minimize the island on double click
                self.animate_to(IslandState.MINIMAL)

    def mouseMoveEvent(self, event):
        if self.state in [IslandState.MINIMAL, IslandState.FULL_DASHBOARD, IslandState.VOICE] or getattr(self, 'ai_state', 'idle') != 'idle' or getattr(self, '_prevent_hover_expand', False):
            super().mouseMoveEvent(event)
            return

        pos = event.position()
        if self.state in [IslandState.COMPACT, IslandState.MEDIA_ACTIVE]:
            if self.active_timer_seconds > 0:
                if self.pill_rect.contains(pos):
                    self.animate_to(IslandState.TIMER_HOVER)
            elif self.active_media and self.active_media.get("active"):
                if self.pill_rect.contains(pos):
                    self.animate_to(IslandState.HOVER)
            else:
                if self.pill_rect.contains(pos):
                    self.animate_to(IslandState.HOVER)

        elif self.state == IslandState.MEDIA_HOVER:
            if not self.pill_rect.contains(pos):
                if self.active_media and self.active_media.get("active"):
                    self.animate_to(IslandState.MEDIA_ACTIVE)
                else:
                    self.animate_to(IslandState.COMPACT)

        elif self.state in [IslandState.HOVER, IslandState.TIMER_HOVER]:
            # Add a 15px safe buffer so hovering over quick action buttons doesn't jitter collapse
            padded_rect = self.pill_rect.adjusted(-15, -15, 15, 15)
            if not padded_rect.contains(pos) and not getattr(self, '_ws_menu_open', False):
                if self.active_media and self.active_media.get("active"):
                    self.animate_to(IslandState.MEDIA_ACTIVE)
                else:
                    self.animate_to(IslandState.COMPACT)
                
        if getattr(self, 'dragging', False):
            new_window_x = int(event.globalPosition().x() - self.drag_offset_x)
            self.move(new_window_x, 0)
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, 'dragging', False):
            self.dragging = False
            screen = QApplication.primaryScreen().geometry()
            target_center_x = (screen.width() - self.width()) // 2
            
            if abs(self.x() - target_center_x) < 150:
                self.pos_anim = QPropertyAnimation(self, b"pos")
                self.pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                self.pos_anim.setDuration(400)
                self.pos_anim.setStartValue(self.pos())
                self.pos_anim.setEndValue(QPoint(target_center_x, 0))
                self.pos_anim.start()
                self.cfg["alignment"] = "Center"
            else:
                self.pos_anim = QPropertyAnimation(self, b"pos")
                self.pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                self.pos_anim.setDuration(400)
                self.pos_anim.setStartValue(self.pos())
                if self.x() < target_center_x:
                    self.pos_anim.setEndValue(QPoint(-150, 0))
                    self.cfg["alignment"] = "Left"
                else:
                    self.pos_anim.setEndValue(QPoint(screen.width() - 450, 0))
                    self.cfg["alignment"] = "Right"
                self.pos_anim.start()
            import config
            config.save_config(self.cfg)
        super().mouseReleaseEvent(event)

    def _is_eyes_only_mode(self):
        return self.cfg.get("display_mode", "Clock & Battery") in ["Only Emo Eyes", "Only Eyes"]

    def _are_eyes_enabled(self):
        return bool(self.cfg.get("companion_eyes", True)) or self._is_eyes_only_mode()

    def _use_eyes_voice_mode(self):
        # Per user request: listening mode with 3 bouncing vertical lines (Emo eyes) is default
        return True

    def _on_mic_level(self, level: float):
        if hasattr(self, "island_eyes"):
            self.island_eyes.set_mic_level(level)

    def update_telemetry(self):
        if self.state == IslandState.VOICE or getattr(self, 'ai_state', 'idle') != 'idle':
            return
        if self.active_timer_seconds > 0:
            if self.update_timer.interval() != 1000:
                self.update_timer.setInterval(1000)
            if not getattr(self, 'is_timer_paused', False):
                # Decrement here when dashboard isn't active/running local tick to avoid double-tick
                dash_ticking = hasattr(self, 'dashboard_widget') and getattr(self.dashboard_widget, 'is_timer_running', False)
                if not dash_ticking:
                    self.active_timer_seconds -= 1
                    if self.active_timer_seconds <= 0:
                        self.speak("Your timer is up!")
                        if self.state not in [IslandState.FULL_DASHBOARD]:
                            self.animate_to(IslandState.COMPACT)
            mins, secs = divmod(self.active_timer_seconds, 60)
            text = f"Timer {mins:02d}:{secs:02d}"
            if hasattr(self, 'dashboard_widget') and hasattr(self.dashboard_widget, 'update_timer_tick'):
                self.dashboard_widget.update_timer_tick(mins, secs, getattr(self, 'is_timer_paused', False))
            if self.state in [IslandState.COMPACT, IslandState.TIMER_HOVER, IslandState.MEDIA_ACTIVE]:
                self.island_eyes.hide()
                self.status_lbl.show()
                if getattr(self, '_last_lbl_color', None) != 'timer':
                    self._last_lbl_color = 'timer'
                    self.status_lbl.setStyleSheet("color: #ffaa00; font-weight: bold; font-family: 'SF Pro Display', 'Segoe UI', sans-serif; font-size: 13px;")
                if self.status_lbl.text() != text:
                    self.status_lbl.setText(text)
                self.lbl_timer_hover.setText(text)
                return
        else:
            if self.update_timer.interval() != 3000:
                self.update_timer.setInterval(3000)
            if getattr(self, '_last_lbl_color', None) != 'normal':
                self._last_lbl_color = 'normal'
                self.status_lbl.setStyleSheet("color: white; font-weight: bold; font-family: 'SF Pro Display', 'Segoe UI', sans-serif; font-size: 13px;")
                
            mode = self.cfg.get("display_mode", "Clock & Battery")
            show_eyes = self._are_eyes_enabled() and (
                self.state in [IslandState.COMPACT, IslandState.MEDIA_ACTIVE]
            ) and self.active_timer_seconds <= 0
            if show_eyes:
                if not self.island_eyes.isVisible():
                    self.island_eyes.show()
            else:
                if self.island_eyes.isVisible():
                    self.island_eyes.hide()

            user_w = max(68, min(300, int(self.cfg.get("compact_width", 180))))
            text = ""

            # Fast path: skip psutil calls completely when showing only Emo Eyes or when pill is too small for text!
            if mode in ["Only Emo Eyes", "Only Eyes"] or (show_eyes and user_w < 118):
                text = ""
            elif mode in ["Only Clock", "Clock"]:
                text = time.strftime("%I:%M %p")
            elif mode in ["Only Battery", "Battery Only"]:
                bat_val = system_tools.get_battery_fast()
                text = f"BAT: {bat_val}%"
            elif mode == "Clock & Battery":
                bat_val = system_tools.get_battery_fast()
                text = f"{time.strftime('%I:%M %p')}  |  BAT: {bat_val}%"
            elif mode == "All Stats":
                stats = system_tools.get_system_stats()
                text = f"C: {int(stats['cpu'])}% | R: {int(stats['ram'])}% | B: {int(stats['battery'])}%"
            else:  # "System Stats"
                stats = system_tools.get_system_stats()
                text = f"BAT: {int(stats['battery'])}% | CPU: {int(stats['cpu'])}%"

            if show_eyes and text:
                text_w = self.status_lbl.fontMetrics().horizontalAdvance(text)
                needed_both = self.island_eyes.width() + 6 + text_w + 22
                if user_w < needed_both:
                    text = ""
                
            if text:
                if self.status_lbl.text() != text:
                    self.status_lbl.setText(text)
                if not self.status_lbl.isVisible():
                    self.status_lbl.show()
            else:
                if self.status_lbl.text():
                    self.status_lbl.setText("")
                if self.status_lbl.isVisible():
                    self.status_lbl.hide()
            self._refit_compact_width()

    def _compact_target_width(self):
        """Directly respect the user's Compact Size slider down to 68px (the exact width of Emo Eyes)."""
        user_w = max(68, min(300, int(self.cfg.get("compact_width", 180))))
        base = int(max(68, min(user_w, self.width() - 40))) if self._are_eyes_enabled() else int(max(90, min(user_w, self.width() - 40)))
        if self.active_media and self.active_media.get("active"):
            base += 46 # Slightly expand the unified pill so disc fits smoothly beside eyes
        return base

    def _refit_compact_width(self, immediate=False):
        if self.state not in [IslandState.COMPACT, IslandState.MEDIA_ACTIVE]:
            return
        target_w = self._compact_target_width()
        cx = self.width() // 2
        end_rect = QRectF(cx - target_w // 2, 0, target_w, 32)
        self.circle_rect = QRectF(cx, 16, 0, 0)

        if immediate:
            anim = getattr(self, 'anim', None)
            if anim is not None and anim.state() == QParallelAnimationGroup.State.Running:
                anim.stop()
            fit = getattr(self, '_fit_anim', None)
            if fit is not None and fit.state() == QPropertyAnimation.State.Running:
                fit.stop()
            self.pill_rect = end_rect
            return

        anim = getattr(self, 'anim', None)
        if anim is not None and anim.state() == QParallelAnimationGroup.State.Running:
            return
        if abs(self.pill_rect.width() - target_w) < 2:
            return
        fit = QPropertyAnimation(self, b"pill_rect")
        fit.setDuration(180)
        fit.setEasingCurve(QEasingCurve.Type.OutCubic)
        fit.setStartValue(self.pill_rect)
        fit.setEndValue(end_rect)
        fit.start()
        self._fit_anim = fit

    def _auto_collapse_if_idle(self):
        if (self.state == IslandState.COMPACT and self.cfg.get("auto_collapse", False)
                and self.active_timer_seconds <= 0 and not self.underMouse()
                and not getattr(self, 'is_recording', False)):
            self.animate_to(IslandState.MINIMAL)
            
    def open_settings(self):
        self.show_apple_settings()

    def show_apple_settings(self):
        from settings_dialog import MinimalSettingsDialog
        self.animate_to(IslandState.COMPACT)
        dlg = MinimalSettingsDialog(self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()
        
    def _apply_voice_theme(self):
        is_ultron = (self.cfg.get("voice", "").lower() == "ultron")
        if hasattr(self, 'island_eyes'):
            self.island_eyes.set_ultron_theme(is_ultron)

    def _on_settings_saved(self, cfg):
        self.cfg = cfg
        self._apply_voice_theme()
        if not self.cfg.get("auto_collapse", False) and hasattr(self, "idle_collapse_timer"):
            self.idle_collapse_timer.stop()
            if self.state == IslandState.MINIMAL:
                self.animate_to(IslandState.COMPACT)
                return
        self.update_telemetry()
        if self.state in [IslandState.COMPACT, IslandState.MEDIA_ACTIVE]:
            self.compact_widget.show()
            self._refit_compact_width(immediate=True)

    def show_workspaces(self):
        import workspace_engine
        self._ws_menu_open = True
        try:
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu { background: #111; color: white; border: 1px solid #333; border-radius: 8px; padding: 5px; }
                QMenu::item { padding: 8px 20px; border-radius: 4px; }
                QMenu::item:selected { background: #1F2D3A; color: #00F0FF; }
            """)

            workspaces = workspace_engine.load_workspaces()
            for name, apps in workspaces.items():
                app_preview = ", ".join(workspace_engine.display_name(a) for a in apps[:3])
                if len(apps) > 3:
                    app_preview += f" +{len(apps)-3}"
                label = f"Launch {name.upper()} ({app_preview})" if app_preview else f"Launch {name.upper()} (empty)"
                action = QAction(label, self)
                action.triggered.connect(lambda checked=False, ws=name: self._launch_ws(ws))
                menu.addAction(action)

            if not workspaces:
                empty = QAction("No Workspaces Saved Yet", self)
                empty.setEnabled(False)
                menu.addAction(empty)

            menu.addSeparator()
            cap_new_act = QAction("+ Capture Open Windows as Workspace...", self)
            cap_new_act.triggered.connect(self._quick_capture_new_workspace)
            menu.addAction(cap_new_act)

            if workspaces:
                add_sub = menu.addMenu("+ Add Open Windows to Existing")
                for name in workspaces.keys():
                    act = QAction(f"Add to {name.upper()}", self)
                    act.triggered.connect(lambda checked=False, ws=name: self._quick_add_open_to_workspace(ws))
                    add_sub.addAction(act)

            manage_act = QAction("Manage Workspaces...", self)
            manage_act.triggered.connect(self.show_apple_settings)
            menu.addAction(manage_act)

            menu.exec(self.btn_quick.mapToGlobal(QPoint(0, self.btn_quick.height())))
        finally:
            self._ws_menu_open = False
            if self.state == IslandState.HOVER and not self.underMouse():
                self.animate_to(IslandState.COMPACT)

    def _quick_capture_new_workspace(self):
        import workspace_engine
        name, ok = QInputDialog.getText(self, "Capture Workspace", "Enter name for workspace (captures open windows):")
        if ok and name.strip():
            res = workspace_engine.capture_active_windows()
            apps = res.get("apps", [])
            workspace_engine.manage_workspace("edit" if name.strip().lower() in workspace_engine.load_workspaces() else "create", name.strip(), apps=apps)
            if hasattr(self, 'island_eyes') and self._are_eyes_enabled():
                self.island_eyes.trigger_happy(2000)
        self.animate_to(IslandState.COMPACT)

    def _quick_add_open_to_workspace(self, name):
        import workspace_engine
        res = workspace_engine.capture_active_windows()
        apps = res.get("apps", [])
        if apps:
            workspace_engine.manage_workspace("edit", name, apps=apps)
            if hasattr(self, 'island_eyes') and self._are_eyes_enabled():
                self.island_eyes.trigger_happy(2000)
        self.animate_to(IslandState.COMPACT)

    def _launch_ws(self, name):
        import workspace_engine
        if hasattr(self, 'island_eyes') and self._are_eyes_enabled():
            self.island_eyes.trigger_happy(2200)
        self.animate_to(IslandState.COMPACT)
        workspace_engine.launch_workspace_async(name)

    def execute_quick_command(self, cmd):
        self.txt_input.setText(cmd)
        self.submit_text()
        
    def add_quick_app(self):
        text, ok = QInputDialog.getText(self, "Add Quick App", "Enter the app name/command (e.g. notepad):", 
                                        QLineEdit.EchoMode.Normal, "")
        if ok and text:
            apps = self.cfg.get("quick_apps", [])
            apps.append(text)
            self.cfg["quick_apps"] = apps
            config.save_config(self.cfg)
            
    def remove_quick_app(self):
        apps = self.cfg.get("quick_apps", [])
        if not apps: return
        item, ok = QInputDialog.getItem(self, "Remove Quick App", "Select app to remove:", apps, 0, False)
        if ok and item:
            apps.remove(item)
            self.cfg["quick_apps"] = apps
            config.save_config(self.cfg)
        
    def add_quick_command(self):
        text, ok = QInputDialog.getText(self, "Add Quick Command", "Enter the command text:", 
                                        QLineEdit.EchoMode.Normal, "")
        if ok and text:
            cmds = self.cfg.get("quick_commands", [])
            cmds.append(text)
            self.cfg["quick_commands"] = cmds
            config.save_config(self.cfg)
            
    def remove_quick_command(self):
        cmds = self.cfg.get("quick_commands", [])
        if not cmds: return
        item, ok = QInputDialog.getItem(self, "Remove Quick Command", "Select command to remove:", cmds, 0, False)
        if ok and item:
            cmds.remove(item)
            self.cfg["quick_commands"] = cmds
            config.save_config(self.cfg)


    def update_mask_and_layout(self):
        from PyQt6.QtGui import QRegion
        pr = self.pill_rect.toRect()
        cr = self.circle_rect.toRect()
        mask_key = (pr.x(), pr.y(), pr.width(), pr.height(), cr.x(), cr.y(), cr.width(), cr.height(), self.state)
        if mask_key != getattr(self, '_last_mask_key', None):
            self._last_mask_key = mask_key
            region = QRegion()
            if self.state == IslandState.MINIMAL:
                # Provide an ergonomic hit area (at least 14px high) so double clicking to unhide is effortless
                hit_rect = QRect(pr.x(), 0, pr.width(), max(pr.height(), 14))
                region = region.united(QRegion(hit_rect))
            else:
                if pr.width() > 0:
                    region = region.united(QRegion(pr))
                if cr.width() > 0:
                    region = region.united(QRegion(cr))
            self.setMask(region)
        
        active_w = None
        if self.state == IslandState.COMPACT:
            active_w = self.compact_widget
        elif self.state == IslandState.BATTERY_ALERT:
            active_w = self.battery_widget
        elif self.state == IslandState.HOVER:
            active_w = self.hover_widget
        elif self.state == IslandState.TIMER_HOVER:
            active_w = self.timer_hover_widget
        elif self.state == IslandState.TEXT:
            active_w = self.text_widget
        elif self.state == IslandState.VOICE:
            active_w = self.compact_widget if self._use_eyes_voice_mode() else self.listening_widget
        elif self.state == IslandState.SETTINGS:
            active_w = self.settings_widget
        elif self.state == IslandState.MEDIA_ACTIVE:
            active_w = self.compact_widget
        elif self.state == IslandState.MEDIA_HOVER:
            active_w = self.media_hover_widget
        elif self.state == IslandState.FULL_DASHBOARD:
            active_w = self.dashboard_widget
            
        if active_w:
            active_w.setGeometry(pr)
            
        self.update()

    def animate_to(self, target_state):
        self.state = target_state
        
        group = QParallelAnimationGroup(self)
        anim_pill = QPropertyAnimation(self, b"pill_rect")
        anim_pill.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_pill.setDuration(400)
        
        anim_circle = QPropertyAnimation(self, b"circle_rect")
        anim_circle.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim_circle.setDuration(400)
        
        self.compact_widget.hide()
        self.hover_widget.hide()
        self.text_widget.hide()
        self.listening_widget.hide()
        if hasattr(self, "drop_widget"): self.drop_widget.hide()
        if hasattr(self, "battery_widget"): self.battery_widget.hide()
        self.settings_widget.hide()
        self.timer_hover_widget.hide()
        self.media_hover_widget.hide()
        if hasattr(self, 'dashboard_widget'):
            self.dashboard_widget.hide()
        
        if target_state != IslandState.VOICE:
            self.siri_orb.stop()
            
        cx = self.width() // 2
        cy = 0
        
        if target_state == IslandState.MINIMAL:
            target_w = 110
            anim_pill.setEndValue(QRectF(cx - target_w//2, cy, target_w, 12))
            anim_circle.setEndValue(QRectF(cx, cy + 4, 0, 0))
            
        elif target_state == IslandState.BATTERY_ALERT:
            target_w = 220
            target_h = 44
            anim_pill.setEndValue(QRectF(cx - target_w//2, cy, target_w, target_h))
            anim_circle.setEndValue(QRectF(cx, cy + target_h//2, 0, 0))
            self.battery_widget.show()
            self._fade_in_widget(self.battery_widget)
            
        elif target_state == IslandState.COMPACT:
            self.island_eyes.set_mood(EyeMood.IDLE)
            self.update_telemetry()  # refresh text + eye visibility first so we can measure it
            target_w = self._compact_target_width()
            anim_pill.setEndValue(QRectF(cx - target_w//2, cy, target_w, 32))
            anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
            self.compact_widget.show()
            self._fade_in_widget(self.compact_widget)
            if self.cfg.get("auto_collapse", False) and self.active_timer_seconds <= 0:
                self.idle_collapse_timer.start()
            
        elif target_state == IslandState.MEDIA_ACTIVE:
            self.island_eyes.set_mood(EyeMood.IDLE)
            self.update_telemetry()
            target_w = self._compact_target_width()
            anim_pill.setEndValue(QRectF(cx - target_w//2, cy, target_w, 32))
            anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
            self.compact_widget.show()
            if hasattr(self, 'compact_music_vis'):
                self.compact_music_vis.show()
            self._fade_in_widget(self.compact_widget)
            
        elif target_state == IslandState.MEDIA_HOVER:
            anim_pill.setEndValue(QRectF(cx - 145, cy, 290, 68))
            anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
            self.media_hover_widget.show()
            self._fade_in_widget(self.media_hover_widget)
            
        elif target_state == IslandState.HOVER:
            self._setup_hover_buttons()
            anim_pill.setEndValue(QRectF(cx - 105, cy, 210, 46))
            anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
            self.hover_widget.show()
            self._fade_in_widget(self.hover_widget)

        elif target_state == IslandState.FULL_DASHBOARD:
            import time
            self._dashboard_open_time = time.time()
            anim_pill.setEndValue(QRectF(cx - 260, cy, 520, 410))
            anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
            self.dashboard_widget.show()
            self._fade_in_widget(self.dashboard_widget)
            
        elif target_state == IslandState.TIMER_HOVER:
            anim_pill.setEndValue(QRectF(cx - 125, cy, 250, 50))
            anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
            self.timer_hover_widget.show()
            self._fade_in_widget(self.timer_hover_widget)
            
        elif target_state == IslandState.TEXT:
            anim_pill.setEndValue(QRectF(cx - 190, cy, 380, 65))
            anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
            self.text_widget.show()
            self._fade_in_widget(self.text_widget)
            self.txt_input.setFocus()
            
        elif target_state == IslandState.VOICE:
            if self._use_eyes_voice_mode():
                target_w = max(130, self._compact_target_width())
                target_h = 32
                anim_pill.setEndValue(QRectF(cx - target_w // 2, 0, target_w, target_h))
                anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
                self.status_lbl.setText("")
                self.status_lbl.hide()
                self.compact_widget.show()
                self.island_eyes.show()
                if getattr(self, 'ai_state', 'idle') in ('thinking', 'responding'):
                    self.island_eyes.set_mood(EyeMood.AI_RESPONDING)
                else:
                    self.island_eyes.set_mood(EyeMood.COMMAND_MIC)
                self.island_eyes._wake_physics()
            else:
                base_w = self.cfg.get("compact_width", 220)
                target_w = max(base_w + 40, 260)
                target_h = 42
                anim_pill.setEndValue(QRectF(cx - target_w // 2, 0, target_w, target_h))
                anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
                self.listening_widget.show()
                self._fade_in_widget(self.listening_widget)
                self.siri_orb.start()
                self.set_voice_text("Listening...")
                self.listening_subtext.setText("")
            
        elif target_state == IslandState.SETTINGS:
            self.refresh_workspace_list()
            anim_pill.setEndValue(QRectF(cx - 240, cy, 480, 320))
            anim_circle.setEndValue(QRectF(cx, cy + 16, 0, 0))
            self.settings_widget.setGeometry(int(cx - 230), int(cy + 10), 460, 300)
            self.settings_widget.show()
            self._fade_in_widget(self.settings_widget)
            
        group.addAnimation(anim_pill)
        group.addAnimation(anim_circle)
        group.start()
        self.anim = group

    def _fade_in_widget(self, widget):
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(250)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.start()
        
        if not hasattr(self, '_fade_anims'):
            self._fade_anims = []
        self._fade_anims.append(anim)
        # Keep only the last 10 to avoid memory leak
        if len(self._fade_anims) > 10:
            self._fade_anims.pop(0)

    def enterEvent(self, event):
        if getattr(self, 'ai_state', 'idle') != 'idle' or self.state == IslandState.VOICE:
            super().enterEvent(event)
            return

        if self.state == IslandState.MINIMAL:
            # Do NOT unhide on hover! Unhiding strictly requires double-clicking.
            super().enterEvent(event)
            return

        if hasattr(self, 'idle_collapse_timer'):
            self.idle_collapse_timer.stop()

        if getattr(self, '_prevent_hover_expand', False):
            super().enterEvent(event)
            return

        pos = QPointF(self.mapFromGlobal(QCursor.pos()))
        if self.state == IslandState.COMPACT:
            if self.active_timer_seconds > 0:
                self.animate_to(IslandState.TIMER_HOVER)
            else:
                self.animate_to(IslandState.HOVER)
        elif self.state == IslandState.MEDIA_ACTIVE:
            if self.pill_rect.contains(pos):
                self.animate_to(IslandState.HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._prevent_hover_expand = False
        if getattr(self, '_ws_menu_open', False):
            super().leaveEvent(event)
            return
        if self.state in (IslandState.MINIMAL, IslandState.VOICE) or getattr(self, 'ai_state', 'idle') != 'idle':
            super().leaveEvent(event)
            return
        if self.state == IslandState.FULL_DASHBOARD:
            # Let _check_dashboard_leave handle cursor tracking with global coordinates and grace period
            super().leaveEvent(event)
            return
        if self.state in [IslandState.HOVER, IslandState.TIMER_HOVER, IslandState.MEDIA_HOVER]:
            if self.active_media and self.active_media.get("active"):
                self.animate_to(IslandState.MEDIA_ACTIVE)
            else:
                self.animate_to(IslandState.COMPACT)
        super().leaveEvent(event)

    def paintEvent(self, event):
        if self.state == IslandState.FULL_DASHBOARD:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        pr = self.pill_rect
        
        painter.setBrush(QColor(0, 0, 0, 255))
        if pr.width() > 0:
            h = pr.height()
            radius = min(h / 2.0, 24.0)
            if radius > 0:
                path = QPainterPath()
                path.moveTo(pr.left(), pr.top())
                path.lineTo(pr.right(), pr.top())
                path.lineTo(pr.right(), pr.bottom() - radius)
                path.arcTo(pr.right() - 2 * radius, pr.bottom() - 2 * radius, 2 * radius, 2 * radius, 0, -90)
                path.lineTo(pr.left() + radius, pr.bottom())
                path.arcTo(pr.left(), pr.bottom() - 2 * radius, 2 * radius, 2 * radius, -90, -90)
                path.lineTo(pr.left(), pr.top())
                painter.fillPath(path, painter.brush())
            else:
                painter.drawRect(pr)
                
        cr = self.circle_rect
        if cr.width() > 0:
            h = cr.height()
            radius = min(h / 2.0, 24.0)
            if radius > 0:
                path = QPainterPath()
                path.moveTo(cr.left(), cr.top())
                path.lineTo(cr.right(), cr.top())
                path.lineTo(cr.right(), cr.bottom() - radius)
                path.arcTo(cr.right() - 2 * radius, cr.bottom() - 2 * radius, 2 * radius, 2 * radius, 0, -90)
                path.lineTo(cr.left() + radius, cr.bottom())
                path.arcTo(cr.left(), cr.bottom() - 2 * radius, 2 * radius, 2 * radius, -90, -90)
                path.lineTo(cr.left(), cr.top())
                painter.fillPath(path, QColor(0, 0, 0, 255))
            else:
                painter.drawRect(cr)

    def _init_settings_ui(self):
        self.settings_widget = QWidget(self)
        self.settings_widget.hide()
        
        v_layout = QVBoxLayout(self.settings_widget)
        v_layout.setContentsMargins(15, 15, 15, 15)
        v_layout.setSpacing(10)
        
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #111; border-radius: 8px; }
            QTabBar::tab {
                background: #222; color: #aaa; padding: 8px 15px; margin-right: 2px;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                font-family: 'Segoe UI'; font-weight: bold; font-size: 13px;
            }
            QTabBar::tab:selected { background: #111; color: #00ffcc; }
            QTabBar::tab:hover { background: #333; }
        """)
        
        # --- 1. General Tab ---
        general_w = QWidget()
        general_l = QFormLayout(general_w)
        general_l.setContentsMargins(20, 20, 20, 20)
        general_l.setSpacing(15)
        
        self.voice_cb = QComboBox()
        self.voice_cb.addItems(["Emo", "Female", "Male", "Ultron"])
        self.voice_cb.setCurrentText(self.cfg.get("voice", "Female"))
        self.voice_cb.setStyleSheet("background: #222; color: white; padding: 5px; border-radius: 4px; border: 1px solid #444;")
        
        self.chk_collapsible = QCheckBox("Enable Collapsible Notch")
        self.chk_collapsible.setStyleSheet("color: white; font-family: 'Segoe UI';")
        self.chk_collapsible.setChecked(self.cfg.get("collapsible_mode", False))
        
        general_l.addRow("<span style='color:#aaa; font-weight:bold;'>AI Voice</span>", self.voice_cb)
        general_l.addRow("", self.chk_collapsible)
        self.settings_tabs.addTab(general_w, "General")
        
        # --- 2. Appearance Tab ---
        app_w = QWidget()
        app_l = QFormLayout(app_w)
        app_l.setContentsMargins(20, 20, 20, 20)
        
        self.display_mode_cb = QComboBox()
        self.display_mode_cb.addItems(["Clock", "System Stats", "Minimal"])
        self.display_mode_cb.setCurrentText(self.cfg.get("display_mode", "Clock"))
        self.display_mode_cb.setStyleSheet("background: #222; color: white; padding: 5px; border-radius: 4px; border: 1px solid #444;")
        
        app_l.addRow("<span style='color:#aaa; font-weight:bold;'>Idle Display</span>", self.display_mode_cb)
        
        self.settings_tabs.addTab(app_w, "Appearance")
        
        
        # --- 4. Workspaces Tab ---
        ws_tab = QWidget()
        ws_l = QVBoxLayout(ws_tab)
        ws_l.setContentsMargins(15, 15, 15, 15)
        
        self.ws_list = QListWidget()
        self.ws_list.setStyleSheet("""
            QListWidget { background: #1a1a1a; color: white; border-radius: 5px; padding: 5px; border: 1px solid #333; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #222; }
        """)
        ws_l.addWidget(self.ws_list)
        
        ws_actions = QHBoxLayout()
        self.btn_new_ws = QPushButton("+ New")
        self.btn_edit_ws = QPushButton("Edit")
        self.btn_del_ws = QPushButton("Delete")
        for b in (self.btn_new_ws, self.btn_edit_ws, self.btn_del_ws):
            b.setStyleSheet("background: #2a2a2a; color: white; padding: 6px; border-radius: 4px; font-weight:bold;")
            ws_actions.addWidget(b)
            
        self.btn_new_ws.clicked.connect(self.create_workspace_ui)
        self.btn_edit_ws.clicked.connect(self.edit_workspace_ui)
        self.btn_del_ws.clicked.connect(self.delete_workspace_ui)
        
        ws_l.addLayout(ws_actions)
        self.settings_tabs.addTab(ws_tab, "Workspaces")
        v_layout.addWidget(self.settings_tabs)
        
        # Bottom Save/Exit Buttons
        btn_layout = QHBoxLayout()
        self.btn_exit_zenith = QPushButton("Exit Zenith OS")
        self.btn_exit_zenith.setStyleSheet("background: #441111; color: #ff5555; padding: 8px 15px; border-radius: 4px; font-weight: bold;")
        self.btn_exit_zenith.clicked.connect(lambda: QApplication.quit())
        
        self.btn_save = QPushButton("Save & Close")
        self.btn_save.setStyleSheet("background: #00ffcc; color: #000; padding: 8px 15px; border-radius: 4px; font-weight: bold;")
        self.btn_save.clicked.connect(self.save_settings)
        
        btn_layout.addWidget(self.btn_exit_zenith)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        v_layout.addLayout(btn_layout)

    def refresh_workspace_list(self):
        import workspace_engine
        self.ws_list.clear()
        workspaces = workspace_engine.load_workspaces()
        for name, apps in workspaces.items():
            app_names = [workspace_engine.display_name(app) for app in apps]
            app_str = ', '.join(app_names) if app_names else 'No apps'
            if len(app_str) > 40:
                app_str = app_str[:37] + '...'
            self.ws_list.addItem(f"[{name.upper()}] - {app_str}")

    def create_workspace_ui(self):
        import workspace_engine
        name, ok = QInputDialog.getText(self, "New Workspace", "Enter workspace name:")
        if ok and name.strip():
            res = workspace_engine.capture_active_windows()
            active_apps = res.get('apps', []) if isinstance(res, dict) else res
            key = name.strip().lower()
            action = "edit" if key in workspace_engine.load_workspaces() else "create"
            workspace_engine.manage_workspace(action, key, apps=active_apps)
            self.refresh_workspace_list()

    def edit_workspace_ui(self):
        import workspace_engine
        item = self.ws_list.currentItem()
        if not item:
            return
        name = item.text().split(']')[0][1:].lower()
        res = workspace_engine.capture_active_windows()
        active_apps = res.get('apps', []) if isinstance(res, dict) else res
        workspace_engine.manage_workspace("edit", name, apps=active_apps)
        self.refresh_workspace_list()

    def delete_workspace_ui(self):
        import workspace_engine
        item = self.ws_list.currentItem()
        if not item:
            return
        name = item.text().split(']')[0][1:].lower()
        workspace_engine.manage_workspace("delete", name)
        self.refresh_workspace_list()

    def update_roundness(self, value):
        self.cfg["roundness"] = value / 100.0
        self.update()


    def _check_battery(self):
        import psutil
        try:
            battery = psutil.sensors_battery()
            if not battery: return
            
            plugged = battery.power_plugged
            percent = battery.percent
            
            if getattr(self, 'last_power_plugged', None) is False and plugged is True:
                self._trigger_battery_alert("CHARGING", QColor(0, 255, 100))
                
            if not plugged and percent <= 20 and not getattr(self, 'low_battery_warned', False):
                self.low_battery_warned = True
                self._trigger_battery_alert("BATTERY LOW", QColor(255, 50, 50))
                
            if plugged:
                self.low_battery_warned = False
                
            self.last_power_plugged = plugged
        except Exception:
            pass

    def _trigger_battery_alert(self, text, color):
        from PyQt6.QtCore import QVariantAnimation
        self.lbl_bat.setText(text)
        self.animate_to(IslandState.BATTERY_ALERT)
        
        self.bat_anim = QVariantAnimation(self)
        self.bat_anim.setDuration(2000)
        self.bat_anim.setStartValue(color)
        self.bat_anim.setEndValue(QColor(0, 0, 0))
        self.bat_anim.valueChanged.connect(self._on_bat_color_change)
        self.bat_anim.finished.connect(self._clear_battery_alert)
        self.bat_anim.start()
        
    def _on_bat_color_change(self, color):
        self.battery_alert_color = color
        self.update()
        
    def _clear_battery_alert(self):
        self.battery_alert_color = None
        self.animate_to(IslandState.COMPACT)
    def save_settings(self):
        self.cfg["display_mode"] = self.display_mode_cb.currentText()
        self.cfg["voice"] = self.voice_cb.currentText()
        self.cfg["collapsible_mode"] = self.chk_collapsible.isChecked()
        
        
        
        config.save_config(self.cfg)
        self.update()
        if self.cfg.get("collapsible_mode", False):
            self.animate_to(IslandState.MINIMAL)
        else:
            self.animate_to(IslandState.COMPACT)


    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._safe_on_hotkey()
                event.accept()
                return
            event.ignore()
            return
        super().keyPressEvent(event)

    def set_voice_text(self, text):
        if not text:
            return
        if self._use_eyes_voice_mode():
            return
        fm = self.listening_text.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        needed_w = text_w + 64 # orb + padding + margins
        target_w = max(220, min(needed_w, 460))
        
        avail_w = target_w - 55
        display_str = fm.elidedText(text, Qt.TextElideMode.ElideRight, avail_w)
        self.listening_text.setText(display_str)
        self.listening_text.setToolTip(text if display_str != text else "")
        
        if self.state == IslandState.VOICE:
            cx = self.width() // 2
            if abs(self.pill_rect.width() - target_w) > 6 or abs(self.pill_rect.height() - 42) > 2:
                anim = QPropertyAnimation(self, b"pill_rect")
                anim.setDuration(220)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.setStartValue(self.pill_rect)
                anim.setEndValue(QRectF(cx - target_w // 2, 0, target_w, 42))
                anim.start()
                self._voice_width_anim = anim

    def _safe_on_hotkey(self):
        if not self.cfg.get("enable_hotkey", True):
            return
        import time
        now = time.time()
        if now - getattr(self, 'last_hotkey_time', 0) < 0.35:
            return
        self.last_hotkey_time = now
        self.toggle_recording()

    def toggle_recording(self):
        if getattr(self, 'is_recording', False):
            # Stop recording and process whatever voice command was captured
            self.audio_recorder.stop_manually(cancel=False)
            self.is_recording = False
            self.ai_state = "thinking"
            self.listening_text.setText("Thinking...")
            if hasattr(self, 'island_eyes'):
                self.island_eyes.set_mood(EyeMood.AI_RESPONDING)
                self.island_eyes._wake_physics()
        else:
            if not self.cfg.get("groq_api_key"):
                self.listening_text.setText("API Key Required")
                self.animate_to(IslandState.VOICE)
                QTimer.singleShot(1800, lambda: self.animate_to(IslandState.COMPACT))
                return
                
            self.is_recording = True
            self.ai_state = "listening"
            if hasattr(self, 'btn_mic') and self.btn_mic:
                self.btn_mic.setText("■")
                self.btn_mic.setStyleSheet("background: transparent; color: #ff4444; font-size: 18px; font-weight: bold; border: none; padding: 5px;")
            self.listening_text.setText("Listening...")
            self.animate_to(IslandState.VOICE)
            if hasattr(self, 'island_eyes'):
                self.island_eyes.set_mood(EyeMood.COMMAND_MIC)
                self.island_eyes._wake_physics()
            self.siri_orb.start()
            self.audio_recorder.start()

    def on_audio_finished(self, temp_wav):
        # Auto-triggered by silence VAD or max timeout
        self.is_recording = False
        if hasattr(self, 'btn_mic') and self.btn_mic:
            self.btn_mic.setText("🎙")
            self.btn_mic.setStyleSheet("background: transparent; color: #00ffcc; font-size: 18px; border: none; padding: 5px;")
        
        if not temp_wav or not os.path.exists(temp_wav) or os.path.getsize(temp_wav) < 1000:
            self.ai_state = "idle"
            self.set_voice_text("I didn't catch that.")
            self.siri_orb.stop()
            if hasattr(self, 'island_eyes') and self._are_eyes_enabled():
                self.island_eyes.trigger_confused(1800)
                QTimer.singleShot(1800, lambda: self.animate_to(IslandState.COMPACT))
            else:
                if hasattr(self, 'island_eyes'):
                    self.island_eyes.hide()
                self.animate_to(IslandState.COMPACT)
            return
            
        self.ai_state = "thinking"
        if hasattr(self, 'island_eyes'):
            self.island_eyes.set_mood(EyeMood.AI_RESPONDING)
            self.island_eyes._wake_physics()
        self.update_ai_status("Thinking...")
        self.process_audio(temp_wav)

    def update_ai_status(self, text):
        if not self._use_eyes_voice_mode():
            self.status_lbl.setText(text)
            self.set_voice_text(text)
        if text == "Thinking...":
            self.ai_state = "thinking"
            if hasattr(self, 'island_eyes'):
                self.island_eyes.set_mood(EyeMood.AI_RESPONDING)
                self.island_eyes._wake_physics()
        elif text in ["Error", "I didn't catch that."]:
            self.ai_state = "idle"
            if text == "Error":
                self.island_eyes._trigger_net_check()
            if hasattr(self, 'island_eyes') and self._are_eyes_enabled():
                self.island_eyes.trigger_confused(2000)
        elif text == "Done":
            self.listening_subtext.setText("processing complete.")

    def check_fast_path(self, text):
        import workspace_engine
        t = text.lower().strip()
        if "lock pc" in t or "lock the pc" in t:
            return {"actions": [{"action": "lock_pc"}], "speech": "Locking the PC."}
        if "minimize" in t and ("window" in t or "all" in t):
            return {"actions": [{"action": "minimize_all"}], "speech": "Minimizing windows."}
        if t.startswith(("open ", "launch ", "start ")):
             rest = re.sub(r"^(open|launch|start)\s+", "", t).strip()
             ws_map = workspace_engine.load_workspaces()
             matched_ws = workspace_engine.match_workspace_name(rest, ws_map)
             if matched_ws and ("workspace" in rest or rest in ws_map):
                 return {
                     "actions": [{"action": "launch_workspace", "workspace_name": matched_ws}],
                     "speech": f"Launching {matched_ws} workspace."
                 }
             if "workspace" not in rest and " and " not in rest and " with " not in rest:
                 return {"actions": [{"action": "launch_app", "target": rest}], "speech": f"Opening {rest}."}
        if "battery" in t:
            return {"actions": [{"action": "stats"}], "speech": "Here are your battery stats."}
        if "volume up" in t or "increase volume" in t:
            return {"actions": [{"action": "set_volume", "value": "+10"}], "speech": "Turning volume up."}
        if "volume down" in t or "decrease volume" in t:
            return {"actions": [{"action": "set_volume", "value": "-10"}], "speech": "Turning volume down."}
        if "brightness up" in t or "increase brightness" in t:
            return {"actions": [{"action": "set_brightness", "value": "+10"}], "speech": "Turning brightness up."}
        if "brightness down" in t or "decrease brightness" in t:
            return {"actions": [{"action": "set_brightness", "value": "-10"}], "speech": "Turning brightness down."}
        return None

    def submit_text(self):
        cmd = self.txt_input.text().strip()
        if not cmd: return
        
        fast_intent = self.check_fast_path(cmd)
        if fast_intent:
            self.txt_input.clear()
            self.execute_action(fast_intent)
            return
            
        if not self.cfg.get("groq_api_key"):
            self.update_ai_status("Check backend config for API Key")
            self.animate_to(IslandState.COMPACT)
            return
            
        self.txt_input.clear()
        self.ai_state = "thinking"
        self.animate_to(IslandState.VOICE)
        if hasattr(self, 'island_eyes'):
            self.island_eyes.set_mood(EyeMood.AI_RESPONDING)
            self.island_eyes._wake_physics()
        self.siri_orb.stop()
        self.update_ai_status("Thinking...")
        self.listening_subtext.setText("reading text....")
        self.btn_stop_listen.hide()
        
        clip_text = QApplication.clipboard().text()
        if len(clip_text) > 2000: clip_text = clip_text[:2000] + "... [truncated]"
        self.ai_thread = AIEngineThread(api_key=self.cfg.get("groq_api_key", ""), text_input=cmd, history=self.messages, clipboard_text=clip_text)
        self.ai_thread.status_update.connect(self.update_ai_status)
        self.ai_thread.transcription_ready.connect(lambda text: self.set_voice_text(f'"{text}"'))
        self.ai_thread.action_ready.connect(self.execute_action)
        self.ai_thread.start()

    def process_audio(self, filepath):
        clip_text = QApplication.clipboard().text()
        if len(clip_text) > 2000: clip_text = clip_text[:2000] + "... [truncated]"
        self.ai_thread = AIEngineThread(api_key=self.cfg.get("groq_api_key", ""), audio_file=filepath, history=self.messages, clipboard_text=clip_text)
        self.ai_thread.status_update.connect(self.update_ai_status)
        self.ai_thread.transcription_ready.connect(lambda text: self.set_voice_text(f'"{text}"'))
        self.ai_thread.action_ready.connect(self.execute_action)
        self.ai_thread.start()
        
    def execute_action(self, intent):
        actions = intent.get("actions", [])
        speech = intent.get("speech", "I have processed your request.")
        
        # If it's the old schema, wrap it in actions
        if "action" in intent and not actions:
            actions = [intent]

        action_messages = []
        for act in actions:
            delay = act.get("delay_seconds", 0)
            if delay > 0:
                QTimer.singleShot(delay * 1000, lambda a=act: self.run_specific_action(a))
            else:
                msg = self.run_specific_action(act)
                if msg:
                    action_messages.append(msg)
                
        self.ai_state = "responding"
        if hasattr(self, 'island_eyes'):
            self.island_eyes.set_mood(EyeMood.AI_RESPONDING)
            self.island_eyes._wake_physics()
        final_speech = speech
        if action_messages and (not speech or speech in ("I have processed your request.", "Done.")):
            final_speech = " ".join(action_messages)
        self.set_voice_text(final_speech)
        self.speak(final_speech)

    def run_specific_action(self, intent):
        action = intent.get("action", "unknown")
        target = intent.get("target")
        
        if action == "create_folder" and target:
            system_tools.create_folder(target)
            
        elif action == "capture_workspace":
            import workspace_engine
            ws_name = intent.get("workspace_name") or target or intent.get("name")
            if ws_name:
                res = workspace_engine.capture_active_windows()
                apps = res.get("apps", [])
                op = "edit" if workspace_engine.match_workspace_name(ws_name, workspace_engine.load_workspaces()) else "create"
                workspace_engine.manage_workspace(op, ws_name, apps=apps)

        elif action == "create_workspace":
            import workspace_engine
            ws_name = intent.get("workspace_name") or target or intent.get("name")
            if ws_name:
                apps = intent.get("apps") or []
                if not apps and self.cfg.get("auto_capture_workspaces", True):
                    apps = workspace_engine.capture_active_windows().get("apps", [])
                op = "edit" if workspace_engine.match_workspace_name(ws_name, workspace_engine.load_workspaces()) else "create"
                workspace_engine.manage_workspace(op, ws_name, apps=apps)

        elif action == "launch_workspace":
            import workspace_engine
            ws_name = intent.get("workspace_name") or target or intent.get("name")
            if ws_name:
                workspace_engine.launch_workspace_async(ws_name)

        elif action == "edit_workspace":
            import workspace_engine
            ws_name = intent.get("workspace_name") or target or intent.get("name")
            if ws_name:
                apps = intent.get("apps") or []
                remove_apps = intent.get("remove_apps") or []
                if not apps and not remove_apps and self.cfg.get("auto_capture_workspaces", True):
                    apps = workspace_engine.capture_active_windows().get("apps", [])
                workspace_engine.manage_workspace("edit", ws_name, apps=apps, remove_apps=remove_apps)

        elif action == "delete_workspace":
            import workspace_engine
            ws_name = intent.get("workspace_name") or target or intent.get("name")
            if ws_name:
                workspace_engine.manage_workspace("delete", ws_name)
            
        elif action == "find_file":
            try:
                files_res = system_tools.find_file(intent.get("filename") or target or "")
                if isinstance(files_res, dict) and files_res.get("paths"):
                    import subprocess
                    subprocess.Popen(['cmd', '/c', 'start', '""', files_res["paths"][0]], creationflags=subprocess.CREATE_NO_WINDOW)
                    return f"Found {os.path.basename(files_res['paths'][0])}."
                return files_res.get("reason", "File not found.") if isinstance(files_res, dict) else "File not found."
            except Exception as e:
                print(f"find_file error: {e}")
                return "Error searching for file."
                
        elif action == "read_website":
            url = intent.get("url")
            if url:
                try:
                    import urllib.request
                    from bs4 import BeautifulSoup
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        html = response.read().decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(html, 'html.parser')
                    for s in soup(['script', 'style', 'nav', 'header', 'footer']):
                        s.decompose()
                    text = ' '.join(soup.stripped_strings)[:800]
                    return f"Website summary: {text[:250]}..."
                except Exception as e:
                    return f"Could not read website: {e}"
                
        elif action == "set_power_mode":
            system_tools.set_power_mode(intent.get("mode"))
            
        elif action == "delete_folder" and target:
            size_bytes = system_tools.get_folder_size(target)
            size_gb = size_bytes / (1024**3)
            if size_gb > 25:
                reply = QMessageBox.question(self, "Safety Check", 
                    f"Warning: This folder is {size_gb:.2f} GB. Are you absolutely sure you want to delete it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: return
            else:
                reply = QMessageBox.question(self, "Confirm Delete", 
                    f"Send {os.path.basename(target)} to recycle bin?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: return
            system_tools.safe_delete(target)
            
        elif action == "move_file" and target:
            target2 = intent.get("target2")
            if target2:
                reply = QMessageBox.question(self, "Confirm Move", 
                    f"Move {os.path.basename(target)} to {os.path.basename(target2)}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    system_tools.move_file(target, target2)
                    
        elif action == "launch_app" and target:
            system_tools.launch_app(target)
            
        elif action == "open_website" and target:
            system_tools.open_website(target)
            
        elif action == "search_web" and target:
            system_tools.search_web(target)
            
        elif action == "minimize_all":
            system_tools.minimize_all()
            
        elif action == "kill_process" and target:
            res = system_tools.kill_process(target)
            if not res["success"]:
                print(res["reason"])
            
        elif action == "set_volume":
            val = intent.get("value")
            if val is not None: system_tools.set_volume(val)
                
        elif action == "set_brightness":
            val = intent.get("value")
            if val is not None: system_tools.set_brightness(val)
                
        elif action == "lock_pc":
            system_tools.lock_pc()
            
        elif action == "create_file":
            filename = intent.get("filename")
            destination = intent.get("destination")
            file_type = intent.get("file_type")
            content = intent.get("content", "")
            if filename and destination and file_type:
                system_tools.create_file_secure(filename, destination, file_type, content)
                
        elif action == "get_size" and target:
            try:
                res = system_tools.get_path_size_formatted(target)
                if res.get('success'):
                    folder_name = os.path.basename(res.get('path', target)) or target
                    return f"The size of {folder_name} is {res.get('size_str')}."
                return res.get('reason', 'Could not get folder size.')
            except Exception as e:
                print(f"get_size error: {e}")
                return "Could not determine folder size."
                
        elif action == "list_files" and target:
            try:
                res = system_tools.list_files(target)
                return res.get("reason", "")
            except Exception as e:
                print(f"list_files error: {e}")
                return 
                
        elif action == "set_timer":
            val = intent.get("value")
            if val is not None:
                try:
                    self.active_timer_seconds = int(val)
                    self.is_timer_paused = False
                    self.update_telemetry()
                except ValueError: pass

        # --- SYSTEM TOGGLES ---
        elif action == "toggle_wifi":
            val = intent.get("value", "on")
            system_tools.toggle_wifi(val)
        elif action == "toggle_bluetooth":
            val = intent.get("value", "on")
            system_tools.toggle_bluetooth(val)
        elif action == "toggle_airplane":
            val = intent.get("value", "on")
            system_tools.toggle_airplane(val)
        elif action == "toggle_hotspot":
            val = intent.get("value", "on")
            system_tools.toggle_hotspot(val)
        elif action == "toggle_battery_saver":
            val = intent.get("value", "on")
            system_tools.toggle_battery_saver(val)
        elif action == "toggle_night_light":
            val = intent.get("value", "on")
            system_tools.toggle_night_light(val)
        elif action == "remember":
            info = intent.get("content") or target or intent.get("value")
            if info:
                mem_file = os.path.join(os.path.expanduser("~"), ".zenith_memory.txt")
                try:
                    with open(mem_file, "a", encoding="utf-8") as f:
                        f.write(f"\n- {info}")
                    return f"I have remembered: {info}"
                except Exception as e:
                    return f"Could not save memory: {e}"
            
    def speak(self, text):
        if not text:
            self.ai_state = "idle"
            if hasattr(self, 'island_eyes') and self._are_eyes_enabled():
                self.island_eyes.trigger_happy(1600)
                QTimer.singleShot(1600, lambda: self.animate_to(IslandState.COMPACT))
            else:
                if hasattr(self, 'island_eyes'):
                    self.island_eyes.hide()
                self.animate_to(IslandState.COMPACT)
            return
        self.ai_state = "responding"
        if hasattr(self, 'island_eyes'):
            self.island_eyes.set_mood(EyeMood.AI_RESPONDING)
            self.island_eyes._wake_physics()
        self.tts_worker = TTSWorker(text, voice=self.cfg.get("voice", "Female"))
        self.tts_worker.speech_finished.connect(self._on_speech_finished)
        self.tts_worker.start()
        # Fallback safety timer proportional to text length
        timeout_ms = max(12000, len(text) * 120)
        QTimer.singleShot(timeout_ms, self._ensure_compact_after_speech)
        
    def _on_speech_finished(self):
        # AI speech response completed! Celebrate with happy eyes only if eyes are enabled, otherwise return straight to compact
        self.ai_state = "idle"
        if hasattr(self, 'island_eyes') and self._are_eyes_enabled():
            self.island_eyes.trigger_happy(1600)
            QTimer.singleShot(1600, lambda: self.animate_to(IslandState.COMPACT))
        else:
            if hasattr(self, 'island_eyes'):
                self.island_eyes.hide()
            self.animate_to(IslandState.COMPACT)
        
    def _ensure_compact_after_speech(self):
        if getattr(self, 'ai_state', 'idle') == 'responding' and self.state == IslandState.VOICE:
            self.ai_state = "idle"
            if hasattr(self, 'island_eyes') and self._are_eyes_enabled():
                self.island_eyes.trigger_happy(1200)
                QTimer.singleShot(1200, lambda: self.animate_to(IslandState.COMPACT))
            else:
                if hasattr(self, 'island_eyes'):
                    self.island_eyes.hide()
                self.animate_to(IslandState.COMPACT)
            
    def closeEvent(self, event):
        try:
            if hasattr(self, 'tray'):
                self.tray.hide()
            if hasattr(self, 'hotkey_thread') and self.hotkey_thread.isRunning():
                self.hotkey_thread.stop()
            if hasattr(self, 'media_worker') and self.media_worker.isRunning():
                self.media_worker.stop_worker()
        except Exception:
            pass
        super().closeEvent(event)


import traceback

def global_exception_handler(exc_type, exc_value, exc_tb):
    try:
        with open("CRASH_LOG.txt", "w", encoding="utf-8") as f:
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = global_exception_handler

def _terminate_stale_instances():
    """Ensure no older Zenith OS / DynamicIslandOS main.py process is still holding Ctrl+Space."""
    try:
        import psutil
        my_pid = os.getpid()
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if p.info["pid"] == my_pid:
                    continue
                pname = (p.info["name"] or "").lower()
                if "python" not in pname:
                    continue
                cmd = " ".join(p.info["cmdline"] or []).lower()
                if "dynamicislandos" in cmd and "main.py" in cmd:
                    p.terminate()
            except Exception:
                pass
    except Exception:
        pass


if __name__ == "__main__":
    import re
    _terminate_stale_instances()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")

    icon_path = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    island = DynamicIsland()
    
    # media circle logic is now internal to DynamicIsland
    
    island.show()
    sys.exit(app.exec())
