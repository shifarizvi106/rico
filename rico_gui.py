#!/usr/bin/env python3
import sys
import os
import datetime
import threading
from pathlib import Path

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QShortcut
from PyQt5.QtGui import QKeySequence

from rico import RicoAssistant


class RicoGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.rico = RicoAssistant(text_mode=True, memory_enabled=True)
        self.setup_ui()
        self.setup_tray()
        self.setup_shortcuts()
        self.add_msg("Rico", "Hey! I'm ready! 💗")
        # Load chat history
        if Path("chat_history.txt").exists():
            self.chat.setPlainText(Path("chat_history.txt").read_text())

    def setup_ui(self):
        self.setWindowTitle("Rico Assistant")
        self.setGeometry(100, 100, 550, 700)
        self.setStyleSheet("""
            QMainWindow { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2b0b23, stop:1 #4a103c); }
            QWidget#central { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #5c184c, stop:0.5 #38082e, stop:1 #190214); border: 3px solid #ff85c0; border-radius: 30px; }
            QTextEdit { background: #170213; color: #ffd6e7; border-top: 3px solid #000; border-left: 3px solid #000; border-right: 2px solid #ff85c0; border-bottom: 2px solid #ff85c0; border-radius: 18px; padding: 12px; font-size: 14px; }
            QLineEdit { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #24031d, stop:1 #450b38); color: #fff; border-top: 2px solid #12010e; border-left: 2px solid #12010e; border-right: 1px solid #ff9ebb; border-bottom: 1px solid #ff9ebb; border-radius: 20px; padding: 8px 15px; }
            QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffb3d9, stop:0.15 #ff69b4, stop:0.5 #ff1493, stop:0.51 #d8006f, stop:1 #ff69b4); color: #fff; border: 1px solid #ffa3d1; border-bottom: 3px solid #800040; border-radius: 18px; padding: 6px 16px; font-weight: bold; }
            QPushButton:pressed { background: #d8006f; border-top: 2px solid #500028; }
            QPushButton#voiceBtn { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffccd5, stop:0.5 #c9184a, stop:1 #800f2f); border: 2px solid #ffb3c1; border-radius: 22px; min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; font-size: 14px; }
            QPushButton#voiceBtn:checked { background: #ff0055; }
            .quickBtn { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffb6c1, stop:0.5 #db7093, stop:1 #ffb6c1); color: #2b0b23; border-radius: 12px; padding: 4px 10px; font-size: 11px; }
            QStatusBar { background: #170213; color: #ffb6c1; font-weight: bold; }
        """)

        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central, spacing=10, contentsMargins=QMargins(20, 20, 20, 20))

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("RICO", styleSheet="color: #ff9ebb; font-size: 22px; font-weight: 900;"))
        hdr.addStretch()
        hdr.addWidget(QLabel("Active", styleSheet="color: #55ff99; font-weight: bold;"))
        layout.addLayout(hdr)

        # Chat Screen
        self.chat = QTextEdit(readOnly=True)
        layout.addWidget(self.chat, 2)

        # Quick Actions
        quick = QHBoxLayout()
        actions = [
            ("Snap", lambda: self.add_msg("Rico", self.rico.take_screenshot())),
            ("Clip", lambda: self.add_msg("Rico", "Reading clipboard...")),
            ("Time", lambda: self.add_msg("Rico", f"It's {datetime.datetime.now().strftime('%I:%M %p')}")),
            ("Memory", lambda: self.add_msg("Rico", "Checking memory bank...")),
            ("Calendar", self.show_calendar),
            ("Reminders", self.show_reminders),
            ("Volume", self.volume_ui),
            ("Brightness", self.brightness_ui),
            ("Dark Mode", self.dark_mode_ui),
            ("Analyze", self.analyze_image_ui),
        ]
        for txt, fn in actions:
            btn = QPushButton(txt, clicked=fn)
            btn.setProperty("class", "quickBtn")
            quick.addWidget(btn)
        quick.addStretch()
        layout.addLayout(quick)

        # Input Section
        inp = QHBoxLayout(spacing=8)
        self.voice_btn = QPushButton("MIC", objectName="voiceBtn", checkable=True, clicked=self.toggle_voice)
        self.field = QLineEdit(placeholderText="Type a message...", returnPressed=self.send_msg)
        self.send_btn = QPushButton("Send", clicked=self.send_msg)

        inp.addWidget(self.voice_btn)
        inp.addWidget(self.field, 3)
        inp.addWidget(self.send_btn)
        layout.addLayout(inp)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready")

    def setup_tray(self):
        """Add system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show)
        hide_action = tray_menu.addAction("Hide")
        hide_action.triggered.connect(self.hide)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.tray_click)

    def tray_click(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event):
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        shortcut_send = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut_send.activated.connect(self.send_msg)

        shortcut_voice = QShortcut(QKeySequence("Ctrl+V"), self)
        shortcut_voice.activated.connect(self.toggle_voice)

        shortcut_quit = QShortcut(QKeySequence("Ctrl+Q"), self)
        shortcut_quit.activated.connect(self.close)

    def add_msg(self, sender, text):
        clr, pfx = ("#ffb3d9", "You") if sender == "You" else ("#ff3399", "Rico")
        self.chat.append(f"<div style='margin:4px 0;'><b style='color:{clr};'>{pfx}:</b> <span style='color:#fff;'>{text}</span></div>")
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        Path("chat_history.txt").write_text(self.chat.toPlainText())

    def send_msg(self):
        txt = self.field.text().strip()
        if not txt:
            return
        self.field.clear()
        self.add_msg("You", txt)
        self.status.showMessage("Thinking...")
        self.send_btn.setEnabled(False)
        self.chat.append("<div style='color:#ff69b4;font-style:italic;'>Rico is typing...</div>")
        threading.Thread(target=self._process, args=(txt,), daemon=True).start()

    def _process(self, txt):
        try:
            res = self.rico.chat(txt)
            cursor = self.chat.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            self.add_msg("Rico", res)
            self.status.showMessage("Ready")
        except Exception as e:
            self.add_msg("Rico", f"Glitch: {str(e)}")
            self.status.showMessage("Error")
        finally:
            self.send_btn.setEnabled(True)

    def toggle_voice(self):
        active = self.voice_btn.isChecked()
        self.voice_btn.setText("REC" if active else "MIC")
        self.status.showMessage("Listening..." if active else "Ready")

    def show_calendar(self):
        self.add_msg("Rico", "Checking calendar...")
        result = self.rico.get_calendar_events()
        self.add_msg("Rico", result)

    def show_reminders(self):
        self.add_msg("Rico", "Checking reminders...")
        result = self.rico.get_reminders()
        self.add_msg("Rico", result)

    def volume_ui(self):
        level, ok = QInputDialog.getInt(self, "Set Volume", "Volume (0-100):", 50, 0, 100)
        if ok:
            self.add_msg("Rico", self.rico.set_volume(level))

    def brightness_ui(self):
        level, ok = QInputDialog.getInt(self, "Set Brightness", "Brightness (0-100):", 50, 0, 100)
        if ok:
            self.add_msg("Rico", self.rico.set_brightness(level))

    def dark_mode_ui(self):
        self.add_msg("Rico", self.rico.toggle_dark_mode())

    def analyze_image_ui(self):
        """Open file dialog and analyze selected image"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Image", os.path.expanduser("~"),
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.tiff)"
        )
        if filepath:
            self.add_msg("Rico", f"Analyzing {os.path.basename(filepath)}...")
            result = self.rico.analyze_image_file(filepath)
            self.add_msg("Rico", f"Analysis: {result}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = RicoGUI()
    win.show()
    sys.exit(app.exec_())
