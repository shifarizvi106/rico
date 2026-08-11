import os
import re
import datetime
import json
import webbrowser
import subprocess
import wikipedia
import requests
import wolframalpha
import google.generativeai as genai
from dotenv import load_dotenv
from gtts import gTTS
from playsound import playsound
from googletrans import Translator, LANGUAGES
import base64
from PIL import Image
from io import BytesIO
import sqlite3
from pathlib import Path

# Text to speech only works when it is not in text mode
try:
    import speech_recognition as sr
except ImportError:
    sr = None

# Images
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class RicoAssistant:
    def __init__(self, text_mode=False, memory_enabled=True):
        load_dotenv()
        self.text_mode = text_mode or (sr is None)
        if sr is None and not text_mode:
            print("WARNING: Speechrecognition library not found. Forcing text mode.")

        # Language support
        self.language_code = 'en'
        self.supported_langs = ['en', 'hi', 'ur']
        self.translator = Translator()
        self.wolfram_client = self._initialize_wolfram()
        self.llm_model = self._initialize_gemini()
        self.memory_enabled = memory_enabled

        # Personality & Memory
        self.name = "Rico"
        self.soul = self._load_soul()
        self.personality = self._load_personality()
        self.user_info = self._load_user_info()
        self.conversation_history = []
        self.image_cache = []

        # Initialize memory database
        if self.memory_enabled:
            self._init_memory_db()

        print(f" {self.name} is online!")
        print(f" Supported languages: {', '.join(self.supported_langs)}")
        print(f" Memory: {'Enabled' if self.memory_enabled else 'Disabled'}")

    def _load_soul(self):
        """Load Rico's soul from soul.md"""
        soul_path = "data/soul.md"
        if os.path.exists(soul_path):
            try:
                with open(soul_path, 'r', encoding='utf-8') as f:
                    print("Soul loaded")
                    return f.read()
            except:
                return "You are Rico, a helpful AI assistant."
        return "You are Rico, a helpful AI assistant."

    def _initialize_wolfram(self):
        try:
            app_id = os.getenv("WOLFRAM_APP_ID")
            if not app_id:
                print("WolframAlpha not configured.")
                return None
            import wolframalpha
            return wolframalpha.Client(app_id)
        except Exception as e:
            print(f"WolframAlpha init failed: {e}")
            return None

    def _initialize_gemini(self):
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                print("Gemini API key not found. Set GEMINI_API_KEY in .env")
                return None
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash-exp")
            print("Gemini LLM configured")
            return model
        except Exception as e:
            print(f"Gemini init failed: {e}")
            return None

    def _load_personality(self):
        return {
            "name": self.name,
            "traits": ["confident", "witty", "helpful", "slightly sarcastic"],
            "greeting": "Hey! I'm Rico. How can I help you today?",
            "farewell": "Bye! I'll be here when you need me."
        }

    def _load_user_info(self):
        info_path = os.path.expanduser("~/rico_user_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_user_info(self):
        info_path = os.path.expanduser("~/rico_user_info.json")
        try:
            with open(info_path, 'w') as f:
                json.dump(self.user_info, f, indent=2)
        except:
            pass

    def _init_memory_db(self):
        db_path = os.path.expanduser("~/rico_memory.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                user_input TEXT,
                response TEXT,
                language TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY,
                fact_type TEXT,
                fact_value TEXT,
                confidence REAL,
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()

   def speak(self, text: str, lang: str = None):
    if not text:
        return
    if lang is None:
        lang = self.language_code
    print(f" {self.name} ({lang}): {text}")
    
    try:
        import edge_tts
        import asyncio
        
        voices = {
            'en': 'en-US-JennyNeural',
            'hi': 'hi-IN-SwaraNeural',
            'ur': 'ur-PK-UzmaNeural'
        }
        voice = voices.get(lang, 'en-US-JennyNeural')
        
        async def speak_edge():
            tts = edge_tts.Communicate(text, voice)
            await tts.save("response.mp3")
        
        asyncio.run(speak_edge())
        playsound("response.mp3")
        os.remove("response.mp3")
        
    except:
        try:
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save("response.mp3")
            playsound("response.mp3")
            os.remove("response.mp3")
        except Exception as e:
            print(f"Voice error: {e}")

    def _listen(self) -> str:
        if sr is None:
            return ""
        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("Listening...")
            r.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = r.listen(source, timeout=5, phrase_time_limit=10)
                return r.recognize_google(audio, language=self.language_code).lower()
            except:
                return ""

    def _translate(self, text: str, src: str, dest: str) -> str:
        if src == dest:
            return text
        try:
            return self.translator.translate(text, src=src, dest=dest).text
        except:
            return text

    def _remember_fact(self, fact_type: str, fact_value: str, confidence: float = 0.8):
        if not self.memory_enabled:
            return
        self.user_info[fact_type] = fact_value
        self._save_user_info()
        db_path = os.path.expanduser("~/rico_memory.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("INSERT INTO facts (fact_type, fact_value, confidence, timestamp) VALUES (?, ?, ?, ?)",
                  (fact_type, fact_value, confidence, datetime.datetime.now().isoformat()))
        conn.commit()
        conn.close()
        print(f"Remembered: {fact_type} = {fact_value}")

    def _recall_fact(self, fact_type: str) -> str:
        if fact_type in self.user_info:
            return self.user_info[fact_type]
        db_path = os.path.expanduser("~/rico_memory.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT fact_value FROM facts WHERE fact_type = ? ORDER BY timestamp DESC LIMIT 1", (fact_type,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

    def _search_web_images(self, query: str, limit: int = 3) -> list:
        try:
            search_url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}&iax=images&ia=images"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(search_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            images = []
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and src.startswith('http') and 'duckduckgo' not in src:
                    images.append(src)
                    if len(images) >= limit:
                        break
            return images[:limit]
        except:
            return []

    def _search_local_images(self, date_query: str) -> list:
        try:
            parsed_date = self._parse_date_query(date_query)
            if not parsed_date:
                return []
            pictures_dir = os.path.expanduser("~/Pictures")
            if not os.path.exists(pictures_dir):
                return []
            results = []
            for root, dirs, files in os.walk(pictures_dir):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.heic')):
                        file_path = os.path.join(root, file)
                        try:
                            mtime = os.path.getmtime(file_path)
                            file_date = datetime.datetime.fromtimestamp(mtime)
                            if (file_date.year == parsed_date.year and
                                file_date.month == parsed_date.month and
                                file_date.day == parsed_date.day):
                                results.append(file_path)
                                if len(results) >= 3:
                                    return results
                        except:
                            continue
            return results
        except:
            return []

    def _parse_date_query(self, query: str):
        query = query.lower()
        today = datetime.datetime.now()
        if "today" in query or "now" in query:
            return today
        if "yesterday" in query:
            return today - datetime.timedelta(days=1)
        import re
        days_match = re.search(r'last\s+(\d+)\s+days?', query)
        if days_match:
            days = int(days_match.group(1))
            return today - datetime.timedelta(days=days)
        date_match = re.search(r'(\w+)\s+(\d+)(?:\s*,?\s*(\d{4}))?', query)
        if date_match:
            month_name = date_match.group(1)
            day = int(date_match.group(2))
            year = int(date_match.group(3)) if date_match.group(3) else today.year
            months = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            month = months.get(month_name.lower(), 0)
            if month > 0:
                try:
                    return datetime.datetime(year, month, day)
                except:
                    return None
        return None

    def _open_youtube(self):
        self.speak("Opening YouTube...")
        webbrowser.open("https://www.youtube.com")

    def _open_google(self):
        self.speak("Opening Google...")
        webbrowser.open("https://www.google.com")

    def _open_spotify(self):
        self.speak("Opening Spotify...")
        subprocess.run(["open", "-a", "Spotify"], capture_output=True)

    def _open_vscode(self):
        self.speak("Opening Visual Studio Code...")
        subprocess.run(["open", "-a", "Visual Studio Code"], capture_output=True)

    def _get_time(self):
        self.speak(f"The time is {datetime.datetime.now().strftime('%I:%M %p')}")

    def _get_date(self):
        self.speak(f"Today is {datetime.datetime.now().strftime('%B %d, %Y')}")

    def _get_system_status(self):
        try:
            import psutil
            cpu = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            battery = psutil.sensors_battery()
            status = f"CPU: {cpu}%, Memory: {memory.percent}%"
            if battery:
                status += f", Battery: {battery.percent}%"
                if battery.power_plugged:
                    status += " (charging)"
            return status
        except:
            return "System status unavailable."

    def _search_wikipedia(self, query: str) -> str:
        search_term = query.replace("wikipedia", "").strip()
        try:
            results = wikipedia.summary(search_term, sentences=3, auto_suggest=False)
            return f"According to Wikipedia: {results}"
        except:
            return "No Wikipedia results found."

    def _calculate(self, query: str) -> str:
        match = re.search(r'(\d+)\s*([+\-*/])\s*(\d+)', query)
        if match:
            try:
                result = eval(match.group(0))
                return f"The result is {result}"
            except:
                return None
        return None

    def search_web(self, query):
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(search_url)
        return f"Searching for '{query}'..."

    def get_news(self):
        api_key = os.getenv("NEWS_API_KEY")
        if not api_key:
            return "Add NEWS_API_KEY to .env file"
        try:
            url = f"https://newsapi.org/v2/top-headlines?country=in&apiKey={api_key}"
            response = requests.get(url, timeout=10)
            data = response.json()
            articles = data.get('articles', [])[:5]
            headlines = [f"{i+1}. {a['title']}" for i, a in enumerate(articles)]
            return "Top headlines:\n" + "\n".join(headlines)
        except:
            return "Couldn't fetch news."

    def get_weather(self, location="current"):
        try:
            url = f"https://wttr.in/{location}?format=%C+%t+%w"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return f"Weather: {response.text}"
            return "Couldn't get weather."
        except:
            return "Weather unavailable."

    def _process_ai_query(self, query: str) -> str:
        # Check if it's a calculation
        calc_result = self._calculate(query)
        if calc_result:
            return calc_result

     elif "screenshot" in query_en or "capture screen" in query_en:
    response_en = self.take_screenshot()

        # Try WolframAlpha
        if self.wolfram_client:
            try:
                res = self.wolfram_client.query(query)
                answer = next(res.results).text
                return f"According to my calculations: {answer}"
            except:
                pass

        # Try Gemini with soul
        if self.llm_model:
            try:
                prompt = f"""
# Soul
{self.soul}

# Personality
{', '.join(self.personality['traits'])}

# User
{query}

# Response as Rico
"""
                response = self.llm_model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                return f"AI error: {e}"

        return "AI offline."

    def _detect_language(self, text: str) -> str:
        try:
            hindi_chars = ['अ', 'आ', 'इ', 'ई', 'उ', 'ऊ', 'ऋ', 'ए', 'ऐ', 'ओ', 'औ',
                          'क', 'ख', 'ग', 'घ', 'च', 'छ', 'ज', 'झ', 'ट', 'ठ', 'ड', 'ढ', 'ण',
                          'त', 'थ', 'द', 'ध', 'न', 'प', 'फ', 'ब', 'भ', 'म', 'य', 'र', 'ल', 'व',
                          'श', 'ष', 'स', 'ह']
            for char in text:
                if char in hindi_chars:
                    return 'hi'
                if char in ['ی', 'ئ', 'ؤ', 'ے', 'ں']:
                    return 'ur'
            return 'en'
        except:
            return 'en'

    def run(self):
        self.speak("Hey! I'm Rico. Pick your language - English, Hindi, or Urdu.", 'en')
        self.speak("अपनी भाषा चुनें - हिंदी, उर्दू, या अंग्रेज़ी।", 'hi')
        self.speak("اپنی زبان منتخب کریں - ہندی، اردو، یا انگریزی۔", 'ur')

        print("\nLanguage options: en (English), hi (Hindi), ur (Urdu)")
        lang_input = input("Enter language code: ").lower().strip()
        if lang_input in ['hi', 'ur']:
            self.language_code = lang_input
        else:
            self.language_code = 'en'

        if self.user_info.get('name'):
            greeting = f"Welcome back, {self.user_info['name']}!"
        else:
            greeting = self.personality['greeting']
        translated_greeting = self._translate(greeting, 'en', self.language_code)
        self.speak(translated_greeting, self.language_code)

        if self.text_mode:
            print("\nCommands: open youtube, open google, open spotify, time, date, status, news, weather, search for [query], remember that [fact], what do you know about me, exit")

        while True:
            if self.text_mode:
                query_original = input("\nYou: ").strip().lower()
            else:
                query_original = self._listen()

            if not query_original:
                continue

            detected_lang = self._detect_language(query_original)
            query_en = self._translate(query_original, detected_lang, 'en')
            print(f"Processed: '{query_en}'")
            self.conversation_history.append({"user": query_original, "lang": detected_lang})

            if query_en in ["exit", "quit", "stop", "bye"]:
                farewell = self._translate(self.personality['farewell'], 'en', self.language_code)
                self.speak(farewell, self.language_code)
                break

            elif "open youtube" in query_en:
                self._open_youtube()
                continue
            elif "open google" in query_en:
                self._open_google()
                continue
            elif "open spotify" in query_en:
                self._open_spotify()
                continue
            elif "open vs code" in query_en or "open vscode" in query_en:
                self._open_vscode()
                continue
            elif "time" in query_en:
                self._get_time()
                continue
            elif "date" in query_en:
                self._get_date()
                continue
            elif "status" in query_en or "system" in query_en:
                response_en = self._get_system_status()
            elif "search for" in query_en:
                q = query_en.split("search for", 1)[1].strip()
                response_en = self.search_web(q)
            elif "news" in query_en or "headlines" in query_en:
                response_en = self.get_news()
            elif "weather" in query_en:
                location = query_en.replace("weather", "").strip() or "current"
                response_en = self.get_weather(location)
            elif "remember" in query_en and "that" in query_en:
                match = re.search(r'remember\s+that\s+(.+?)(?:\s*\.\s*|$)', query_en)
                if match:
                    fact = match.group(1).strip()
                    if " is " in fact:
                        parts = fact.split(" is ", 1)
                        if len(parts) == 2:
                            self._remember_fact(parts[0].strip(), parts[1].strip())
                            response_en = f"I'll remember that your {parts[0].strip()} is {parts[1].strip()}."
                        else:
                            self._remember_fact("general", fact)
                            response_en = f"I'll remember that: {fact}"
                    else:
                        self._remember_fact("general", fact)
                        response_en = f"I'll remember that: {fact}"
                else:
                    response_en = "What should I remember? Try: 'remember that my name is Rico'"
            elif "what do you know about me" in query_en or "what do you remember" in query_en:
                if self.user_info:
                    facts = [f"Your {k} is {v}" for k, v in self.user_info.items()]
                    response_en = "Here's what I know:\n" + "\n".join(facts)
                else:
                    response_en = "I don't know much about you yet."
            elif "what is my" in query_en or "what's my" in query_en:
                match = re.search(r"what('s| is) my (.+?)(?:\?|$)", query_en)
                if match:
                    key = match.group(2).strip()
                    value = self._recall_fact(key)
                    if value:
                        response_en = f"Your {key} is {value}."
                    else:
                        response_en = f"I don't know your {key}."
                else:
                    response_en = "What would you like to know?"
            elif "find images" in query_en or "search images" in query_en:
                match = re.search(r'(?:find|search)\s+images?\s+of\s+(.+?)(?:\s*\.\s*|$)', query_en)
                if match:
                    search_query = match.group(1).strip()
                    self.speak(f"Searching for images of {search_query}...")
                    images = self._search_web_images(search_query, limit=3)
                    if images:
                        response_en = f"Found {len(images)} images for '{search_query}'.\n" + "\n".join(images[:3])
                        for img_url in images[:1]:
                            webbrowser.open(img_url)
                    else:
                        response_en = f"No images found for '{search_query}'."
                else:
                    response_en = "What images are you looking for?"
            elif "photos from" in query_en:
                match = re.search(r'photos?\s+from\s+(.+?)(?:\s*\.\s*|$)', query_en)
                if match:
                    date_query = match.group(1).strip()
                    photos = self._search_local_images(date_query)
                    if photos:
                        response_en = f"Found {len(photos)} photos from {date_query}:\n" + "\n".join(photos[:3])
                    else:
                        response_en = f"No photos found from {date_query}."
                else:
                    response_en = "What date should I search for?"
            elif "wikipedia" in query_en:
                response_en = self._search_wikipedia(query_en)
            else:
                response_en = self._process_ai_query(query_en)

            final_response = self._translate(response_en, 'en', self.language_code)
            self.speak(final_response, self.language_code)
            self.conversation_history.append({"assistant": final_response, "lang": self.language_code})

def analyze_image(self, image_path, prompt="Describe what you see in this image"):
    """Analyze an image using Gemini Vision"""
    try:
        import base64
        from PIL import Image
        
        # Resize to reduce API cost
        img = Image.open(image_path)
        img.thumbnail((800, 800))
        img.save(image_path)
        
        # Convert to base64
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Send to Gemini
        if self.llm_model:
            response = self.llm_model.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_data}
            ])
            return response.text.strip()
        return "AI offline."
    except Exception as e:
        return f"Analysis error: {e}"

def take_screenshot(self):
    """Take a screenshot and analyze it"""
    try:
        import pyautogui
        from PIL import Image
        
        path = os.path.expanduser("~/rico_screenshot.png")
        screenshot = pyautogui.screenshot()
        screenshot.save(path)
        
        # Analyze
        result = self.analyze_image(path, "Describe what you see in this screenshot in detail.")
        return f" Screenshot taken and analyzed:\n{result}"
    except Exception as e:
        return f"Couldn't take screenshot: {str(e)}"

def analyze_image_file(self, filepath, prompt="Describe what you see in this image in detail."):
    """Analyze any image file using Gemini Vision"""
    try:
        import base64
        from PIL import Image
        
        if not os.path.exists(filepath):
            return f"File not found: {filepath}"
        
        # Resize to reduce API cost
        img = Image.open(filepath)
        img.thumbnail((800, 800))
        img.save(filepath)
        
        # Convert to base64
        with open(filepath, "rb") as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Send to Gemini
        if self.llm_model:
            response = self.llm_model.generate_content([
                prompt,
                {"mime_type": "image/png", "data": img_data}
            ])
            return response.text.strip()
        return "AI offline."
    except Exception as e:
        return f"Analysis error: {e}"

elif "analyze image" in query_en or "describe image" in query_en:
    # Extract file path
    match = re.search(r'(?:analyze|describe)\s+image\s+(.+?)(?:\s*\.\s*|$)', query_en)
    if match:
        filepath = os.path.expanduser(match.group(1).strip())
        response_en = self.analyze_image_file(filepath)
    else:
        response_en = "Please specify an image path. Example: analyze image ~/Pictures/photo.jpg"

def get_calendar_events(self, days=7):
    """Get calendar events for the next N days using Apple Calendar"""
    try:
        import subprocess
        import datetime
        
        # Get events using AppleScript
        script = f'''
        tell application "Calendar"
            set startDate to current date
            set endDate to startDate + ({days} * days)
            set theEvents to every event of calendar 1 whose start date is greater than or equal to startDate and start date is less than or equal to endDate
            set eventList to ""
            repeat with anEvent in theEvents
                set eventTitle to summary of anEvent
                set eventDate to start date of anEvent
                set eventTime to time string of eventDate
                set eventList to eventList & eventTitle & " at " & eventTime & "|"
            end repeat
            return eventList
        end tell
        '''
        
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        events = result.stdout.strip()
        
        if events:
            event_list = [e.strip() for e in events.split('|') if e.strip()]
            if event_list:
                return "Upcoming events:\n" + "\n".join([f"  • {e}" for e in event_list[:10]])
        return "No upcoming events found."
    except Exception as e:
        return f"Couldn't get calendar: {e}"

def add_calendar_event(self, title, date=None, time=None, duration=60):
    """Add an event to Apple Calendar"""
    try:
        import subprocess
        import datetime
        
        if date is None:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        if time is None:
            time = "09:00"
        
        start_datetime = f"{date} {time}:00"
        end_datetime = (datetime.datetime.strptime(start_datetime, "%Y-%m-%d %H:%M:%S") + 
                       datetime.timedelta(minutes=duration)).strftime("%Y-%m-%d %H:%M:%S")
        
        script = f'''
        tell application "Calendar"
            tell calendar "Home"
                set newEvent to make new event with properties {{summary:"{title}", start date:date "{start_datetime}", end date:date "{end_datetime}"}}
            end tell
        end tell
        '''
        
        subprocess.run(["osascript", "-e", script], check=True)
        return f"Event '{title}' added for {date} at {time}."
    except Exception as e:
        return f"Couldn't add event: {e}"

elif "calendar" in query_en or "events" in query_en:
    if "add" in query_en:
        # Extract event details
        match = re.search(r'add\s+event\s+(.+?)(?:\s+on\s+(\d{4}-\d{2}-\d{2}))?(?:\s+at\s+(\d{2}:\d{2}))?', query_en)
        if match:
            title = match.group(1).strip()
            date = match.group(2) if match.group(2) else None
            time = match.group(3) if match.group(3) else None
            response_en = self.add_calendar_event(title, date, time)
        else:
            response_en = "Please specify: add event [title] on [YYYY-MM-DD] at [HH:MM]"
    else:
        response_en = self.get_calendar_events()

def set_reminder(self, text, time, date=None):
    """Set a reminder using Apple Reminders"""
    try:
        import subprocess
        import datetime
        
        if date is None:
            date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        due_datetime = f"{date} {time}:00"
        
        script = f'''
        tell application "Reminders"
            tell default list
                set newReminder to make new reminder with properties {{name:"{text}", due date:date "{due_datetime}"}}
            end tell
        end tell
        '''
        
        subprocess.run(["osascript", "-e", script], check=True)
        return f"Reminder set: '{text}' for {date} at {time}"
    except Exception as e:
        return f"Couldn't set reminder: {e}"

def get_reminders(self):
    """Get active reminders"""
    try:
        import subprocess
        
        script = '''
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
        '''
        
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        reminders = result.stdout.strip()
        
        if reminders:
            reminder_list = [r.strip() for r in reminders.split('|') if r.strip()]
            if reminder_list:
                return "Your reminders:\n" + "\n".join([f"  • {r}" for r in reminder_list[:10]])
        return "No active reminders."
    except Exception as e:
        return f"Couldn't get reminders: {e}"

def complete_reminder(self, title):
    """Mark a reminder as completed"""
    try:
        import subprocess
        
        script = f'''
        tell application "Reminders"
            tell default list
                repeat with aReminder in reminders
                    if name of aReminder contains "{title}" then
                        set completed of aReminder to true
                        return "Completed: " & name of aReminder
                    end if
                end repeat
                return "Reminder not found"
            end tell
        end tell
        '''
        
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Couldn't complete reminder: {e}"

elif "reminder" in query_en or "remind" in query_en:
    if "complete" in query_en or "done" in query_en:
        # Extract reminder title
        match = re.search(r'(?:complete|done)\s+reminder\s+(.+?)(?:\s*\.\s*|$)', query_en)
        if match:
            title = match.group(1).strip()
            response_en = self.complete_reminder(title)
        else:
            response_en = "Which reminder to complete?"
    elif "list" in query_en or "show" in query_en:
        response_en = self.get_reminders()
    else:
        # Set reminder: remind me to [task] at [time]
        match = re.search(r'remind\s+me\s+to\s+(.+?)\s+at\s+(\d{1,2}:\d{2})', query_en)
        if match:
            task = match.group(1).strip()
            time = match.group(2).strip()
            response_en = self.set_reminder(task, time)
        else:
            response_en = "Usage: remind me to [task] at [HH:MM]"

def set_volume(self, level):
    """Set system volume (0-100)"""
    try:
        import subprocess
        if 0 <= level <= 100:
            script = f'set volume output volume {level}'
            subprocess.run(["osascript", "-e", script], check=True)
            return f"Volume set to {level}%"
        return "Volume must be between 0 and 100"
    except Exception as e:
        return f"Couldn't set volume: {e}"

def set_brightness(self, level):
    """Set display brightness (0-100)"""
    try:
        import subprocess
        if 0 <= level <= 100:
            script = f'''
            tell application "System Events"
                repeat with d in (get display brightness)
                    set display brightness to {level/100}
                end repeat
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)
            return f"Brightness set to {level}%"
        return "Brightness must be between 0 and 100"
    except Exception as e:
        return f"Couldn't set brightness: {e}"

def toggle_dark_mode(self):
    """Toggle dark mode on/off"""
    try:
        import subprocess
        script = '''
        tell application "System Events"
            tell appearance preferences
                set dark mode to not dark mode
            end tell
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True)
        return "Dark mode toggled"
    except Exception as e:
        return f"Couldn't toggle dark mode: {e}"

def lock_screen(self):
    """Lock the screen"""
    try:
        import subprocess
        script = '''
        tell application "System Events"
            keystroke "q" using {control down, command down}
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True)
        return "Screen locked"
    except Exception as e:
        return f"Couldn't lock screen: {e}"

def restart_mac(self):
    """Restart the Mac (requires confirmation)"""
    try:
        import subprocess
        script = '''
        tell application "System Events"
            restart
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True)
        return "Restarting..."
    except Exception as e:
        return f"Couldn't restart: {e}"

def shutdown_mac(self):
    """Shutdown the Mac (requires confirmation)"""
    try:
        import subprocess
        script = '''
        tell application "System Events"
            shut down
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True)
        return "Shutting down..."
    except Exception as e:
        return f"Couldn't shutdown: {e}"

elif "volume" in query_en:
    match = re.search(r'volume\s+(\d+)', query_en)
    if match:
        level = int(match.group(1))
        response_en = self.set_volume(level)
    else:
        response_en = "Usage: volume [0-100]"

elif "brightness" in query_en:
    match = re.search(r'brightness\s+(\d+)', query_en)
    if match:
        level = int(match.group(1))
        response_en = self.set_brightness(level)
    else:
        response_en = "Usage: brightness [0-100]"

elif "dark mode" in query_en:
    response_en = self.toggle_dark_mode()

elif "lock screen" in query_en:
    response_en = self.lock_screen()

elif "restart" in query_en:
    response_en = self.restart_mac()

elif "shutdown" in query_en:
    response_en = self.shutdown_mac()


if __name__ == "__main__":
    import sys
    text_mode = "--text" in sys.argv or "--type" in sys.argv
    rico = RicoAssistant(text_mode=text_mode, memory_enabled=True)
    rico.run()
