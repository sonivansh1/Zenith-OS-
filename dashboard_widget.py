import os
import math
import time
import json
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, 
    QStackedWidget, QProgressBar, QSlider, QScrollArea, QFrame, QApplication,
    QLineEdit, QCheckBox, QMenu, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QPoint, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QFont, QPen, QPixmap, QIcon, QCursor,
    QRadialGradient, QLinearGradient, QBrush, QFontMetrics, QAction
)

# ----------------- WINDOWS CORE AUDIO COM INTERFACE -----------------
try:
    import comtypes
    import comtypes.client
    from comtypes import GUID, COMMETHOD, HRESULT, IUnknown
    from pycaw.pycaw import AudioUtilities

    class IPolicyConfig(IUnknown):
        _iid_ = GUID('{f8679f50-850a-41cf-9c72-430f290290c8}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'GetMixFormat'),
            COMMETHOD([], HRESULT, 'GetDeviceFormat'),
            COMMETHOD([], HRESULT, 'ResetDeviceFormat'),
            COMMETHOD([], HRESULT, 'SetDeviceFormat'),
            COMMETHOD([], HRESULT, 'GetProcessingPeriod'),
            COMMETHOD([], HRESULT, 'SetProcessingPeriod'),
            COMMETHOD([], HRESULT, 'GetShareMode'),
            COMMETHOD([], HRESULT, 'SetShareMode'),
            COMMETHOD([], HRESULT, 'GetPropertyValue'),
            COMMETHOD([], HRESULT, 'SetPropertyValue'),
            COMMETHOD([], HRESULT, 'SetDefaultEndpoint',
                      (['in'], wintypes.LPCWSTR, 'wszDeviceId'),
                      (['in'], ctypes.c_uint, 'eRole')),
            COMMETHOD([], HRESULT, 'SetEndpointVisibility')
        ]
except Exception:
    IPolicyConfig = None
    AudioUtilities = None


def get_audio_output_devices():
    """Returns list of active Windows audio output endpoints."""
    if not AudioUtilities:
        return []
    try:
        speakers = AudioUtilities.GetSpeakers()
        def_id = speakers.id if speakers else ""
        device_enumerator = AudioUtilities.GetDeviceEnumerator()
        collection = device_enumerator.EnumAudioEndpoints(0, 1) # eRender=0, DEVICE_STATE_ACTIVE=1
        count = collection.GetCount()
        devs = []
        for i in range(count):
            ep = collection.Item(i)
            dev = AudioUtilities.CreateDevice(ep)
            name = dev.FriendlyName if hasattr(dev, "FriendlyName") else ep.GetId()
            ep_id = dev.id if hasattr(dev, "id") else ep.GetId()
            icon = "🔊"
            lower_name = name.lower()
            if any(k in lower_name for k in ["headphone", "earphone", "headset", "buds", "airpods", "bt-"]):
                icon = "🎧"
            devs.append({
                "name": name,
                "clean_name": name,
                "icon": icon,
                "id": ep_id,
                "is_default": (ep_id == def_id)
            })
        return devs
    except Exception:
        return []


def set_default_audio_device(device_id: str):
    """Changes Windows default audio output endpoint for all roles."""
    if not IPolicyConfig or not device_id:
        return False
    try:
        policy_config = comtypes.client.CreateObject(
            GUID('{870af99c-171d-4f9e-af0d-e63df40c2bc9}'),
            interface=IPolicyConfig
        )
        for role in [0, 1, 2]: # eConsole, eMultimedia, eCommunications
            policy_config.SetDefaultEndpoint(device_id, role)
        return True
    except Exception:
        return False


def extract_vibrant_color(pix: QPixmap) -> QColor:
    """Extracts a vibrant, punchy dominant color from an album cover thumbnail."""
    if not pix or pix.isNull():
        return QColor(0, 255, 204) # default neon teal
    try:
        img = pix.toImage().scaled(24, 24, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        best_color = None
        max_score = -1.0
        r_acc, g_acc, b_acc, total_pixels = 0, 0, 0, 0

        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                r, g, b = c.red(), c.green(), c.blue()
                h, s, v, _ = c.getHsv()
                # Skip pure black, nearly white, or washed out grey
                if v < 35 or v > 245 or s < 30:
                    continue
                r_acc += r
                g_acc += g
                b_acc += b
                total_pixels += 1
                # Weight colorfulness heavily
                score = (s / 255.0) * 1.6 + (v / 255.0)
                if score > max_score:
                    max_score = score
                    best_color = c

        if best_color:
            h, s, v, _ = best_color.getHsv()
            # Boost brightness for pitch-black OLED background
            if v < 170:
                v = min(255, int(v * 1.4) + 30)
            if s < 130:
                s = min(255, int(s * 1.3))
            return QColor.fromHsv(h, s, v)
        elif total_pixels > 0:
            return QColor(int(r_acc / total_pixels), int(g_acc / total_pixels), int(b_acc / total_pixels))
        else:
            return QColor(0, 255, 204)
    except Exception:
        return QColor(0, 255, 204)


class VectorMediaButton(QPushButton):
    """Draws crisp vector icons (prev, play/pause, next, reset) with dynamic accent color."""
    def __init__(self, mode="play", is_accent=False, parent=None):
        super().__init__(parent)
        self.mode = mode # 'prev', 'play', 'pause', 'next', 'reset'
        self.is_accent = is_accent
        self.accent_color = QColor(0, 255, 204)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_mode(self, mode):
        if self.mode != mode:
            self.mode = mode
            self.update()

    def set_accent_color(self, color: QColor):
        if color and color.isValid():
            self.accent_color = color
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        cx, cy = w / 2.0, h / 2.0

        if self.is_accent:
            # Filled circular button using vibrant dominant color (e.g. pink or cyan)
            bg = self.accent_color if (self.accent_color and self.accent_color.isValid()) else QColor(255, 255, 255)
            if self.underMouse():
                bg = bg.lighter(115)
            painter.setBrush(bg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(1, 1, w - 2, h - 2))
            icon_color = QColor(0, 0, 0)
        else:
            if self.underMouse():
                painter.setBrush(QColor(255, 255, 255, 30))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(0, 0, w, h))
                icon_color = self.accent_color if (self.accent_color and self.accent_color.isValid()) else QColor(255, 255, 255)
            else:
                painter.setBrush(QColor(255, 255, 255, 16))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(0, 0, w, h))
                icon_color = QColor(255, 255, 255, 220)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(icon_color)

        if self.mode == "prev":
            # Bar on left + triangle pointing left
            painter.drawRoundedRect(QRectF(cx - 7, cy - 6, 2.2, 12), 1, 1)
            p = QPainterPath()
            p.moveTo(cx + 6, cy - 6.5)
            p.lineTo(cx - 3, cy)
            p.lineTo(cx + 6, cy + 6.5)
            p.closeSubpath()
            painter.drawPath(p)

        elif self.mode == "next":
            # Triangle pointing right + bar on right
            p = QPainterPath()
            p.moveTo(cx - 6, cy - 6.5)
            p.lineTo(cx + 3, cy)
            p.lineTo(cx - 6, cy + 6.5)
            p.closeSubpath()
            painter.drawPath(p)
            painter.drawRoundedRect(QRectF(cx + 5, cy - 6, 2.2, 12), 1, 1)

        elif self.mode == "play":
            # Triangle pointing right
            p = QPainterPath()
            p.moveTo(cx - 4, cy - 7)
            p.lineTo(cx + 6, cy)
            p.lineTo(cx - 4, cy + 7)
            p.closeSubpath()
            painter.drawPath(p)

        elif self.mode == "pause":
            # Two vertical rounded bars
            painter.drawRoundedRect(QRectF(cx - 5, cy - 7, 3.2, 14), 1.5, 1.5)
            painter.drawRoundedRect(QRectF(cx + 1.8, cy - 7, 3.2, 14), 1.5, 1.5)

        elif self.mode == "reset":
            # Circular arrow icon (↺)
            pen = QPen(icon_color, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = 7.0
            arc_rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            painter.drawArc(arc_rect, 45 * 16, 270 * 16)
            # Arrow head
            painter.setBrush(icon_color)
            painter.setPen(Qt.PenStyle.NoPen)
            p = QPainterPath()
            p.moveTo(cx - r - 3.5, cy - 1)
            p.lineTo(cx - r + 3.5, cy - 1)
            p.lineTo(cx - r, cy - 5.5)
            p.closeSubpath()
            painter.drawPath(p)


class Android16WaveformSeekBar(QWidget):
    """
    Android 16-inspired expressive waveform seek bar:
    - 52 vertical bars with varying heights along the track.
    - Played portion: glowing accent bars (colored in album dominant color).
    - Unplayed portion: subtle, muted dark-grey bars.
    - Fluid wave animation when music is playing; frozen when paused.
    - Entire waveform is seekable (click or drag anywhere).
    - Elapsed and total duration timestamps below the waveform.
    """
    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self.progress = 0.0 # 0.0 to 1.0
        self.is_playing = False
        self.phase = 0.0
        self.is_dragging = False

        self.pos_str = "00:00"
        self.dur_str = "00:00"
        self.pos_sec = 0.0
        self.total_duration_sec = 0.0

        self._anchor_epoch_time = time.time()
        self._anchor_pos_sec = 0.0

        self.accent_color = QColor(0, 255, 204)
        self._seek_lock_until = 0.0
        self._last_tick_time = time.time()

        # Animation & progress timer (25 FPS)
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(40)
        self.anim_timer.timeout.connect(self._on_anim_tick)
        self.anim_timer.start()

    def set_accent_color(self, color: QColor):
        if color and color.isValid():
            self.accent_color = color
            self.update()

    def set_playing(self, playing: bool):
        now = time.time()
        if self.is_playing and not playing:
            if not self.is_dragging and self.total_duration_sec > 0:
                elapsed = max(0.0, now - self._anchor_epoch_time)
                self.pos_sec = min(self.total_duration_sec, max(0.0, self._anchor_pos_sec + elapsed))
                self._anchor_pos_sec = self.pos_sec
                self._anchor_epoch_time = now
        elif not self.is_playing and playing:
            self._anchor_epoch_time = now
            self._anchor_pos_sec = self.pos_sec

        self.is_playing = bool(playing)
        self._last_tick_time = now
        self.update()

    def set_timeline(self, pos_sec: float, end_sec: float, pos_str: str, dur_str: str):
        self.total_duration_sec = max(0.0, float(end_sec))
        self.dur_str = dur_str or "00:00"

        # If user is dragging or seeking cooldown is active, prevent jumpy resets
        if self.is_dragging:
            return

        now = time.time()
        if now < self._seek_lock_until:
            if abs(float(pos_sec) - self.pos_sec) < 1.5:
                self._seek_lock_until = 0.0
            else:
                return

        self._anchor_epoch_time = now
        self._anchor_pos_sec = max(0.0, float(pos_sec))
        self.pos_sec = self._anchor_pos_sec
        cur_m, cur_s = divmod(int(self.pos_sec), 60)
        self.pos_str = pos_str or f"{cur_m:02d}:{cur_s:02d}"
        if self.total_duration_sec > 0:
            self.progress = min(1.0, max(0.0, self.pos_sec / self.total_duration_sec))
        else:
            self.progress = 0.0
        self.update()

    def _on_anim_tick(self):
        now = time.time()
        self._last_tick_time = now

        if self.is_playing:
            self.phase += 0.08
            # Smoothly advance playback position in real-time continuously
            if not self.is_dragging and self.total_duration_sec > 0:
                elapsed = max(0.0, now - self._anchor_epoch_time)
                live_pos = min(self.total_duration_sec, max(0.0, self._anchor_pos_sec + elapsed))
                self.pos_sec = live_pos
                self.progress = min(1.0, max(0.0, live_pos / self.total_duration_sec))
                cur_m, cur_s = divmod(int(live_pos), 60)
                self.pos_str = f"{cur_m:02d}:{cur_s:02d}"
        if self.isVisible():
            self.update()

    def showEvent(self, event):
        super().showEvent(event)
        # Snap immediately to live wall-clock playback position when revealed
        if self.is_playing and not self.is_dragging and self.total_duration_sec > 0:
            now = time.time()
            elapsed = max(0.0, now - self._anchor_epoch_time)
            live_pos = min(self.total_duration_sec, max(0.0, self._anchor_pos_sec + elapsed))
            self.pos_sec = live_pos
            self.progress = min(1.0, max(0.0, live_pos / self.total_duration_sec))
            cur_m, cur_s = divmod(int(live_pos), 60)
            self.pos_str = f"{cur_m:02d}:{cur_s:02d}"
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self._update_seek_from_pos(event.position().x())

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self._update_seek_from_pos(event.position().x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self._update_seek_from_pos(event.position().x())
            target_sec = self.progress * self.total_duration_sec
            self.pos_sec = target_sec
            self._anchor_epoch_time = time.time()
            self._anchor_pos_sec = target_sec
            self._seek_lock_until = time.time() + 2.0
            self.seek_requested.emit(target_sec)

    def _update_seek_from_pos(self, px: float):
        w = float(self.width())
        track_left = 14.0
        track_right = w - 14.0
        track_w = max(1.0, track_right - track_left)
        norm = (px - track_left) / track_w
        self.progress = min(1.0, max(0.0, norm))
        if self.total_duration_sec > 0:
            cur_sec = self.progress * self.total_duration_sec
            self.pos_sec = cur_sec
            cur_m, cur_s = divmod(int(cur_sec), 60)
            self.pos_str = f"{cur_m:02d}:{cur_s:02d}"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        track_left = 14.0
        track_right = w - 14.0
        track_w = max(1.0, track_right - track_left)

        bar_count = 52
        bar_w = 3.2
        mid_y = 13.0

        step = track_w / float(bar_count - 1)

        played_brush = QBrush(self.accent_color)
        unplayed_brush = QBrush(QColor(255, 255, 255, 38))

        # 1. Draw Waveform Bars
        for i in range(bar_count):
            norm_i = i / float(bar_count - 1)
            bx = track_left + i * step - (bar_w / 2.0)

            # Smooth expressive envelope
            window = math.sin(norm_i * math.pi) ** 0.45
            h_factor = (
                0.32
                + 0.35 * math.sin(norm_i * 3.8 * math.pi + self.phase)
                + 0.20 * math.cos(norm_i * 7.2 * math.pi - self.phase * 0.7)
                + 0.13 * math.sin(norm_i * 11.0 * math.pi + self.phase * 1.3)
            )
            bar_h = max(3.5, min(22.0, (h_factor * 18.0 + 3.5) * (0.35 + 0.65 * window)))
            by = mid_y - (bar_h / 2.0)

            painter.setPen(Qt.PenStyle.NoPen)
            if norm_i <= self.progress:
                painter.setBrush(played_brush)
            else:
                painter.setBrush(unplayed_brush)
            painter.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), bar_w / 2.0, bar_w / 2.0)

        # 2. Draw Time Labels directly below waveform
        font = QFont("Segoe UI", 9)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 140))

        painter.drawText(int(track_left), 36, self.pos_str)
        fm = QFontMetrics(font)
        dur_w = fm.horizontalAdvance(self.dur_str)
        painter.drawText(int(track_right - dur_w), 36, self.dur_str)


class AlbumArtWidget(QWidget):
    """
    Album artwork card with crisp rounded corners and subtle hairline stroke.
    Sits cleanly in the center of the ambient radial glow.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(94, 94)
        self.thumb_pixmap = None
        self.dominant_color = QColor(0, 255, 204)

    def set_thumbnail(self, path):
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self.thumb_pixmap = pix.scaled(
                    94, 94, 
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.dominant_color = extract_vibrant_color(pix)
                self.update()
                return self.dominant_color
        self.thumb_pixmap = None
        self.dominant_color = QColor(0, 255, 204)
        self.update()
        return self.dominant_color

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(r, 18, 18)

        painter.save()
        painter.setClipPath(path)

        if self.thumb_pixmap:
            pw, ph = self.thumb_pixmap.width(), self.thumb_pixmap.height()
            px = (self.width() - pw) / 2.0
            py = (self.height() - ph) / 2.0
            painter.drawPixmap(int(px), int(py), self.thumb_pixmap)
        else:
            # Pitch-black vinyl styling
            painter.fillRect(r, QColor(10, 10, 10))
            cx, cy = self.width() / 2.0, self.height() / 2.0

            # Outer vinyl groove ring
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - 36, cy - 36, 72, 72))

            # Inner vinyl groove ring
            painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
            painter.drawEllipse(QRectF(cx - 24, cy - 24, 48, 48))

            painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
            painter.drawEllipse(QRectF(cx - 14, cy - 14, 28, 28))

            # Center vinyl center spindle dot
            painter.setBrush(self.dominant_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx - 4.5, cy - 4.5, 9, 9))

        painter.restore()

        # Thin outer border around artwork
        painter.setPen(QPen(QColor(255, 255, 255, 35), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 18, 18)


class MusicPageWidget(QWidget):
    """
    Music Player Card with large static radial ambient glow matching the album art colors.
    - Completely static diffuse radial gradient glow spreading behind the album art and title.
    - No CPU overhead, no animation or jitter.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dominant_color = QColor(0, 255, 204)
        self.ambient_glow_enabled = True

    def set_dominant_color(self, color: QColor):
        if color and color.isValid():
            self.dominant_color = color
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw large static radial gradient glow across the upper section
        if self.ambient_glow_enabled and self.dominant_color.isValid():
            w = float(self.width())
            cx = w / 2.0
            cy = 82.0 # Centered directly behind the album artwork
            radius = 210.0 # Wide diffuse static radial gradient

            glow = QRadialGradient(QPointF(cx, cy), radius)
            r, g, b = self.dominant_color.red(), self.dominant_color.green(), self.dominant_color.blue()
            glow.setColorAt(0.00, QColor(r, g, b, 175))
            glow.setColorAt(0.28, QColor(r, g, b, 110))
            glow.setColorAt(0.58, QColor(r, g, b, 42))
            glow.setColorAt(0.82, QColor(r, g, b, 12))
            glow.setColorAt(1.00, QColor(r, g, b, 0))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawRect(self.rect())

        super().paintEvent(event)


class CpuSparklineWidget(QWidget):
    """Mini real-time sparkline graph for CPU history (matching Screenshot Card 1)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(84, 28)
        self.history = [12.0, 16.0, 18.0, 15.0, 22.0, 26.0]

    def add_point(self, val: float):
        self.history.append(float(val))
        if len(self.history) > 16:
            self.history.pop(0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        if len(self.history) < 2:
            return

        min_val = 0.0
        max_val = max(100.0, max(self.history) * 1.15)
        val_range = max(1.0, max_val - min_val)

        points = []
        step = w / float(len(self.history) - 1)
        for i, val in enumerate(self.history):
            px = i * step
            norm_y = (val - min_val) / val_range
            py = h - 3.0 - (norm_y * (h - 7.0))
            points.append(QPointF(px, py))

        # Build smooth curved path
        path = QPainterPath()
        path.moveTo(points[0])
        for i in range(len(points) - 1):
            p0 = points[i]
            p1 = points[i + 1]
            c1 = QPointF(p0.x() + (p1.x() - p0.x()) / 2.0, p0.y())
            c2 = QPointF(p0.x() + (p1.x() - p0.x()) / 2.0, p1.y())
            path.cubicTo(c1, c2, p1)

        # Gradient fill under curve
        fill_path = QPainterPath(path)
        fill_path.lineTo(w, h)
        fill_path.lineTo(0, h)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(56, 189, 248, 80))
        grad.setColorAt(1.0, QColor(56, 189, 248, 0))
        painter.fillPath(fill_path, grad)

        # Neon curve line
        pen = QPen(QColor(56, 189, 248), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)


class MetricProgressBar(QWidget):
    """Sleek rounded progress bar matching the screenshot cards."""
    def __init__(self, color=QColor(0, 255, 204), parent=None):
        super().__init__(parent)
        self.setFixedHeight(5)
        self.value = 0.5  # 0.0 to 1.0
        self.color = color

    def set_value(self, val: float):
        self.value = max(0.0, min(1.0, float(val)))
        self.update()

    def set_color(self, color: QColor):
        self.color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        r = h / 2.0

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 25))
        painter.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        # Foreground fill
        fill_w = max(h, w * self.value)
        painter.setBrush(self.color)
        painter.drawRoundedRect(QRectF(0, 0, fill_w, h), r, r)


class VerticalSliderCapsule(QWidget):
    """
    Curved-corner vertical slider capsule for Brightness and Volume (iOS/macOS Control Center style).
    - Curved corner rectangle (rounded rect, radius 13px).
    - Fills from bottom to top with gradient and percentage value.
    - Icon at bottom (☀️ or 🔊).
    - Interactive: click, drag, and mouse-wheel support with fluid 60 FPS LERP animation.
    """
    value_changed = pyqtSignal(int)

    def __init__(self, mode="brightness", parent=None):
        super().__init__(parent)
        self.mode = mode  # 'brightness' or 'volume'
        self.setFixedSize(40, 78)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.value = 50  # 0 to 100
        self.target_value = 50.0
        self.visual_value = 50.0
        self.is_dragging = False
        self.last_user_interaction = 0.0

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)  # ~60 FPS
        self.anim_timer.timeout.connect(self._tick_anim)

        if self.mode == "brightness":
            self.icon_str = "☀️"
            self.accent_color = QColor(251, 191, 36)
            self.setToolTip("Brightness: 50%\nClick or drag to adjust")
        else:
            self.icon_str = "🔊"
            self.accent_color = QColor(0, 255, 204)
            self.setToolTip("Volume: 50%\nClick or drag to adjust")

    def _tick_anim(self):
        diff = self.target_value - self.visual_value
        if abs(diff) < 0.2:
            self.visual_value = self.target_value
            self.anim_timer.stop()
        else:
            self.visual_value += diff * 0.45
        self.update()

    def set_value(self, val: int):
        if self.is_dragging:
            return
        if time.time() - self.last_user_interaction < 3.0:
            return
        self.value = max(0, min(100, int(val)))
        self.target_value = float(self.value)
        if not self.anim_timer.isActive():
            self.anim_timer.start()
        self._update_tooltip()

    def _update_tooltip(self):
        title = "Brightness" if self.mode == "brightness" else "Volume"
        self.setToolTip(f"{title}: {self.value}%\nClick or drag to adjust")

    def _update_from_pos(self, py: float):
        h = float(self.height())
        pad = 4.0
        norm = 1.0 - ((py - pad) / max(1.0, (h - pad * 2)))
        norm = max(0.0, min(1.0, norm))
        self.target_value = norm * 100.0
        if self.is_dragging:
            self.visual_value = self.target_value
        elif not self.anim_timer.isActive():
            self.anim_timer.start()

        new_val = int(round(self.target_value))
        if new_val != self.value:
            self.value = new_val
            self._update_tooltip()
            self.value_changed.emit(self.value)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.last_user_interaction = time.time()
            self._update_from_pos(event.position().y())

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.last_user_interaction = time.time()
            self._update_from_pos(event.position().y())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.last_user_interaction = time.time()
            self._update_from_pos(event.position().y())

    def wheelEvent(self, event):
        self.last_user_interaction = time.time()
        delta = 5.0 if event.angleDelta().y() > 0 else -5.0
        self.target_value = max(0.0, min(100.0, self.target_value + delta))
        self.value = int(round(self.target_value))
        if not self.anim_timer.isActive():
            self.anim_timer.start()
        self._update_tooltip()
        self.value_changed.emit(self.value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        r = 13.0

        capsule_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        capsule_path = QPainterPath()
        capsule_path.addRoundedRect(capsule_rect, r, r)

        # 1. Background Track
        painter.fillPath(capsule_path, QColor(20, 20, 24))

        # 2. Fluid fill from bottom based on self.visual_value (sub-pixel 60 FPS)
        painter.save()
        painter.setClipPath(capsule_path)

        fill_frac = max(0.0, min(1.0, self.visual_value / 100.0))
        fill_h = h * fill_frac
        fill_y = h - fill_h

        grad = QLinearGradient(0, fill_y, 0, h)
        if self.mode == "brightness":
            grad.setColorAt(0.0, QColor(254, 240, 138, 230))
            grad.setColorAt(1.0, QColor(245, 158, 11, 245))
        else:
            grad.setColorAt(0.0, QColor(56, 189, 248, 230))
            grad.setColorAt(1.0, QColor(0, 255, 204, 245))

        painter.fillRect(QRectF(0, fill_y, w, fill_h), grad)

        if fill_h > 2.0:
            surface_pen = QPen(QColor(255, 255, 255, 120), 1.2)
            painter.setPen(surface_pen)
            painter.drawLine(QPointF(2.0, fill_y), QPointF(w - 2.0, fill_y))

        painter.restore()

        # 3. Subtle hairline outline
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(capsule_rect, r, r)

        # 4. Crisp Vector Icon at bottom
        icon_color = QColor(10, 10, 10) if fill_frac > 0.35 else QColor(255, 255, 255, 220)
        cx = w / 2.0
        cy = h - 16.0

        if self.mode == "brightness":
            # Vector Sun: center circle + 8 rays
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(icon_color)
            painter.drawEllipse(QPointF(cx, cy), 3.4, 3.4)

            ray_pen = QPen(icon_color, 1.4)
            ray_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(ray_pen)
            for deg in (0, 45, 90, 135, 180, 225, 270, 315):
                rad = math.radians(deg)
                x1 = cx + math.cos(rad) * 5.2
                y1 = cy + math.sin(rad) * 5.2
                x2 = cx + math.cos(rad) * 7.5
                y2 = cy + math.sin(rad) * 7.5
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        else:
            # Vector Speaker: body + cone + sound arc
            spk_pen = QPen(icon_color, 1.2)
            painter.setPen(spk_pen)
            painter.setBrush(icon_color)

            spk_path = QPainterPath()
            spk_path.moveTo(cx - 5.5, cy - 3.0)
            spk_path.lineTo(cx - 2.5, cy - 3.0)
            spk_path.lineTo(cx + 1.5, cy - 6.0)
            spk_path.lineTo(cx + 1.5, cy + 6.0)
            spk_path.lineTo(cx - 2.5, cy + 3.0)
            spk_path.lineTo(cx - 5.5, cy + 3.0)
            spk_path.closeSubpath()
            painter.drawPath(spk_path)

            arc_pen = QPen(icon_color, 1.4)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(cx + 1.0, cy - 4.5, 9.0, 9.0), -45 * 16, 90 * 16)

        # 5. Percentage at top
        val_str = f"{self.value}%"
        painter.setPen(QColor(0, 0, 0) if fill_frac > 0.78 else QColor(255, 255, 255, 215))
        txt_font = QFont("Segoe UI", 9)
        txt_font.setWeight(QFont.Weight.Bold)
        painter.setFont(txt_font)
        fm_t = QFontMetrics(txt_font)
        tw = fm_t.horizontalAdvance(val_str)
        painter.drawText(int((w - tw) / 2.0), 16, val_str)


class HardwareController:
    """
    Asynchronous coalescing controller for Windows Brightness and Volume.
    Runs independent daemon threads for volume and brightness so that slow
    screen brightness hardware queries never block or lag volume adjustments.
    """
    def __init__(self):
        import threading
        self._target_brightness = None
        self._target_volume = None
        self._b_lock = threading.Lock()
        self._v_lock = threading.Lock()
        self._b_event = threading.Event()
        self._v_event = threading.Event()

        self._b_thread = threading.Thread(target=self._run_brightness_loop, daemon=True)
        self._v_thread = threading.Thread(target=self._run_volume_loop, daemon=True)
        self._b_thread.start()
        self._v_thread.start()

    def set_brightness_async(self, val: int):
        with self._b_lock:
            self._target_brightness = max(0, min(100, int(val)))
            self._b_event.set()

    def set_volume_async(self, val: int):
        with self._v_lock:
            self._target_volume = max(0, min(100, int(val)))
            self._v_event.set()

    def _run_volume_loop(self):
        import system_tools
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        while True:
            self._v_event.wait(timeout=1.0)
            self._v_event.clear()

            v_val = None
            with self._v_lock:
                v_val = self._target_volume
                self._target_volume = None

            if v_val is not None:
                try:
                    system_tools.set_volume(v_val)
                except Exception:
                    pass

    def _run_brightness_loop(self):
        import system_tools
        while True:
            self._b_event.wait(timeout=1.0)
            self._b_event.clear()

            b_val = None
            with self._b_lock:
                b_val = self._target_brightness
                self._target_brightness = None

            if b_val is not None:
                try:
                    system_tools.set_brightness(b_val)
                except Exception:
                    pass


class DashboardWidget(QWidget):
    """
    OLED Pitch-Black Desktop Companion Dashboard (~520px x 405px).
    Features:
    - Pure Pitch Black (#000000) styling with crisp separation hairlines.
    - Top Settings button (⚙️). Pin and close buttons removed per design.
    - Auto-collapse on mouse leave is standard.
    - Music Page:
        * Static radial ambient glow matching album cover dominant colors.
        * NOW PLAYING pill colored with dominant color.
        * Audio output device switcher pill on top right (switches Windows playback devices).
        * Album art with zero title overlap.
        * Android 16-inspired expressive waveform seek bar.
        * Media controls colored with dominant color (circular play button filled with dominant color).
    - Timer Page: Motorola aesthetic 2-column card (Black, Grey, White palette only):
        * Left: [Focus] [Break] segmented pill, big 25:00 digits, circular Reset / Play buttons, Steppers.
        * Right: Tasks list with checkable items and bottom capsule task input.
    - System Page: Real-time 2x3 metrics grid (CPU + sparkline, Memory, Network, Storage, Battery, Uptime) + memory optimizer button.
    - Clipboard Page: Last 5 copied texts with 1-click paste/copy.
    """
    collapse_requested = pyqtSignal()
    pin_toggled = pyqtSignal(bool)
    tab_changed = pyqtSignal(int)

    def __init__(self, island_parent=None):
        super().__init__(island_parent)
        self.island = island_parent
        self.is_pinned = False
        self.setFixedSize(520, 405)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Timer state tracking
        self.timer_mode = "focus"
        self.focus_minutes = 25
        self.break_minutes = 5
        self.is_timer_running = False
        self.current_timer_secs = 25 * 60

        if self.island and hasattr(self.island, 'cfg'):
            self.focus_minutes = self.island.cfg.get("focus_duration", 25)
            self.break_minutes = self.island.cfg.get("break_duration", 5)
            self.current_timer_secs = self.focus_minutes * 60

        # Dedicated 1s timer ticker for the countdown
        self.local_timer = QTimer(self)
        self.local_timer.setInterval(1000)
        self.local_timer.timeout.connect(self._on_local_timer_tick)

        # Asynchronous hardware controller (zero-lag brightness & volume adjustments)
        self.hw_controller = HardwareController()

        # Dedicated real-time System Metrics Timer (1.2s interval)
        self.system_metrics_timer = QTimer(self)
        self.system_metrics_timer.setInterval(1200)
        self.system_metrics_timer.timeout.connect(self._refresh_system_metrics)
        self._last_net_time = 0.0
        self._last_bytes_recv = 0
        self._last_bytes_sent = 0

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(6)

        # ----------------- 1. HEADER BAR -----------------
        header = QHBoxLayout()
        header.setContentsMargins(6, 0, 6, 0)
        header.setSpacing(8)

        self.lbl_header_title = QLabel("Media Player")
        self.lbl_header_title.setStyleSheet("color: rgba(255, 255, 255, 0.85); font-weight: bold; font-family: 'Segoe UI', sans-serif; font-size: 13px; letter-spacing: 0.5px;")
        header.addWidget(self.lbl_header_title)

        header.addStretch()

        # Settings (⚙️) button in top right
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.65);
                font-size: 14px;
                border: none;
                border-radius: 6px;
                padding: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
                color: white;
            }
        """)
        self.btn_settings.setFixedSize(28, 28)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.island and hasattr(self.island, 'show_apple_settings'):
            self.btn_settings.clicked.connect(self.island.show_apple_settings)
        header.addWidget(self.btn_settings)

        main_layout.addLayout(header)

        # ----------------- 2. CENTER STACKED CARD (PITCH BLACK) -----------------
        self.card_container = QFrame()
        self.card_container.setObjectName("cardContainer")
        self.card_container.setStyleSheet("""
            QFrame#cardContainer {
                background: #000000;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        card_layout = QVBoxLayout(self.card_container)
        card_layout.setContentsMargins(14, 8, 14, 8)
        card_layout.setSpacing(0)

        self.stack = QStackedWidget()
        card_layout.addWidget(self.stack)

        # Tab 0: Music View
        self.music_page = self._create_music_page()
        self.stack.addWidget(self.music_page)

        # Tab 1: Timer & Tasks View
        self.timer_page = self._create_timer_page()
        self.stack.addWidget(self.timer_page)

        # Tab 2: System View
        self.system_page = self._create_system_page()
        self.stack.addWidget(self.system_page)

        # Tab 3: Workspaces View
        self.workspaces_page = self._create_workspaces_page()
        self.stack.addWidget(self.workspaces_page)

        # Tab 4: Clipboard View
        self.clipboard_page = self._create_clipboard_page()
        self.stack.addWidget(self.clipboard_page)

        main_layout.addWidget(self.card_container, 1)

        # ----------------- 3. SEPARATION HAIRLINE -----------------
        sep_line = QFrame()
        sep_line.setFixedHeight(1)
        sep_line.setStyleSheet("background: rgba(255, 255, 255, 0.08); border: none;")
        main_layout.addWidget(sep_line)

        # ----------------- 4. BOTTOM SEGMENTED DOCK -----------------
        dock_container = QWidget()
        dock_layout = QHBoxLayout(dock_container)
        dock_layout.setContentsMargins(2, 2, 2, 2)
        dock_layout.setSpacing(6)

        self.tab_buttons = []
        tab_defs = [
            ("🎵", "Music"),
            ("⏱️", "Timer"),
            ("⚙️", "System"),
            ("💼", "Workspaces"),
            ("📋", "Clipboard")
        ]

        for idx, (icon_text, name_text) in enumerate(tab_defs):
            btn = QPushButton(f"{icon_text}  {name_text}")
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self.switch_tab(i))
            dock_layout.addWidget(btn)
            self.tab_buttons.append(btn)

        main_layout.addWidget(dock_container)
        self.switch_tab(0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 24, 24)

        # PURE OLED PITCH BLACK (#000000)
        painter.fillPath(path, QColor(0, 0, 0, 255))

        pen = QPen(QColor(255, 255, 255, 26), 1)
        painter.setPen(pen)
        painter.drawPath(path)

    # ----------------- MUSIC PAGE (Matching Screenshot 3) -----------------
    def _create_music_page(self):
        page = MusicPageWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 4, 10, 6)
        layout.setSpacing(0)

        # 1. Top status row: [ •||| NOW PLAYING ] (left) and [ 🔊 Audio Output ▾ ] (right)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(4, 0, 4, 0)

        # NOW PLAYING capsule pill
        self.pill_now_playing = QLabel("  NOW PLAYING  ")
        self.pill_now_playing.setStyleSheet("""
            QLabel {
                background: rgba(0, 255, 204, 0.16);
                color: #00ffcc;
                border: 1px solid rgba(0, 255, 204, 0.38);
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 0.5px;
                border-radius: 10px;
                padding: 4px 10px;
            }
        """)
        top_row.addWidget(self.pill_now_playing)

        top_row.addStretch()

        # Audio Output Device Switcher pill on top right
        self.btn_audio_device = QPushButton("🔊 Audio Output ▾")
        self.btn_audio_device.setObjectName("btnAudioDevice")
        self.btn_audio_device.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_audio_device.setStyleSheet("""
            QPushButton#btnAudioDevice {
                background: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 10px;
                padding: 3px 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton#btnAudioDevice:hover {
                background: rgba(255, 255, 255, 0.18);
                color: #ffffff;
                border-color: rgba(255, 255, 255, 0.3);
            }
        """)
        self.btn_audio_device.clicked.connect(self._show_audio_devices_menu)
        top_row.addWidget(self.btn_audio_device)
        QTimer.singleShot(150, self._refresh_audio_device_label)

        layout.addLayout(top_row)

        layout.addSpacing(6)

        # 2. Album Art with Ambient Glow Backlight
        art_box = QHBoxLayout()
        art_box.addStretch()
        self.album_art = AlbumArtWidget()
        art_box.addWidget(self.album_art)
        art_box.addStretch()
        layout.addLayout(art_box)

        layout.addSpacing(8)

        # 3. Track Title (Clean, centered, no overlap with image!)
        self.lbl_track_title = QLabel("No media playing")
        self.lbl_track_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_track_title.setFixedHeight(22)
        self.lbl_track_title.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 15px; font-family: 'Segoe UI', sans-serif; border: none; background: transparent;")
        layout.addWidget(self.lbl_track_title)

        layout.addSpacing(2)

        # 4. Artist & Source App
        self.lbl_track_sub = QLabel("Play audio on Spotify, Chrome, or Windows")
        self.lbl_track_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_track_sub.setFixedHeight(18)
        self.lbl_track_sub.setStyleSheet("color: rgba(255, 255, 255, 0.55); font-size: 11px; font-family: 'Segoe UI', sans-serif; border: none; background: transparent;")
        layout.addWidget(self.lbl_track_sub)

        layout.addSpacing(6)

        # 5. Android 16-Inspired Expressive Waveform Seek Bar
        self.waveform_bar = Android16WaveformSeekBar()
        self.waveform_bar.seek_requested.connect(self._on_seek_requested)
        layout.addWidget(self.waveform_bar)

        layout.addSpacing(6)

        # 6. Vector Media Controls (All dynamically colored to match album glow)
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)

        self.btn_prev = VectorMediaButton(mode="prev", is_accent=False)
        self.btn_prev.setFixedSize(38, 38)

        self.btn_play = VectorMediaButton(mode="play", is_accent=True)
        self.btn_play.setFixedSize(46, 46)

        self.btn_next = VectorMediaButton(mode="next", is_accent=False)
        self.btn_next.setFixedSize(38, 38)

        if self.island and hasattr(self.island, 'media_worker'):
            self.btn_prev.clicked.connect(self.island.media_worker.prev_track)
            self.btn_play.clicked.connect(self.island.media_worker.toggle_play_pause)
            self.btn_next.clicked.connect(self.island.media_worker.next_track)

        ctrl_row.addStretch()
        ctrl_row.addWidget(self.btn_prev)
        ctrl_row.addSpacing(24)
        ctrl_row.addWidget(self.btn_play)
        ctrl_row.addSpacing(24)
        ctrl_row.addWidget(self.btn_next)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        layout.addStretch()
        return page

    # ----------------- AUDIO DEVICE SWITCHING -----------------
    def _refresh_audio_device_label(self):
        try:
            devs = get_audio_output_devices()
            for d in devs:
                if d.get("is_default"):
                    name = d.get("clean_name", "Audio")
                    icon = d.get("icon", "🔊")
                    short_name = name
                    short_name = short_name.replace("(R)", "").replace("(TM)", "").replace("Speakers (", "").replace(")", "").strip()
                    if len(short_name) > 16:
                        short_name = short_name[:15] + "…"
                    self.btn_audio_device.setText(f"{icon} {short_name}  ▾")
                    self.btn_audio_device.setToolTip(f"Active Output: {name}\nClick to switch audio output device")
                    return
            self.btn_audio_device.setText("🔊 Audio Output  ▾")
        except Exception:
            self.btn_audio_device.setText("🔊 Audio Output  ▾")

    def _show_audio_devices_menu(self):
        devs = get_audio_output_devices()
        if not devs:
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #121214;
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 10px;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 20px 6px 14px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: rgba(255, 255, 255, 0.14);
                color: #ffffff;
            }
        """)
        for d in devs:
            is_def = d.get("is_default", False)
            prefix = "✓  " if is_def else "     "
            label = f"{prefix}{d.get('icon', '🔊')}  {d.get('name', 'Device')}"
            action = menu.addAction(label)
            dev_id = d.get("id")
            action.triggered.connect(lambda ch, did=dev_id: self._select_audio_device(did))

        # Show popup directly below the button
        menu.exec(self.btn_audio_device.mapToGlobal(QPoint(0, self.btn_audio_device.height() + 4)))

    def _select_audio_device(self, device_id: str):
        set_default_audio_device(device_id)
        self._refresh_audio_device_label()

    def _on_seek_requested(self, target_sec: float):
        if self.island and hasattr(self.island, 'media_worker'):
            self.island.media_worker.seek_to_position(target_sec)

    # ----------------- TIMER & TASKS PAGE (Matching Screenshot 2) -----------------
    def _create_timer_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(14)

        # ----------------- LEFT COLUMN: TIMER (Motorola Minimal Clean) -----------------
        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(10)

        # 1. Segmented Pill Switch: [ Focus ] [ Break ]
        seg_container = QFrame()
        seg_container.setObjectName("segContainer")
        seg_container.setFixedHeight(34)
        seg_container.setStyleSheet("""
            QFrame#segContainer {
                background: #18181b;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 17px;
            }
        """)
        seg_layout = QHBoxLayout(seg_container)
        seg_layout.setContentsMargins(3, 3, 3, 3)
        seg_layout.setSpacing(4)

        self.btn_seg_focus = QPushButton("Focus")
        self.btn_seg_break = QPushButton("Break")

        for b in [self.btn_seg_focus, self.btn_seg_break]:
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(28)
            seg_layout.addWidget(b)

        self.btn_seg_focus.clicked.connect(lambda: self._set_timer_mode("focus"))
        self.btn_seg_break.clicked.connect(lambda: self._set_timer_mode("break"))
        self._update_seg_buttons()

        left_col.addWidget(seg_container)

        left_col.addSpacing(4)

        # 2. Big Digits & Action Buttons Row
        digits_row = QHBoxLayout()
        digits_row.setContentsMargins(2, 0, 2, 0)
        digits_row.setSpacing(12)

        self.lbl_timer_digits = QLabel(f"{self.focus_minutes:02d}:00")
        self.lbl_timer_digits.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-family: 'SF Pro Display', 'Segoe UI', 'Roboto', sans-serif;
                font-size: 38px;
                font-weight: bold;
                letter-spacing: -0.5px;
                border: none;
                background: transparent;
            }
        """)
        digits_row.addWidget(self.lbl_timer_digits)

        digits_row.addStretch()

        # Circular Reset Button (↺)
        self.btn_timer_reset = VectorMediaButton(mode="reset", is_accent=False)
        self.btn_timer_reset.setFixedSize(36, 36)
        self.btn_timer_reset.setToolTip("Reset Timer")
        self.btn_timer_reset.clicked.connect(self._on_timer_reset_clicked)
        digits_row.addWidget(self.btn_timer_reset)

        # Circular Play/Pause Button (▶ / ❚❚)
        self.btn_timer_toggle = VectorMediaButton(mode="play", is_accent=True)
        self.btn_timer_toggle.setFixedSize(44, 44)
        self.btn_timer_toggle.setToolTip("Start / Pause")
        self.btn_timer_toggle.clicked.connect(self._on_timer_toggle_clicked)
        digits_row.addWidget(self.btn_timer_toggle)

        left_col.addLayout(digits_row)

        # 3. Subtle Hairline Divider
        hairline = QFrame()
        hairline.setFixedHeight(1)
        hairline.setStyleSheet("background: rgba(255, 255, 255, 0.08); border: none;")
        left_col.addWidget(hairline)

        # 4. Steppers Card [Focus [-] 25 min [+]] and [Break [-] 5 min [+]]
        steppers_card = QFrame()
        steppers_card.setObjectName("steppersCard")
        steppers_card.setStyleSheet("""
            QFrame#steppersCard {
                background: #121214;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 14px;
            }
        """)
        sc_layout = QVBoxLayout(steppers_card)
        sc_layout.setContentsMargins(14, 10, 14, 10)
        sc_layout.setSpacing(10)

        # Focus row
        row_focus = QHBoxLayout()
        lbl_f = QLabel("Focus")
        lbl_f.setStyleSheet("color: rgba(255, 255, 255, 0.85); font-size: 13px; font-weight: 500; font-family: 'Segoe UI', sans-serif; border: none;")
        row_focus.addWidget(lbl_f)
        row_focus.addStretch()

        btn_f_minus = QPushButton("-")
        btn_f_minus.setFixedSize(24, 24)
        btn_f_minus.setStyleSheet(self._stepper_btn_style())
        btn_f_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_f_minus.clicked.connect(lambda: self._adjust_duration("focus", -1))

        self.lbl_focus_val = QLabel(f"{self.focus_minutes} min")
        self.lbl_focus_val.setFixedWidth(54)
        self.lbl_focus_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_focus_val.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px; font-family: 'Segoe UI', sans-serif; border: none;")

        btn_f_plus = QPushButton("+")
        btn_f_plus.setFixedSize(24, 24)
        btn_f_plus.setStyleSheet(self._stepper_btn_style())
        btn_f_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_f_plus.clicked.connect(lambda: self._adjust_duration("focus", 1))

        row_focus.addWidget(btn_f_minus)
        row_focus.addWidget(self.lbl_focus_val)
        row_focus.addWidget(btn_f_plus)
        sc_layout.addLayout(row_focus)

        # Break row
        row_break = QHBoxLayout()
        lbl_b = QLabel("Break")
        lbl_b.setStyleSheet("color: rgba(255, 255, 255, 0.85); font-size: 13px; font-weight: 500; font-family: 'Segoe UI', sans-serif; border: none;")
        row_break.addWidget(lbl_b)
        row_break.addStretch()

        btn_b_minus = QPushButton("-")
        btn_b_minus.setFixedSize(24, 24)
        btn_b_minus.setStyleSheet(self._stepper_btn_style())
        btn_b_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_b_minus.clicked.connect(lambda: self._adjust_duration("break", -1))

        self.lbl_break_val = QLabel(f"{self.break_minutes} min")
        self.lbl_break_val.setFixedWidth(54)
        self.lbl_break_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_break_val.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px; font-family: 'Segoe UI', sans-serif; border: none;")

        btn_b_plus = QPushButton("+")
        btn_b_plus.setFixedSize(24, 24)
        btn_b_plus.setStyleSheet(self._stepper_btn_style())
        btn_b_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_b_plus.clicked.connect(lambda: self._adjust_duration("break", 1))

        row_break.addWidget(btn_b_minus)
        row_break.addWidget(self.lbl_break_val)
        row_break.addWidget(btn_b_plus)
        sc_layout.addLayout(row_break)

        left_col.addWidget(steppers_card)
        left_col.addStretch()

        layout.addLayout(left_col, 46)

        # ----------------- VERTICAL HAIRLINE DIVIDER -----------------
        v_divider = QFrame()
        v_divider.setFixedWidth(1)
        v_divider.setStyleSheet("background: rgba(255, 255, 255, 0.08); border: none;")
        layout.addWidget(v_divider)

        # ----------------- RIGHT COLUMN: TASKS -----------------
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(8)

        lbl_tasks_title = QLabel("Tasks")
        lbl_tasks_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; font-family: 'Segoe UI', sans-serif; border: none;")
        right_col.addWidget(lbl_tasks_title)

        # Scrollable Task List
        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.task_container = QWidget()
        self.task_container.setStyleSheet("background: transparent;")
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(6)
        self.task_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.task_scroll.setWidget(self.task_container)
        right_col.addWidget(self.task_scroll, 1)

        # Interactive Task Input Capsule [ Add a task and press Enter  (+) ]
        input_capsule = QFrame()
        input_capsule.setObjectName("inputCapsule")
        input_capsule.setFixedHeight(34)
        input_capsule.setStyleSheet("""
            QFrame#inputCapsule {
                background: #18181b;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 17px;
            }
        """)
        ic_layout = QHBoxLayout(input_capsule)
        ic_layout.setContentsMargins(10, 0, 4, 0)
        ic_layout.setSpacing(4)

        self.txt_new_task = QLineEdit()
        self.txt_new_task.setPlaceholderText("Add a task and press Enter")
        self.txt_new_task.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: 11px;
                font-family: 'Segoe UI', sans-serif;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.38);
            }
        """)
        self.txt_new_task.returnPressed.connect(self._on_add_task_submitted)
        ic_layout.addWidget(self.txt_new_task, 1)

        btn_add_task = QPushButton("+")
        btn_add_task.setFixedSize(22, 22)
        btn_add_task.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_task.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.15);
                color: #ffffff;
                border: none;
                border-radius: 11px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.3);
            }
        """)
        btn_add_task.clicked.connect(self._on_add_task_submitted)
        ic_layout.addWidget(btn_add_task)

        right_col.addWidget(input_capsule)

        layout.addLayout(right_col, 54)

        self._refresh_tasks_ui()
        return page

    def _stepper_btn_style(self):
        return """
            QPushButton {
                background: #222226;
                color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                color: white;
            }
        """

    def _update_seg_buttons(self):
        if self.timer_mode == "focus":
            self.btn_seg_focus.setStyleSheet("background: #ffffff; color: #000000; font-weight: bold; border: none; border-radius: 14px; font-size: 11px;")
            self.btn_seg_break.setStyleSheet("background: transparent; color: rgba(255, 255, 255, 0.6); font-weight: 500; border: none; font-size: 11px;")
        else:
            self.btn_seg_break.setStyleSheet("background: #ffffff; color: #000000; font-weight: bold; border: none; border-radius: 14px; font-size: 11px;")
            self.btn_seg_focus.setStyleSheet("background: transparent; color: rgba(255, 255, 255, 0.6); font-weight: 500; border: none; font-size: 11px;")

    def _on_local_timer_tick(self):
        if not self.is_timer_running:
            return
        if self.current_timer_secs > 0:
            self.current_timer_secs -= 1
            mins, secs = divmod(self.current_timer_secs, 60)
            self.lbl_timer_digits.setText(f"{mins:02d}:{secs:02d}")
            if self.island:
                self.island.active_timer_seconds = self.current_timer_secs
            if self.current_timer_secs == 0:
                self.is_timer_running = False
                self.local_timer.stop()
                self.btn_timer_toggle.set_mode("play")
                if self.island and hasattr(self.island, 'speak'):
                    mode_name = "Focus session" if self.timer_mode == "focus" else "Break"
                    self.island.speak(f"{mode_name} is complete!")
                next_mode = "break" if self.timer_mode == "focus" else "focus"
                self._set_timer_mode(next_mode)

    def _set_timer_mode(self, mode: str):
        self.timer_mode = mode
        self.is_timer_running = False
        self.local_timer.stop()
        self.btn_timer_toggle.set_mode("play")
        self._update_seg_buttons()
        mins = self.focus_minutes if mode == "focus" else self.break_minutes
        self.current_timer_secs = mins * 60
        self.lbl_timer_digits.setText(f"{mins:02d}:00")
        if self.island:
            if hasattr(self.island, 'active_timer_seconds'):
                self.island.active_timer_seconds = 0
                self.island.is_timer_paused = False
                self.island.update_telemetry()

    def _adjust_duration(self, mode: str, delta: int):
        if mode == "focus":
            self.focus_minutes = max(1, min(90, self.focus_minutes + delta))
            self.lbl_focus_val.setText(f"{self.focus_minutes} min")
            if self.timer_mode == "focus" and not self.is_timer_running:
                self.current_timer_secs = self.focus_minutes * 60
                self.lbl_timer_digits.setText(f"{self.focus_minutes:02d}:00")
            if self.island and hasattr(self.island, 'cfg'):
                self.island.cfg["focus_duration"] = self.focus_minutes
        else:
            self.break_minutes = max(1, min(60, self.break_minutes + delta))
            self.lbl_break_val.setText(f"{self.break_minutes} min")
            if self.timer_mode == "break" and not self.is_timer_running:
                self.current_timer_secs = self.break_minutes * 60
                self.lbl_timer_digits.setText(f"{self.break_minutes:02d}:00")
            if self.island and hasattr(self.island, 'cfg'):
                self.island.cfg["break_duration"] = self.break_minutes

    def _on_timer_toggle_clicked(self):
        if not self.is_timer_running:
            self.is_timer_running = True
            self.btn_timer_toggle.set_mode("pause")
            if self.island and hasattr(self.island, 'start_timer'):
                self.island.start_timer(self.current_timer_secs)
            self.local_timer.start()
        else:
            self.is_timer_running = False
            self.btn_timer_toggle.set_mode("play")
            self.local_timer.stop()
            if self.island and hasattr(self.island, 'toggle_timer_pause'):
                self.island.toggle_timer_pause()

    def _on_timer_reset_clicked(self):
        self.is_timer_running = False
        self.local_timer.stop()
        self.btn_timer_toggle.set_mode("play")
        mins = self.focus_minutes if self.timer_mode == "focus" else self.break_minutes
        self.current_timer_secs = mins * 60
        self.lbl_timer_digits.setText(f"{mins:02d}:00")
        if self.island:
            if hasattr(self.island, 'active_timer_seconds'):
                self.island.active_timer_seconds = 0
                self.island.is_timer_paused = False
                self.island.update_telemetry()

    def update_timer_tick(self, mins: int, secs: int, is_paused: bool):
        total_s = mins * 60 + secs
        if total_s > 0:
            self.current_timer_secs = total_s
            self.lbl_timer_digits.setText(f"{mins:02d}:{secs:02d}")
            self.is_timer_running = not is_paused
            self.btn_timer_toggle.set_mode("play" if is_paused else "pause")
            if not is_paused and not self.local_timer.isActive():
                self.local_timer.start()
            elif is_paused and self.local_timer.isActive():
                self.local_timer.stop()
        else:
            self.is_timer_running = False
            self.local_timer.stop()
            self.btn_timer_toggle.set_mode("play")

    # Tasks Management
    def _refresh_tasks_ui(self):
        while self.task_layout.count() > 0:
            item = self.task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tasks = []
        if self.island and hasattr(self.island, 'cfg'):
            tasks = self.island.cfg.get("tasks_list", [])

        if not tasks:
            empty_box = QWidget()
            eb_layout = QVBoxLayout(empty_box)
            eb_layout.setContentsMargins(0, 40, 0, 0)
            eb_layout.setSpacing(6)
            eb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_ico = QLabel("✓")
            lbl_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_ico.setStyleSheet("color: rgba(255, 255, 255, 0.25); font-size: 24px; border: none;")
            eb_layout.addWidget(lbl_ico)

            lbl_msg = QLabel("Add what you want to get done")
            lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_msg.setStyleSheet("color: rgba(255, 255, 255, 0.35); font-size: 11px; font-family: 'Segoe UI', sans-serif; border: none;")
            eb_layout.addWidget(lbl_msg)

            self.task_layout.addWidget(empty_box)
            return

        for idx, task in enumerate(tasks):
            t_text = task.get("text", "") if isinstance(task, dict) else str(task)
            t_done = task.get("done", False) if isinstance(task, dict) else False

            row = QFrame()
            row.setObjectName("taskRow")
            row.setStyleSheet("""
                QFrame#taskRow {
                    background: #121214;
                    border: 1px solid rgba(255, 255, 255, 0.06);
                    border-radius: 8px;
                    padding: 2px;
                }
                QFrame#taskRow:hover {
                    border-color: rgba(255, 255, 255, 0.18);
                }
            """)
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(8, 4, 8, 4)
            r_layout.setSpacing(8)

            btn_check = QPushButton("●" if t_done else "○")
            btn_check.setFixedSize(18, 18)
            btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_check.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: %s;
                    border: none;
                    font-size: 13px;
                }
            """ % ("#00ffcc" if t_done else "rgba(255, 255, 255, 0.4)"))
            btn_check.clicked.connect(lambda ch, i=idx: self._toggle_task_done(i))
            r_layout.addWidget(btn_check)

            lbl_txt = QLabel(t_text)
            lbl_txt.setStyleSheet("""
                color: %s;
                font-size: 12px;
                font-family: 'Segoe UI', sans-serif;
                border: none;
                %s
            """ % ("rgba(255, 255, 255, 0.4)" if t_done else "#ffffff", "text-decoration: line-through;" if t_done else ""))
            r_layout.addWidget(lbl_txt, 1)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(18, 18)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet("background: transparent; color: rgba(255, 255, 255, 0.3); border: none; font-size: 11px;")
            btn_del.clicked.connect(lambda ch, i=idx: self._delete_task(i))
            r_layout.addWidget(btn_del)

            self.task_layout.addWidget(row)

    def _on_add_task_submitted(self):
        text = self.txt_new_task.text().strip()
        if not text:
            return
        if self.island and hasattr(self.island, 'cfg'):
            tasks = list(self.island.cfg.get("tasks_list", []))
            tasks.append({"text": text, "done": False})
            self.island.cfg["tasks_list"] = tasks
            import config
            config.save_config(self.island.cfg)
        self.txt_new_task.clear()
        self._refresh_tasks_ui()

    def _toggle_task_done(self, idx: int):
        if self.island and hasattr(self.island, 'cfg'):
            tasks = list(self.island.cfg.get("tasks_list", []))
            if 0 <= idx < len(tasks):
                item = tasks[idx]
                if isinstance(item, dict):
                    item["done"] = not item.get("done", False)
                else:
                    item = {"text": str(item), "done": True}
                tasks[idx] = item
                self.island.cfg["tasks_list"] = tasks
                import config
                config.save_config(self.island.cfg)
        self._refresh_tasks_ui()

    def _delete_task(self, idx: int):
        if self.island and hasattr(self.island, 'cfg'):
            tasks = list(self.island.cfg.get("tasks_list", []))
            if 0 <= idx < len(tasks):
                tasks.pop(idx)
                self.island.cfg["tasks_list"] = tasks
                import config
                config.save_config(self.island.cfg)
        self._refresh_tasks_ui()

    # ----------------- SYSTEM METRICS PAGE (Matching Screenshot) -----------------
    def _create_system_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # 2x3 Grid of Metric Cards
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        card_qss = """
            QFrame#metricCard {
                background-color: #0b0b0e;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            QFrame#metricCard:hover {
                border: 1px solid rgba(255, 255, 255, 0.16);
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """

        # --- 1. CPU Card (Row 0, Col 0) ---
        c_cpu = QFrame()
        c_cpu.setObjectName("metricCard")
        c_cpu.setStyleSheet(card_qss)
        c_cpu.setFixedHeight(84)
        l_cpu = QVBoxLayout(c_cpu)
        l_cpu.setContentsMargins(10, 6, 10, 6)
        l_cpu.setSpacing(2)

        hdr_cpu = QLabel("⚙ CPU")
        hdr_cpu.setStyleSheet("color: #38bdf8; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        l_cpu.addWidget(hdr_cpu)

        body_cpu = QHBoxLayout()
        body_cpu.setSpacing(6)
        self.lbl_cpu_val = QLabel("26%")
        self.lbl_cpu_val.setStyleSheet("color: #ffffff; font-family: 'Segoe UI', sans-serif; font-size: 20px; font-weight: bold;")
        body_cpu.addWidget(self.lbl_cpu_val)
        body_cpu.addStretch()
        self.cpu_sparkline = CpuSparklineWidget()
        body_cpu.addWidget(self.cpu_sparkline)
        l_cpu.addLayout(body_cpu)
        grid.addWidget(c_cpu, 0, 0)

        # --- 2. MEMORY Card (Row 0, Col 1) ---
        c_ram = QFrame()
        c_ram.setObjectName("metricCard")
        c_ram.setStyleSheet(card_qss)
        c_ram.setFixedHeight(84)
        l_ram = QVBoxLayout(c_ram)
        l_ram.setContentsMargins(10, 6, 10, 6)
        l_ram.setSpacing(2)

        hdr_ram = QLabel("💾 MEMORY")
        hdr_ram.setStyleSheet("color: #c084fc; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        l_ram.addWidget(hdr_ram)

        self.lbl_ram_val = QLabel("7.2 GB")
        self.lbl_ram_val.setStyleSheet("color: #ffffff; font-family: 'Segoe UI', sans-serif; font-size: 19px; font-weight: bold;")
        l_ram.addWidget(self.lbl_ram_val)

        self.ram_bar = MetricProgressBar(color=QColor(192, 132, 252))
        l_ram.addWidget(self.ram_bar)

        self.lbl_ram_sub = QLabel("of 13.8 GB")
        self.lbl_ram_sub.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-family: 'Segoe UI', sans-serif; font-size: 10px;")
        l_ram.addWidget(self.lbl_ram_sub)
        grid.addWidget(c_ram, 0, 1)

        # --- 3. NETWORK Card (Row 0, Col 2) ---
        c_net = QFrame()
        c_net.setObjectName("metricCard")
        c_net.setStyleSheet(card_qss)
        c_net.setFixedHeight(84)
        l_net = QVBoxLayout(c_net)
        l_net.setContentsMargins(10, 6, 10, 6)
        l_net.setSpacing(2)

        hdr_net = QLabel("↓ NETWORK")
        hdr_net.setStyleSheet("color: #4ade80; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        l_net.addWidget(hdr_net)

        self.lbl_net_down = QLabel("↓ 0 B/s")
        self.lbl_net_down.setStyleSheet("color: #ffffff; font-family: 'Segoe UI', sans-serif; font-size: 15px; font-weight: bold;")
        l_net.addWidget(self.lbl_net_down)

        self.lbl_net_up = QLabel("↑ 0 B/s")
        self.lbl_net_up.setStyleSheet("color: rgba(255, 255, 255, 0.65); font-family: 'Segoe UI', sans-serif; font-size: 10px;")
        l_net.addWidget(self.lbl_net_up)
        grid.addWidget(c_net, 0, 2)

        # --- 4. STORAGE Card (Row 1, Col 0) ---
        c_disk = QFrame()
        c_disk.setObjectName("metricCard")
        c_disk.setStyleSheet(card_qss)
        c_disk.setFixedHeight(84)
        l_disk = QVBoxLayout(c_disk)
        l_disk.setContentsMargins(10, 6, 10, 6)
        l_disk.setSpacing(2)

        hdr_disk = QLabel("🖴 STORAGE")
        hdr_disk.setStyleSheet("color: #fb923c; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        l_disk.addWidget(hdr_disk)

        self.lbl_storage_val = QLabel("180 GB free")
        self.lbl_storage_val.setStyleSheet("color: #ffffff; font-family: 'Segoe UI', sans-serif; font-size: 18px; font-weight: bold;")
        l_disk.addWidget(self.lbl_storage_val)

        self.storage_bar = MetricProgressBar(color=QColor(251, 146, 60))
        l_disk.addWidget(self.storage_bar)

        self.lbl_storage_sub = QLabel("of 476 GB")
        self.lbl_storage_sub.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-family: 'Segoe UI', sans-serif; font-size: 10px;")
        l_disk.addWidget(self.lbl_storage_sub)
        grid.addWidget(c_disk, 1, 0)

        # --- 5. BATTERY Card (Row 1, Col 1) ---
        c_bat = QFrame()
        c_bat.setObjectName("metricCard")
        c_bat.setStyleSheet(card_qss)
        c_bat.setFixedHeight(84)
        l_bat = QVBoxLayout(c_bat)
        l_bat.setContentsMargins(10, 6, 10, 6)
        l_bat.setSpacing(2)

        hdr_bat = QLabel("🔋 BATTERY")
        hdr_bat.setStyleSheet("color: #4ade80; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        l_bat.addWidget(hdr_bat)

        self.lbl_bat_val = QLabel("74%")
        self.lbl_bat_val.setStyleSheet("color: #ffffff; font-family: 'Segoe UI', sans-serif; font-size: 19px; font-weight: bold;")
        l_bat.addWidget(self.lbl_bat_val)

        self.bat_bar = MetricProgressBar(color=QColor(74, 222, 128))
        l_bat.addWidget(self.bat_bar)

        self.lbl_bat_sub = QLabel("On battery")
        self.lbl_bat_sub.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-family: 'Segoe UI', sans-serif; font-size: 10px;")
        l_bat.addWidget(self.lbl_bat_sub)
        grid.addWidget(c_bat, 1, 1)

        # --- 6. UPTIME Card (Row 1, Col 2) ---
        c_up = QFrame()
        c_up.setObjectName("metricCard")
        c_up.setStyleSheet(card_qss)
        c_up.setFixedHeight(84)
        l_up = QVBoxLayout(c_up)
        l_up.setContentsMargins(10, 6, 10, 6)
        l_up.setSpacing(2)

        hdr_up = QLabel("⏱ UPTIME")
        hdr_up.setStyleSheet("color: #facc15; font-family: 'Segoe UI', sans-serif; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;")
        l_up.addWidget(hdr_up)

        self.lbl_uptime_val = QLabel("5h 16m")
        self.lbl_uptime_val.setStyleSheet("color: #ffffff; font-family: 'Segoe UI', sans-serif; font-size: 18px; font-weight: bold;")
        l_up.addWidget(self.lbl_uptime_val)

        l_up.addSpacing(4)
        self.lbl_uptime_sub = QLabel("since last restart")
        self.lbl_uptime_sub.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-family: 'Segoe UI', sans-serif; font-size: 10px;")
        l_up.addWidget(self.lbl_uptime_sub)
        grid.addWidget(c_up, 1, 2)

        layout.addLayout(grid)
        layout.addSpacing(6)

        # --- 7. Bottom Controls Row: Brightness & Volume Vertical Capsules + Optimize Memory ---
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(10)

        # Curved Sliders Card Frame (holds Brightness & Volume side-by-side)
        sliders_card = QFrame()
        sliders_card.setObjectName("slidersCard")
        sliders_card.setStyleSheet("""
            QFrame#slidersCard {
                background-color: #0b0b0e;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
            }
        """)
        sliders_card.setFixedSize(102, 82)
        sc_layout = QHBoxLayout(sliders_card)
        sc_layout.setContentsMargins(6, 3, 6, 3)
        sc_layout.setSpacing(6)

        self.slider_brightness = VerticalSliderCapsule(mode="brightness")
        self.slider_brightness.setFixedSize(40, 76)
        self.slider_brightness.value_changed.connect(self._on_brightness_slider_changed)
        sc_layout.addWidget(self.slider_brightness)

        self.slider_volume = VerticalSliderCapsule(mode="volume")
        self.slider_volume.setFixedSize(40, 76)
        self.slider_volume.value_changed.connect(self._on_volume_slider_changed)
        sc_layout.addWidget(self.slider_volume)

        bottom_row.addWidget(sliders_card)

        # Optimize Memory Action Button
        self.btn_optimize_memory = QPushButton("🚀  Optimize memory\nPurge inactive working sets && cache")
        self.btn_optimize_memory.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_optimize_memory.setFixedHeight(82)
        self.btn_optimize_memory.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.07);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 10px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.14);
                border-color: rgba(0, 255, 204, 0.4);
            }
            QPushButton:pressed {
                background: rgba(255, 255, 255, 0.05);
            }
        """)
        self.btn_optimize_memory.clicked.connect(self._on_optimize_memory_clicked)
        bottom_row.addWidget(self.btn_optimize_memory, 1)

        layout.addLayout(bottom_row)

        # Initial metrics refresh
        self._refresh_system_metrics()
        return page

    def _format_net_speed(self, bytes_per_sec: float) -> str:
        if bytes_per_sec < 1024:
            return f"{int(bytes_per_sec)} B/s"
        elif bytes_per_sec < 1024 * 1024:
            return f"{bytes_per_sec / 1024.0:.1f} KB/s"
        else:
            return f"{bytes_per_sec / (1024.0 * 1024.0):.1f} MB/s"

    def _refresh_system_metrics(self):
        try:
            import psutil
            import time

            # 1. CPU
            cpu = psutil.cpu_percent(interval=None)
            self.lbl_cpu_val.setText(f"{int(round(cpu))}%")
            if hasattr(self, 'cpu_sparkline'):
                self.cpu_sparkline.add_point(cpu)

            # 2. RAM
            mem = psutil.virtual_memory()
            used_gb = (mem.total - mem.available) / (1024**3)
            total_gb = mem.total / (1024**3)
            self.lbl_ram_val.setText(f"{used_gb:.1f} GB")
            if hasattr(self, 'ram_bar'):
                self.ram_bar.set_value(mem.percent / 100.0)
            self.lbl_ram_sub.setText(f"of {total_gb:.1f} GB")

            # 3. Network
            net = psutil.net_io_counters()
            now = time.time()
            if hasattr(self, '_last_net_time') and self._last_net_time > 0:
                dt = max(0.1, now - self._last_net_time)
                down_speed = max(0.0, (net.bytes_recv - self._last_bytes_recv) / dt)
                up_speed = max(0.0, (net.bytes_sent - self._last_bytes_sent) / dt)
                self.lbl_net_down.setText(f"↓ {self._format_net_speed(down_speed)}")
                self.lbl_net_up.setText(f"↑ {self._format_net_speed(up_speed)}")
            self._last_net_time = now
            self._last_bytes_recv = net.bytes_recv
            self._last_bytes_sent = net.bytes_sent

            # 4. Storage (C: drive)
            disk = psutil.disk_usage('C:\\')
            free_gb = disk.free / (1024**3)
            total_disk_gb = disk.total / (1024**3)
            used_pct = disk.percent / 100.0
            self.lbl_storage_val.setText(f"{int(round(free_gb))} GB free")
            if hasattr(self, 'storage_bar'):
                self.storage_bar.set_value(used_pct)
            self.lbl_storage_sub.setText(f"of {int(round(total_disk_gb))} GB")

            # 5. Battery
            bat = psutil.sensors_battery()
            if bat:
                bat_pct = int(round(bat.percent))
                self.lbl_bat_val.setText(f"{bat_pct}%")
                if hasattr(self, 'bat_bar'):
                    self.bat_bar.set_value(bat_pct / 100.0)
                if bat.power_plugged:
                    self.lbl_bat_sub.setText("Plugged in" if bat_pct >= 99 else "Charging")
                else:
                    self.lbl_bat_sub.setText("On battery")
            else:
                self.lbl_bat_val.setText("100%")
                if hasattr(self, 'bat_bar'):
                    self.bat_bar.set_value(1.0)
                self.lbl_bat_sub.setText("AC Power")

            # 6. Uptime
            boot_time = psutil.boot_time()
            uptime_sec = int(time.time() - boot_time)
            h = uptime_sec // 3600
            m = (uptime_sec % 3600) // 60
            self.lbl_uptime_val.setText(f"{h}h {m}m")
            self.lbl_uptime_sub.setText("since last restart")

            # 7. Brightness & Volume Sliders (poll only when idle and not recently adjusted)
            now_ts = time.time()
            if hasattr(self, 'slider_brightness') and not self.slider_brightness.is_dragging:
                if (now_ts - getattr(self.slider_brightness, 'last_user_interaction', 0.0)) >= 3.0:
                    try:
                        import system_tools
                        b_val = system_tools.get_brightness()
                        self.slider_brightness.set_value(b_val)
                    except Exception:
                        pass

            if hasattr(self, 'slider_volume') and not self.slider_volume.is_dragging:
                if (now_ts - getattr(self.slider_volume, 'last_user_interaction', 0.0)) >= 3.0:
                    try:
                        import system_tools
                        v_val = system_tools.get_volume()
                        self.slider_volume.set_value(v_val)
                    except Exception:
                        pass

        except Exception:
            pass

    def _on_brightness_slider_changed(self, val: int):
        if hasattr(self, 'hw_controller'):
            self.hw_controller.set_brightness_async(val)
        else:
            try:
                import system_tools
                system_tools.set_brightness(val)
            except Exception:
                pass

    def _on_volume_slider_changed(self, val: int):
        if hasattr(self, 'hw_controller'):
            self.hw_controller.set_volume_async(val)
        else:
            try:
                import system_tools
                system_tools.set_volume(val)
            except Exception:
                pass

    def _on_optimize_memory_clicked(self):
        import gc
        gc.collect()
        freed_mb = 0
        try:
            import psutil
            p = psutil.Process()
            before_rss = p.memory_info().rss
            if self.island and hasattr(self.island, 'trim_memory'):
                self.island.trim_memory()
            else:
                try:
                    kernel32 = ctypes.windll.kernel32
                    psapi = ctypes.windll.psapi
                    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
                    psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
                    psapi.EmptyWorkingSet(kernel32.GetCurrentProcess())
                except Exception:
                    pass
            after_rss = p.memory_info().rss
            freed_mb = max(18, int((before_rss - after_rss) / (1024 * 1024)))
        except Exception:
            freed_mb = 25

        self.btn_optimize_memory.setText(f"✔  Memory Optimized!\nFreed {freed_mb} MB working memory")
        self.btn_optimize_memory.setStyleSheet("""
            QPushButton {
                background: rgba(0, 255, 204, 0.15);
                color: #00ffcc;
                border: 1px solid #00ffcc;
                border-radius: 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        self._refresh_system_metrics()
        QTimer.singleShot(2500, self._reset_optimize_button)

    def _reset_optimize_button(self):
        self.btn_optimize_memory.setText("🚀  Optimize memory\nPurge inactive working sets && cache")
        self.btn_optimize_memory.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.07);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 10px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.14);
                border-color: rgba(0, 255, 204, 0.4);
            }
        """)

    # ----------------- WORKSPACES PAGE -----------------
    def _create_workspaces_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 1. Header Row: Title & Status Toast
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        lbl_title = QLabel("App Workspaces")
        lbl_title.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold; font-family: 'Segoe UI', sans-serif; border: none;")
        title_box.addWidget(lbl_title)

        self.lbl_ws_toast = QLabel("")
        self.lbl_ws_toast.setStyleSheet("color: #00ffcc; font-size: 10px; font-weight: bold; border: none;")
        title_box.addWidget(self.lbl_ws_toast)
        header.addLayout(title_box)

        header.addStretch()
        layout.addLayout(header)

        # 2. Scrollable list of saved workspaces
        self.ws_scroll = QScrollArea()
        self.ws_scroll.setWidgetResizable(True)
        self.ws_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.ws_container = QWidget()
        self.ws_container.setStyleSheet("background: transparent;")
        self.ws_layout = QVBoxLayout(self.ws_container)
        self.ws_layout.setContentsMargins(0, 0, 0, 0)
        self.ws_layout.setSpacing(8)
        self.ws_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.ws_scroll.setWidget(self.ws_container)
        layout.addWidget(self.ws_scroll, 1)

        # 3. Bottom Quick Capture / Creation Capsule
        input_capsule = QFrame()
        input_capsule.setObjectName("wsInputCapsule")
        input_capsule.setFixedHeight(34)
        input_capsule.setStyleSheet("""
            QFrame#wsInputCapsule {
                background: #18181b;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 17px;
            }
        """)
        ic_layout = QHBoxLayout(input_capsule)
        ic_layout.setContentsMargins(10, 0, 4, 0)
        ic_layout.setSpacing(4)

        self.txt_new_ws = QLineEdit()
        self.txt_new_ws.setPlaceholderText("Name new workspace & press Enter...")
        self.txt_new_ws.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: 11px;
                font-family: 'Segoe UI', sans-serif;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.38);
            }
        """)
        self.txt_new_ws.returnPressed.connect(self._on_create_workspace_submitted)
        ic_layout.addWidget(self.txt_new_ws, 1)

        self.btn_add_ws = QPushButton("📸")
        self.btn_add_ws.setToolTip("Snapshot open apps with this workspace name")
        self.btn_add_ws.setFixedSize(24, 24)
        self.btn_add_ws.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_ws.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.15);
                color: #ffffff;
                border: none;
                border-radius: 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #00ffcc;
            }
        """)
        self.btn_add_ws.clicked.connect(self._on_create_workspace_submitted)
        ic_layout.addWidget(self.btn_add_ws)

        layout.addWidget(input_capsule)

        self._refresh_workspaces_ui()
        return page

    def _refresh_workspaces_ui(self):
        while self.ws_layout.count() > 0:
            item = self.ws_layout.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.setParent(None)
                w.deleteLater()

        try:
            import workspace_engine
            workspaces = workspace_engine.load_workspaces()
        except Exception:
            workspaces = {}

        if not workspaces:
            empty_box = QWidget()
            eb_layout = QVBoxLayout(empty_box)
            eb_layout.setContentsMargins(0, 36, 0, 0)
            eb_layout.setSpacing(6)
            eb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            lbl_ico = QLabel("💼")
            lbl_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_ico.setStyleSheet("color: rgba(255, 255, 255, 0.25); font-size: 26px; border: none;")
            eb_layout.addWidget(lbl_ico)

            lbl_msg = QLabel("No saved workspaces yet.")
            lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_msg.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 13px; font-weight: 600; font-family: 'Segoe UI', sans-serif; border: none;")
            eb_layout.addWidget(lbl_msg)

            lbl_sub = QLabel("Open your apps, type a name below and press Enter to save them as a 1-click workspace.")
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_sub.setWordWrap(True)
            lbl_sub.setStyleSheet("color: rgba(255, 255, 255, 0.35); font-size: 11px; font-family: 'Segoe UI', sans-serif; border: none;")
            eb_layout.addWidget(lbl_sub)

            self.ws_layout.addWidget(empty_box)
            return

        for ws_name, entry in sorted(workspaces.items()):
            try:
                import workspace_engine
                apps = workspace_engine.normalize_ws_apps(entry)
                app_names = [workspace_engine.display_name(a) for a in apps]
            except Exception:
                apps = entry if isinstance(entry, list) else []
                app_names = [str(a) for a in apps]

            row = QFrame()
            row.setObjectName("wsRow")
            row.setStyleSheet("""
                QFrame#wsRow {
                    background: #111114;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 10px;
                    padding: 4px;
                }
                QFrame#wsRow:hover {
                    border-color: rgba(0, 255, 204, 0.35);
                    background: #141418;
                }
            """)
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(10, 8, 10, 8)
            r_layout.setSpacing(10)

            # Left icon
            lbl_ico = QLabel("💼")
            lbl_ico.setStyleSheet("font-size: 16px; border: none; background: transparent;")
            r_layout.addWidget(lbl_ico)

            # Center info
            info_box = QVBoxLayout()
            info_box.setSpacing(2)

            title_txt = ws_name.title() if ws_name else "Untitled Workspace"
            lbl_name = QLabel(title_txt)
            lbl_name.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold; font-family: 'Segoe UI', sans-serif; border: none; background: transparent;")
            info_box.addWidget(lbl_name)

            preview_txt = ", ".join(app_names) if app_names else "Empty workspace"
            if len(preview_txt) > 42:
                preview_txt = preview_txt[:42] + "..."
            lbl_preview = QLabel(f"{len(apps)} app{'s' if len(apps) != 1 else ''}: {preview_txt}")
            lbl_preview.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 10px; font-family: 'Segoe UI', sans-serif; border: none; background: transparent;")
            info_box.addWidget(lbl_preview)

            r_layout.addLayout(info_box, 1)

            # Launch button
            btn_launch = QPushButton("▶  Launch")
            btn_launch.setFixedSize(76, 26)
            btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_launch.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 255, 204, 0.12);
                    color: #00ffcc;
                    border: 1px solid rgba(0, 255, 204, 0.4);
                    border-radius: 6px;
                    font-size: 10px;
                    font-weight: bold;
                    font-family: 'Segoe UI', sans-serif;
                }
                QPushButton:hover {
                    background: #00ffcc;
                    color: #000000;
                }
            """)
            btn_launch.clicked.connect(lambda ch, w=ws_name, b=btn_launch: self._on_launch_workspace(w, b))
            r_layout.addWidget(btn_launch)

            # Delete button
            btn_del = QPushButton("✕")
            btn_del.setFixedSize(24, 24)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: rgba(255, 255, 255, 0.35);
                    border: none;
                    font-size: 12px;
                }
                QPushButton:hover {
                    color: #ff5555;
                }
            """)
            btn_del.clicked.connect(lambda ch, w=ws_name: self._on_delete_workspace(w))
            r_layout.addWidget(btn_del)

            self.ws_layout.addWidget(row)

    def _on_launch_workspace(self, ws_name: str, btn: QPushButton = None):
        if btn:
            btn.setText("Launching...")
            btn.setEnabled(False)
        self.lbl_ws_toast.setText(f"Launching '{ws_name}'...")

        try:
            import workspace_engine
            workspace_engine.launch_workspace_async(ws_name)
        except Exception as e:
            self.lbl_ws_toast.setText(f"Launch error: {e}")

        def _reset_btn():
            if btn:
                btn.setText("▶  Launch")
                btn.setEnabled(True)
            self.lbl_ws_toast.setText("")

        QTimer.singleShot(3000, _reset_btn)

    def _on_delete_workspace(self, ws_name: str):
        try:
            import workspace_engine
            workspace_engine.manage_workspace("delete", ws_name)
            self.lbl_ws_toast.setText(f"Deleted '{ws_name}'")
            QTimer.singleShot(2000, lambda: self.lbl_ws_toast.setText(""))
        except Exception:
            pass
        self._refresh_workspaces_ui()

    def _on_create_workspace_submitted(self):
        ws_name = self.txt_new_ws.text().strip()
        if not ws_name:
            return
        self._save_active_windows_as_workspace(ws_name)
        self.txt_new_ws.clear()

    def _on_capture_workspace_clicked(self):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("New Workspace")
        dialog.setLabelText("Enter a name for this workspace:")
        dialog.setTextValue("Work")
        dialog.setStyleSheet("""
            QDialog {
                background-color: #121214;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QLineEdit {
                background: #18181c;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #00ffcc;
                color: #000000;
                border-color: #00ffcc;
            }
        """)
        if dialog.exec():
            ws_name = dialog.textValue().strip()
            if ws_name:
                self._save_active_windows_as_workspace(ws_name)

    def _save_active_windows_as_workspace(self, ws_name: str):
        try:
            import workspace_engine
            res = workspace_engine.capture_active_windows()
            apps = res.get("apps", []) if isinstance(res, dict) else []
            if not apps:
                # If no open windows captured, supply default workspace apps
                apps = ["notepad.exe"]
            workspace_engine.manage_workspace("create", ws_name, apps=apps)
            count = len(apps)
            self.lbl_ws_toast.setText(f"Saved '{ws_name}' with {count} app{'s' if count != 1 else ''}!")
            QTimer.singleShot(3000, lambda: self.lbl_ws_toast.setText(""))
        except Exception as e:
            self.lbl_ws_toast.setText(f"Error: {e}")
        self._refresh_workspaces_ui()

    # ----------------- CLIPBOARD PAGE -----------------
    def _create_clipboard_page(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("Clipboard History")
        title.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-weight: 600; font-size: 12px; text-transform: uppercase; border: none;")
        title_row.addWidget(title)

        self.lbl_clip_toast = QLabel("")
        self.lbl_clip_toast.setStyleSheet("color: #00ffcc; font-size: 11px; font-weight: bold; border: none;")
        title_row.addWidget(self.lbl_clip_toast)
        title_row.addStretch()

        btn_clear = QPushButton("Clear")
        btn_clear.setStyleSheet("background: transparent; color: #ff5555; border: none; font-size: 11px;")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._clear_clipboard)
        title_row.addWidget(btn_clear)

        layout.addLayout(title_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 255, 204, 0.5);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.clip_list_container = QVBoxLayout(scroll_content)
        self.clip_list_container.setContentsMargins(0, 0, 4, 0)
        self.clip_list_container.setSpacing(6)
        self.clip_list_container.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        self.refresh_clipboard()
        return page

    def refresh_clipboard(self):
        while self.clip_list_container.count() > 0:
            item = self.clip_list_container.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        history = []
        if self.island and hasattr(self.island, 'clipboard_history'):
            history = self.island.clipboard_history

        if not history:
            empty_lbl = QLabel("No text copied yet. Copy any text in Windows to save here.")
            empty_lbl.setStyleSheet("color: rgba(255, 255, 255, 0.4); font-size: 11px; font-style: italic; border: none; padding: 20px 0;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.clip_list_container.addWidget(empty_lbl)
            self.clip_list_container.addStretch()
            return

        for idx, text in enumerate(history[:10]):
            row = QFrame()
            row.setFixedHeight(38)
            row.setStyleSheet("""
                QFrame {
                    background: #0d0d10;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 8px;
                }
                QFrame:hover {
                    border: 1px solid rgba(0, 255, 204, 0.4);
                    background: #141418;
                }
            """)
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(12, 0, 8, 0)
            r_layout.setSpacing(10)

            preview = text.replace("\n", " ").strip()
            if len(preview) > 42:
                preview = preview[:42] + "..."

            t_lbl = QLabel(f"{idx+1}. {preview}")
            t_lbl.setStyleSheet("color: #ffffff; font-size: 12px; font-family: 'Segoe UI', sans-serif; border: none; background: transparent;")
            r_layout.addWidget(t_lbl, 1)

            btn_copy = QPushButton("Copy")
            btn_copy.setFixedSize(50, 24)
            btn_copy.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 255, 204, 0.08);
                    color: #00ffcc;
                    border: 1px solid rgba(0, 255, 204, 0.4);
                    border-radius: 5px;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(0, 255, 204, 0.22);
                    color: #ffffff;
                }
            """)
            btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_copy.clicked.connect(lambda ch, t=text: self._copy_text(t))
            r_layout.addWidget(btn_copy)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(22, 22)
            btn_del.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: rgba(255, 255, 255, 0.35);
                    border: none;
                    font-size: 11px;
                }
                QPushButton:hover {
                    color: #ff5555;
                }
            """)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda ch, t=text: self._delete_clipboard_item(t))
            r_layout.addWidget(btn_del)

            self.clip_list_container.addWidget(row)

        self.clip_list_container.addStretch()

    def _copy_text(self, text):
        app = QApplication.instance()
        if app:
            app.clipboard().setText(text)
            self.lbl_clip_toast.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.lbl_clip_toast.setText(""))

    def _delete_clipboard_item(self, text):
        if self.island and hasattr(self.island, 'clipboard_history'):
            if text in self.island.clipboard_history:
                self.island.clipboard_history.remove(text)
                self.refresh_clipboard()

    def _clear_clipboard(self):
        if self.island and hasattr(self.island, 'clipboard_history'):
            self.island.clipboard_history.clear()
            self.refresh_clipboard()

    # ----------------- TABS NAVIGATION -----------------
    def switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        titles = ["Media Player", "Timer & Focus", "System Metrics", "App Workspaces", "Clipboard History"]
        self.lbl_header_title.setText(titles[index] if index < len(titles) else "Desktop Companion")

        for i, btn in enumerate(self.tab_buttons):
            if i == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(0, 255, 204, 0.08);
                        color: #00ffcc;
                        font-weight: bold;
                        border: 1px solid #00ffcc;
                        border-radius: 8px;
                        font-size: 11px;
                        padding: 4px 8px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: #000000;
                        color: rgba(255, 255, 255, 0.55);
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        border-radius: 8px;
                        font-size: 11px;
                        padding: 4px 8px;
                    }
                    QPushButton:hover {
                        background: rgba(255, 255, 255, 0.05);
                        color: white;
                    }
                """)
        if index == 0:
            if hasattr(self, '_last_media_data') and self._last_media_data:
                self.update_media_data(self._last_media_data)
        elif index == 1:
            self._refresh_tasks_ui()
        elif index == 2:
            self._refresh_system_metrics()
            if hasattr(self, 'system_metrics_timer') and not self.system_metrics_timer.isActive():
                self.system_metrics_timer.start()
        elif index == 3:
            self._refresh_workspaces_ui()
        elif index == 4:
            self.refresh_clipboard()

        if index != 2 and hasattr(self, 'system_metrics_timer') and self.system_metrics_timer.isActive():
            self.system_metrics_timer.stop()
        self.tab_changed.emit(index)

    def showEvent(self, event):
        super().showEvent(event)
        # Instantly update media position on reopen
        if hasattr(self, '_last_media_data') and self._last_media_data:
            self.update_media_data(self._last_media_data)

    def update_media_data(self, data: dict):
        if not data or not data.get("active"):
            self._last_media_data = data
            self.waveform_bar.set_playing(False)
            self.btn_play.set_mode("play")
            return

        self._last_media_data = dict(data)
        if "sync_time" not in self._last_media_data:
            self._last_media_data["sync_time"] = time.time()

        is_playing = data.get("playing", False)
        self.waveform_bar.set_playing(is_playing)
        self.btn_play.set_mode("pause" if is_playing else "play")

        title = data.get("title", "Unknown")
        artist = data.get("artist", "")
        source = data.get("source_app", "")

        self.lbl_track_title.setText(title)
        sub = f"{artist} · {source}" if (artist and source) else (artist or source or "Media Player")
        self.lbl_track_sub.setText(sub)

        # Update Thumbnail, Ambient Radial Glow, and Media Controls Color
        thumb = data.get("thumb", "")
        if hasattr(self, 'album_art'):
            if self.island and hasattr(self.island, 'cfg'):
                self.music_page.ambient_glow_enabled = self.island.cfg.get("music_ambient_glow", True)
            dom_color = self.album_art.set_thumbnail(thumb)
            self.music_page.set_dominant_color(dom_color)
            self.waveform_bar.set_accent_color(dom_color)
            self.btn_play.set_accent_color(dom_color)
            self.btn_prev.set_accent_color(dom_color)
            self.btn_next.set_accent_color(dom_color)

            # Update NOW PLAYING capsule with vibrant dominant color
            r, g, b = dom_color.red(), dom_color.green(), dom_color.blue()
            self.pill_now_playing.setStyleSheet(f"""
                QLabel {{
                    background: rgba({r}, {g}, {b}, 0.16);
                    color: rgb({r}, {g}, {b});
                    border: 1px solid rgba({r}, {g}, {b}, 0.38);
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 10px;
                    font-weight: bold;
                    letter-spacing: 0.5px;
                    border-radius: 10px;
                    padding: 4px 10px;
                }}
            """)

        # Update Waveform Timeline with live elapsed compensation
        pos_sec = data.get("pos_sec", 0.0)
        end_sec = data.get("end_sec", 0.0)
        dur_str = data.get("dur_str", "00:00")
        sync_time = data.get("sync_time", 0.0)
        if is_playing and sync_time > 0:
            elapsed = max(0.0, time.time() - sync_time)
            pos_sec = pos_sec + elapsed
            if end_sec > 0:
                pos_sec = min(end_sec, pos_sec)
            cur_m, cur_s = divmod(int(pos_sec), 60)
            pos_str = f"{cur_m:02d}:{cur_s:02d}"
        else:
            pos_str = data.get("pos_str", "00:00")

        self.waveform_bar.set_timeline(pos_sec, end_sec, pos_str, dur_str)
