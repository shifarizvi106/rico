import os
import re
import datetime
import json
import webbrowser
import subprocess
import threading
import time
import random
import sqlite3
import base64
import operator
from pathlib import Path
from io import BytesIO
from typing import Optional, Dict, List, Any, Tuple, Union

import requests
from PIL import Image
from dotenv import load_dotenv


try:
    import wikipedia
except ImportError:
    wikipedia = None

try:
    import wolframalpha
except ImportError:
    wolframalpha = None

# ===== NEW: Google GenAI SDK =====
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    from playsound import playsound
except ImportError:
    playsound = None

try:
    from googletrans import Translator, LANGUAGES
except ImportError:
    Translator = None
    LANGUAGES = {}

try:
    from rico_rag import RicoRAG
except ImportError:
    RicoRAG = None

try:
    from playwright.sync_api import sync_playwright
    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False

try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False

try:
    import pyaudio
except ImportError:
    pyaudio = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import pyautogui
except ImportError:
    pyautogui = None


# ---------------------------------------------------------------------------
# Rico Assistant
# ---------------------------------------------------------------------------
class RicoAssistant:
    """
    Rico — A multilingual local AI assistant with voice, memory,
    system control, calendar integration, and document understanding.

    Features:
        - Multilingual support (English, Hindi, Urdu)
        - Voice input/output with multiple TTS engines
        - Persistent memory via SQLite
        - macOS system integration (calendar, reminders, volume, brightness)
        - Web search, news, weather, Wikipedia
        - Image analysis and screenshots via Gemini
        - PDF summarisation
        - RAG (Retrieval-Augmented Generation) for document Q&A
        - Wake word detection ("Hey Rico")
        - Proactive engagement after idle periods
    """

    SUPPORTED_LANGS: List[str] = ["en", "hi", "ur"]
    DEFAULT_LANG: str = "en"
    VOICE_MAP: Dict[str, str] = {
        "en": "en-US-JennyNeural",
        "hi": "hi-IN-SwaraNeural",
        "ur": "ur-PK-UzmaNeural",
    }
    PROACTIVE_INTERVAL: int = 300  # seconds
    PREDICT_INTERVAL: int = 300    # seconds
    IDLE_SHORT: float = 6.0        # hours
    IDLE_LONG: float = 12.0        # hours

    # -----------------------------------------------------------------------
    # Initialisation
    # -----------------------------------------------------------------------
    def __init__(self, text_mode: bool = False, memory_enabled: bool = True) -> None:
        """
        Initialize Rico Assistant.

        Args:
            text_mode: Force text-only mode (no voice I/O).
            memory_enabled: Enable persistent SQLite memory storage.
        """
        load_dotenv()

        self.text_mode: bool = text_mode or (sr is None)
        if sr is None and not text_mode:
            print("WARNING: SpeechRecognition not found. Forcing text mode.")

        self.language_code: str = self.DEFAULT_LANG
        self.memory_enabled: bool = memory_enabled
        self.name: str = "Rico"
        self.wake_word_enabled: bool = False
        self.rag_mode: str = "auto"
        self.last_interaction: datetime.datetime = datetime.datetime.now()
        self.last_active: datetime.datetime = datetime.datetime.now()
        self.conversation_history: List[Dict[str, str]] = []
        self.image_cache: List[str] = []
        self._last_prediction: Optional[str] = None
        self._db_lock: threading.Lock = threading.Lock()
        self.genai_client: Optional[Any] = None  # New client

        # External clients
        self.translator: Optional[Any] = Translator() if Translator else None
        self.wolfram_client: Optional[Any] = self._initialize_wolfram()
        self.llm_model: Optional[Any] = self._initialize_gemini()  # Now returns the client
        self.rag: Optional[Any] = RicoRAG() if RicoRAG else None

        # Personality & memory
        self.soul: str = self._load_soul()
        self.personality: Dict[str, Any] = self._load_personality()
        self.user_info: Dict[str, str] = self._load_user_info()

        if self.memory_enabled:
            self._init_memory_db()

        # Background services
        self._start_proactive_loop()
        self._start_predict_loop()

        if PORCUPINE_AVAILABLE and pyaudio:
            self.wake_word_enabled = True
            self._start_wake_word_listener()
        else:
            print("Wake word disabled — install pvporcupine and pyaudio.")

        print(f" {self.name} is online!")
        print(f" Supported languages: {', '.join(self.SUPPORTED_LANGS)}")
        print(f" Memory: {'Enabled' if self.memory_enabled else 'Disabled'}")

    # -----------------------------------------------------------------------
    # Soul & Personality
    # -----------------------------------------------------------------------
    def _load_soul(self) -> str:
        """Load the assistant's soul/personality prompt from file."""
        soul_path = Path("data/soul.md")
        if soul_path.exists():
            try:
                return soul_path.read_text(encoding="utf-8")
            except Exception as exc:
                print(f"Could not read soul: {exc}")
        return "You are Rico, a helpful AI assistant."

    def _load_personality(self) -> Dict[str, Any]:
        """Load default personality configuration."""
        return {
            "name": self.name,
            "traits": ["confident", "witty", "helpful", "slightly sarcastic"],
            "greeting": "Hey! I am Rico. How can I help you today?",
            "farewell": "Bye! I will be here when you need me.",
        }

    def _load_user_info(self) -> Dict[str, str]:
        """Load persisted user information from JSON file."""
        info_path = Path.home() / "rico_user_info.json"
        if info_path.exists():
            try:
                return json.loads(info_path.read_text())
            except Exception:
                pass
        return {}

    def _save_user_info(self) -> None:
        """Persist user information to JSON file."""
        info_path = Path.home() / "rico_user_info.json"
        try:
            info_path.write_text(json.dumps(self.user_info, indent=2))
        except Exception as exc:
            print(f"Could not save user info: {exc}")

    # -----------------------------------------------------------------------
    # External API initialisation
    # -----------------------------------------------------------------------
    def _initialize_wolfram(self) -> Optional[Any]:
        """Initialize WolframAlpha client if API key is available."""
        app_id = os.getenv("WOLFRAM_APP_ID")
        if not app_id or wolframalpha is None:
            print("WolframAlpha not configured.")
            return None
        return wolframalpha.Client(app_id)

    def _initialize_gemini(self) -> Optional[Any]:
        """
        Initialize Gemini using the new google-genai SDK.

        Returns:
            The Gemini client object, or None if unavailable.
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or not GENAI_AVAILABLE:
            print("Gemini API key not found or google-genai SDK not installed.")
            print("Install: pip install google-genai")
            return None

        try:
            self.genai_client = genai.Client(api_key=api_key)
            print("✅ Gemini 2.0 configured (new SDK)")
            return self.genai_client
        except Exception as e:
            print(f"Gemini init error: {e}")
            return None

    # -----------------------------------------------------------------------
    # Database (thread-safe)
    # -----------------------------------------------------------------------
    def _db_path(self) -> Path:
        """Return the path to the SQLite memory database."""
        return Path.home() / "rico_memory.db"

    def _db_execute(self, query: str, params: Tuple = ()) -> List[Tuple]:
        """
        Execute a SQLite query in a thread-safe manner.

        Args:
            query: SQL query string.
            params: Query parameters.

        Returns:
            List of result rows.
        """
        with self._db_lock:
            conn = sqlite3.connect(str(self._db_path()), check_same_thread=False)
            try:
                cur = conn.cursor()
                cur.execute(query, params)
                conn.commit()
                return cur.fetchall()
            finally:
                conn.close()

    def _init_memory_db(self) -> None:
        """Initialize the SQLite database schema for conversations and facts."""
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                user_input TEXT,
                response TEXT,
                language TEXT
            )
            """
        )
        self._db_execute(
            """
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY,
                fact_type TEXT,
                fact_value TEXT,
                confidence REAL,
                timestamp TEXT
            )
            """
        )

    def _log_conversation(self, user_input: str, response: str, language: str) -> None:
        """Log a conversation turn to the database."""
        if not self.memory_enabled:
            return
        self._db_execute(
            "INSERT INTO conversations (timestamp, user_input, response, language) VALUES (?, ?, ?, ?)",
            (datetime.datetime.now().isoformat(), user_input, response, language),
        )

    def _remember_fact(self, fact_type: str, fact_value: str, confidence: float = 0.8) -> None:
        """
        Store a fact about the user in both JSON cache and SQLite.

        Args:
            fact_type: Category or key for the fact.
            fact_value: The fact itself.
            confidence: Confidence score (0.0–1.0).
        """
        if not self.memory_enabled:
            return
        self.user_info[fact_type] = fact_value
        self._save_user_info()
        self._db_execute(
            "INSERT INTO facts (fact_type, fact_value, confidence, timestamp) VALUES (?, ?, ?, ?)",
            (fact_type, fact_value, confidence, datetime.datetime.now().isoformat()),
        )
        print(f"Remembered: {fact_type} = {fact_value}")

    def _recall_fact(self, fact_type: str) -> Optional[str]:
        """
        Recall a stored fact about the user.

        Args:
            fact_type: The fact key to look up.

        Returns:
            The fact value, or None if not found.
        """
        if fact_type in self.user_info:
            return self.user_info[fact_type]
        rows = self._db_execute(
            "SELECT fact_value FROM facts WHERE fact_type = ? ORDER BY timestamp DESC LIMIT 1",
            (fact_type,),
        )
        return rows[0][0] if rows else None

    # -----------------------------------------------------------------------
    # Language
    # -----------------------------------------------------------------------
    def _detect_language(self, text: str) -> str:
        """
        Detect whether the input text is English, Hindi, or Urdu.

        Args:
            text: Input text to analyse.

        Returns:
            Language code: 'en', 'hi', or 'ur'.
        """
        hindi_chars = set(
            "अआइईउऊऋएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह"
        )
        urdu_chars = set("یئؤےں")
        for ch in text:
            if ch in hindi_chars:
                return "hi"
            if ch in urdu_chars:
                return "ur"
        return "en"

    def _translate(self, text: str, src: str, dest: str) -> str:
        """
        Translate text between languages.

        Args:
            text: Text to translate.
            src: Source language code.
            dest: Destination language code.

        Returns:
            Translated text, or original on failure.
        """
        if src == dest or not self.translator:
            return text
        try:
            return self.translator.translate(text, src=src, dest=dest).text
        except Exception as exc:
            print(f"Translation error: {exc}")
            return text

    # -----------------------------------------------------------------------
    # Voice I/O
    # -----------------------------------------------------------------------
    def speak(self, text: str, lang: Optional[str] = None) -> None:
        """
        Speak text using the best available TTS engine.

        Args:
            text: Text to speak.
            lang: Language code override. Uses current language if None.
        """
        if not text:
            return
        lang = lang or self.language_code
        print(f" {self.name} ({lang}): {text}")

        # Try edge-tts first (best quality)
        try:
            import edge_tts
            import asyncio

            voice = self.VOICE_MAP.get(lang, self.VOICE_MAP["en"])
            out_path = Path.home() / "rico_response.mp3"

            async def _edge() -> None:
                tts = edge_tts.Communicate(text, voice)
                await tts.save(str(out_path))

            asyncio.run(_edge())
            self._play_audio(str(out_path))
            out_path.unlink(missing_ok=True)
            return
        except Exception as exc:
            print(f"edge-tts failed: {exc}")

        # Fallback to gTTS
        if gTTS:
            try:
                out_path = Path.home() / "rico_response.mp3"
                tts = gTTS(text=text, lang=lang, slow=False)
                tts.save(str(out_path))
                self._play_audio(str(out_path))
                out_path.unlink(missing_ok=True)
                return
            except Exception as exc:
                print(f"gTTS failed: {exc}")

    def _play_audio(self, path: str) -> None:
        """Play an audio file using the best available player."""
        if playsound:
            try:
                playsound(path)
                return
            except Exception:
                pass
        # macOS fallback
        try:
            subprocess.run(["afplay", path], check=True, capture_output=True)
            return
        except Exception:
            pass
        # Linux fallback
        try:
            subprocess.run(["mpg123", path], check=True, capture_output=True)
            return
        except Exception:
            pass
        print("Could not play audio — no suitable player found.")

    def _listen(self) -> str:
        """
        Listen for voice input via microphone.

        Returns:
            Recognised text, or empty string on failure/timeout.
        """
        if sr is None:
            return ""
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                return recognizer.recognize_google(audio, language=self.language_code).lower()
            except sr.WaitTimeoutError:
                return ""
            except sr.UnknownValueError:
                return ""
            except sr.RequestError as exc:
                print(f"Speech recognition error: {exc}")
                return ""

    # -----------------------------------------------------------------------
    # System utilities
    # -----------------------------------------------------------------------
    @staticmethod
    def _escape_applescript(text: str) -> str:
        """Escape quotes for safe AppleScript insertion."""
        return text.replace("\\", "\\\\").replace('"', '\\"')

    def _open_youtube(self) -> str:
        """Open YouTube in the default browser."""
        self.speak("Opening YouTube...")
        webbrowser.open("https://www.youtube.com")
        return "Opened YouTube."

    def _open_google(self) -> str:
        """Open Google in the default browser."""
        self.speak("Opening Google...")
        webbrowser.open("https://www.google.com")
        return "Opened Google."

    def _open_spotify(self) -> str:
        """Open Spotify application."""
        self.speak("Opening Spotify...")
        subprocess.run(["open", "-a", "Spotify"], capture_output=True)
        return "Opened Spotify."

    def _open_vscode(self) -> str:
        """Open Visual Studio Code application."""
        self.speak("Opening Visual Studio Code...")
        subprocess.run(["open", "-a", "Visual Studio Code"], capture_output=True)
        return "Opened VS Code."

    def _get_time(self) -> str:
        """Return and speak the current time."""
        now = datetime.datetime.now().strftime("%I:%M %p")
        self.speak(f"The time is {now}")
        return f"The time is {now}."

    def _get_date(self) -> str:
        """Return and speak today's date."""
        today = datetime.datetime.now().strftime("%B %d, %Y")
        self.speak(f"Today is {today}")
        return f"Today is {today}."

    def _get_system_status(self) -> str:
        """Return CPU, memory, and battery status."""
        if psutil is None:
            return "System status unavailable (psutil not installed)."
        cpu = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        status = f"CPU: {cpu}%, Memory: {memory.percent}%"
        if battery:
            status += f", Battery: {battery.percent}%"
            if battery.power_plugged:
                status += " (charging)"
        return status

    def _set_volume(self, level: int) -> str:
        """Set system output volume (macOS)."""
        if not 0 <= level <= 100:
            return "Volume must be between 0 and 100."
        try:
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"], check=True)
            return f"Volume set to {level}%."
        except Exception as exc:
            return f"Could not set volume: {exc}"

    def _set_brightness(self, level: int) -> str:
        """Set display brightness (macOS)."""
        if not 0 <= level <= 100:
            return "Brightness must be between 0 and 100."
        frac = level / 100.0
        # Try brightness CLI first
        try:
            subprocess.run(["brightness", str(frac)], check=True, capture_output=True)
            return f"Brightness set to {level}%."
        except Exception:
            pass
        # AppleScript fallback
        try:
            script = f'tell application "System Events" to set brightness of display 1 to {frac}'
            subprocess.run(["osascript", "-e", script], check=True)
            return f"Brightness set to {level}%."
        except Exception as exc:
            return f"Could not set brightness: {exc}"

    def _toggle_dark_mode(self) -> str:
        """Toggle macOS dark mode."""
        try:
            script = 'tell application "System Events" to tell appearance preferences to set dark mode to not dark mode'
            subprocess.run(["osascript", "-e", script], check=True)
            return "Dark mode toggled."
        except Exception as exc:
            return f"Could not toggle dark mode: {exc}"

    def _lock_screen(self) -> str:
        """Lock the macOS screen."""
        try:
            subprocess.run(
                ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"],
                check=True,
                capture_output=True,
            )
            return "Screen locked."
        except Exception as exc:
            return f"Could not lock screen: {exc}"

    def send_notification(self, title: str, message: str) -> None:
        """Send a native macOS notification."""
        safe_title = self._escape_applescript(title)
        safe_msg = self._escape_applescript(message)
        script = f'display notification "{safe_msg}" with title "{safe_title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True)

    # -----------------------------------------------------------------------
    # Web & Knowledge
    # -----------------------------------------------------------------------
    def _search_wikipedia(self, query: str) -> str:
        """Search Wikipedia and return a summary."""
        if wikipedia is None:
            return "Wikipedia library not installed."
        search_term = query.replace("wikipedia", "").strip()
        try:
            summary = wikipedia.summary(search_term, sentences=3, auto_suggest=False)
            return f"According to Wikipedia: {summary}"
        except wikipedia.exceptions.DisambiguationError as exc:
            return f"Too many results. Did you mean: {', '.join(exc.options[:3])}?"
        except wikipedia.exceptions.PageError:
            return "No Wikipedia page found."
        except Exception as exc:
            return f"Wikipedia error: {exc}"

    def search_web(self, query: str) -> str:
        """Open a web search in the default browser."""
        webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
        return f"Searching for '{query}'..."

    def get_news(self) -> str:
        """Fetch top news headlines via NewsAPI."""
        api_key = os.getenv("NEWS_API_KEY")
        if not api_key:
            return "Add NEWS_API_KEY to your .env file."
        try:
            url = f"https://newsapi.org/v2/top-headlines?country=in&apiKey={api_key}"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])[:5]
            headlines = [f"{i+1}. {a['title']}" for i, a in enumerate(articles)]
            return "Top headlines:\n" + "\n".join(headlines)
        except Exception as exc:
            return f"Could not fetch news: {exc}"

    def get_weather(self, location: str = "") -> str:
        """Get weather from wttr.in. Empty location uses IP geolocation."""
        try:
            loc = location if location and location != "current" else ""
            url = f"https://wttr.in/{loc}?format=%C+%t+%w"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            return f"Weather: {resp.text.strip()}"
        except Exception as exc:
            return f"Weather unavailable: {exc}"

    def _search_web_images(self, query: str, limit: int = 3) -> List[str]:
        """Search images via DuckDuckGo. NOTE: Scraping is fragile."""
        if BeautifulSoup is None:
            return []
        try:
            url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}&iax=images&ia=images"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            images = []
            for img in soup.find_all("img"):
                src = img.get("src")
                if src and src.startswith("http") and "duckduckgo" not in src:
                    images.append(src)
                    if len(images) >= limit:
                        break
            return images[:limit]
        except Exception:
            return []

    # -----------------------------------------------------------------------
    # Images & Screenshots
    # -----------------------------------------------------------------------
    def analyze_image(self, image_path: str, prompt: str = "Describe what you see in this image") -> str:
        """
        Analyse an image using the Gemini vision model.

        Args:
            image_path: Path to the image file.
            prompt: Custom prompt for the analysis.

        Returns:
            AI-generated description of the image.
        """
        if self.genai_client is None:
            return "Gemini client not initialized. Check your API key."

        path = Path(image_path).expanduser()
        if not path.exists():
            return f"File not found: {path}"

        try:
            img = Image.open(path)
            img.thumbnail((800, 800))
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

            response = self.genai_client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[
                    prompt,
                    {"mime_type": "image/png", "data": img_data},
                ]
            )
            return response.text.strip()
        except Exception as exc:
            return f"Analysis error: {exc}"

    def take_screenshot(self) -> str:
        """Capture the screen and analyse it with AI."""
        if pyautogui is None:
            return "pyautogui not installed."
        try:
            path = Path.home() / "rico_screenshot.png"
            screenshot = pyautogui.screenshot()
            screenshot.save(path)
            result = self.analyze_image(str(path), "Describe what you see in this screenshot.")
            return f"Screenshot analyzed:\n{result}"
        except Exception as exc:
            return f"Could not take screenshot: {exc}"

    def analyze_image_file(self, filepath: str, prompt: str = "Describe what you see.") -> str:
        """Analyse an image file with a custom prompt."""
        return self.analyze_image(filepath, prompt)

    # -----------------------------------------------------------------------
    # Calendar & Reminders (macOS)
    # -----------------------------------------------------------------------
    def get_calendar_events(self, days: int = 7) -> str:
        """Fetch upcoming calendar events from macOS Calendar."""
        try:
            script = f"""
            tell application "Calendar"
                set startDate to current date
                set endDate to startDate + ({days} * days)
                set theEvents to every event of calendar 1 whose start date ≥ startDate and start date ≤ endDate
                set eventList to ""
                repeat with anEvent in theEvents
                    set eventTitle to summary of anEvent
                    set eventDate to start date of anEvent
                    set eventTime to time string of eventDate
                    set eventList to eventList & eventTitle & " at " & eventTime & "|"
                end repeat
                return eventList
            end tell
            """
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            events = result.stdout.strip()
            if events:
                event_list = [e.strip() for e in events.split("|") if e.strip()]
                if event_list:
                    return "Upcoming events:\n" + "\n".join([f"  • {e}" for e in event_list[:10]])
            return "No upcoming events found."
        except Exception as exc:
            return f"Could not get calendar: {exc}"

    def add_calendar_event(self, title: str, date: Optional[str] = None, time_str: Optional[str] = None, duration: int = 60) -> str:
        """Add an event to macOS Calendar."""
        try:
            date = date or datetime.datetime.now().strftime("%Y-%m-%d")
            time_str = time_str or "09:00"
            start_dt = f"{date} {time_str}:00"
            end_dt = (
                datetime.datetime.strptime(start_dt, "%Y-%m-%d %H:%M:%S")
                + datetime.timedelta(minutes=duration)
            ).strftime("%Y-%m-%d %H:%M:%S")
            safe_title = self._escape_applescript(title)
            script = f"""
            tell application "Calendar"
                tell calendar "Home"
                    make new event with properties {{summary:"{safe_title}", start date:date "{start_dt}", end date:date "{end_dt}"}}
                end tell
            end tell
            """
            subprocess.run(["osascript", "-e", script], check=True)
            return f"Event '{title}' added for {date} at {time_str}."
        except Exception as exc:
            return f"Could not add event: {exc}"

    def set_reminder(self, text: str, time_str: str, date: Optional[str] = None) -> str:
        """Set a reminder in macOS Reminders."""
        try:
            date = date or datetime.datetime.now().strftime("%Y-%m-%d")
            due_dt = f"{date} {time_str}:00"
            safe_text = self._escape_applescript(text)
            script = f"""
            tell application "Reminders"
                tell default list
                    make new reminder with properties {{name:"{safe_text}", due date:date "{due_dt}"}}
                end tell
            end tell
            """
            subprocess.run(["osascript", "-e", script], check=True)
            return f"Reminder set: '{text}' for {date} at {time_str}."
        except Exception as exc:
            return f"Could not set reminder: {exc}"

    def get_reminders(self) -> str:
        """Fetch active reminders from macOS Reminders."""
        try:
            script = """
            tell application "Reminders"
                tell default list
                    set reminderList to ""
                    repeat with aReminder in reminders
                        if completed of aReminder is false then
                            set reminderTitle to name of aReminder
                            set reminderDate to due date of aReminder
                            if reminderDate is not missing value then
                                set reminderList to reminderList & reminderTitle & " (due: " & (date string of reminderDate) & " at " & (time string of reminderDate) & ")|"
                            else
                                set reminderList to reminderList & reminderTitle & " (no due date)|"
                            end if
                        end if
                    end repeat
                    return reminderList
                end tell
            end tell
            """
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            reminders = result.stdout.strip()
            if reminders:
                rem_list = [r.strip() for r in reminders.split("|") if r.strip()]
                if rem_list:
                    return "Your reminders:\n" + "\n".join([f"  • {r}" for r in rem_list[:10]])
            return "No active reminders."
        except Exception as exc:
            return f"Could not get reminders: {exc}"

    def complete_reminder(self, title: str) -> str:
        """Mark a reminder as completed."""
        try:
            safe_title = self._escape_applescript(title)
            script = f"""
            tell application "Reminders"
                tell default list
                    repeat with aReminder in reminders
                        if name of aReminder contains "{safe_title}" then
                            set completed of aReminder to true
                            return "Completed: " & name of aReminder
                        end if
                    end repeat
                    return "Reminder not found"
                end tell
            end tell
            """
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return result.stdout.strip()
        except Exception as exc:
            return f"Could not complete reminder: {exc}"

    # -----------------------------------------------------------------------
    # Local photos
    # -----------------------------------------------------------------------
    def _search_local_images(self, date_query: str) -> List[str]:
        """Search local Photos library for images matching a date query."""
        parsed = self._parse_date_query(date_query)
        if not parsed:
            return []
        pictures_dir = Path.home() / "Pictures"
        if not pictures_dir.exists():
            return []
        results = []
        for file_path in pictures_dir.rglob("*"):
            if file_path.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".heic"):
                try:
                    mtime = datetime.datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime.year == parsed.year and mtime.month == parsed.month and mtime.day == parsed.day:
                        results.append(str(file_path))
                        if len(results) >= 3:
                            return results
                except Exception:
                    continue
        return results

    def _parse_date_query(self, query: str) -> Optional[datetime.datetime]:
        """
        Parse natural language date queries into datetime objects.

        Supports: today, yesterday, last N days, Month Day Year.
        """
        q = query.lower()
        today = datetime.datetime.now()
        if "today" in q or "now" in q:
            return today
        if "yesterday" in q:
            return today - datetime.timedelta(days=1)
        days_match = re.search(r"last\s+(\d+)\s+days?", q)
        if days_match:
            return today - datetime.timedelta(days=int(days_match.group(1)))
        date_match = re.search(r"(\w+)\s+(\d+)(?:\s*,?\s*(\d{4}))?", q)
        if date_match:
            month_name = date_match.group(1)
            day = int(date_match.group(2))
            year = int(date_match.group(3)) if date_match.group(3) else today.year
            months = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }
            month = months.get(month_name.lower(), 0)
            if month > 0:
                try:
                    return datetime.datetime(year, month, day)
                except ValueError:
                    return None
        return None

    # -----------------------------------------------------------------------
    # AI / LLM
    # -----------------------------------------------------------------------
    def _calculate(self, query: str) -> Optional[str]:
        """
        Safely evaluate simple arithmetic expressions.

        Args:
            query: String containing a math expression like "5 + 3".

        Returns:
            Result string, or None if no math detected.
        """
        match = re.search(r"(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)", query)
        if not match:
            return None
        try:
            a, op, b = match.group(1), match.group(2), match.group(3)
            a_f, b_f = float(a), float(b)
            ops = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv}
            result = ops[op](a_f, b_f)
            if result == int(result):
                result = int(result)
            return f"The result is {result}"
        except Exception:
            return None

    def _process_ai_query(self, query: str) -> str:
        """
        Process a query through the AI pipeline: math → Wolfram → RAG → Gemini.

        Args:
            query: The user's question in English.

        Returns:
            AI-generated response string.
        """
        # 1. Math
        calc = self._calculate(query)
        if calc:
            return calc

        # 2. WolframAlpha
        if self.wolfram_client:
            try:
                res = self.wolfram_client.query(query)
                answer = next(res.results).text
                return f"According to calculations: {answer}"
            except Exception:
                pass

        # 3. RAG
        if self.rag and self.is_rag_enabled():
            try:
                rag_result = self.rag.query(query, k=3)
                if rag_result and "No relevant information found" not in rag_result:
                    if self.genai_client:
                        prompt = f"""
# Soul
{self.soul}

# Knowledge Base
{rag_result}

# User Question
{query}

# Response
Use the knowledge base above to answer. Cite your source. Be personal and concise.
"""
                        response = self.genai_client.models.generate_content(
                            model="gemini-2.0-flash-exp",
                            contents=prompt
                        )
                        return response.text.strip()
                    return f"From your documents:\n\n{rag_result}"
            except Exception as exc:
                print(f"RAG lookup error: {exc}")

        # 4. Gemini fallback
        if self.genai_client:
            try:
                traits = ", ".join(self.personality.get("traits", [])) if isinstance(self.personality, dict) else ""
                prompt = f"""
# Soul
{self.soul}

# Traits
{traits}

# User
{query}

# Response
"""
                response = self.genai_client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=prompt
                )
                return response.text.strip()
            except Exception as exc:
                return f"AI error: {exc}"

        return "AI offline."

    # -----------------------------------------------------------------------
    # RAG interface
    # -----------------------------------------------------------------------
    def index_documents(self, folder: str) -> str:
        """Index a folder of documents for RAG search."""
        if self.rag is None:
            return "RAG not available."
        return self.rag.index_folder(folder)

    def search_knowledge(self, query: str) -> str:
        """Search the indexed knowledge base."""
        if self.rag is None:
            return "RAG not available."
        return self.rag.query(query)

    def get_knowledge_stats(self) -> str:
        """Get statistics about the knowledge base."""
        if self.rag is None:
            return "RAG not available."
        return self.rag.get_stats()

    def toggle_rag_mode(self, mode: Optional[str] = None) -> str:
        """
        Toggle RAG search mode: auto, manual, or off.

        Args:
            mode: Specific mode to set, or None to cycle.

        Returns:
            Confirmation message with current mode.
        """
        modes = ["auto", "manual", "off"]
        if mode is None:
            current_idx = modes.index(self.rag_mode)
            self.rag_mode = modes[(current_idx + 1) % len(modes)]
        elif mode in modes:
            self.rag_mode = mode
        else:
            return f"Invalid mode. Choose from: {', '.join(modes)}"
        return f"RAG mode: {self.rag_mode.upper()}"

    def is_rag_enabled(self) -> bool:
        """Check if RAG should be used for queries."""
        return self.rag_mode != "off"

    # -----------------------------------------------------------------------
    # PDF Summarisation
    # -----------------------------------------------------------------------
    def summarize_pdf(self, filepath: str, sentences: int = 5) -> str:
        """
        Extract and summarise text from a PDF file.

        Args:
            filepath: Path to the PDF file.
            sentences: Number of sentences for the summary.

        Returns:
            AI-generated summary or error message.
        """
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            return "PyPDF2 not installed. Run: pip install PyPDF2"

        path = Path(filepath).expanduser()
        if not path.exists():
            return f"File not found: {path}"

        try:
            text = ""
            with open(path, "rb") as f:
                reader = PdfReader(f)
                pages_to_read = min(len(reader.pages), 10)
                for i in range(pages_to_read):
                    page_text = reader.pages[i].extract_text()
                    if page_text:
                        text += page_text + "\n"

            if not text.strip():
                return "Could not extract text — PDF may be scanned or image-based."

            text = text[:5000]
            if self.genai_client:
                prompt = f"""
Summarize the following PDF content in {sentences} clear, concise sentences.
Focus on the main points and key takeaways.

PDF Content:
{text}

Summary:
"""
                response = self.genai_client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=prompt
                )
                return response.text.strip()
            return "Gemini client not available."
        except Exception as exc:
            return f"PDF summarisation error: {exc}"

    # -----------------------------------------------------------------------
    # Automation (Playwright)
    # -----------------------------------------------------------------------
    def automate(self, task: str) -> str:
        """Automate a web search using Playwright."""
        if not WEB_AVAILABLE:
            return "Playwright not available. Install: pip install playwright && playwright install"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(f"https://google.com/search?q={task.replace(' ', '+')}")
                return f"Opened search for: {task}"
        except Exception as exc:
            return f"Automation error: {exc}"

    # -----------------------------------------------------------------------
    # Wake word
    # -----------------------------------------------------------------------
    def _start_wake_word_listener(self) -> None:
        """Start background thread listening for 'Hey Rico' wake word."""
        if not PORCUPINE_AVAILABLE or pyaudio is None:
            return

        def listener():
            porcupine = None
            stream = None
            pa = None
            try:
                porcupine = pvporcupine.create(keywords=["hey rico"])
                pa = pyaudio.PyAudio()
                stream = pa.open(
                    rate=porcupine.sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    frames_per_buffer=porcupine.frame_length,
                )
                print("Listening for 'Hey Rico'...")
                while True:
                    pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
                    if porcupine.process(pcm) >= 0:
                        self._on_wake_word()
            except Exception as exc:
                print(f"Wake word error: {exc}")
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
                if pa:
                    pa.terminate()
                if porcupine:
                    porcupine.delete()

        threading.Thread(target=listener, daemon=True).start()

    def _on_wake_word(self) -> None:
        """Handle wake word detection."""
        self.speak("Yes? I am listening.")
        if not self.text_mode:
            command = self._listen()
            if command:
                self.process_query(command)

    def toggle_wake_word(self) -> str:
        """Toggle wake word detection on/off."""
        self.wake_word_enabled = not self.wake_word_enabled
        return f"Wake word {'enabled' if self.wake_word_enabled else 'disabled'}."


    # -----------------------------------------------------------------------
    # Focus Mode & Pomodoro
    # -----------------------------------------------------------------------
    def _toggle_focus_mode(self, duration_minutes: Optional[int] = None) -> str:
        """
        Toggle Do Not Disturb / Focus mode on macOS.
        Optionally start a Pomodoro-style timer.

        Args:
            duration_minutes: If provided, automatically turns off DND after this many minutes.

        Returns:
            Confirmation message.
        """
        try:
            script = 'tell application "System Events" to tell application process "Control Center" to click menu bar item 1 of menu bar 1'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        except Exception:
            pass

        if duration_minutes and duration_minutes > 0:
            def _focus_complete():
                self.speak("Focus time is up. Great work!")
                self.send_notification("Rico", "Your focus session has ended.")

            timer = threading.Timer(duration_minutes * 60, _focus_complete)
            timer.daemon = True
            timer.start()
            return f"Focus mode enabled for {duration_minutes} minutes. I will let you know when it is done."

        return "Focus mode toggled."

    # -----------------------------------------------------------------------
    # Window Management (macOS)
    # -----------------------------------------------------------------------
    def _window_tile_left(self) -> str:
        """Tile the frontmost window to the left half of the screen."""
        return self._window_position("left")

    def _window_tile_right(self) -> str:
        """Tile the frontmost window to the right half of the screen."""
        return self._window_position("right")

    def _window_maximise(self) -> str:
        """Maximise the frontmost window."""
        return self._window_position("maximise")

    def _window_close_others(self) -> str:
        """Close all windows of the frontmost app except the active one."""
        try:
            script = 'tell application "System Events" to set frontApp to name of first application process whose frontmost is true'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            front_app = result.stdout.strip()
            if not front_app:
                return "Could not identify frontmost application."

            close_script = 'tell application "' + front_app + '" to close (every window whose index > 1)'
            subprocess.run(["osascript", "-e", close_script], check=True, capture_output=True)
            return "Closed other windows."
        except Exception as exc:
            return f"Could not close windows: {exc}"

    def _window_position(self, position: str) -> str:
        """
        Position the frontmost window using AppleScript.

        Args:
            position: 'left', 'right', or 'maximise'.
        """
        try:
            size_script = 'tell application "Finder" to get bounds of window of desktop'
            result = subprocess.run(["osascript", "-e", size_script], capture_output=True, text=True, check=True)
            bounds = result.stdout.strip().replace("{", "").replace("}", "").split(", ")
            screen_w = int(bounds[2])
            screen_h = int(bounds[3])

            if position == "left":
                x, y, w, h = 0, 25, screen_w // 2, screen_h - 25
            elif position == "right":
                x, y, w, h = screen_w // 2, 25, screen_w // 2, screen_h - 25
            elif position == "maximise":
                x, y, w, h = 0, 25, screen_w, screen_h - 25
            else:
                return "Unknown position."

            script = 'tell application "System Events" to set frontApp to name of first application process whose frontmost is true'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            front_app = result.stdout.strip()

            pos_script = 'tell application "' + front_app + '" to set bounds of front window to {' + f"{x}, {y}, {x + w}, {y + h}" + '}'
            subprocess.run(["osascript", "-e", pos_script], check=True, capture_output=True)
            return f"Window moved to {position}."
        except Exception as exc:
            return f"Window management error: {exc}"

    # -----------------------------------------------------------------------
    # Apple Notes
    # -----------------------------------------------------------------------
    def _create_note(self, title: str, body: str) -> str:
        """
        Create a new note in Apple Notes.

        Args:
            title: Note title.
            body: Note body content.

        Returns:
            Confirmation message.
        """
        safe_title = self._escape_applescript(title)
        safe_body = self._escape_applescript(body)
        try:
            script = 'tell application "Notes" to tell account "iCloud" to tell folder "Notes" to make new note with properties {name:"' + safe_title + '", body:"' + safe_body + '"}'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return f"Note '{title}' created."
        except Exception as exc:
            return f"Could not create note: {exc}"

    def _read_last_note(self) -> str:
        """Read the most recently modified note from Apple Notes."""
        try:
            script = 'tell application "Notes" to set theNote to first note of folder "Notes" of account "iCloud"\nset noteTitle to name of theNote\nset noteBody to body of theNote\nreturn noteTitle & "|" & noteBody'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            parts = result.stdout.strip().split("|", 1)
            if len(parts) == 2:
                return f"Note: {parts[0]}\n\n{parts[1][:500]}"
            return result.stdout.strip()
        except Exception as exc:
            return f"Could not read notes: {exc}"

    def _search_notes(self, query: str) -> str:
        """Search Apple Notes for a query string."""
        safe_query = self._escape_applescript(query)
        try:
            # Use a simpler script approach to avoid f-string brace issues
            script = 'tell application "Notes" to set noteList to ""\nrepeat with aNote in notes of folder "Notes" of account "iCloud"\nif name of aNote contains "' + safe_query + '" then\nset noteList to noteList & (name of aNote) & "|"\nend if\nend repeat\nreturn noteList'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            notes = result.stdout.strip()
            if not notes:
                return "No notes found."
            note_list = [n.strip() for n in notes.split("|") if n.strip()]
            if not note_list:
                return "No notes found."
            return "Found notes:\n" + "\n".join([f"  • {n}" for n in note_list[:10]])
        except Exception as exc:
            return f"Could not search notes: {exc}"

    # -----------------------------------------------------------------------
    # Safari Integration
    # -----------------------------------------------------------------------
    def _safari_summarise(self) -> str:
        """
        Summarise the current Safari page using Gemini.

        Returns:
            AI-generated summary of the page content.
        """
        try:
            script = 'tell application "Safari" to set pageText to do JavaScript "document.body.innerText" in front document\nset pageTitle to name of front document\nreturn pageTitle & "|||" & pageText'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            if "|||" not in output:
                return "Could not extract page content."

            title, text = output.split("|||", 1)
            text = text[:4000]

            if self.genai_client:
                prompt = f"Summarise the following web page in 3-4 concise bullet points.\n\nPage Title: {title}\n\nContent:\n{text}\n\nSummary:"
                response = self.genai_client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=prompt
                )
                return f"Summary of '{title}':\n\n{response.text.strip()}"
            return "Gemini client not available. Cannot summarise page."
        except Exception as exc:
            return f"Safari error: {exc}"

    def _safari_close_other_tabs(self) -> str:
        """Close all Safari tabs except the current front one."""
        try:
            script = 'tell application "Safari" to tell front window to close (every tab whose index is not (get index of current tab))'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return "Closed all other tabs."
        except Exception as exc:
            return f"Could not close tabs: {exc}"

    def _safari_get_url(self) -> str:
        """Return the URL of the current Safari page."""
        try:
            script = 'tell application "Safari" to return URL of front document'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return f"Current page: {result.stdout.strip()}"
        except Exception as exc:
            return f"Could not get URL: {exc}"

    # -----------------------------------------------------------------------
    # MacBook Diagnostics (Bonus)
    # -----------------------------------------------------------------------
    def _get_battery_status(self) -> str:
        """Return detailed battery status for MacBook."""
        if psutil is None:
            return "psutil not installed."
        try:
            battery = psutil.sensors_battery()
            if not battery:
                return "No battery information available."

            try:
                result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, check=True)
                pmset_info = result.stdout.strip()
            except Exception:
                pmset_info = ""

            status = f"Battery: {battery.percent}%"
            if battery.power_plugged:
                status += " (Charging)"
            else:
                secs = battery.secsleft
                if secs != psutil.POWER_TIME_UNLIMITED and secs > 0:
                    hrs = secs // 3600
                    mins = (secs % 3600) // 60
                    status += f" — about {hrs}h {mins}m remaining"
                status += " (On battery)"

            if pmset_info:
                status += f"\n\n{pmset_info}"
            return status
        except Exception as exc:
            return f"Battery error: {exc}"

    def _get_storage_status(self) -> str:
        """Return storage usage breakdown for MacBook."""
        try:
            result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 5:
                    total, used, avail, percent = parts[1], parts[2], parts[3], parts[4]
                    return f"Storage: {used} used of {total} ({percent} full). {avail} available."
            return result.stdout.strip()
        except Exception as exc:
            return f"Storage error: {exc}"

    def _clean_desktop(self) -> str:
        """Move all files from Desktop to an Archive folder organised by date."""
        try:
            desktop = Path.home() / "Desktop"
            archive = Path.home() / "Desktop" / "Archive"
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            archive_folder = archive / today
            archive_folder.mkdir(parents=True, exist_ok=True)

            moved = 0
            for item in desktop.iterdir():
                if item.name == "Archive":
                    continue
                if item.is_file() or item.is_dir():
                    dest = archive_folder / item.name
                    counter = 1
                    while dest.exists():
                        dest = archive_folder / f"{item.stem}_{counter}{item.suffix}"
                        counter += 1
                    item.rename(dest)
                    moved += 1

            if moved == 0:
                return "Desktop is already clean!"
            return f"Moved {moved} item(s) to Desktop/Archive/{today}/"
        except Exception as exc:
            return f"Could not clean desktop: {exc}"


    # -----------------------------------------------------------------------
    # Spotify Integration (AppleScript — no API key needed)
    # -----------------------------------------------------------------------
    def _spotify_play(self, query: str = "") -> str:
        """
        Play, pause, or search and play on Spotify.

        Args:
            query: Search term, or empty to toggle play/pause.

        Returns:
            Confirmation message.
        """
        try:
            if query:
                safe_query = query.replace('"', '\\"')
                script = 'tell application "Spotify" to play track "spotify:search:' + safe_query + '"'
                subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
                return f"Playing '{query}' on Spotify."
            script = 'tell application "Spotify" to playpause'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return "Toggled playback."
        except Exception as exc:
            return f"Spotify error: {exc}"

    def _spotify_next(self) -> str:
        """Skip to the next track on Spotify."""
        try:
            subprocess.run(["osascript", "-e", 'tell application "Spotify" to next track'], check=True, capture_output=True)
            return "Skipped to next track."
        except Exception as exc:
            return f"Spotify error: {exc}"

    def _spotify_previous(self) -> str:
        """Go to the previous track on Spotify."""
        try:
            subprocess.run(["osascript", "-e", 'tell application "Spotify" to previous track'], check=True, capture_output=True)
            return "Previous track."
        except Exception as exc:
            return f"Spotify error: {exc}"

    def _spotify_now_playing(self) -> str:
        """Return the currently playing track on Spotify."""
        try:
            script = 'tell application "Spotify" to return name of current track & " by " & artist of current track'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return f"Now playing: {result.stdout.strip()}"
        except Exception as exc:
            return f"Spotify error: {exc}"

    def _spotify_volume(self, level: int) -> str:
        """Set Spotify playback volume (0-100)."""
        try:
            subprocess.run(["osascript", "-e", f'tell application "Spotify" to set sound volume to {level}'], check=True, capture_output=True)
            return f"Spotify volume set to {level}%."
        except Exception as exc:
            return f"Spotify error: {exc}"

    def _spotify_like(self) -> str:
        """Add the current track to Liked Songs on Spotify."""
        try:
            script = 'tell application "Spotify" to set loved of current track to true'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return "Added to Liked Songs."
        except Exception as exc:
            return f"Spotify error: {exc}"

    # -----------------------------------------------------------------------
    # Email Integration (Mail.app via AppleScript)
    # -----------------------------------------------------------------------
    def _check_email(self) -> str:
        """
        Check unread email count and sender list from Mail.app.

        Returns:
            Summary of unread emails.
        """
        try:
            script = 'tell application "Mail" to set unreadCount to unread count of inbox\nset senderList to ""\nrepeat with msg in (messages of inbox whose read status is false)\nset senderList to senderList & (sender of msg) & "|"\nif length of senderList > 500 then exit repeat\nend repeat\nreturn (unreadCount as string) & "|||" & senderList'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            parts = result.stdout.strip().split("|||", 1)
            count = parts[0]
            senders = [s.strip() for s in parts[1].split("|") if s.strip()][:5]
            if int(count) == 0:
                return "No unread emails."
            unique_senders = list(dict.fromkeys(senders))  # Preserve order, remove duplicates
            return f"You have {count} unread email(s) from: {', '.join(unique_senders)}"
        except Exception as exc:
            return f"Mail error: {exc}"

    def _summarise_email(self) -> str:
        """
        Summarise unread emails using Gemini AI.

        Returns:
            Bullet-point summary of unread email subjects and previews.
        """
        try:
            script = 'tell application "Mail" to set summaries to ""\nrepeat with msg in (messages of inbox whose read status is false)\nset summaries to summaries & "Subject: " & (subject of msg) & "\n" & "Preview: " & (content of msg as string) & "\n---\n"\nif length of summaries > 3000 then exit repeat\nend repeat\nreturn summaries'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            text = result.stdout.strip()[:3000]
            if not text:
                return "No unread emails to summarise."
            if self.genai_client:
                prompt = f"Summarise these unread emails in concise bullet points:\n\n{text}\n\nSummary:"
                response = self.genai_client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=prompt
                )
                return response.text.strip()
            return "Gemini client not available."
        except Exception as exc:
            return f"Mail error: {exc}"

    def _draft_email(self, to: str, subject: str, body: str) -> str:
        """
        Open Mail.app with a pre-filled draft email.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Email body content.

        Returns:
            Confirmation message.
        """
        safe_to = self._escape_applescript(to)
        safe_subj = self._escape_applescript(subject)
        safe_body = self._escape_applescript(body)
        try:
            script = 'tell application "Mail" to set newMessage to make new outgoing message with properties {subject:"' + safe_subj + '", content:"' + safe_body + '"}\ntell newMessage to make new to recipient at end of to recipients with properties {address:"' + safe_to + '"}\nset visible of newMessage to true\nactivate'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return f"Draft email to {to} opened in Mail."
        except Exception as exc:
            return f"Mail error: {exc}"

    # -----------------------------------------------------------------------
    # iMessage Integration (AppleScript)
    # -----------------------------------------------------------------------
    def _send_imessage(self, contact: str, message: str) -> str:
        """
        Send an iMessage to a contact.

        Args:
            contact: Contact name or phone number.
            message: Message text to send.

        Returns:
            Confirmation message.
        """
        safe_contact = self._escape_applescript(contact)
        safe_msg = self._escape_applescript(message)
        try:
            script = 'tell application "Messages" to send "' + safe_msg + '" to buddy "' + safe_contact + '" of (service 1 whose service type is iMessage)'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return f"Message sent to {contact}."
        except Exception as exc:
            return f"Messages error: {exc}"

    def _check_imessages(self, contact: str = "") -> str:
        """
        Check recent iMessages from a contact.

        Args:
            contact: Contact name to search for, or empty for all recent.

        Returns:
            Recent message preview.
        """
        try:
            if contact:
                safe_contact = self._escape_applescript(contact)
                script = 'tell application "Messages" to set msgList to ""\nrepeat with aChat in chats\nrepeat with aMsg in (messages of aChat whose handle is "' + safe_contact + '" or text contains "' + safe_contact + '")\nset msgList to msgList & (text of aMsg) & "|"\nif length of msgList > 800 then exit repeat\nend repeat\nif length of msgList > 800 then exit repeat\nend repeat\nreturn msgList'
            else:
                script = 'tell application "Messages" to set msgList to ""\nrepeat with aChat in (first 5 chats)\nrepeat with aMsg in (last message of aChat)\nset msgList to msgList & (handle of aMsg) & ": " & (text of aMsg) & "|"\nend repeat\nend repeat\nreturn msgList'
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            msgs = result.stdout.strip()
            if not msgs:
                return "No recent messages found."
            msg_list = [m.strip() for m in msgs.split("|") if m.strip()]
            return "Recent messages:\n" + "\n".join([f"  • {m}" for m in msg_list[:5]])
        except Exception as exc:
            return f"Messages error: {exc}"

    # -----------------------------------------------------------------------
    # Proactive & Predict loops
    # -----------------------------------------------------------------------
    def _start_proactive_loop(self) -> None:
        """Start background thread for proactive check-ins after idle time."""
        def worker():
            while True:
                time.sleep(self.PROACTIVE_INTERVAL)
                hours_since = (datetime.datetime.now() - self.last_interaction).total_seconds() / 3600
                if self.IDLE_SHORT < hours_since < self.IDLE_LONG:
                    msgs = [
                        "Hey, I was just thinking about you. How is your day going?",
                        "It has been a while! What have you been up to?",
                        "I am here if you need anything. Just wanted to check in!",
                    ]
                    self.speak(random.choice(msgs))
                    self.last_interaction = datetime.datetime.now()
                elif hours_since >= self.IDLE_LONG:
                    msgs = [
                        "Hey! It has been a while. I hope everything is okay.",
                        "Just checking in... it has been a long time since we last talked.",
                        "Missing our chats! What is new with you?",
                    ]
                    self.speak(random.choice(msgs))
                    self.last_interaction = datetime.datetime.now()

        threading.Thread(target=worker, daemon=True).start()

    def _start_predict_loop(self) -> None:
        """Start background thread for activity prediction/suggestions."""
        def worker():
            while True:
                time.sleep(self.PREDICT_INTERVAL)
                if (datetime.datetime.now() - self.last_active).total_seconds() > 3600:
                    self.speak("You have been quiet. Want to do something?")
                    self._last_prediction = "Say 'help' for suggestions"
                    self.last_active = datetime.datetime.now()

        threading.Thread(target=worker, daemon=True).start()

    def get_prediction(self) -> Optional[str]:
        """Return the last generated prediction/suggestion."""
        return self._last_prediction

    # -----------------------------------------------------------------------
    # Command router
    # -----------------------------------------------------------------------
    def process_query(self, query: str) -> None:
        """
        Process a single user query with voice output.

        Args:
            query: Raw user input text.
        """
        if not query:
            return

        self.last_interaction = datetime.datetime.now()
        self.last_active = datetime.datetime.now()

        lang = self._detect_language(query)
        q_en = self._translate(query, lang, "en").lower().strip()

        # Exit check
        if q_en in ("exit", "quit", "stop", "bye"):
            farewell = self._translate(self.personality["farewell"], "en", self.language_code)
            self.speak(farewell, self.language_code)
            raise SystemExit

        response = self._handle_command(q_en, query)

        if response:
            final = self._translate(response, "en", self.language_code)
            self.speak(final, self.language_code)
            self.conversation_history.append({"user": query, "assistant": final, "lang": self.language_code})
            self._log_conversation(query, final, self.language_code)

    def chat(self, query: str) -> str:
        """
        Process a text query and return the response without speaking.

        This is the primary interface for GUI and programmatic use.

        Args:
            query: User's text input.

        Returns:
            Assistant's text response.
        """
        if not query or not query.strip():
            return "I did not hear anything."

        self.last_interaction = datetime.datetime.now()
        self.last_active = datetime.datetime.now()

        lang = self._detect_language(query)
        q_en = self._translate(query, lang, "en").lower().strip()

        if q_en in ("exit", "quit", "stop", "bye"):
            return self._translate(self.personality["farewell"], "en", self.language_code)

        response = self._handle_command(q_en, query)
        if response:
            final = self._translate(response, "en", self.language_code)
            self.conversation_history.append({"user": query, "assistant": final, "lang": self.language_code})
            self._log_conversation(query, final, self.language_code)
            return final
        return "I am not sure how to help with that."

    def _handle_command(self, q_en: str, query_raw: str) -> Optional[str]:
        """
        Route user commands to their appropriate handlers.

        Args:
            q_en: Query translated to English and lowercased.
            query_raw: Original user query.

        Returns:
            Response string, or None if no handler matched.
        """
        # --- App launchers ---
        if "open youtube" in q_en:
            return self._open_youtube()
        if "open google" in q_en:
            return self._open_google()
        if "open spotify" in q_en:
            return self._open_spotify()
        if "open vscode" in q_en or "open visual studio code" in q_en:
            return self._open_vscode()

        # --- Info ---
        if q_en in ("what time is it", "time", "what is the time"):
            return self._get_time()
        if q_en in ("what is the date", "date", "what is today"):
            return self._get_date()
        if "system status" in q_en or "status" in q_en:
            return self._get_system_status()

        # --- Web ---
        if "search for" in q_en:
            term = q_en.split("search for", 1)[1].strip()
            return self.search_web(term)
        if "news" in q_en or "headlines" in q_en:
            return self.get_news()
        if "weather" in q_en:
            location = q_en.replace("weather", "").strip()
            return self.get_weather(location)
        if "wikipedia" in q_en:
            return self._search_wikipedia(q_en)

        # --- Images ---
        if "screenshot" in q_en or "capture screen" in q_en:
            return self.take_screenshot()
        if "analyze image" in q_en or "describe image" in q_en:
            match = re.search(r"(?:analyze|describe)\s+image\s+(.+?)(?:\s*\.\s*|$)", q_en)
            if match:
                filepath = os.path.expanduser(match.group(1).strip())
                return self.analyze_image_file(filepath)
            return "Specify an image path."
        if "find images" in q_en or "search images" in q_en:
            match = re.search(r"(?:find|search)\s+images?\s+of\s+(.+?)(?:\s*\.\s*|$)", q_en)
            if match:
                q = match.group(1).strip()
                images = self._search_web_images(q, limit=3)
                if images:
                    webbrowser.open(images[0])
                    return f"Found images for '{q}':\n" + "\n".join(images[:3])
                return f"No images found for '{q}'."
            return "What images should I search for?"
        if "photos from" in q_en:
            match = re.search(r"photos?\s+from\s+(.+?)(?:\s*\.\s*|$)", q_en)
            if match:
                photos = self._search_local_images(match.group(1).strip())
                if photos:
                    return "Found photos:\n" + "\n".join(photos[:3])
                return "No photos found."
            return "What date should I search for?"

        # --- Calendar ---
        if "calendar" in q_en or "events" in q_en:
            if "add" in q_en:
                match = re.search(
                    r"add\s+event\s+(.+?)(?:\s+on\s+(\d{4}-\d{2}-\d{2}))?(?:\s+at\s+(\d{2}:\d{2}))?",
                    q_en,
                )
                if match:
                    title = match.group(1).strip()
                    date = match.group(2)
                    time_str = match.group(3)
                    return self.add_calendar_event(title, date, time_str)
                return "Format: add event [title] on [YYYY-MM-DD] at [HH:MM]"
            return self.get_calendar_events()

        # --- Reminders ---
        if "reminder" in q_en or "remind" in q_en:
            if "complete" in q_en or "done" in q_en:
                match = re.search(r"(?:complete|done)\s+reminder\s+(.+?)(?:\s*\.\s*|$)", q_en)
                if match:
                    return self.complete_reminder(match.group(1).strip())
                return "Which reminder should I complete?"
            if "list" in q_en or "show" in q_en:
                return self.get_reminders()
            match = re.search(r"remind\s+me\s+to\s+(.+?)\s+at\s+(\d{1,2}:\d{2})", q_en)
            if match:
                return self.set_reminder(match.group(1).strip(), match.group(2).strip())
            return "Usage: remind me to [task] at [HH:MM]"

        # --- System control ---
        if "volume" in q_en:
            match = re.search(r"volume\s+(\d+)", q_en)
            if match:
                return self._set_volume(int(match.group(1)))
            return "Usage: volume [0-100]"
        if "brightness" in q_en:
            match = re.search(r"brightness\s+(\d+)", q_en)
            if match:
                return self._set_brightness(int(match.group(1)))
            return "Usage: brightness [0-100]"
        if "dark mode" in q_en:
            return self._toggle_dark_mode()
        if "lock screen" in q_en:
            return self._lock_screen()

        # --- Memory ---
        if "remember" in q_en and "that" in q_en:
            match = re.search(r"remember\s+that\s+(.+?)(?:\s*\.\s*|$)", q_en)
            if match:
                fact = match.group(1).strip()
                if " is " in fact:
                    k, v = fact.split(" is ", 1)
                    self._remember_fact(k.strip(), v.strip())
                    return f"Remembered: {k.strip()} is {v.strip()}"
                self._remember_fact("general", fact)
                return f"Remembered: {fact}"
            return "What should I remember?"
        if "what do you know about me" in q_en or "what do you remember" in q_en:
            if self.user_info:
                facts = [f"  Your {k} is {v}" for k, v in self.user_info.items()]
                return "I know:\n" + "\n".join(facts)
            return "I do not know much about you yet."
        if "what is my" in q_en or "what is my" in q_en:
            match = re.search(r"what(?:'s| is) my (.+?)(?:\?|$)", q_en)
            if match:
                key = match.group(1).strip()
                val = self._recall_fact(key)
                return f"Your {key} is {val}" if val else f"I do not know your {key}"
            return "What do you want to know?"

        # --- RAG / Knowledge ---
        if "summarize pdf" in q_en or "pdf summary" in q_en:
            match = re.search(r"(?:summarize|pdf)\s+(?:pdf\s+)?(.+?)(?:\s*\.\s*|$)", q_en)
            if match:
                filepath = os.path.expanduser(match.group(1).strip())
                return self.summarize_pdf(filepath)
            return "Usage: summarize pdf ~/Documents/file.pdf"
        if "index" in q_en and "folder" in q_en:
            match = re.search(r"index\s+folder\s+(.+?)(?:\s*\.\s*|$)", q_en)
            if match:
                folder = os.path.expanduser(match.group(1).strip())
                return self.index_documents(folder)
            return "Usage: index folder ~/Documents"
        if "search knowledge" in q_en:
            q = q_en.replace("search knowledge", "").strip()
            if q:
                return self.search_knowledge(q)
            return "What would you like to search for?"
        if "knowledge stats" in q_en:
            return self.get_knowledge_stats()
        if "rag mode" in q_en:
            return self.toggle_rag_mode()


        # --- Focus & Pomodoro ---
        if "focus mode" in q_en or "pomodoro" in q_en or "do not disturb" in q_en or "dnd" in q_en:
            match = re.search(r"(?:focus|pomodoro|dnd)(?:\s+mode)?(?:\s+for)?\s*(\d+)?\s*(?:min|minutes)?", q_en)
            duration = int(match.group(1)) if match and match.group(1) else None
            return self._toggle_focus_mode(duration)

        # --- Window Management ---
        if "tile left" in q_en or "window left" in q_en or "left half" in q_en:
            return self._window_tile_left()
        if "tile right" in q_en or "window right" in q_en or "right half" in q_en:
            return self._window_tile_right()
        if "maximise" in q_en or "maximize" in q_en or "full screen" in q_en:
            return self._window_maximise()
        if "close other windows" in q_en or "close all windows" in q_en:
            return self._window_close_others()

        # --- Notes ---
        if "create note" in q_en or "new note" in q_en or "add note" in q_en:
            match = re.search(r"(?:create|new|add)\s+note\s+(?:titled\s+)?(.+?)(?:\s+saying\s+|\s+with\s+|\s+body\s+)?(?:\s*:\s*)?(.+)?", q_en, re.IGNORECASE)
            if match:
                title = match.group(1).strip() if match.group(1) else "Quick Note"
                body = match.group(2).strip() if match.group(2) else ""
                return self._create_note(title, body)
            return "What should the note be titled?"
        if "read my last note" in q_en or "last note" in q_en or "recent note" in q_en:
            return self._read_last_note()
        if "search notes" in q_en or "find note" in q_en:
            query = q_en.replace("search notes", "").replace("find note", "").strip()
            if query:
                return self._search_notes(query)
            return "What should I search for in your notes?"
        if "show notes" in q_en or "my notes" in q_en:
            return self._search_notes("")

        # --- Safari ---
        if "summarise this page" in q_en or "summarise safari" in q_en or "summarize page" in q_en:
            return self._safari_summarise()
        if "close other tabs" in q_en or "close safari tabs" in q_en:
            return self._safari_close_other_tabs()
        if "current page" in q_en or "safari url" in q_en or "what page" in q_en:
            return self._safari_get_url()

        # --- MacBook Diagnostics ---
        if "battery" in q_en:
            return self._get_battery_status()
        if "storage" in q_en or "disk space" in q_en:
            return self._get_storage_status()
        if "clean desktop" in q_en or "tidy desktop" in q_en:
            return self._clean_desktop()


        # --- Spotify ---
        if "spotify" in q_en or "play music" in q_en or "music" in q_en:
            if "next" in q_en or "skip" in q_en:
                return self._spotify_next()
            if "previous" in q_en or "back" in q_en or "last track" in q_en:
                return self._spotify_previous()
            if "what's playing" in q_en or "now playing" in q_en or "current track" in q_en:
                return self._spotify_now_playing()
            if "like" in q_en or "love" in q_en or "favourite" in q_en or "favorite" in q_en:
                return self._spotify_like()
            if "volume" in q_en:
                match = re.search(r"volume\s+(\d+)", q_en)
                if match:
                    return self._spotify_volume(int(match.group(1)))
                return "Usage: spotify volume [0-100]"
            # Play/search
            query = q_en.replace("spotify", "").replace("play", "").replace("music", "").strip()
            return self._spotify_play(query)

        # --- Email ---
        if "check my email" in q_en or "unread emails" in q_en or "any emails" in q_en:
            return self._check_email()
        if "summarise my emails" in q_en or "summarize my emails" in q_en or "email summary" in q_en:
            return self._summarise_email()
        if "draft an email" in q_en or "compose email" in q_en or "new email" in q_en:
            # Try to parse: draft an email to [person] about [subject] saying [body]
            match = re.search(r"(?:draft|compose|new)\s+(?:an\s+)?email\s+(?:to\s+)?(.+?)(?:\s+about\s+(.+?))?(?:\s+saying\s+(.+))?", q_en)
            if match:
                to = match.group(1).strip() if match.group(1) else ""
                subject = match.group(2).strip() if match.group(2) else "No Subject"
                body = match.group(3).strip() if match.group(3) else ""
                return self._draft_email(to, subject, body)
            return "Usage: draft an email to [address] about [subject] saying [body]"

        # --- iMessage ---
        if "send a message" in q_en or "send a text" in q_en or "imessage" in q_en or "text" in q_en:
            match = re.search(r"(?:send\s+(?:a\s+)?(?:message|text)\s+to|text)\s+(.+?)(?:\s+saying\s+|\s+that\s+|\s+:\s*)(.+)", q_en)
            if match:
                contact = match.group(1).strip()
                message = match.group(2).strip()
                return self._send_imessage(contact, message)
            return "Usage: send a message to [contact] saying [message]"
        if "did i get any texts" in q_en or "check messages" in q_en or "recent messages" in q_en:
            match = re.search(r"(?:from|by)\s+(.+)", q_en)
            contact = match.group(1).strip() if match else ""
            return self._check_imessages(contact)

        # --- Fallback to AI ---
        return self._process_ai_query(q_en)

    # -----------------------------------------------------------------------
    # Main loop (CLI)
    # -----------------------------------------------------------------------
    def run(self) -> None:
        """Run the interactive CLI mode."""
        self.speak("Pick your language - English, Hindi, or Urdu.", "en")
        self.speak("अपनी भाषा चुनें - हिंदी, उर्दू, या अंग्रेज़ी।", "hi")
        self.speak("اپنی زبان منتخب کریں - ہندی، اردو، یا انگریزی۔", "ur")

        lang_input = input("Language code (en/hi/ur): ").lower().strip()
        if lang_input in self.SUPPORTED_LANGS:
            self.language_code = lang_input
        else:
            self.language_code = "en"

        if self.user_info.get("name"):
            greeting = f"Welcome back, {self.user_info['name']}!"
        else:
            greeting = self.personality["greeting"]
        self.speak(self._translate(greeting, "en", self.language_code), self.language_code)

        while True:
            try:
                if self.text_mode:
                    query = input("\nYou: ").strip()
                else:
                    query = self._listen()

                if query:
                    self.process_query(query)
            except SystemExit:
                break
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as exc:
                print(f"Error: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    text_mode = "--text" in sys.argv or "--type" in sys.argv
    rico = RicoAssistant(text_mode=text_mode, memory_enabled=True)
    rico.run()
