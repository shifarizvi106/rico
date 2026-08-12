#!/usr/bin/env python3
import sys
import os
import datetime
import json
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, List, Any

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QStatusBar,
    QSystemTrayIcon, QMenu, QShortcut, QInputDialog, QFileDialog,
    QDialog, QDialogButtonBox, QTabWidget, QFormLayout, QSpinBox,
    QComboBox, QCheckBox, QGroupBox, QScrollArea, QFrame,
    QMessageBox, QProgressBar, QSplitter, QPlainTextEdit,
    QToolButton, QMenuBar, QAction, QGridLayout, QSizePolicy,
    QSplashScreen, QPixmap, QPainter, QFont, QColor, QPen,
    QMargins, QKeySequence, QTextCursor
)
from PyQt5.QtCore import (
    Qt, QThread, QObject, pyqtSignal, QRunnable, QThreadPool,
    QTimer, QSize, QPoint
)
from PyQt5.QtGui import (
    QFontDatabase, QIcon, QKeyEvent, QTextCharFormat, QTextCursor,
    QPalette, QLinearGradient, QGradient, QBrush
)

# Lazy import RicoAssistant to avoid blocking GUI startup
_RicoAssistant: Optional[Any] = None


def _import_rico() -> Any:
    """Lazy-load the RicoAssistant class."""
    global _RicoAssistant
    if _RicoAssistant is None:
        from rico import RicoAssistant
        _RicoAssistant = RicoAssistant
    return _RicoAssistant


# ---------------------------------------------------------------------------
# Stylesheet — Professional Rose-Gold Theme
# ---------------------------------------------------------------------------
PROFESSIONAL_PINK_THEME = """
/* Main Window */
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1a1218, stop:1 #2d1f2a);
}

/* Central Widget */
QWidget#centralWidget {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2d1f2a, stop:0.6 #231820, stop:1 #1a1218);
    border: 2px solid #c0809f;
    border-radius: 20px;
}

/* Chat Display */
QTextEdit#chatDisplay {
    background: #141015;
    color: #f5e6ee;
    border: 1px solid #3d2b35;
    border-radius: 16px;
    padding: 14px;
    font-size: 14px;
    line-height: 1.4;
    selection-background-color: #5a3d4d;
}

/* Message Input */
QLineEdit#messageInput {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1f161c, stop:1 #2a1e25);
    color: #f5e6ee;
    border: 1px solid #5a3d4d;
    border-radius: 18px;
    padding: 10px 18px;
    font-size: 14px;
}
QLineEdit#messageInput:focus {
    border: 1px solid #c0809f;
}
QLineEdit#messageInput::placeholder {
    color: #7a5a6a;
}

/* Standard Buttons */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d484a8, stop:0.3 #c07094, stop:0.7 #a85e7e, stop:1 #8f4f6a);
    color: #ffffff;
    border: 1px solid #b07090;
    border-radius: 14px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e8a0bf, stop:0.3 #d484a8, stop:0.7 #b86e8e, stop:1 #9e5f78);
}
QPushButton:pressed {
    background: #7a4058;
    border: 1px solid #5a3d4d;
}
QPushButton:disabled {
    background: #3d2b35;
    color: #7a5a6a;
    border: 1px solid #2d1f2a;
}

/* Voice Button */
QPushButton#voiceButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e8a0bf, stop:0.5 #c07094, stop:1 #8f4f6a);
    border: 2px solid #d484a8;
    border-radius: 22px;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton#voiceButton:checked {
    background: #ff3366;
    border: 2px solid #ff5588;
}

/* Quick Action Buttons */
QPushButton#quickButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c07094, stop:0.5 #a85e7e, stop:1 #8f4f6a);
    color: #ffffff;
    border-radius: 10px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 500;
}
QPushButton#quickButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #d484a8, stop:0.5 #b86e8e, stop:1 #9e5f78);
}
QPushButton#quickButton:pressed {
    background: #7a4058;
}

/* Status Bar */
QStatusBar {
    background: #141015;
    color: #c0809f;
    font-weight: 600;
    border-top: 1px solid #3d2b35;
}
QStatusBar::item {
    border: none;
}

/* Menu Bar */
QMenuBar {
    background: #1a1218;
    color: #f5e6ee;
    border-bottom: 1px solid #3d2b35;
    padding: 2px 8px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background: #3d2b35;
    color: #f5e6ee;
}
QMenuBar::item:pressed {
    background: #5a3d4d;
}

/* Menus */
QMenu {
    background: #1f161c;
    color: #f5e6ee;
    border: 1px solid #3d2b35;
    padding: 6px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #5a3d4d;
}
QMenu::separator {
    height: 1px;
    background: #3d2b35;
    margin: 4px 8px;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #141015;
    width: 10px;
    border-radius: 5px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #5a3d4d;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #7a5a6a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: #141015;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #5a3d4d;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #7a5a6a;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Header Labels */
QLabel#headerLabel {
    color: #e8a0bf;
    font-size: 24px;
    font-weight: 900;
    letter-spacing: 2px;
}
QLabel#statusLabel {
    color: #88ccaa;
    font-weight: 600;
    font-size: 12px;
}
QLabel#typingLabel {
    color: #c0809f;
    font-style: italic;
    font-size: 12px;
    padding: 4px 12px;
}

/* Dialogs */
QDialog {
    background: #1f161c;
    color: #f5e6ee;
}
QDialog QLineEdit, QDialog QComboBox, QDialog QSpinBox, QDialog QTextEdit {
    background: #2a1e25;
    color: #f5e6ee;
    border: 1px solid #5a3d4d;
    border-radius: 8px;
    padding: 6px;
}
QDialog QPushButton {
    padding: 6px 14px;
    font-size: 12px;
}
QDialog QLabel {
    color: #e8a0bf;
    font-weight: 500;
}
QDialog QGroupBox {
    color: #e8a0bf;
    font-weight: 600;
    border: 1px solid #3d2b35;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
}
QDialog QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QTabWidget::pane {
    border: 1px solid #3d2b35;
    border-radius: 8px;
    background: #1a1218;
}
QTabBar::tab {
    background: #2a1e25;
    color: #c0809f;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #5a3d4d;
    color: #f5e6ee;
}
QTabBar::tab:hover {
    background: #3d2b35;
}

/* Tooltips */
QToolTip {
    background: #2a1e25;
    color: #f5e6ee;
    border: 1px solid #c0809f;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #3d2b35;
    border-radius: 6px;
    text-align: center;
    color: #f5e6ee;
    background: #141015;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #c07094, stop:1 #e8a0bf);
    border-radius: 6px;
}
"""


# ---------------------------------------------------------------------------
# Splash Screen
# ---------------------------------------------------------------------------
class SplashScreen(QSplashScreen):
    """Animated splash screen shown during assistant initialisation."""

    def __init__(self) -> None:
        pixmap = QPixmap(420, 320)
        pixmap.fill(QColor("#1a1218"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw decorative border
        pen = QPen(QColor("#c0809f"), 3)
        painter.setPen(pen)
        painter.drawRoundedRect(15, 15, 390, 290, 20, 20)

        # Draw title
        painter.setPen(QColor("#e8a0bf"))
        painter.setFont(QFont("Segoe UI", 32, QFont.Bold))
        painter.drawText(pixmap.rect().adjusted(0, -40, 0, 0), Qt.AlignCenter, "RICO")

        # Draw subtitle
        painter.setPen(QColor("#a85e7e"))
        painter.setFont(QFont("Segoe UI", 14))
        painter.drawText(pixmap.rect().adjusted(0, 30, 0, 0), Qt.AlignCenter, "Your Personal AI Assistant")

        # Draw loading text
        painter.setPen(QColor("#7a5a6a"))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(pixmap.rect().adjusted(0, 100, 0, 0), Qt.AlignCenter, "Initialising...")

        painter.end()
        super().__init__(pixmap)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.show()


# ---------------------------------------------------------------------------
# About Dialog
# ---------------------------------------------------------------------------
class AboutDialog(QDialog):
    """About dialog showing app information and credits."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Rico")
        self.setFixedSize(420, 340)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("RICO")
        title.setObjectName("headerLabel")
        title.setStyleSheet("font-size: 28px; font-weight: 900; color: #e8a0bf;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Version
        version = QLabel("Version 1.0.0")
        version.setStyleSheet("color: #a85e7e; font-size: 13px;")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #3d2b35;")
        layout.addWidget(line)

        # Description
        desc = QLabel(
            "Rico is a multilingual local AI assistant with voice, memory, "
            "and deep system integration. Built for macOS with love."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #f5e6ee; font-size: 13px; line-height: 1.5;")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        # Features list
        features = QLabel(
            "• Voice I/O  • Calendar & Reminders  • Image Analysis\n"
            "• Web Search  • PDF Summarisation  • Document RAG\n"
            "• System Control  • Multilingual (EN/HI/UR)"
        )
        features.setWordWrap(True)
        features.setStyleSheet("color: #c0809f; font-size: 12px; line-height: 1.6;")
        features.setAlignment(Qt.AlignCenter)
        layout.addWidget(features)

        layout.addStretch()

        # Credits
        credits = QLabel("Built with PyQt5, Gemini, and caffeine ☕")
        credits.setStyleSheet("color: #7a5a6a; font-size: 11px;")
        credits.setAlignment(Qt.AlignCenter)
        layout.addWidget(credits)

        # Close button
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignCenter)


# ---------------------------------------------------------------------------
# Settings Dialog
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    """
    Settings dialog for configuring Rico.

    Tabs: General, API Keys, Voice, Advanced
    """

    settings_saved = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None, current_settings: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rico Settings")
        self.setMinimumSize(480, 420)
        self._settings = current_settings or {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._api_tab(), "API Keys")
        tabs.addTab(self._voice_tab(), "Voice")
        tabs.addTab(self._advanced_tab(), "Advanced")
        layout.addWidget(tabs)

        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._save_settings)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        # Language
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English (en)", "Hindi (hi)", "Urdu (ur)"])
        current_lang = self._settings.get("language", "en")
        index = {"en": 0, "hi": 1, "ur": 2}.get(current_lang, 0)
        self.lang_combo.setCurrentIndex(index)
        self.lang_combo.setToolTip("Default language for Rico's responses")
        layout.addRow("Language:", self.lang_combo)

        # Memory
        self.memory_check = QCheckBox("Enable persistent memory")
        self.memory_check.setChecked(self._settings.get("memory_enabled", True))
        self.memory_check.setToolTip("Store conversations and facts in SQLite database")
        layout.addRow(self.memory_check)

        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Rose Gold (Default)", "Dark", "Light"])
        self.theme_combo.setCurrentIndex(self._settings.get("theme_index", 0))
        self.theme_combo.setToolTip("UI colour theme (requires restart)")
        layout.addRow("Theme:", self.theme_combo)

        # Startup
        self.startup_check = QCheckBox("Start minimised to tray")
        self.startup_check.setChecked(self._settings.get("start_minimised", False))
        self.startup_check.setToolTip("Launch Rico minimised to the system tray")
        layout.addRow(self.startup_check)

        layout.addStretch()
        return tab

    def _api_tab(self) -> QWidget:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        group = QGroupBox("API Configuration")
        group_layout = QFormLayout(group)

        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.Password)
        self.gemini_key.setText(self._settings.get("gemini_key", ""))
        self.gemini_key.setPlaceholderText("Paste your Gemini API key")
        self.gemini_key.setToolTip("Required for AI responses and image analysis")
        group_layout.addRow("Gemini API Key:", self.gemini_key)

        self.wolfram_key = QLineEdit()
        self.wolfram_key.setEchoMode(QLineEdit.Password)
        self.wolfram_key.setText(self._settings.get("wolfram_key", ""))
        self.wolfram_key.setPlaceholderText("Paste your WolframAlpha App ID")
        self.wolfram_key.setToolTip("Optional — enables advanced calculations")
        group_layout.addRow("WolframAlpha App ID:", self.wolfram_key)

        self.news_key = QLineEdit()
        self.news_key.setEchoMode(QLineEdit.Password)
        self.news_key.setText(self._settings.get("news_key", ""))
        self.news_key.setPlaceholderText("Paste your NewsAPI key")
        self.news_key.setToolTip("Required for news headlines")
        group_layout.addRow("NewsAPI Key:", self.news_key)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    def _voice_tab(self) -> QWidget:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        # TTS Engine
        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["edge-tts (Recommended)", "gTTS (Google)", "System Default"])
        self.tts_combo.setCurrentIndex(self._settings.get("tts_engine", 0))
        self.tts_combo.setToolTip("Text-to-speech engine preference")
        layout.addRow("TTS Engine:", self.tts_combo)

        # Voice
        self.voice_combo = QComboBox()
        self.voice_combo.addItems([
            "Jenny (en-US)", "Swara (hi-IN)", "Uzma (ur-PK)",
            "System Default"
        ])
        self.voice_combo.setCurrentIndex(self._settings.get("voice_index", 0))
        self.voice_combo.setToolTip("Voice persona for speech output")
        layout.addRow("Voice:", self.voice_combo)

        # Text mode
        self.text_mode_check = QCheckBox("Force text mode (disable voice)")
        self.text_mode_check.setChecked(self._settings.get("text_mode", False))
        self.text_mode_check.setToolTip("Use text-only interaction, no microphone or speakers")
        layout.addRow(self.text_mode_check)

        layout.addStretch()
        return tab

    def _advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(12)

        # RAG Mode
        self.rag_combo = QComboBox()
        self.rag_combo.addItems(["Auto", "Manual", "Off"])
        self.rag_combo.setCurrentIndex({"auto": 0, "manual": 1, "off": 2}.get(
            self._settings.get("rag_mode", "auto"), 0))
        self.rag_combo.setToolTip("When to use document knowledge for answers")
        layout.addRow("RAG Mode:", self.rag_combo)

        # Wake Word
        self.wake_check = QCheckBox("Enable 'Hey Rico' wake word")
        self.wake_check.setChecked(self._settings.get("wake_word", True))
        self.wake_check.setToolTip("Listen for voice activation keyword (requires pvporcupine)")
        layout.addRow(self.wake_check)

        # Proactive
        self.proactive_check = QCheckBox("Enable proactive messages")
        self.proactive_check.setChecked(self._settings.get("proactive", True))
        self.proactive_check.setToolTip("Rico will check in after periods of inactivity")
        layout.addRow(self.proactive_check)

        # Debug
        self.debug_check = QCheckBox("Debug mode (verbose logging)")
        self.debug_check.setChecked(self._settings.get("debug", False))
        self.debug_check.setToolTip("Print detailed logs to console")
        layout.addRow(self.debug_check)

        layout.addStretch()
        return tab

    def _save_settings(self) -> None:
        """Collect settings and emit signal."""
        settings = {
            "language": ["en", "hi", "ur"][self.lang_combo.currentIndex()],
            "memory_enabled": self.memory_check.isChecked(),
            "theme_index": self.theme_combo.currentIndex(),
            "start_minimised": self.startup_check.isChecked(),
            "gemini_key": self.gemini_key.text(),
            "wolfram_key": self.wolfram_key.text(),
            "news_key": self.news_key.text(),
            "tts_engine": self.tts_combo.currentIndex(),
            "voice_index": self.voice_combo.currentIndex(),
            "text_mode": self.text_mode_check.isChecked(),
            "rag_mode": ["auto", "manual", "off"][self.rag_combo.currentIndex()],
            "wake_word": self.wake_check.isChecked(),
            "proactive": self.proactive_check.isChecked(),
            "debug": self.debug_check.isChecked(),
        }
        self.settings_saved.emit(settings)
        self.accept()


# ---------------------------------------------------------------------------
# Worker Threads
# ---------------------------------------------------------------------------
class RicoLoader(QObject):
    """Background loader for RicoAssistant to avoid blocking the GUI."""

    loaded = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, text_mode: bool = True, memory_enabled: bool = True) -> None:
        super().__init__()
        self.text_mode = text_mode
        self.memory_enabled = memory_enabled

    def load(self) -> None:
        """Initialise RicoAssistant in background."""
        try:
            self.progress.emit("Loading AI models...")
            RicoClass = _import_rico()
            assistant = RicoClass(text_mode=self.text_mode, memory_enabled=self.memory_enabled)
            self.loaded.emit(assistant)
        except Exception as exc:
            self.error.emit(str(exc))


class QueryWorker(QObject):
    """Process a user query in a background thread."""

    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, rico: Any, query: str) -> None:
        super().__init__()
        self.rico = rico
        self.query = query

    def process(self) -> None:
        """Execute the query and emit results."""
        try:
            if hasattr(self.rico, "chat"):
                result = self.rico.chat(self.query)
            else:
                result = "Error: Rico assistant does not support chat mode."
            self.result_ready.emit(result)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()


# ---------------------------------------------------------------------------
# Main GUI Window
# ---------------------------------------------------------------------------
class RicoGUI(QMainWindow):
    """
    Main application window for Rico Assistant.

    Provides a chat interface, quick action buttons, system tray integration,
    and proper thread-safe communication with the backend assistant.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rico: Optional[Any] = None
        self._chat_buffer: List[Dict[str, str]] = []
        self._history_path = Path.home() / ".rico" / "chat_history.json"
        self._settings_path = Path.home() / ".rico" / "settings.json"
        self._settings: Dict[str, Any] = self._load_settings()
        self._worker_thread: Optional[QThread] = None
        self._rico_thread: Optional[QThread] = None
        self._typing_timer: Optional[QTimer] = None

        self.setWindowTitle("Rico Assistant")
        self.setGeometry(100, 100, 580, 760)
        self.setStyleSheet(PROFESSIONAL_PINK_THEME)

        self._init_ui()
        self._init_menus()
        self._init_tray()
        self._init_shortcuts()
        self._load_history()
        self._init_rico_async()

    # -----------------------------------------------------------------------
    # UI Construction
    # -----------------------------------------------------------------------
    def _init_ui(self) -> None:
        """Build the main user interface."""
        central = QWidget(objectName="centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(QMargins(20, 20, 20, 20))

        # Header
        header = self._build_header()
        layout.addLayout(header)

        # Chat Display
        self.chat_display = QTextEdit(readOnly=True, objectName="chatDisplay")
        self.chat_display.setOpenExternalLinks(True)
        layout.addWidget(self.chat_display, stretch=3)

        # Typing indicator
        self.typing_label = QLabel("", objectName="typingLabel")
        self.typing_label.setVisible(False)
        layout.addWidget(self.typing_label)

        # Quick Actions
        quick = self._build_quick_actions()
        layout.addLayout(quick)

        # Input Section
        input_row = self._build_input_row()
        layout.addLayout(input_row)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Initialising...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(120)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _build_header(self) -> QHBoxLayout:
        """Build the top header with title and status."""
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.title_label = QLabel("RICO")
        self.title_label.setObjectName("headerLabel")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.status_indicator = QLabel("● Initialising")
        self.status_indicator.setObjectName("statusLabel")
        self.status_indicator.setStyleSheet("color: #d4a017;")
        layout.addWidget(self.status_indicator)

        # Settings button
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(32, 32)
        self.settings_btn.setToolTip("Open Settings (Ctrl+,)")
        self.settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_btn)

        return layout

    def _build_quick_actions(self) -> QHBoxLayout:
        """Build the quick action button row."""
        layout = QHBoxLayout()
        layout.setSpacing(6)

        actions = [
            ("Snap", "Take a screenshot and analyse it", self._on_screenshot),
            ("Clip", "Read text from clipboard", self._on_clipboard),
            ("Time", "Show current time", self._on_time),
            ("Memory", "Show what Rico remembers about you", self._on_memory),
            ("Calendar", "Show upcoming calendar events", self._on_calendar),
            ("Reminders", "Show active reminders", self._on_reminders),
            ("Volume", "Adjust system volume", self._on_volume),
            ("Brightness", "Adjust screen brightness", self._on_brightness),
            ("Dark", "Toggle dark mode", self._on_dark_mode),
            ("Analyse", "Analyse an image file", self._on_analyse_image),
            ("PDF", "Summarise a PDF file", self._on_summarize_pdf),
            ("Index", "Index a folder for RAG", self._on_index_folder),
            ("Search", "Search knowledge base", self._on_search_knowledge),
            ("Stats", "Show knowledge base stats", self._on_knowledge_stats),
            ("Wake", "Toggle wake word detection", self._on_toggle_wake),
            ("Focus", "Start a focus/Pomodoro session", self._on_focus_mode),
            ("Notes", "Create or read Apple Notes", self._on_create_note),
            ("Safari", "Summarise current Safari page", self._on_safari_summary),
            ("Battery", "Check MacBook battery status", self._on_battery),
            ("Storage", "Check disk storage", self._on_storage),
            ("Clean", "Tidy up Desktop", self._on_clean_desktop),
            ("Spotify", "Control Spotify playback", self._on_spotify),
            ("Email", "Check unread emails", self._on_email),
            ("Text", "Send an iMessage", self._on_imessage),
        ]

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMaximumHeight(52)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        hlayout = QHBoxLayout(container)
        hlayout.setSpacing(6)
        hlayout.setContentsMargins(0, 0, 0, 0)

        for txt, tip, fn in actions:
            btn = QPushButton(txt)
            btn.setObjectName("quickButton")
            btn.setToolTip(tip)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(fn)
            hlayout.addWidget(btn)

        hlayout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)
        return layout

    def _build_input_row(self) -> QHBoxLayout:
        """Build the message input row with voice button."""
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.voice_btn = QPushButton("MIC")
        self.voice_btn.setObjectName("voiceButton")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setToolTip("Toggle voice input (Ctrl+V)")
        self.voice_btn.clicked.connect(self._toggle_voice)
        layout.addWidget(self.voice_btn)

        self.message_input = QLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Type a message or command...")
        self.message_input.setToolTip("Press Enter to send, Ctrl+Enter for new line")
        self.message_input.returnPressed.connect(self._send_message)
        layout.addWidget(self.message_input, stretch=3)

        self.send_btn = QPushButton("Send")
        self.send_btn.setToolTip("Send message (Enter)")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._send_message)
        layout.addWidget(self.send_btn)

        return layout

    # -----------------------------------------------------------------------
    # Menu Bar
    # -----------------------------------------------------------------------
    def _init_menus(self) -> None:
        """Initialise the menu bar with File, Tools, and Help menus."""
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("File")
        file_menu.setToolTipsVisible(True)

        clear_action = QAction("Clear Chat", self)
        clear_action.setShortcut("Ctrl+Shift+C")
        clear_action.setToolTip("Clear the chat display (history remains saved)")
        clear_action.triggered.connect(self._clear_chat)
        file_menu.addAction(clear_action)

        save_action = QAction("Save Chat...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.setToolTip("Export chat history to a file")
        save_action.triggered.connect(self._save_chat)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        settings_action = QAction("Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.setToolTip("Open application settings")
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setToolTip("Quit Rico")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools Menu
        tools_menu = menubar.addMenu("Tools")
        tools_menu.setToolTipsVisible(True)

        screenshot_action = QAction("Screenshot", self)
        screenshot_action.setShortcut("Ctrl+Shift+S")
        screenshot_action.setToolTip("Capture and analyse screen")
        screenshot_action.triggered.connect(self._on_screenshot)
        tools_menu.addAction(screenshot_action)

        analyse_action = QAction("Analyse Image...", self)
        analyse_action.setToolTip("Select and analyse an image file")
        analyse_action.triggered.connect(self._on_analyse_image)
        tools_menu.addAction(analyse_action)

        pdf_action = QAction("Summarise PDF...", self)
        pdf_action.setToolTip("Select and summarise a PDF file")
        pdf_action.triggered.connect(self._on_summarize_pdf)
        tools_menu.addAction(pdf_action)

        tools_menu.addSeparator()

        index_action = QAction("Index Folder...", self)
        index_action.setToolTip("Index documents for RAG search")
        index_action.triggered.connect(self._on_index_folder)
        tools_menu.addAction(index_action)

        search_action = QAction("Search Knowledge...", self)
        search_action.setToolTip("Query the document knowledge base")
        search_action.triggered.connect(self._on_search_knowledge)
        tools_menu.addAction(search_action)

        tools_menu.addSeparator()

        wake_action = QAction("Toggle Wake Word", self)
        wake_action.setToolTip("Enable/disable 'Hey Rico' voice activation")
        wake_action.triggered.connect(self._on_toggle_wake)
        tools_menu.addAction(wake_action)

        tools_menu.addSeparator()

        focus_action = QAction("Focus Mode...", self)
        focus_action.setShortcut("Ctrl+Shift+F")
        focus_action.setToolTip("Start a Pomodoro focus session")
        focus_action.triggered.connect(self._on_focus_mode)
        tools_menu.addAction(focus_action)

        note_action = QAction("New Note...", self)
        note_action.setToolTip("Create a new Apple Note")
        note_action.triggered.connect(self._on_create_note)
        tools_menu.addAction(note_action)

        safari_action = QAction("Summarise Safari Page", self)
        safari_action.setShortcut("Ctrl+Shift+U")
        safari_action.setToolTip("Summarise the current Safari page with AI")
        safari_action.triggered.connect(self._on_safari_summary)
        tools_menu.addAction(safari_action)

        clean_action = QAction("Clean Desktop", self)
        clean_action.setToolTip("Move Desktop clutter to Archive folder")
        clean_action.triggered.connect(self._on_clean_desktop)
        tools_menu.addAction(clean_action)

        tools_menu.addSeparator()

        spotify_action = QAction("Spotify Control...", self)
        spotify_action.setToolTip("Control Spotify playback")
        spotify_action.triggered.connect(self._on_spotify)
        tools_menu.addAction(spotify_action)

        email_action = QAction("Email...", self)
        email_action.setToolTip("Check emails or draft a new one")
        email_action.triggered.connect(self._on_email)
        tools_menu.addAction(email_action)

        imessage_action = QAction("Send iMessage...", self)
        imessage_action.setToolTip("Send a text via iMessage")
        imessage_action.triggered.connect(self._on_imessage)
        tools_menu.addAction(imessage_action)

        # Help Menu
        help_menu = menubar.addMenu("Help")
        help_menu.setToolTipsVisible(True)

        guide_action = QAction("User Guide", self)
        guide_action.setToolTip("Open the user guide documentation")
        guide_action.triggered.connect(self._open_user_guide)
        help_menu.addAction(guide_action)

        help_menu.addSeparator()

        about_action = QAction("About Rico", self)
        about_action.setToolTip("Show application information")
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # -----------------------------------------------------------------------
    # System Tray
    # -----------------------------------------------------------------------
    def _init_tray(self) -> None:
        """Initialise system tray icon and context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("Rico Assistant — Click to show")

        # Create a simple icon (fallback to system icon if no custom one)
        icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu { background: #1f161c; color: #f5e6ee; border: 1px solid #3d2b35; }
            QMenu::item:selected { background: #5a3d4d; }
        """)

        show_action = QAction("Show Rico", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)

        hide_action = QAction("Hide to Tray", self)
        hide_action.triggered.connect(self.hide)
        tray_menu.addAction(hide_action)

        tray_menu.addSeparator()

        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._open_settings)
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (click/double-click)."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event) -> None:
        """Override close to minimise to tray instead of quitting."""
        if self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "Rico",
                "Running in background. Click the tray icon to restore.",
                QSystemTrayIcon.Information,
                2000
            )
            event.ignore()
        else:
            self._quit_app()
            event.accept()

    def _quit_app(self) -> None:
        """Cleanly shut down the application."""
        self._save_history()
        self.tray_icon.hide()
        QApplication.quit()

    
    # Keyboard Shortcuts
    # ---------------------------------------------------------------------
    def _init_shortcuts(self) -> None:
        """Register global keyboard shortcuts."""
        shortcuts = [
            ("Ctrl+Return", self._send_message, "Send message"),
            ("Ctrl+V", self._toggle_voice, "Toggle voice input"),
            ("Ctrl+Shift+C", self._clear_chat, "Clear chat"),
            ("Ctrl+Shift+S", self._on_screenshot, "Take screenshot"),
            ("Ctrl+Q", self._quit_app, "Quit application"),
        ]
        for seq, slot, tip in shortcuts:
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(slot)

    
    # Rico Initialisation (Lazy Loading)
   
    def _init_rico_async(self) -> None:
        """Start RicoAssistant in a background thread to avoid UI blocking."""
        self.status_bar.showMessage("Loading assistant...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self._set_ui_enabled(False)

        self._rico_thread = QThread()
        self._rico_loader = RicoLoader(
            text_mode=self._settings.get("text_mode", True),
            memory_enabled=self._settings.get("memory_enabled", True)
        )
        self._rico_loader.moveToThread(self._rico_thread)
        self._rico_thread.started.connect(self._rico_loader.load)
        self._rico_loader.loaded.connect(self._on_rico_ready)
        self._rico_loader.error.connect(self._on_rico_error)
        self._rico_loader.progress.connect(self.status_bar.showMessage)
        self._rico_thread.start()

    def _on_rico_ready(self, rico: Any) -> None:
        """Handle successful Rico initialisation."""
        self.rico = rico
        self._rico_thread.quit()
        self._rico_thread.wait()

        self.status_indicator.setText("● Online")
        self.status_indicator.setStyleSheet("color: #55cc88;")
        self.status_bar.showMessage("Ready")
        self.progress_bar.setVisible(False)
        self._set_ui_enabled(True)

        self._add_message("Rico", "Hey! I am ready. How can I help you today?")

    def _on_rico_error(self, error_msg: str) -> None:
        """Handle Rico initialisation failure."""
        self._rico_thread.quit()
        self._rico_thread.wait()

        self.status_indicator.setText("● Error")
        self.status_indicator.setStyleSheet("color: #ff4466;")
        self.status_bar.showMessage(f"Error: {error_msg}")
        self.progress_bar.setVisible(False)
        self._set_ui_enabled(True)

        self._add_message("System", f"Failed to initialise Rico: {error_msg}")
        self._add_message("System", "Some features may be unavailable. Check your API keys and dependencies.")

    def _set_ui_enabled(self, enabled: bool) -> None:
        """Enable or disable interactive UI elements."""
        self.message_input.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        self.voice_btn.setEnabled(enabled)

    # CHAT
    def _add_message(self, sender: str, text: str) -> None:
        """
        Add a formatted message to the chat display.

        Args:
            sender: 'You', 'Rico', or 'System'.
            text: Message content (supports HTML).
        """
        timestamp = datetime.datetime.now().strftime("%I:%M %p")

        if sender == "You":
            color = "#ffb3d9"
            prefix = "You"
            align = "right"
            bg = "#2d1f2a"
        elif sender == "System":
            color = "#d4a017"
            prefix = "System"
            align = "center"
            bg = "#1a1218"
        else:
            color = "#ff3399"
            prefix = "Rico"
            align = "left"
            bg = "#231820"

        # Escape HTML in text but preserve basic formatting
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_text = safe_text.replace("\n", "<br>")

        html = f"""
        <div style="margin: 6px 0; text-align: {align};">
            <div style="display: inline-block; max-width: 85%; background: {bg}; 
                        border-radius: 12px; padding: 10px 14px; 
                        border: 1px solid #3d2b35;">
                <div style="color: {color}; font-weight: 700; font-size: 12px; margin-bottom: 4px;">
                    {prefix} <span style="color: #7a5a6a; font-weight: 400; font-size: 10px;">{timestamp}</span>
                </div>
                <div style="color: #f5e6ee; font-size: 13px; line-height: 1.5;">
                    {safe_text}
                </div>
            </div>
        </div>
        """

        self.chat_display.append(html)
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

        # Buffer for history
        self._chat_buffer.append({
            "sender": sender,
            "text": text,
            "timestamp": timestamp,
            "datetime": datetime.datetime.now().isoformat(),
        })

        # Flush history periodically (every 5 messages)
        if len(self._chat_buffer) >= 5:
            self._save_history()

    def _show_typing(self, visible: bool) -> None:
        """Show or hide the typing indicator."""
        if visible:
            self.typing_label.setText("Rico is thinking...")
            self.typing_label.setVisible(True)
        else:
            self.typing_label.setVisible(False)

    def _send_message(self) -> None:
        """Handle sending a user message."""
        text = self.message_input.text().strip()
        if not text or not self.rico:
            return

        self.message_input.clear()
        self._add_message("You", text)
        self._show_typing(True)
        self.status_bar.showMessage("Processing...")
        self.send_btn.setEnabled(False)

        # Process in background thread
        self._worker_thread = QThread()
        self._worker = QueryWorker(self.rico, text)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.process)
        self._worker.result_ready.connect(self._on_query_result)
        self._worker.error_occurred.connect(self._on_query_error)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def _on_query_result(self, result: str) -> None:
        """Handle successful query result."""
        self._show_typing(False)
        self._add_message("Rico", result)
        self.status_bar.showMessage("Ready")
        self.send_btn.setEnabled(True)

    def _on_query_error(self, error_msg: str) -> None:
        """Handle query processing error."""
        self._show_typing(False)
        self._add_message("System", f"Error: {error_msg}")
        self.status_bar.showMessage("Error occurred")
        self.send_btn.setEnabled(True)

    def _clear_chat(self) -> None:
        """Clear the chat display (preserves saved history)."""
        self.chat_display.clear()
        self._add_message("System", "Chat cleared. History is still saved.")

    def _save_chat(self) -> None:
        """Export chat history to a user-selected file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Chat History", str(Path.home() / "rico_chat.txt"),
            "Text Files (*.txt);;HTML Files (*.html);;JSON Files (*.json)"
        )
        if filepath:
            try:
                if filepath.endswith(".html"):
                    content = self.chat_display.toHtml()
                elif filepath.endswith(".json"):
                    content = json.dumps(self._chat_buffer, indent=2)
                else:
                    lines = []
                    for msg in self._chat_buffer:
                        lines.append(f"[{msg['timestamp']}] {msg['sender']}: {msg['text']}")
                    content = "\n".join(lines)
                Path(filepath).write_text(content, encoding="utf-8")
                self.status_bar.showMessage(f"Chat saved to {filepath}")
            except Exception as exc:
                self._add_message("System", f"Could not save chat: {exc}")

   
    def _on_screenshot(self) -> None:
        """Capture and analyse screen."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._add_message("You", "[Screenshot requested]")
        self._run_async(lambda: self.rico.take_screenshot())

    def _on_clipboard(self) -> None:
        """Read clipboard content and paste into input."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            preview = text[:200] + ("..." if len(text) > 200 else "")
            self._add_message("You", f"[Clipboard] {preview}")
            self.message_input.setText(text)
            self.message_input.setFocus()
        else:
            self._add_message("System", "Clipboard is empty or contains no text.")

    def _on_time(self) -> None:
        """Show current time."""
        now = datetime.datetime.now().strftime("%I:%M %p")
        self._add_message("Rico", f"The time is {now}.")

    def _on_memory(self) -> None:
        """Show what Rico remembers."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico.chat("what do you remember about me"))

    def _on_calendar(self) -> None:
        """Show calendar events."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico.get_calendar_events())

    def _on_reminders(self) -> None:
        """Show reminders."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico.get_reminders())

    def _on_volume(self) -> None:
        """Show volume adjustment dialog."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        level, ok = QInputDialog.getInt(
            self, "Set Volume", "Volume level (0–100):",
            value=50, min=0, max=100
        )
        if ok:
            self._run_async(lambda: self.rico._set_volume(level))

    def _on_brightness(self) -> None:
        """Show brightness adjustment dialog."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        level, ok = QInputDialog.getInt(
            self, "Set Brightness", "Brightness level (0–100):",
            value=50, min=0, max=100
        )
        if ok:
            self._run_async(lambda: self.rico._set_brightness(level))

    def _on_dark_mode(self) -> None:
        """Toggle dark mode."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico._toggle_dark_mode())

    def _on_analyse_image(self) -> None:
        """Open file dialog and analyse selected image."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Image", str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.webp)"
        )
        if filepath:
            self._add_message("You", f"[Analyse image: {Path(filepath).name}]")
            self._run_async(lambda: self.rico.analyze_image_file(filepath))

    def _on_summarize_pdf(self) -> None:
        """Open file dialog and summarise selected PDF."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select PDF", str(Path.home()),
            "PDF Files (*.pdf)"
        )
        if filepath:
            self._add_message("You", f"[Summarise PDF: {Path(filepath).name}]")
            self._run_async(lambda: self.rico.summarize_pdf(filepath))

    def _on_index_folder(self) -> None:
        """Open folder dialog and index documents."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder to Index", str(Path.home())
        )
        if folder:
            self._add_message("You", f"[Index folder: {folder}]")
            self._run_async(lambda: self.rico.index_documents(folder))

    def _on_search_knowledge(self) -> None:
        """Search the knowledge base."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        query, ok = QInputDialog.getText(
            self, "Search Knowledge", "What would you like to know?"
        )
        if ok and query.strip():
            self._add_message("You", f"[Search: {query}]")
            self._run_async(lambda: self.rico.search_knowledge(query))

    def _on_knowledge_stats(self) -> None:
        """Show knowledge base statistics."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico.get_knowledge_stats())

    def _on_toggle_wake(self) -> None:
        """Toggle wake word detection."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico.toggle_wake_word())

    def _toggle_voice(self) -> None:
        """Toggle voice input mode."""
        active = self.voice_btn.isChecked()
        self.voice_btn.setText("REC" if active else "MIC")
        if active:
            self.status_bar.showMessage("Voice mode active — speak now")
            # Start listening in background
            if self.rico and not self.rico.text_mode:
                self._run_async(lambda: self.rico._listen(), callback=self._on_voice_result)
            else:
                self._add_message("System", "Voice input unavailable. Check microphone and speech_recognition setup.")
                self.voice_btn.setChecked(False)
                self.voice_btn.setText("MIC")
        else:
            self.status_bar.showMessage("Ready")

    def _on_voice_result(self, text: str) -> None:
        """Handle voice recognition result."""
        self.voice_btn.setChecked(False)
        self.voice_btn.setText("MIC")
        if text:
            self.message_input.setText(text)
            self._send_message()
        else:
            self._add_message("System", "Could not understand audio. Please try again.")

    def _run_async(self, fn, callback=None):
        """
        Run a function in a background thread with result handling.

        Args:
            fn: Callable that returns a string result.
            callback: Optional callable to handle result instead of default.
        """
        if not self.rico:
            return

        self._show_typing(True)
        self.send_btn.setEnabled(False)

        def worker():
            try:
                result = fn()
                if callback:
                    callback(result)
                else:
                    self._worker_result = result
                    # Use timer to emit from main thread
                    QTimer.singleShot(0, lambda: self._on_query_result(result))
            except Exception as exc:
                QTimer.singleShot(0, lambda: self._on_query_error(str(exc)))
            finally:
                QTimer.singleShot(0, lambda: self.send_btn.setEnabled(True))

        threading.Thread(target=worker, daemon=True).start()


    
    def _on_focus_mode(self) -> None:
        """Start a focus/Pomodoro session."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        duration, ok = QInputDialog.getInt(
            self, "Focus Mode", "Duration in minutes:",
            value=25, min=5, max=120, step=5
        )
        if ok:
            self._add_message("You", f"[Focus mode: {duration} min]")
            self._run_async(lambda: self.rico._toggle_focus_mode(duration))

    def _on_window_left(self) -> None:
        """Tile window left."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico._window_tile_left())

    def _on_window_right(self) -> None:
        """Tile window right."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico._window_tile_right())

    def _on_window_max(self) -> None:
        """Maximise front window."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico._window_maximise())

    def _on_create_note(self) -> None:
        """Create a new Apple Note."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        title, ok = QInputDialog.getText(self, "New Note", "Note title:")
        if ok and title.strip():
            body, ok2 = QInputDialog.getMultiLineText(self, "New Note", "Note content:")
            if ok2:
                self._add_message("You", f"[New note: {title}]")
                self._run_async(lambda: self.rico._create_note(title.strip(), body))

    def _on_read_notes(self) -> None:
        """Read recent notes."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico._read_last_note())

    def _on_safari_summary(self) -> None:
        """Summarise current Safari page."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._add_message("You", "[Summarise Safari page]")
        self._run_async(lambda: self.rico._safari_summarise())

    def _on_battery(self) -> None:
        """Show battery status."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico._get_battery_status())

    def _on_storage(self) -> None:
        """Show storage status."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        self._run_async(lambda: self.rico._get_storage_status())

    def _on_clean_desktop(self) -> None:
        """Clean up Desktop."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        reply = QMessageBox.question(
            self, "Clean Desktop",
            "Move all Desktop items to Desktop/Archive/Today's date?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._run_async(lambda: self.rico._clean_desktop())


   
    def _on_spotify(self) -> None:
        """Show Spotify control dialog."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Spotify Control")
        dialog.setFixedSize(300, 220)
        layout = QVBoxLayout(dialog)

        btn_row1 = QHBoxLayout()
        play_btn = QPushButton("Play/Pause")
        play_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._spotify_play()))
        prev_btn = QPushButton("Previous")
        prev_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._spotify_previous()))
        next_btn = QPushButton("Next")
        next_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._spotify_next()))
        btn_row1.addWidget(play_btn)
        btn_row1.addWidget(prev_btn)
        btn_row1.addWidget(next_btn)
        layout.addLayout(btn_row1)

        now_btn = QPushButton("What is Playing?")
        now_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._spotify_now_playing()))
        layout.addWidget(now_btn)

        like_btn = QPushButton("Like Current Track")
        like_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._spotify_like()))
        layout.addWidget(like_btn)

        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Volume:"))
        vol_spin = QSpinBox()
        vol_spin.setRange(0, 100)
        vol_spin.setValue(50)
        vol_layout.addWidget(vol_spin)
        vol_btn = QPushButton("Set")
        vol_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._spotify_volume(vol_spin.value())))
        vol_layout.addWidget(vol_btn)
        layout.addLayout(vol_layout)

        search_layout = QHBoxLayout()
        search_input = QLineEdit(placeholderText="Search and play...")
        search_btn = QPushButton("Play")
        search_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._spotify_play(search_input.text())))
        search_layout.addWidget(search_input)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)

        dialog.exec_()

    def _on_email(self) -> None:
        """Show email options dialog."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Email")
        dialog.setFixedSize(320, 200)
        layout = QVBoxLayout(dialog)

        check_btn = QPushButton("Check Unread Emails")
        check_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._check_email()))
        layout.addWidget(check_btn)

        summary_btn = QPushButton("Summarise Unread Emails")
        summary_btn.clicked.connect(lambda: self._run_async(lambda: self.rico._summarise_email()))
        layout.addWidget(summary_btn)

        draft_btn = QPushButton("Draft New Email...")
        draft_btn.clicked.connect(self._on_draft_email)
        layout.addWidget(draft_btn)

        dialog.exec_()

    def _on_draft_email(self) -> None:
        """Open draft email dialog."""
        if not self.rico:
            return
        to, ok = QInputDialog.getText(self, "Draft Email", "To:")
        if not ok or not to.strip():
            return
        subject, ok2 = QInputDialog.getText(self, "Draft Email", "Subject:")
        if not ok2:
            return
        body, ok3 = QInputDialog.getMultiLineText(self, "Draft Email", "Body:")
        if ok3:
            self._add_message("You", f"[Draft email to {to}]")
            self._run_async(lambda: self.rico._draft_email(to.strip(), subject.strip(), body))

    def _on_imessage(self) -> None:
        """Send an iMessage."""
        if not self.rico:
            self._add_message("System", "Rico is not ready yet.")
            return
        contact, ok = QInputDialog.getText(self, "Send iMessage", "To (name or number):")
        if not ok or not contact.strip():
            return
        message, ok2 = QInputDialog.getMultiLineText(self, "Send iMessage", "Message:")
        if ok2 and message.strip():
            self._add_message("You", f"[Text to {contact}]")
            self._run_async(lambda: self.rico._send_imessage(contact.strip(), message.strip()))

   
    # Settings & Persistence
   
    def _open_settings(self) -> None:
        """Open the settings dialog."""
        dialog = SettingsDialog(self, self._settings)
        dialog.settings_saved.connect(self._apply_settings)
        dialog.exec_()

    def _apply_settings(self, settings: Dict[str, Any]) -> None:
        """Apply saved settings and persist to disk."""
        self._settings = settings
        self._save_settings()

        # Apply to Rico if available
        if self.rico:
            self.rico.language_code = settings.get("language", "en")
            self.rico.memory_enabled = settings.get("memory_enabled", True)
            self.rico.text_mode = settings.get("text_mode", True)
            if hasattr(self.rico, 'rag_mode'):
                self.rico.rag_mode = settings.get("rag_mode", "auto")

        self.status_bar.showMessage("Settings saved")

    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from disk or return defaults."""
        if self._settings_path.exists():
            try:
                return json.loads(self._settings_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "language": "en",
            "memory_enabled": True,
            "theme_index": 0,
            "text_mode": True,
            "rag_mode": "auto",
            "wake_word": True,
            "proactive": True,
        }

    def _save_settings(self) -> None:
        """Persist settings to disk."""
        try:
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            self._settings_path.write_text(
                json.dumps(self._settings, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            print(f"Could not save settings: {exc}")

    def _load_history(self) -> None:
        """Load chat history from disk."""
        if self._history_path.exists():
            try:
                data = json.loads(self._history_path.read_text(encoding="utf-8"))
                self._chat_buffer = data.get("messages", [])
                # Replay last 20 messages
                for msg in self._chat_buffer[-20:]:
                    self._add_message(msg["sender"], msg["text"])
            except Exception:
                self._chat_buffer = []

    def _save_history(self) -> None:
        """Persist chat history to disk."""
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._history_path.write_text(
                json.dumps({"messages": self._chat_buffer}, indent=2),
                encoding="utf-8"
            )
        except Exception as exc:
            print(f"Could not save history: {exc}")

   
    # Help & About
   
    def _show_about(self) -> None:
        """Show the About dialog."""
        dialog = AboutDialog(self)
        dialog.exec_()

    def _open_user_guide(self) -> None:
        """Open the user guide in the default browser or show a message."""
        guide_path = Path("USER_GUIDE.md")
        if guide_path.exists():
            import webbrowser
            webbrowser.open(f"file://{guide_path.absolute()}")
        else:
            QMessageBox.information(
                self, "User Guide",
                "User Guide not found. Please check the project directory for USER_GUIDE.md"
            )

    def send_notification(self, title: str, message: str) -> None:
        """Send a native macOS notification."""
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Rico Assistant")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("RicoProject")

    # Show splash screen
    splash = SplashScreen()
    app.processEvents()

    # Create main window (loads in background)
    window = RicoGUI()
    splash.finish(window)
    window.show()

    # Handle startup minimised
    if window._settings.get("start_minimised", False):
        window.hide()
        window.tray_icon.showMessage(
            "Rico",
            "Rico is running in the background.",
            QSystemTrayIcon.Information,
            3000
        )

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
