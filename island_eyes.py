import math
import random
import socket
import threading
from enum import Enum, auto
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath


class EyeMood(Enum):
    NEUTRAL_IDLE = auto()
    CURIOUS_SQUINT = auto()
    WIDE_AWAKE = auto()
    SUBTLE_LOOK = auto()
    HAPPY_ARCH = auto()
    SLEEPY_DROOP = auto()
    LOVE_HEARTS = auto()
    WINK = auto()
    ANGRY_DEVIL = auto()
    SAD_POUT = auto()
    DIZZY_CONFUSED = auto()
    STAR_SPARKLE = auto()
    FOCUSED_SCANNER = auto()
    SHOCKED_SURPRISE = auto()
    BORED_ROLL = auto()
    COMMAND_MIC = auto()   
    AI_RESPONDING = auto()
    DEAD_OFFLINE = auto() 

    # Backwards-compatible aliases
    IDLE = NEUTRAL_IDLE
    LISTENING = COMMAND_MIC
    RESPONDING = AI_RESPONDING
    THINKING = FOCUSED_SCANNER
    CONFUSED = DIZZY_CONFUSED
    HAPPY = HAPPY_ARCH
    HEARTS = LOVE_HEARTS
    STARS = STAR_SPARKLE
    ANGRY = ANGRY_DEVIL
    SAD = SAD_POUT


def create_heart_path(cx, cy, w, h):
    path = QPainterPath()
    top_y = cy - h * 0.45
    bottom_y = cy + h * 0.5
    notch_y = cy - h * 0.15
    left_x = cx - w * 0.5
    right_x = cx + w * 0.5
    
    path.moveTo(cx, notch_y)
    path.cubicTo(cx - w * 0.25, top_y, left_x, top_y + h * 0.2, left_x, cy)
    path.cubicTo(left_x, cy + h * 0.3, cx - w * 0.1, bottom_y - h * 0.1, cx, bottom_y)
    path.cubicTo(cx + w * 0.1, bottom_y - h * 0.1, right_x, cy + h * 0.3, right_x, cy)
    path.cubicTo(right_x, top_y + h * 0.2, cx + w * 0.25, top_y, cx, notch_y)
    path.closeSubpath()
    return path


def create_star_path(cx, cy, r_outer, r_inner):
    path = QPainterPath()
    points = [
        (cx, cy - r_outer),
        (cx + r_inner, cy - r_inner),
        (cx + r_outer, cy),
        (cx + r_inner, cy + r_inner),
        (cx, cy + r_outer),
        (cx - r_inner, cy + r_inner),
        (cx - r_outer, cy),
        (cx - r_inner, cy - r_inner),
    ]
    path.moveTo(points[0][0], points[0][1])
    for px, py in points[1:]:
        path.lineTo(px, py)
    path.closeSubpath()
    return path


class DynamicIslandEyes(QWidget):
    """
    Autonomous Expressive Robot Eyes for Emo AI Notch (PyQt6).
    - 100% procedural vector rendering in paintEvent via drawRoundedRect, drawArc, and drawLine.
    - Event-driven 60 FPS (16ms) LERP physics engine: automatically sleeps at 0.00% CPU
      once target coordinates are reached, waking only during blinks, mood transitions, or mic input.
    - Command Mode (EyeMood.COMMAND_MIC): Smoothly morphs the 2 eyes into 3 vertical lines
      whose heights are dynamically manipulated by real-time microphone audio input.
    - Offline Dead Mode (EyeMood.DEAD_OFFLINE): Automatically detects internet absence and
      morphs the eyes into Red Crossed 'X  X' dead eyes until connection is restored.
    - Expanded Living Robot Moods: Love Hearts, Winks, Stars, Angry Pout, Sad Eyes, Dizzy,
      Focused Scanner, Shocked Look, etc., randomly and naturally cycled during idle.
    """

    _net_status_changed = pyqtSignal(bool)  # True = online, False = offline

    COLOR_CYAN = (0.0, 240.0, 255.0)            # #00F0FF Signature Neo-Aqua Cyan
    COLOR_CHARGING_GREEN = (0.0, 255.0, 136.0)  # #00FF88 Electric Green when charger connected
    COLOR_ULTRON = (255.0, 25.0, 45.0)          # Crimson red for Ultron voice theme
    COLOR_DEAD_RED = (255.0, 34.0, 51.0)        # #FF2233 Dead Offline Red
    COLOR_LOVE_PINK = (255.0, 80.0, 150.0)      # Soft Neon Pink for Love Hearts
    COLOR_ANGRY_AMBER = (255.0, 110.0, 30.0)    # Fiery Amber for Angry Devil

    # Complete autonomous pool of expressive robot moods randomly cycled during idle
    EXPRESSION_POOL = [
        EyeMood.NEUTRAL_IDLE,
        EyeMood.NEUTRAL_IDLE,
        EyeMood.CURIOUS_SQUINT,
        EyeMood.WIDE_AWAKE,
        EyeMood.SUBTLE_LOOK,
        EyeMood.HAPPY_ARCH,
        EyeMood.SLEEPY_DROOP,
        EyeMood.LOVE_HEARTS,
        EyeMood.WINK,
        EyeMood.ANGRY_DEVIL,
        EyeMood.SAD_POUT,
        EyeMood.DIZZY_CONFUSED,
        EyeMood.STAR_SPARKLE,
        EyeMood.FOCUSED_SCANNER,
        EyeMood.SHOCKED_SURPRISE,
        EyeMood.BORED_ROLL,
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 26)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.mood = EyeMood.NEUTRAL_IDLE
        self.is_ultron = False
        self._is_offline = False
        self._checking_net = False
        self._is_charging = False
        self._last_plugged = None

        # Microphone input level for COMMAND_MIC (3 vertical lines) mode
        self._mic_level = 0.0
        self._smooth_mic = 0.0
        self._mic_phase = 0.0

        # Current interpolated physics state (2 eyes + 3rd center line + morphs)
        self.cur_lx = -11.5
        self.cur_rx = 11.5
        self.cur_lw = 13.5
        self.cur_rw = 13.5
        self.cur_lh = 17.5
        self.cur_rh = 17.5
        self.cur_cw = 0.0
        self.cur_ch = 2.0
        self.cur_calpha = 0.0
        self.cur_ox = 0.0
        self.cur_oy = 0.0
        self.cur_ldy = 0.0
        self.cur_rdy = 0.0
        self.cur_radius = 5.2
        self.cur_larch = 0.0    # 0.0 = squircle, 1.0 = ^ arch
        self.cur_rarch = 0.0
        self.cur_x_eyes = 0.0   # 0.0 = normal, 1.0 = X X dead offline eyes
        self.cur_hearts = 0.0   # 0.0 = normal, 1.0 = <3 <3 hearts
        self.cur_stars = 0.0    # 0.0 = normal, 1.0 = * * stars
        self.cur_lslant = 0.0   # Left eye tilt degrees
        self.cur_rslant = 0.0   # Right eye tilt degrees

        # Target physics state (set by current expression)
        self.base_lw = 13.5
        self.base_rw = 13.5
        self.base_lh = 17.5
        self.base_rh = 17.5
        self.target_lx = -11.5
        self.target_rx = 11.5
        self.target_lw = 13.5
        self.target_rw = 13.5
        self.target_lh = 17.5
        self.target_rh = 17.5
        self.target_cw = 0.0
        self.target_ch = 2.0
        self.target_calpha = 0.0
        self.target_ox = 0.0
        self.target_oy = 0.0
        self.target_ldy = 0.0
        self.target_rdy = 0.0
        self.target_radius = 5.2
        self.target_larch = 0.0
        self.target_rarch = 0.0
        self.target_x_eyes = 0.0
        self.target_hearts = 0.0
        self.target_stars = 0.0
        self.target_lslant = 0.0
        self.target_rslant = 0.0

        # Current & target RGB color
        self.cur_r, self.cur_g, self.cur_b = self.COLOR_CYAN
        self.target_r, self.target_g, self.target_b = self.COLOR_CYAN

        # Blink state
        self._blinking = False

        # Connect thread-safe network status signal
        self._net_status_changed.connect(self._on_net_status_changed)

        # 1. On-Demand 60 FPS LERP Physics Timer (16ms, auto-sleeps when settled)
        self.physics_timer = QTimer(self)
        self.physics_timer.setInterval(16)
        self.physics_timer.timeout.connect(self._tick_physics)

        # 2. Autonomous Expression Cycle Timer (4 to 8 seconds randomized)
        self.expression_timer = QTimer(self)
        self.expression_timer.timeout.connect(self._pick_random_expression)
        self.expression_timer.start(random.randint(4000, 8000))

        # 3. Independent Organic Blink Timer (3 to 6 seconds randomized)
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._trigger_blink_cycle)
        self.blink_timer.start(random.randint(3000, 6000))

        # 4. Lightweight Offline/Online Connectivity Monitor (every 4 seconds)
        self.net_timer = QTimer(self)
        self.net_timer.setInterval(4000)
        self.net_timer.timeout.connect(self._trigger_net_check)
        self.net_timer.start()
        self._trigger_net_check()

        # 5. Battery / Charger Telemetry Monitor (every 2 seconds)
        self.battery_timer = QTimer(self)
        self.battery_timer.setInterval(2000)
        self.battery_timer.timeout.connect(self._poll_battery)
        self.battery_timer.start()
        self._poll_battery()

    # Backwards-compatible properties
    @property
    def cur_arch(self):
        return max(self.cur_larch, self.cur_rarch)

    @property
    def target_arch(self):
        return max(self.target_larch, self.target_rarch)

    @target_arch.setter
    def target_arch(self, val):
        self.target_larch = float(val)
        self.target_rarch = float(val)

    def _wake_physics(self):
        if self.isVisible() and not self.physics_timer.isActive():
            self.physics_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.expression_timer.isActive():
            self.expression_timer.start(random.randint(4000, 8000))
        if not self.blink_timer.isActive():
            self.blink_timer.start(random.randint(3000, 6000))
        if not self.net_timer.isActive():
            self.net_timer.start()
        if not self.battery_timer.isActive():
            self.battery_timer.start()
        self._trigger_net_check()
        self._poll_battery()
        self._wake_physics()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.physics_timer.stop()
        self.expression_timer.stop()
        self.blink_timer.stop()
        self.net_timer.stop()
        self.battery_timer.stop()

    # ------------------------------------------------------------------
    # Battery & Charger Telemetry (Electric Green on Plug-In)
    # ------------------------------------------------------------------
    def _poll_battery(self):
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery is None:
                return
            plugged = bool(battery.power_plugged)
            if plugged != self._last_plugged:
                prev = self._last_plugged
                self._last_plugged = plugged
                self.set_charging(plugged, celebrate=plugged)
            elif plugged != self._is_charging:
                self.set_charging(plugged, celebrate=plugged)
        except Exception:
            pass

    @property
    def is_charging(self) -> bool:
        return self._is_charging

    def set_charging(self, charging: bool, celebrate: bool = True):
        self._is_charging = bool(charging)
        self._update_color_target()
        if self._is_charging and celebrate and not self._is_offline:
            self.trigger_happy(3000)
        self._wake_physics()

    # ------------------------------------------------------------------
    # Non-Blocking Internet Connectivity Detection
    # ------------------------------------------------------------------
    def _trigger_net_check(self):
        if self._checking_net:
            return
        self._checking_net = True

        def _probe():
            online = False
            for host in ("1.1.1.1", "8.8.8.8"):
                try:
                    with socket.create_connection((host, 53), timeout=1.0):
                        online = True
                        break
                except OSError:
                    continue
            self._checking_net = False
            try:
                self._net_status_changed.emit(online)
            except RuntimeError:
                pass

        threading.Thread(target=_probe, daemon=True).start()

    @property
    def is_offline(self) -> bool:
        return self._is_offline

    def _on_net_status_changed(self, is_online: bool):
        offline = not is_online
        if offline != self._is_offline:
            self.set_offline(offline)

    def set_offline(self, offline: bool):
        self._is_offline = bool(offline)
        self._update_color_target()
        if self._is_offline:
            self._apply_expression(EyeMood.DEAD_OFFLINE)
        else:
            if self.mood == EyeMood.DEAD_OFFLINE:
                self._apply_expression(EyeMood.NEUTRAL_IDLE)
        self._wake_physics()

    # ------------------------------------------------------------------
    # Public API & Integration Hooks
    # ------------------------------------------------------------------
    def set_ultron_theme(self, enabled: bool):
        self.is_ultron = bool(enabled)
        self._update_color_target()
        self._wake_physics()

    def set_mood(self, mood: EyeMood):
        if self._is_offline and mood not in (EyeMood.DEAD_OFFLINE, EyeMood.COMMAND_MIC):
            self._apply_expression(EyeMood.DEAD_OFFLINE)
            return
        self._apply_expression(mood)

    def set_mic_level(self, level: float):
        self._mic_level = max(0.0, min(1.0, float(level)))
        self._wake_physics()

    def trigger_happy(self, duration_ms=2200):
        if self._is_offline:
            return
        self._apply_expression(EyeMood.HAPPY_ARCH)
        QTimer.singleShot(duration_ms, self._restore_after_transient)

    def trigger_confused(self, duration_ms=2000):
        if self._is_offline:
            return
        self._apply_expression(EyeMood.CURIOUS_SQUINT)
        QTimer.singleShot(duration_ms, self._restore_after_transient)

    def _restore_after_transient(self):
        if self._is_offline:
            self._apply_expression(EyeMood.DEAD_OFFLINE)
        elif self.mood not in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING):
            self._apply_expression(EyeMood.NEUTRAL_IDLE)

    def _update_color_target(self):
        if self._is_offline:
            self.target_r, self.target_g, self.target_b = self.COLOR_DEAD_RED
        elif self._is_charging:
            self.target_r, self.target_g, self.target_b = self.COLOR_CHARGING_GREEN
        elif self.is_ultron:
            self.target_r, self.target_g, self.target_b = self.COLOR_ULTRON
        elif self.mood == EyeMood.LOVE_HEARTS:
            self.target_r, self.target_g, self.target_b = self.COLOR_LOVE_PINK
        elif self.mood == EyeMood.ANGRY_DEVIL:
            self.target_r, self.target_g, self.target_b = self.COLOR_ANGRY_AMBER
        else:
            self.target_r, self.target_g, self.target_b = self.COLOR_CYAN

    # ------------------------------------------------------------------
    # Autonomous Random Expression & Blink Schedulers
    # ------------------------------------------------------------------
    def _pick_random_expression(self):
        if self._is_offline:
            if self.mood != EyeMood.DEAD_OFFLINE:
                self._apply_expression(EyeMood.DEAD_OFFLINE)
            return
        if self.mood in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING):
            return
        candidates = [m for m in self.EXPRESSION_POOL if m != self.mood] or self.EXPRESSION_POOL
        chosen = random.choice(candidates)
        self._apply_expression(chosen)
        self.expression_timer.setInterval(random.randint(4000, 8000))

    def _apply_expression(self, mood: EyeMood):
        self.mood = mood

        # Reset all standard morph targets
        self.target_larch = 0.0
        self.target_rarch = 0.0
        self.target_hearts = 0.0
        self.target_stars = 0.0
        self.target_lslant = 0.0
        self.target_rslant = 0.0
        self.target_x_eyes = 0.0
        self.target_cw = 0.0
        self.target_ch = 2.0
        self.target_calpha = 0.0
        self.target_lx = -11.5
        self.target_rx = 11.5
        self.target_ox = 0.0
        self.target_oy = 0.0
        self.target_ldy = 0.0
        self.target_rdy = 0.0

        if mood == EyeMood.DEAD_OFFLINE:
            self._blinking = False
            self.base_lw = self.base_rw = 13.5
            self.base_lh = self.base_rh = 13.5
            self.target_radius = 3.0
            self.target_x_eyes = 1.0
            self._update_color_target()
            self._wake_physics()
            return

        if mood in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING):
            self._blinking = False
            self.target_lx = -10.5
            self.target_rx = 10.5
            self.base_lw = self.base_rw = 4.2
            self.base_lh = self.base_rh = 9.0
            self.target_lw = 4.2
            self.target_rw = 4.2
            self.target_lh = 9.0
            self.target_rh = 9.0
            self.target_cw = 4.2
            self.target_ch = 12.0
            self.target_calpha = 1.0
            self.target_radius = 2.1
            self._update_color_target()
            self._wake_physics()
            return

        # --- RANDOM IDLE EXPRESSIONS ---
        if mood == EyeMood.NEUTRAL_IDLE:
            self.base_lw = self.base_rw = 13.5
            self.base_lh = self.base_rh = 17.5
            self.target_radius = 5.2

        elif mood == EyeMood.CURIOUS_SQUINT:
            if random.random() < 0.5:
                self.base_lw, self.base_lh = 14.0, 19.0
                self.base_rw, self.base_rh = 14.5, 9.0
                self.target_ldy, self.target_rdy = -1.5, 1.5
            else:
                self.base_lw, self.base_lh = 14.5, 9.0
                self.base_rw, self.base_rh = 14.0, 19.0
                self.target_ldy, self.target_rdy = 1.5, -1.5
            self.target_ox = random.choice([-2.0, 0.0, 2.0])
            self.target_radius = 4.2

        elif mood == EyeMood.WIDE_AWAKE:
            self.base_lw = self.base_rw = 15.5
            self.base_lh = self.base_rh = 20.5
            self.target_oy = -1.0
            self.target_radius = 7.0

        elif mood == EyeMood.SUBTLE_LOOK:
            self.base_lw = self.base_rw = 13.5
            self.base_lh = self.base_rh = 17.5
            self.target_ox = random.choice([-3.8, -2.8, 2.8, 3.8])
            self.target_oy = random.choice([-1.5, 0.0, 1.0])
            self.target_radius = 5.2

        elif mood == EyeMood.HAPPY_ARCH:
            self.base_lw = self.base_rw = 14.5
            self.base_lh = self.base_rh = 11.5
            self.target_oy = -1.0
            self.target_radius = 5.5
            self.target_larch = 1.0
            self.target_rarch = 1.0

        elif mood == EyeMood.SLEEPY_DROOP:
            self.base_lw = self.base_rw = 14.5
            self.base_lh = self.base_rh = 8.0
            self.target_oy = 2.0
            self.target_radius = 3.0

        elif mood == EyeMood.LOVE_HEARTS:
            self.base_lw = self.base_rw = 15.0
            self.base_lh = self.base_rh = 15.5
            self.target_oy = -0.5
            self.target_radius = 4.0
            self.target_hearts = 1.0

        elif mood == EyeMood.WINK:
            # Randomly pick which eye winks
            if random.random() < 0.5:
                self.base_lw, self.base_lh = 14.5, 11.5
                self.target_larch = 1.0
                self.base_rw, self.base_rh = 14.0, 18.0
                self.target_rarch = 0.0
                self.target_rdy = 0.5
            else:
                self.base_lw, self.base_lh = 14.0, 18.0
                self.target_larch = 0.0
                self.base_rw, self.base_rh = 14.5, 11.5
                self.target_rarch = 1.0
                self.target_ldy = 0.5
            self.target_radius = 5.2

        elif mood == EyeMood.ANGRY_DEVIL:
            self.base_lw = self.base_rw = 14.0
            self.base_lh = self.base_rh = 12.0
            self.target_lslant = 15.0   # inward slant
            self.target_rslant = -15.0  # inward slant
            self.target_oy = 0.5
            self.target_radius = 4.0

        elif mood == EyeMood.SAD_POUT:
            self.base_lw = self.base_rw = 13.5
            self.base_lh = self.base_rh = 13.0
            self.target_lslant = -13.0  # outward droop
            self.target_rslant = 13.0   # outward droop
            self.target_oy = 1.8
            self.target_radius = 4.5

        elif mood == EyeMood.DIZZY_CONFUSED:
            self.base_lw, self.base_lh = 11.0, 11.0
            self.target_ldy = -2.5
            self.target_lslant = 12.0
            self.base_rw, self.base_rh = 15.5, 15.5
            self.target_rdy = 2.0
            self.target_rslant = -12.0
            self.target_ox = random.choice([-1.5, 1.5])
            self.target_radius = 4.0

        elif mood == EyeMood.STAR_SPARKLE:
            self.base_lw = self.base_rw = 15.0
            self.base_lh = self.base_rh = 15.0
            self.target_oy = -0.5
            self.target_radius = 4.0
            self.target_stars = 1.0

        elif mood == EyeMood.FOCUSED_SCANNER:
            self.base_lw = self.base_rw = 16.5
            self.base_lh = self.base_rh = 5.5
            self.target_ox = random.choice([-2.0, 0.0, 2.0])
            self.target_radius = 2.2

        elif mood == EyeMood.SHOCKED_SURPRISE:
            self.base_lw = self.base_rw = 16.0
            self.base_lh = self.base_rh = 22.5
            self.target_oy = -1.2
            self.target_radius = 8.0

        elif mood == EyeMood.BORED_ROLL:
            self.base_lw = self.base_rw = 13.5
            self.base_lh = self.base_rh = 12.0
            self.target_ox = 3.6
            self.target_oy = -3.2
            self.target_radius = 5.0

        if not self._blinking:
            self.target_lw = self.base_lw
            self.target_rw = self.base_rw
            self.target_lh = self.base_lh
            self.target_rh = self.base_rh

        self._update_color_target()
        self._wake_physics()

    def _trigger_blink_cycle(self):
        if self._is_offline or self.mood in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING, EyeMood.DEAD_OFFLINE):
            return
        self._blinking = True
        self.target_lh = 1.6
        self.target_rh = 1.6
        self._wake_physics()
        QTimer.singleShot(110, self._open_eyes_after_blink)

    def _open_eyes_after_blink(self):
        self._blinking = False
        if self._is_offline or self.mood in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING, EyeMood.DEAD_OFFLINE):
            return
        self.target_lh = self.base_lh
        self.target_rh = self.base_rh
        self.target_lw = self.base_lw
        self.target_rw = self.base_rw
        self._wake_physics()

    # ------------------------------------------------------------------
    # Event-Driven 60 FPS LERP Physics Engine (Auto-Sleeps When Settled)
    # ------------------------------------------------------------------
    def _tick_physics(self):
        if not self.isVisible():
            self.physics_timer.stop()
            return

        if self.mood in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING):
            self._mic_phase += 0.26
            if self._mic_phase > math.pi * 200:
                self._mic_phase -= math.pi * 200

            if self.mood == EyeMood.AI_RESPONDING:
                # Continuous harmonic speaking/responding wave (3 rhythmic phase-shifted bars)
                self.target_lh = 9.5 + 7.5 * math.sin(self._mic_phase * 0.9)
                self.target_ch = 13.0 + 9.5 * math.sin(self._mic_phase * 1.1 + 1.2)
                self.target_rh = 9.5 + 7.5 * math.sin(self._mic_phase * 0.9 + 2.4)
                self.target_lw = 4.2
                self.target_rw = 4.2
                self.target_cw = 4.2
                self.target_calpha = 1.0
                self.target_radius = 2.1
            else:
                self._smooth_mic += (self._mic_level - self._smooth_mic) * 0.35
                self._mic_level *= 0.88
                lvl = self._smooth_mic

                idle_wave_l = 1.2 * math.sin(self._mic_phase * 0.7)
                idle_wave_c = 1.5 * math.sin(self._mic_phase * 0.9 + 1.1)
                idle_wave_r = 1.2 * math.sin(self._mic_phase * 0.7 + 2.2)

                voice_l = lvl * (12.5 + 3.5 * math.sin(self._mic_phase * 1.3))
                voice_c = lvl * (14.5 + 3.5 * math.cos(self._mic_phase * 1.5))
                voice_r = lvl * (12.5 + 3.5 * math.sin(self._mic_phase * 1.1 + 1.2))

                self.target_lh = max(5.5, min(22.0, 7.5 + idle_wave_l + voice_l))
                self.target_ch = max(7.0, min(24.0, 10.0 + idle_wave_c + voice_c))
                self.target_rh = max(5.5, min(22.0, 7.5 + idle_wave_r + voice_r))
                self.target_lw = 4.2
                self.target_rw = 4.2
                self.target_cw = 4.2
                self.target_calpha = 1.0
                self.target_radius = 2.1

        k = 0.15
        kh = 0.30 if (self._blinking or self.mood in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING)) else k

        dlx = (self.target_lx - self.cur_lx) * k
        drx = (self.target_rx - self.cur_rx) * k
        dlw = (self.target_lw - self.cur_lw) * k
        drw = (self.target_rw - self.cur_rw) * k
        dlh = (self.target_lh - self.cur_lh) * kh
        drh = (self.target_rh - self.cur_rh) * kh
        dcw = (self.target_cw - self.cur_cw) * k
        dch = (self.target_ch - self.cur_ch) * kh
        dcalpha = (self.target_calpha - self.cur_calpha) * k
        dox = (self.target_ox - self.cur_ox) * k
        doy = (self.target_oy - self.cur_oy) * k
        dldy = (self.target_ldy - self.cur_ldy) * k
        drdy = (self.target_rdy - self.cur_rdy) * k
        drad = (self.target_radius - self.cur_radius) * k
        dlarch = (self.target_larch - self.cur_larch) * k
        drarch = (self.target_rarch - self.cur_rarch) * k
        dxeyes = (self.target_x_eyes - self.cur_x_eyes) * k
        dhearts = (self.target_hearts - self.cur_hearts) * k
        dstars = (self.target_stars - self.cur_stars) * k
        dlslant = (self.target_lslant - self.cur_lslant) * k
        drslant = (self.target_rslant - self.cur_rslant) * k

        dr = (self.target_r - self.cur_r) * k
        dg = (self.target_g - self.cur_g) * k
        db = (self.target_b - self.cur_b) * k

        self.cur_lx += dlx
        self.cur_rx += drx
        self.cur_lw += dlw
        self.cur_rw += drw
        self.cur_lh += dlh
        self.cur_rh += drh
        self.cur_cw += dcw
        self.cur_ch += dch
        self.cur_calpha += dcalpha
        self.cur_ox += dox
        self.cur_oy += doy
        self.cur_ldy += dldy
        self.cur_rdy += drdy
        self.cur_radius += drad
        self.cur_larch += dlarch
        self.cur_rarch += drarch
        self.cur_x_eyes += dxeyes
        self.cur_hearts += dhearts
        self.cur_stars += dstars
        self.cur_lslant += dlslant
        self.cur_rslant += drslant

        self.cur_r += dr
        self.cur_g += dg
        self.cur_b += db

        motion = (
            abs(dlx) + abs(drx) + abs(dlw) + abs(drw) + abs(dlh) + abs(drh)
            + abs(dcw) + abs(dch) + abs(dcalpha)
            + abs(dox) + abs(doy) + abs(dldy) + abs(drdy)
            + abs(drad) + abs(dlarch) + abs(drarch) + abs(dxeyes)
            + abs(dhearts) + abs(dstars) + abs(dlslant) + abs(drslant)
            + (abs(dr) + abs(dg) + abs(db)) * 0.05
        )
        if motion > 0.012:
            self.update()
        elif self.mood not in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING) and not self._blinking:
            self.physics_timer.stop()

    # ------------------------------------------------------------------
    # Vector Rendering (QPainter drawRoundedRect, drawArc, and drawLine)
    # ------------------------------------------------------------------
    def _draw_eye(self, painter, cx, cy, w, h, radius, arch, hearts, stars, slant, eye_color, glow_color):
        if hearts > 0.35:
            scale = min(1.0, max(0.2, hearts))
            hw, hh = w * scale, h * scale
            path = create_heart_path(cx, cy, hw, hh)
            glow_pen = QPen(glow_color, 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.setBrush(glow_color)
            painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(eye_color)
            painter.drawPath(path)
            return

        if stars > 0.35:
            scale = min(1.0, max(0.2, stars))
            ro = max(w, h) * 0.48 * scale
            ri = ro * 0.34
            path = create_star_path(cx, cy, ro, ri)
            glow_pen = QPen(glow_color, 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.setBrush(glow_color)
            painter.drawPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(eye_color)
            painter.drawPath(path)
            return

        if arch > 0.45:
            arch_w = w
            arch_h = max(6.0, h * arch)
            arc_rect = QRectF(cx - arch_w / 2.0, cy - arch_h / 2.0 + 2.0, arch_w, arch_h)
            glow_pen = QPen(glow_color, 5.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(arc_rect, 20 * 16, 140 * 16)
            core_pen = QPen(eye_color, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(core_pen)
            painter.drawArc(arc_rect, 20 * 16, 140 * 16)
            return

        # Standard squircle with optional tilt/slant rotation
        rad = min(radius, w / 2.0, h / 2.0)
        rect = QRectF(-w / 2.0, -h / 2.0, w, h)

        painter.save()
        painter.translate(cx, cy)
        if abs(slant) > 0.5:
            painter.rotate(slant)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow_color)
        painter.drawRoundedRect(rect.adjusted(-1.6, -1.6, 1.6, 1.6), rad + 1.4, rad + 1.4)
        painter.setBrush(eye_color)
        painter.drawRoundedRect(rect, rad, rad)
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        cy = h / 2.0 + self.cur_oy

        center_x = w / 2.0 + self.cur_ox
        left_cx = center_x + self.cur_lx
        right_cx = center_x + self.cur_rx

        r = int(max(0, min(255, self.cur_r)))
        g = int(max(0, min(255, self.cur_g)))
        b = int(max(0, min(255, self.cur_b)))

        eye_color = QColor(r, g, b)
        glow_color = QColor(r, g, b, 68)

        # 1. Render DEAD_OFFLINE Crossed 'X  X' Eyes in Red when offline
        if self.cur_x_eyes > 0.35 and self.cur_calpha < 0.2:
            scale = max(0.4, min(1.0, self.cur_x_eyes))
            dx = (self.cur_lw * 0.44) * scale
            dy = (self.cur_lh * 0.44) * scale

            glow_pen = QPen(glow_color, 5.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for cx, ey_off in ((left_cx, self.cur_ldy), (right_cx, self.cur_rdy)):
                ey = cy + ey_off
                painter.drawLine(QPointF(cx - dx, ey - dy), QPointF(cx + dx, ey + dy))
                painter.drawLine(QPointF(cx - dx, ey + dy), QPointF(cx + dx, ey - dy))

            core_pen = QPen(eye_color, 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(core_pen)
            for cx, ey_off in ((left_cx, self.cur_ldy), (right_cx, self.cur_rdy)):
                ey = cy + ey_off
                painter.drawLine(QPointF(cx - dx, ey - dy), QPointF(cx + dx, ey + dy))
                painter.drawLine(QPointF(cx - dx, ey + dy), QPointF(cx + dx, ey - dy))
            return

        # 2. Render COMMAND_MIC / AI_RESPONDING Mode (3 bouncing vertical voice equalizer / responding lines)
        if self.mood in (EyeMood.COMMAND_MIC, EyeMood.AI_RESPONDING) or self.cur_calpha > 0.05:
            ca = max(0.0, min(1.0, self.cur_calpha))
            cw = max(2.0, self.cur_cw)
            c_rad = min(self.cur_radius, cw / 2.0)

            if self.mood == EyeMood.AI_RESPONDING:
                # Responsive glowing cyan/teal wave for speech response
                pulse = 0.85 + 0.15 * math.sin(self._mic_phase * 1.5)
                c_glow = QColor(0, int(220 * pulse), int(255 * pulse), int(90 * ca * pulse))
                c_core = QColor(30, int(245 * pulse), 255, int(255 * ca))
            else:
                c_glow = QColor(r, g, b, int(68 * ca))
                c_core = QColor(r, g, b, int(255 * ca))

            for cx_pos, h_val in (
                (left_cx, self.cur_lh),
                (center_x, self.cur_ch),
                (right_cx, self.cur_rh)
            ):
                line_rect = QRectF(cx_pos - cw / 2.0, cy - h_val / 2.0, cw, h_val)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(c_glow)
                painter.drawRoundedRect(line_rect.adjusted(-1.8, -1.8, 1.8, 1.8), c_rad + 1.4, c_rad + 1.4)
                painter.setBrush(c_core)
                painter.drawRoundedRect(line_rect, c_rad, c_rad)
            return

        # 3. Render Left and Right Eyes (supports standard squircle, arches, hearts, stars, slants)
        lw, lh = max(2.0, self.cur_lw), max(2.0, self.cur_lh)
        rw, rh = max(2.0, self.cur_rw), max(2.0, self.cur_rh)

        self._draw_eye(
            painter, left_cx, cy + self.cur_ldy, lw, lh,
            self.cur_radius, self.cur_larch, self.cur_hearts, self.cur_stars, self.cur_lslant,
            eye_color, glow_color
        )
        self._draw_eye(
            painter, right_cx, cy + self.cur_rdy, rw, rh,
            self.cur_radius, self.cur_rarch, self.cur_hearts, self.cur_stars, self.cur_rslant,
            eye_color, glow_color
        )


IslandEyes = DynamicIslandEyes
