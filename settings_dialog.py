import json
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QStackedWidget,
    QComboBox, QCheckBox, QSlider, QLineEdit, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QColor, QFont, QPainter, QIcon

COMBO_STYLE = """
    QComboBox {
        background-color: #2C2C2E;
        color: #FFFFFF;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 6px;
        padding: 4px 12px;
        font-family: 'SF Pro Display', 'Segoe UI', sans-serif;
        font-size: 12px;
    }
    QComboBox:hover {
        background-color: #36363A;
        border-color: rgba(255, 255, 255, 0.25);
    }
    QComboBox::drop-down {
        border: none;
        width: 18px;
    }
    QComboBox QAbstractItemView {
        background-color: #1E1E22;
        color: #FFFFFF;
        selection-background-color: rgba(0, 255, 204, 0.25);
        selection-color: #00ffcc;
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 6px;
        padding: 4px;
        outline: none;
    }
    QComboBox QAbstractItemView::item {
        min-height: 26px;
        padding: 4px 10px;
        color: #E5E5EA;
        border-radius: 4px;
    }
    QComboBox QAbstractItemView::item:hover {
        background-color: rgba(255, 255, 255, 0.12);
        color: #FFFFFF;
    }
    QComboBox QAbstractItemView::item:selected {
        background-color: rgba(0, 255, 204, 0.2);
        color: #00ffcc;
        font-weight: bold;
    }
"""

class AppleToggle(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QCheckBox { background: transparent; }")

    def hitButton(self, pos: QPoint) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Track
        rect = self.rect()
        painter.setPen(Qt.PenStyle.NoPen)
        if self.isChecked():
            painter.setBrush(QColor(48, 209, 88))
        else:
            painter.setBrush(QColor(57, 57, 61))
        painter.drawRoundedRect(rect, 13, 13)
        
        # Knob
        painter.setBrush(QColor(255, 255, 255))
        if self.isChecked():
            painter.drawEllipse(22, 2, 22, 22)
        else:
            painter.drawEllipse(2, 2, 22, 22)

class SettingsCard(QFrame):
    def __init__(self, title, subtitle, control_widget, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            SettingsCard {
                background-color: #1E1E22;
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        self.setFixedHeight(54)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: white; font-size: 14px; font-weight: 500; font-family: 'SF Pro Display', 'Segoe UI';")
        
        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setStyleSheet("color: #86868B; font-size: 12px; font-family: 'SF Pro Display', 'Segoe UI';")
        
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(subtitle_lbl)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(control_widget)

class MinimalSettingsDialog(QDialog):
    settings_saved = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(620, 420)
        
        self.cfg_path = os.path.expanduser("~/.dynamic_island_settings.json")
        self.cfg = self.load_settings()
        
        self.drag_pos = None
        
        self.init_ui()

    def load_settings(self):
        import config
        return config.load_config()
        
    def save_settings(self):
        import config
        config.save_config(self.cfg)
        self.settings_saved.emit(self.cfg)
        self.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(22, 22, 24, 255))
        painter.setPen(QColor(255, 255, 255, 20)) # 0.08 alpha border
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 16, 16)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()
    
    def mouseMoveEvent(self, event):
        if self.drag_pos is not None:
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + delta)
            self.drag_pos = event.globalPosition().toPoint()
            
    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # --- SIDEBAR ---
        sidebar = QWidget()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-right: 1px solid rgba(255, 255, 255, 0.05);
            }
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                color: #9A9A9E;
                font-family: 'SF Pro Display', 'Segoe UI';
                font-size: 13px;
                font-weight: 500;
                padding: 10px 14px;
                border-radius: 8px;
                margin: 4px 8px;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.04);
                color: #D1D1D6;
            }
            QListWidget::item:selected {
                background-color: rgba(255, 255, 255, 0.09);
                color: #FFFFFF;
                font-weight: 600;
            }
        """)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 0)
        
        self.nav_list = QListWidget()
        for item in ["General", "Appearance", "Workspaces", "API & Safety"]:
            self.nav_list.addItem(item)
        self.nav_list.setCurrentRow(0)
        sidebar_layout.addWidget(self.nav_list)
        
        content_layout.addWidget(sidebar)
        
        # --- MAIN PAGES ---
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background: transparent;")
        
        self.init_general_page()
        self.init_appearance_page()
        self.init_workspaces_page()
        self.init_api_page()
        
        self.nav_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        
        content_layout.addWidget(self.pages)
        main_layout.addWidget(content_widget)
        
        # --- FOOTER ---
        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet("""
            QWidget {
                border-top: 1px solid rgba(255, 255, 255, 0.06);
                background: transparent;
            }
            QPushButton#btnQuit {
                color: #FF453A;
                font-family: 'SF Pro Display', 'Segoe UI';
                font-size: 13px;
                background: transparent;
                border: none;
                font-weight: 500;
            }
            QPushButton#btnQuit:hover {
                color: #FF6961;
            }
            QPushButton#btnCancel {
                color: white;
                font-family: 'SF Pro Display', 'Segoe UI';
                font-size: 13px;
                background: transparent;
                border: none;
                padding: 6px 16px;
                border-radius: 6px;
            }
            QPushButton#btnCancel:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            QPushButton#btnDone {
                color: black;
                background: white;
                font-family: 'SF Pro Display', 'Segoe UI';
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 14px;
                padding: 6px 24px;
            }
            QPushButton#btnDone:hover {
                background: #E5E5EA;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 0)
        
        btn_quit = QPushButton("Quit Zenith OS")
        btn_quit.setObjectName("btnQuit")
        btn_quit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_quit.clicked.connect(self._quit_app)
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        
        btn_done = QPushButton("Done")
        btn_done.setObjectName("btnDone")
        btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_done.clicked.connect(self._save_and_close)
        
        footer_layout.addWidget(btn_quit)
        footer_layout.addStretch()
        footer_layout.addWidget(btn_cancel)
        footer_layout.addWidget(btn_done)
        
        main_layout.addWidget(footer)

    def _create_page_container(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(20, 14, 20, 14)
        l.setSpacing(8)
        l.setAlignment(Qt.AlignmentFlag.AlignTop)
        return w, l

    def init_general_page(self):
        page, layout = self._create_page_container()
        
        cb_voice = QComboBox()
        cb_voice.addItems(["Emo", "Female", "Male", "Ultron"])
        cb_voice.setCurrentText(self.cfg.get("voice", "Emo"))
        cb_voice.setStyleSheet(COMBO_STYLE)
        cb_voice.currentTextChanged.connect(self._live_save)
        
        self.toggle_duck = AppleToggle()
        self.toggle_duck.setChecked(self.cfg.get("audio_ducking", True))
        self.toggle_duck.toggled.connect(self._live_save)
        
        self.toggle_startup = AppleToggle()
        self.toggle_startup.setChecked(self.cfg.get("launch_at_login", False))
        
        self.toggle_hotkey = AppleToggle()
        self.toggle_hotkey.setChecked(self.cfg.get("enable_hotkey", True))
        self.toggle_hotkey.toggled.connect(self._live_save)

        self.toggle_ambient_glow = AppleToggle()
        self.toggle_ambient_glow.setChecked(self.cfg.get("music_ambient_glow", True))
        self.toggle_ambient_glow.toggled.connect(self._live_save)

        layout.addWidget(SettingsCard("AI Voice", "Select the voice (Emo cute robot, Ultron, Female, or Male)", cb_voice))
        layout.addWidget(SettingsCard("Voice Shortcut (Ctrl+Space)", "Enable global hotkey (Ctrl + Space) for Voice Assistant", self.toggle_hotkey))
        layout.addWidget(SettingsCard("Music Ambient Glow", "Soft ambient color glow behind album art", self.toggle_ambient_glow))
        layout.addWidget(SettingsCard("Media Ducking", "Lower background volume while listening to commands", self.toggle_duck))
        layout.addWidget(SettingsCard("Launch at Login", "Start Zenith OS automatically when Windows boots", self.toggle_startup))

        # Quick Actions (3 hover buttons)
        qa = self.cfg.get("quick_actions", ["music", "timer", "clipboard"])
        action_options = ["Music", "Timer", "System", "Clipboard", "Voice Assistant"]
        action_map = {"Music": "music", "Timer": "timer", "System": "system", "Clipboard": "clipboard", "Voice Assistant": "voice"}
        rev_map = {v: k for k, v in action_map.items()}

        combo_qss = COMBO_STYLE

        self.cb_qa1 = QComboBox()
        self.cb_qa1.addItems(action_options)
        self.cb_qa1.setCurrentText(rev_map.get(qa[0] if len(qa) > 0 else "music", "Music"))
        self.cb_qa1.setStyleSheet(combo_qss)
        self.cb_qa1.currentTextChanged.connect(self._live_save)

        self.cb_qa2 = QComboBox()
        self.cb_qa2.addItems(action_options)
        self.cb_qa2.setCurrentText(rev_map.get(qa[1] if len(qa) > 1 else "timer", "Timer"))
        self.cb_qa2.setStyleSheet(combo_qss)
        self.cb_qa2.currentTextChanged.connect(self._live_save)

        self.cb_qa3 = QComboBox()
        self.cb_qa3.addItems(action_options)
        self.cb_qa3.setCurrentText(rev_map.get(qa[2] if len(qa) > 2 else "clipboard", "Clipboard"))
        self.cb_qa3.setStyleSheet(combo_qss)
        self.cb_qa3.currentTextChanged.connect(self._live_save)

        layout.addWidget(SettingsCard("Quick Action 1", "Slot 1 button when hovering over notch", self.cb_qa1))
        layout.addWidget(SettingsCard("Quick Action 2", "Slot 2 button when hovering over notch", self.cb_qa2))
        layout.addWidget(SettingsCard("Quick Action 3", "Slot 3 button when hovering over notch", self.cb_qa3))
        
        self.cb_voice = cb_voice
        self.pages.addWidget(page)

    def init_appearance_page(self):
        page, layout = self._create_page_container()
        
        w_slider = QSlider(Qt.Orientation.Horizontal)
        w_slider.setRange(68, 300)
        w_slider.setValue(max(68, min(300, int(self.cfg.get("compact_width", 180)))))
        w_slider.setFixedWidth(130)
        w_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        w_slider.setStyleSheet("QSlider::handle:horizontal { background: #FFFFFF; border-radius: 7px; width: 14px; height: 14px; margin: -5px 0; } QSlider::groove:horizontal { background: #3A3A3C; height: 4px; border-radius: 2px; } QSlider::sub-page:horizontal { background: #00F0FF; height: 4px; border-radius: 2px; }")
        
        self.toggle_collapse = AppleToggle()
        self.toggle_collapse.setChecked(self.cfg.get("auto_collapse", False))
        self.toggle_collapse.toggled.connect(self._live_save)
        
        cb_display = QComboBox()
        cb_display.addItems(["Primary Display", "Follow Active Mouse"])
        cb_display.setCurrentText(self.cfg.get("target_display", "Primary Display"))
        cb_display.setStyleSheet(COMBO_STYLE)
        cb_display.currentTextChanged.connect(self._live_save)
        
        cb_stats_mode = QComboBox()
        cb_stats_mode.addItems(["Only Emo Eyes", "Clock & Battery", "Only Clock", "Only Battery", "System Stats", "All Stats"])
        saved_mode = self.cfg.get("display_mode", "Clock & Battery")
        if saved_mode in ["Only Eyes", "Only Emo Eyes"]:
            saved_mode = "Only Emo Eyes"
        cb_stats_mode.setCurrentText(saved_mode)
        cb_stats_mode.setStyleSheet(COMBO_STYLE)
        cb_stats_mode.currentTextChanged.connect(self._live_save)
        
        self.toggle_eyes = AppleToggle()
        self.toggle_eyes.setChecked(self.cfg.get("companion_eyes", True))
        self.toggle_eyes.toggled.connect(self._live_save)
        
        layout.addWidget(SettingsCard("Companion Robot Eyes", "Show expressive animated robot eyes on idle", self.toggle_eyes))
        layout.addWidget(SettingsCard("Idle Display Mode", "Select what stats are shown on the resting island", cb_stats_mode))
        layout.addWidget(SettingsCard("Compact Size", "Width of the idle island (down to Emo Eyes width)", w_slider))
        layout.addWidget(SettingsCard("Auto-Collapse", "Tuck notch subtly into the top screen edge when inactive", self.toggle_collapse))
        layout.addWidget(SettingsCard("Active Display", "Choose which monitor hosts the island", cb_display))
        
        self.w_slider = w_slider
        self.w_slider.valueChanged.connect(self._live_save)
        self.cb_display = cb_display
        self.cb_stats_mode = cb_stats_mode
        self.pages.addWidget(page)

    def _live_save(self, *args):
        if hasattr(self, 'w_slider'):
            self.cfg["compact_width"] = self.w_slider.value()
        if hasattr(self, 'cb_stats_mode'):
            mode = self.cb_stats_mode.currentText()
            self.cfg["display_mode"] = mode
            if mode == "Only Emo Eyes" and hasattr(self, 'toggle_eyes') and not self.toggle_eyes.isChecked():
                self.toggle_eyes.blockSignals(True)
                self.toggle_eyes.setChecked(True)
                self.toggle_eyes. _offset = 22
                self.toggle_eyes.update()
                self.toggle_eyes.blockSignals(False)
        if hasattr(self, 'toggle_eyes'):
            self.cfg["companion_eyes"] = self.toggle_eyes.isChecked()
        if hasattr(self, 'toggle_collapse'):
            self.cfg["auto_collapse"] = self.toggle_collapse.isChecked()
        if hasattr(self, 'cb_display'):
            self.cfg["target_display"] = self.cb_display.currentText()
        if hasattr(self, 'cb_voice'):
            self.cfg["voice"] = self.cb_voice.currentText()
        if hasattr(self, 'toggle_duck'):
            self.cfg["audio_ducking"] = self.toggle_duck.isChecked()
        if hasattr(self, 'toggle_hotkey'):
            self.cfg["enable_hotkey"] = self.toggle_hotkey.isChecked()
        if hasattr(self, 'toggle_ambient_glow'):
            self.cfg["music_ambient_glow"] = self.toggle_ambient_glow.isChecked()
        if hasattr(self, 'toggle_ws_capture'):
            self.cfg["auto_capture_workspaces"] = self.toggle_ws_capture.isChecked()
        if hasattr(self, 'cb_qa1') and hasattr(self, 'cb_qa2') and hasattr(self, 'cb_qa3'):
            action_map = {"Music": "music", "Timer": "timer", "System": "system", "Clipboard": "clipboard", "Voice Assistant": "voice"}
            self.cfg["quick_actions"] = [
                action_map.get(self.cb_qa1.currentText(), "music"),
                action_map.get(self.cb_qa2.currentText(), "timer"),
                action_map.get(self.cb_qa3.currentText(), "clipboard"),
            ]
        import config
        config.save_config(self.cfg)
        self.settings_saved.emit(self.cfg)

    def init_workspaces_page(self):
        page, layout = self._create_page_container()
        
        self.toggle_ws_capture = AppleToggle()
        self.toggle_ws_capture.setChecked(self.cfg.get("auto_capture_workspaces", True))
        self.toggle_ws_capture.toggled.connect(self._live_save)
        layout.addWidget(SettingsCard("Auto-Capture Windows", "Scan and capture open apps when creating a workspace", self.toggle_ws_capture))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        self.ws_layout = QVBoxLayout(content)
        self.ws_layout.setContentsMargins(0,0,0,0)
        self.ws_layout.setSpacing(8)
        self.ws_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.refresh_workspaces()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        btn_add = QPushButton("+ Add Workspace")
        btn_add.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px dashed rgba(255, 255, 255, 0.2);
                color: #86868B;
                border-radius: 8px;
                padding: 12px;
                font-family: 'SF Pro Display', 'Segoe UI';
                font-weight: 500;
            }
            QPushButton:hover {
                color: white;
                border-color: rgba(255, 255, 255, 0.5);
            }
        """)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._add_workspace)
        layout.addWidget(btn_add)
        
        self.pages.addWidget(page)

    def refresh_workspaces(self):
        import workspace_engine
        for i in reversed(range(self.ws_layout.count())):
            w = self.ws_layout.itemAt(i).widget()
            if w is not None:
                w.setParent(None)

        workspaces = workspace_engine.load_workspaces()

        for name, app_list in workspaces.items():
            card = QFrame()
            card.setStyleSheet("QFrame { background: #1E1E22; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); }")
            card.setFixedHeight(52)
            clayout = QHBoxLayout(card)
            clayout.setContentsMargins(12, 0, 12, 0)

            lbl = QLabel(name.upper())
            lbl.setStyleSheet("color: white; font-weight: bold; font-family: 'SF Pro Display', 'Segoe UI'; border: none;")

            app_names = [workspace_engine.display_name(a) for a in app_list]
            app_text = ", ".join(app_names[:4]) if app_names else "No apps added yet"
            if len(app_names) > 4:
                app_text += f" (+{len(app_names) - 4})"

            sub = QLabel(app_text)
            sub.setStyleSheet("color: #86868B; font-size: 11px; border: none;")

            left_v = QVBoxLayout()
            left_v.setSpacing(0)
            left_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            left_v.addWidget(lbl)
            left_v.addWidget(sub)

            btn_launch = QPushButton("Launch")
            btn_launch.setStyleSheet("QPushButton { background: #143322; color: #30D158; border-radius: 4px; padding: 4px 10px; border: none; font-size: 11px; font-weight: bold; } QPushButton:hover { background: #1E4730; }")
            btn_launch.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_launch.clicked.connect(lambda checked, n=name, b=btn_launch: self._launch_workspace(n, b))

            btn_edit = QPushButton("+ Add / Edit Apps")
            btn_edit.setStyleSheet("QPushButton { background: #1F2D3A; color: #00F0FF; border-radius: 4px; padding: 4px 8px; border: none; font-size: 11px; } QPushButton:hover { background: #293D4F; }")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.clicked.connect(lambda checked, n=name, al=list(app_list): self._open_workspace_editor(n, al))

            btn_del = QPushButton("Trash")
            btn_del.setStyleSheet("QPushButton { background: #331111; color: #FF4444; border-radius: 4px; padding: 4px 8px; border: none; font-size: 11px; } QPushButton:hover { background: #441111; }")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.clicked.connect(lambda checked, n=name: self._del_workspace(n))

            clayout.addLayout(left_v)
            clayout.addStretch()
            clayout.addWidget(btn_launch)
            clayout.addWidget(btn_edit)
            clayout.addWidget(btn_del)

            self.ws_layout.addWidget(card)

    def _launch_workspace(self, name, btn=None):
        import workspace_engine
        from PyQt6.QtCore import QTimer
        if btn is not None:
            btn.setText("Launching...")
            btn.setEnabled(False)

        def _done(res):
            if btn is not None:
                def _restore():
                    try:
                        btn.setText("Launched ✓" if res.get("success") else "Failed")
                        btn.setEnabled(True)
                        QTimer.singleShot(1800, lambda: btn.setText("Launch"))
                    except RuntimeError:
                        pass
                QTimer.singleShot(0, _restore)

        workspace_engine.launch_workspace_async(name, callback=_done)

    def _open_workspace_editor(self, ws_name="", existing_apps=None):
        import workspace_engine
        from PyQt6.QtWidgets import QFileDialog, QListWidgetItem

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Workspace" if ws_name else "New Workspace")
        dlg.setFixedSize(460, 420)
        dlg.setStyleSheet("""
            QDialog { background-color: #1A1A1E; color: white; border-radius: 12px; }
            QLabel { color: #E5E5EA; font-family: 'SF Pro Display', 'Segoe UI'; font-size: 12px; }
            QLineEdit { background: #2C2C2E; color: white; border-radius: 6px; padding: 6px 10px; border: 1px solid #3A3A3C; }
            QListWidget { background: #121214; color: white; border-radius: 6px; border: 1px solid #2C2C2E; padding: 4px; font-size: 12px; }
            QListWidget::item { padding: 5px; border-bottom: 1px solid #1E1E22; }
            QPushButton { background: #2C2C2E; color: white; border-radius: 6px; padding: 6px 12px; border: none; font-size: 12px; }
            QPushButton:hover { background: #3A3A3C; }
        """)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(8)

        # 1. Name input
        v.addWidget(QLabel("Workspace Name:"))
        name_input = QLineEdit(ws_name)
        name_input.setPlaceholderText("e.g. Power, Gaming, Coding, Study")
        v.addWidget(name_input)

        # 2. Apps list
        lbl_apps_header = QLabel("Apps in Workspace (select an app and click Remove to delete):")
        v.addWidget(lbl_apps_header)
        app_list_w = QListWidget()
        v.addWidget(app_list_w)

        status_lbl = QLabel("")
        status_lbl.setStyleSheet("color: #00F0FF; font-size: 11px;")
        v.addWidget(status_lbl)

        current_apps = list(existing_apps or [])
        if not ws_name and self.cfg.get("auto_capture_workspaces", True) and not current_apps:
            res = workspace_engine.capture_active_windows()
            current_apps = list(res.get("apps", []) if isinstance(res, dict) else res)
            if current_apps:
                status_lbl.setText(f"Auto-captured {len(current_apps)} currently open window(s).")

        def _repopulate():
            app_list_w.clear()
            for a in current_apps:
                friendly = workspace_engine.display_name(a)
                display = f"{friendly}   —   {a}" if friendly.lower() != a.lower() else friendly
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, a)
                app_list_w.addItem(item)
            lbl_apps_header.setText(f"Apps in Workspace ({len(current_apps)}):")

        _repopulate()

        # 3. Manual add / Browse .exe / Capture open windows row
        add_row = QHBoxLayout()
        txt_app = QLineEdit()
        txt_app.setPlaceholderText("Type app name (e.g. chrome, spotify, discord, code) & press + Add")
        btn_add_manual = QPushButton("+ Add")
        btn_add_manual.setStyleSheet("background: #1F2D3A; color: #00F0FF; font-weight: bold;")
        btn_browse = QPushButton("Browse .exe")

        def _on_add_manual():
            val = txt_app.text().strip()
            if not val:
                return 0
            added = 0
            existing_low = {x.lower() for x in current_apps}
            existing_disp = {workspace_engine.display_name(x).lower() for x in current_apps}
            for part in val.split(","):
                p = part.strip().strip('"')
                if not p:
                    continue
                resolved = workspace_engine.resolve_launch_target(p)
                token = workspace_engine.normalize_app_token(resolved or p)
                if token.lower() not in existing_low and workspace_engine.display_name(token).lower() not in existing_disp:
                    existing_low.add(token.lower())
                    existing_disp.add(workspace_engine.display_name(token).lower())
                    current_apps.append(token)
                    added += 1
            txt_app.clear()
            _repopulate()
            if added:
                status_lbl.setText(f"Added {added} app(s) to list.")
            return added

        def _on_browse():
            fpath, _ = QFileDialog.getOpenFileName(
                dlg, "Select Application or Shortcut", os.path.expanduser("~"),
                "Applications & Shortcuts (*.exe *.lnk *.url *.bat *.cmd)"
            )
            if fpath:
                tok = workspace_engine.normalize_app_token(fpath)
                if tok.lower() not in {x.lower() for x in current_apps}:
                    current_apps.append(tok)
                    _repopulate()
                    status_lbl.setText(f"Added {workspace_engine.display_name(tok)}.")

        btn_add_manual.clicked.connect(_on_add_manual)
        txt_app.returnPressed.connect(_on_add_manual)
        btn_browse.clicked.connect(_on_browse)
        add_row.addWidget(txt_app)
        add_row.addWidget(btn_add_manual)
        add_row.addWidget(btn_browse)
        v.addLayout(add_row)

        # 4. Action buttons row (Capture Open Windows, Remove Selected, Save)
        act_row = QHBoxLayout()
        btn_cap_open = QPushButton("+ Capture Open Windows")
        btn_rem_sel = QPushButton("Remove Selected")
        btn_rem_sel.setStyleSheet("background: #331111; color: #FF5555;")
        btn_save_ws = QPushButton("Save Workspace")
        btn_save_ws.setStyleSheet("background: #00F0FF; color: black; font-weight: bold;")

        def _on_capture_open():
            res = workspace_engine.capture_active_windows()
            captured = res.get("apps", []) if isinstance(res, dict) else res
            existing_low = {x.lower() for x in current_apps}
            existing_disp = {workspace_engine.display_name(x).lower() for x in current_apps}
            added = 0
            for c in captured:
                d = workspace_engine.display_name(c).lower()
                if c.lower() not in existing_low and d not in existing_disp:
                    existing_low.add(c.lower())
                    existing_disp.add(d)
                    current_apps.append(c)
                    added += 1
            _repopulate()
            status_lbl.setText(f"Captured {added} new open window(s) ({len(captured)} total detected).")

        def _on_remove_selected():
            row = app_list_w.currentRow()
            if 0 <= row < len(current_apps):
                removed = current_apps.pop(row)
                _repopulate()
                status_lbl.setText(f"Removed {workspace_engine.display_name(removed)}.")

        def _on_save():
            # Always flush any text typed into the app box even if user didn't click '+ Add' first!
            if txt_app.text().strip():
                _on_add_manual()
            final_name = name_input.text().strip().lower()
            if not final_name:
                status_lbl.setText("Please enter a workspace name first.")
                name_input.setFocus()
                return
            all_ws = workspace_engine.load_workspaces()
            if not ws_name and final_name in all_ws:
                # User entered an existing workspace name in "+ Add Workspace": merge apps!
                workspace_engine.manage_workspace("edit", final_name, apps=current_apps)
            else:
                if ws_name and ws_name.lower() != final_name:
                    workspace_engine.manage_workspace("delete", ws_name)
                workspace_engine.manage_workspace("create", final_name, apps=current_apps)
            dlg.accept()
            self.refresh_workspaces()

        btn_cap_open.clicked.connect(_on_capture_open)
        btn_rem_sel.clicked.connect(_on_remove_selected)
        btn_save_ws.clicked.connect(_on_save)

        act_row.addWidget(btn_cap_open)
        act_row.addWidget(btn_rem_sel)
        act_row.addStretch()
        act_row.addWidget(btn_save_ws)
        v.addLayout(act_row)

        dlg.exec()

    def _del_workspace(self, name):
        import workspace_engine
        workspace_engine.manage_workspace('delete', name)
        self.refresh_workspaces()
        
    def _add_workspace(self):
        self._open_workspace_editor("", [])

    def init_api_page(self):
        page, layout = self._create_page_container()
        
        self.api_input = QLineEdit()
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setPlaceholderText("gsk_••••••••••••")
        self.api_input.setText(self.cfg.get("groq_api_key", ""))
        self.api_input.setFixedWidth(160)
        self.api_input.setStyleSheet("QLineEdit { background: #2C2C2E; color: white; border-radius: 6px; padding: 4px 10px; border: none; }")
        
        badge = QLabel("● Active Sandboxing")
        badge.setStyleSheet("color: #30D158; font-family: 'SF Pro Display', 'Segoe UI'; font-size: 12px; font-weight: bold; background: rgba(48, 209, 88, 0.1); padding: 4px 8px; border-radius: 6px;")
        
        layout.addWidget(SettingsCard("Groq API Token", "Neural engine backend authentication", self.api_input))
        layout.addWidget(SettingsCard("Protected Directories", "System root locations are locked by default", badge))
        
        self.pages.addWidget(page)

    def _save_and_close(self):
        self.cfg["voice"] = self.cb_voice.currentText()
        self.cfg["audio_ducking"] = self.toggle_duck.isChecked()
        self.cfg["launch_at_login"] = self.toggle_startup.isChecked()
        if hasattr(self, 'toggle_hotkey'):
            self.cfg["enable_hotkey"] = self.toggle_hotkey.isChecked()
        if hasattr(self, 'toggle_ambient_glow'):
            self.cfg["music_ambient_glow"] = self.toggle_ambient_glow.isChecked()
        self.cfg["compact_width"] = self.w_slider.value()
        self.cfg["auto_collapse"] = self.toggle_collapse.isChecked()
        self.cfg["target_display"] = self.cb_display.currentText()
        if hasattr(self, 'cb_stats_mode'):
            self.cfg["display_mode"] = self.cb_stats_mode.currentText()
        if hasattr(self, 'toggle_eyes'):
            self.cfg["companion_eyes"] = self.toggle_eyes.isChecked()
        if hasattr(self, 'toggle_ws_capture'):
            self.cfg["auto_capture_workspaces"] = self.toggle_ws_capture.isChecked()
        if hasattr(self, 'cb_qa1') and hasattr(self, 'cb_qa2') and hasattr(self, 'cb_qa3'):
            action_map = {"Music": "music", "Timer": "timer", "System": "system", "Clipboard": "clipboard", "Voice Assistant": "voice"}
            self.cfg["quick_actions"] = [
                action_map.get(self.cb_qa1.currentText(), "music"),
                action_map.get(self.cb_qa2.currentText(), "timer"),
                action_map.get(self.cb_qa3.currentText(), "clipboard"),
            ]
        self.cfg["groq_api_key"] = self.api_input.text()
        self.save_settings()
        self._apply_launch_at_login()

    def _apply_launch_at_login(self):
        import winreg
        import sys, os
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "ZenithDynamicIsland"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if self.cfg.get("launch_at_login", False):
                script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Launch_Island.bat"))
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{script_path}"')
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except OSError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print("Failed to set registry key:", e)

    def _quit_app(self):
        import sys
        sys.exit(0)
