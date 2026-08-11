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
import PIL from Image
from io import BytesIO
import sqlite3
from pathlib import Path
import PyQt5.QtWidgets
import QsystemTrayIcon, Qmenu, Qstyle


 # Text to speech only works when it is not in text mode, duh.
try :
  import speech_recognition as sr
except ImportError:
  sr = None

 # Images ke liye hai 
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

class RicoAssistant:
  def __init__(self, text_mode =False, memory_enabled=True):
    load_dotenv()
    self.text_mode = text_mode or (sr is None)
    if sr is None and not text_mode:
      print ("WARNING : Speechrecognition library not found. Forcing text mode.")

             # Language support 
             self.language_code = 'en'
             self.supported_langs = ['en', 'hi', 'ur']
             self.translator = Translator ()
             self.wolfram_client = self._initialize_wolfram()
        self.llm_model = self._initialize_gemini()
        self.memory_enabled = memory_enabled

# personality
self.name = "Rico"
        self.personality = self._load_personality()
        self.user_info = self._load_user_info()
        self.conversation_history = []
        self.image_cache = []

# Initialize memory database
        if self.memory_enabled:
            self._init_memory_db()

# Print startup message
        print(f" {self.name} is online!")
        print(f" Supported languages: {', '.join(self.supported_langs)}")
        print(f" Memory: {'Enabled' if self.memory_enabled else 'Disabled'}")
# Intialise
def _initialize_wolfram(self):
        try:
            app_id = os.getenv("WOLFRAM_APP_ID")
            if not app_id: 
                print("⚠️ WolframAlpha not configured. Using Gemini for calculations.")
                return None
            import wolframalpha
            return wolframalpha.Client(app_id)
        except Exception as e:
            print(f"⚠️ WolframAlpha initialization failed: {e}")
            return None
          def _initialize_gemini(self):
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                print("⚠️ Gemini API key not found. Set GEMINI_API_KEY in .env")
                return None
            genai.configure(api_key=api_key)
            # Use gemini-2.0-flash for faster responses
            model = genai.GenerativeModel("gemini-2.0-flash-exp")
            print("✅ Gemini LLM configured")
            return model
        except Exception as e:
            print(f"⚠️ Gemini initialization failed: {e}")
            return None
    
   def _load_personality(self):
    """Load Rico's personality settings"""
    return {
        "name": self.name,
        "traits": ["confident", "witty", "helpful", "slightly sarcastic", "girly", "girlboss"],
        "tone": "casual, sharp, and engaging",
        "greeting": "Hey! I'm Rico. How can I help you today?",
        "farewell": "Bye! I'll be here when you need me.",
        "quirks": [
            "analytical",
            "makes light jokes",
            "uses expressive emojis occasionally"
        ],
        "system_rules": [
            "Keep answers concise and ideal for spoken output.",
            "If unsure, admit it with a touch of humor.",
            "Address the user naturally without repeating their name constantly."
          
        ]
    }
                
            class RicoAssistant:
  

    def _load_user_info(self):
        """Load user information from file"""
        info_path = os.path.expanduser("~/rico_user_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_user_info(self):
        """Save user information"""
        info_path = os.path.expanduser("~/rico_user_info.json")
        try:
            with open(info_path, 'w') as f:
                json.dump(self.user_info, f, indent=2)
        except Exception:
            pass
def _init_memory_db(self):
        """Initialize SQLite database for conversation memory"""
        db_path = os.path.expanduser("~/rico_memory.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                user_input TEXT,
                response TEXT,
                language TEXT
            )
        ''')
        cursor.execute('''
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

# Core IO

def speak(self, text: str, lang: str = None):
        """Speak with emotion and personality"""
        if not text:
            return
        
        # Use default language if none specified
        if lang is None:
            lang = self.language_code
        
        # Add personality markers occasionally
        final_text = self._add_personality(text)
        
        print(f" {self.name} ({lang}): {final_text}")
        
        try:
            tts = gTTS(text=final_text, lang=lang, slow=False)
            tts.save("response.mp3")
            playsound("response.mp3")
            os.remove("response.mp3")
        except Exception as e:
            print(f"⚠️ Voice error: {e}")

def _add_personality(self, text: str) -> str:
        """Add personality markers to speech"""
        # Don't modify if it's already short or has emojis
        if len(text) < 20 or any(c in text for c in ['💗', '✨', '🔥']):
            return text
        
        # Occasionally add personality
        import random
        if random.random() < 0.15:
            markers = [
                " you know", " honestly", " trust me", 
                " between us", " I mean", " to be fair"
            ]
            # Insert at a natural break
            words = text.split()
            if len(words) > 5:
                insert_pos = random.randint(2, min(5, len(words)-2))
                words.insert(insert_pos, random.choice(markers))
                return " ".join(words)
        return text

    def _listen(self) -> str:
        """Listen for voice input with language support"""
        if sr is None:
            return ""
        
        r = sr.Recognizer()
        with sr.Microphone() as source:
            lang_name = LANGUAGES.get(self.language_code, 'Unknown')
            print(f"Listening in {lang_name}...")
            r.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = r.listen(source, timeout=5, phrase_time_limit=10)
            except sr.WaitTimeoutError:
                return ""
        
        try:
            print(" Recognizing...")
            query = r.recognize_google(audio, language=self.language_code)
            print(f" You said: {query}\n")
            return query.lower()
        except sr.UnknownValueError:
            print("❌ Speech not understood")
            return ""
        except sr.RequestError as e:
            print(f"⚠️ Google API error: {e}")
            return ""

def _translate(self, text: str, src: str, dest: str) -> str:
        """Translate text between languages"""
        if src == dest:
            return text
        try:
            result = self.translator.translate(text, src=src, dest=dest)
            return result.text
        except Exception as e:
            print(f"⚠️ Translation error: {e}")
            return text

    # --- New Feature: Memory & User Info ---
    def _remember_fact(self, fact_type: str, fact_value: str, confidence: float = 0.8):
        """Store a fact about the user"""
        if not self.memory_enabled:
            return
        
        # Store in user_info
        self.user_info[fact_type] = fact_value
        self._save_user_info()
        
        # Store in database
        db_path = os.path.expanduser("~/rico_memory.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO facts (fact_type, fact_value, confidence, timestamp) VALUES (?, ?, ?, ?)",
            (fact_type, fact_value, confidence, datetime.datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        print(f" Remembered: {fact_type} = {fact_value}")

    def _recall_fact(self, fact_type: str) -> str:
        """Recall a fact about the user"""
        if fact_type in self.user_info:
            return self.user_info[fact_type]
        
        # Check database
        db_path = os.path.expanduser("~/rico_memory.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT fact_value FROM facts WHERE fact_type = ? ORDER BY timestamp DESC LIMIT 1",
            (fact_type,)
        )
        result = cursor.fetchone()
        conn.close()
if result:
            return result[0]
        return None

    # --- New Feature: Image Search (Web) ---
    def _search_web_images(self, query: str, limit: int = 3) -> list:
        """Search for images on the web"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            # Using DuckDuckGo (no API key needed)
            search_url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}&iax=images&ia=images"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(search_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find image URLs
            images = []
            for img in soup.find_all('img'):
                src = img.get('src')
                if src and src.startswith('http') and not 'duckduckgo' in src:
                    images.append(src)
                    if len(images) >= limit:
                        break
            
            return images[:limit]
        except Exception as e:
            print(f"⚠️ Image search error: {e}")
            return []

    # --- New Feature: Image Search (Local/Device) ---
    def _search_local_images(self, date_query: str) -> list:
        """Search for images on device by date"""
        try:
            from PIL import Image
            import datetime
            
            # Parse date query (e.g., "June 15" or "yesterday")
            parsed_date = self._parse_date_query(date_query)
            
            if not parsed_date:
                return []
            
            # Search in Pictures folder
            pictures_dir = os.path.expanduser("~/Pictures")
            if not os.path.exists(pictures_dir):
                return []
            
            results = []
            for root, dirs, files in os.walk(pictures_dir):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.heic')):
                        file_path = os.path.join(root, file)
                        try:
                            # Get file modification date
                            mtime = os.path.getmtime(file_path)
                            file_date = datetime.datetime.fromtimestamp(mtime)
                            
                            # Check if it matches the query date
                            if (file_date.year == parsed_date.year and 
                                file_date.month == parsed_date.month and 
                                file_date.day == parsed_date.day):
                                results.append(file_path)
                                if len(results) >= 3:
                                    return results
                        except:
                            continue
            
            return results
        except Exception as e:
            print(f"⚠️ Local image search error: {e}")
            return []

    def _parse_date_query(self, query: str) -> datetime.datetime:
        """Parse natural language date query"""
        query = query.lower()
        today = datetime.datetime.now()
        
        # Handle "today"
        if "today" in query or "now" in query:
            return today
        
        # Handle "yesterday"
        if "yesterday" in query:
            return today - datetime.timedelta(days=1)
        
        # Handle "last X days"
        import re
        days_match = re.search(r'last\s+(\d+)\s+days?', query)
        if days_match:
            days = int(days_match.group(1))
            return today - datetime.timedelta(days=days)
        
        # Handle specific dates like "June 15 2025"
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
# --- Command & Query Methods ---
    def _open_youtube(self):
        self.speak("Opening YouTube...", 'en')
        webbrowser.open("https://www.youtube.com")
    
    def _open_google(self):
        self.speak("Opening Google...", 'en')
        webbrowser.open("https://www.google.com")
    
    def _open_spotify(self):
        self.speak("Opening Spotify...", 'en')
        subprocess.run(["open", "-a", "Spotify"], capture_output=True)
    
    def _open_vscode(self):
        self.speak("Opening Visual Studio Code...", 'en')
        subprocess.run(["open", "-a", "Visual Studio Code"], capture_output=True)
    
    def _get_time(self):
        str_time = datetime.datetime.now().strftime("%I:%M %p")
        self.speak(f"The time is {str_time}", 'en')
    
    def _get_date(self):
        str_date = datetime.datetime.now().strftime("%B %d, %Y")
        self.speak(f"Today is {str_date}", 'en')
    
    def _get_system_status(self):
        """Get system status (CPU, memory, battery)"""
        try:
            import psutil
            cpu = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            battery = psutil.sensors_battery()
            
            status = f"System Status: CPU at {cpu}%, Memory at {memory.percent}%"
            if battery:
                status += f", Battery at {battery.percent}%"
                if battery.power_plugged:
                    status += " (charging)"
            return status
        except:
            return "System status check is not available."

    def _search_wikipedia(self, query: str) -> str:
        search_term = query.replace("wikipedia", "").strip()
        try:
            import wikipedia
            results = wikipedia.summary(search_term, sentences=3, auto_suggest=False)
            return f"According to Wikipedia: {results}"
        except Exception as e:
            return f"Sorry, I couldn't find any results on Wikipedia."

    def _calculate(self, query: str) -> str | None:
        match = re.search(r'(\d+)\s*([\+\-\*\/])\s*(\d+)', query)
        if match:
            try:
                result = eval(match.group(0))
                return f"The result is {result}"
            except:
                return None
        return None

    def _get_news(self) -> str:
        """Fetches top 5 Indian news headlines and summarizes them."""
        news_api_key = os.getenv("NEWS_API_KEY")
        if not news_api_key:
            return "News API key is not configured. Please add NEWS_API_KEY to your .env file."
        
        url = f"https://newsapi.org/v2/top-headlines?country=in&apiKey={news_api_key}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            news_data = response.json()
            articles = news_data.get("articles", [])
            if not articles:
                return "I couldn't find any top headlines at the moment."
            
            headlines = [article['title'] for article in articles[:5]]
            
            if self.llm_model:
                summary_prompt = f"You are a casual news anchor. Briefly summarize these top 5 Indian headlines in a single, concise paragraph: {'; '.join(headlines)}"
                news_summary = self.llm_model.generate_content(summary_prompt).text
                return news_summary.strip()
            else:
                return "The AI model is offline, so I cannot summarize the news."
        except Exception as e:
            return f"Sorry, I couldn't connect to the news service. Error: {e}"

   def _process_ai_query(self, query: str) -> str:
    if self.llm_model:
        try:
            prompt = f"# Soul\n{self.soul}\n\n# User\n{query}\n\n# Response as Rico"
            return self.llm_model.generate_content(prompt).text.strip()
        except Exception as e:
            return f"AI error: {e}"
    return "AI offline."
        # Check if it's a calculation
        calc_result = self._calculate(query)
        if calc_result:
            return calc_result
        
        # Try WolframAlpha
        if self.wolfram_client:
            try:
                res = self.wolfram_client.query(query)
                answer = next(res.results).text
                return f"According to my calculations: {answer}"
            except:
                pass
        
        # Try Gemini with Rico's personality
        if self.llm_model:
            try:
                # Add Rico's personality to the prompt
                personality_context = f"""
                You are {self.name}, a confident, witty, and helpful AI assistant.
                Your personality traits: {', '.join(self.personality['traits'])}.
                You speak casually but sharply. You occasionally use emojis.
                You remember context from this conversation.
                """
                
                full_prompt = f"{personality_context}\n\nUser query: {query}\n\nYour response:"
                response = self.llm_model.generate_content(full_prompt)
                return response.text.strip()
            except Exception as e:
                return f"An error occurred with the AI model: {e}"
        
        return "Sorry, my AI capabilities are offline."

# --- Language Detection ---
    def _detect_language(self, text: str) -> str:
        """Detect language of input text"""
        try:
            # Simple detection for Hindi/Urdu script
            hindi_chars = ['अ', 'आ', 'इ', 'ई', 'उ', 'ऊ', 'ऋ', 'ए', 'ऐ', 'ओ', 'औ', 
                          'क', 'ख', 'ग', 'घ', 'च', 'छ', 'ज', 'झ', 'ट', 'ठ', 'ड', 'ढ', 'ण',
                          'त', 'थ', 'द', 'ध', 'न', 'प', 'फ', 'ब', 'भ', 'म', 'य', 'र', 'ल', 'व',
                          'श', 'ष', 'स', 'ह']
            
            for char in text:
                if char in hindi_chars:
                    return 'hi'  # Hindi/Urdu
                if char in ['ی', 'ئ', 'ؤ', 'ے', 'ں']:  # Urdu-specific chars
                    return 'ur'
            
            # Default to English
            return 'en'
        except:
            return 'en'

    # --- Main Run Method ---
    def run(self):
        """Main loop with personality"""
        # Language selection with personality
        self.speak("Hey! I'm Rico. Pick your language - English, Hindi, or Urdu.", 'en')
        self.speak("अपनी भाषा चुनें - हिंदी, उर्दू, या अंग्रेज़ी।", 'hi')
        self.speak("اپنی زبان منتخب کریں - ہندی، اردو، یا انگریزی۔", 'ur')
        
        print("\n Language options: en (English), hi (Hindi), ur (Urdu)")
        lang_input = input("Enter language code: ").lower().strip()
        
        if lang_input in ['hi', 'ur']:
            self.language_code = lang_input
        else:
            self.language_code = 'en'
        
        # Personalized greeting
        if self.user_info.get('name'):
            greeting = f"Welcome back, {self.user_info['name']}! What can I do for you today?"
        else:
            greeting = self.personality['greeting']
        
        translated_greeting = self._translate(greeting, 'en', self.language_code)
        self.speak(translated_greeting, self.language_code)

 # Show available commands
        if self.text_mode:
            print("\n Available commands:")
            print("  • 'open youtube' - Open YouTube")
            print("  • 'open google' - Open Google")
            print("  • 'open spotify' - Open Spotify")
            print("  • 'time' - Get current time")
            print("  • 'news' - Get top headlines")
            print("  • 'remember [fact]' - Remember something about you")
            print("  • 'what do you know about me' - Recall stored info")
            print("  • 'find images of [query]' - Search for images")
            print("  • 'photos from [date]' - Find photos on device")
            print("  • 'status' - Check system status")
            print("  • 'exit' - Quit")
        
        while True:
            # Get input
            if self.text_mode:
                query_original = input("\n You: ").strip().lower()
            else:
                query_original = self._listen()
            
            if not query_original:
                continue
            
            # Detect language
            detected_lang = self._detect_language(query_original)
            if detected_lang != self.language_code:
                print(f" Detected language: {LANGUAGES.get(detected_lang, 'Unknown')}")
            
            # Translate to English for processing
            query_en = self._translate(query_original, detected_lang, 'en')
            print(f"Processed: '{query_en}'")
            
            # Store conversation
            self.conversation_history.append({"user": query_original, "lang": detected_lang})
            
            response_en = ""

# --- Command Handlers ---
            
            # Exit commands
            if query_en in ["exit", "quit", "stop", "bye"]:
                farewell = self._translate(self.personality['farewell'], 'en', self.language_code)
                self.speak(farewell, self.language_code)
                break
            
            # App opening
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
            
            # Time and Date
            elif "time" in query_en:
                self._get_time()
                continue
            elif "date" in query_en:
                self._get_date()
                continue
            
            # System Status
            elif "status" in query_en or "system" in query_en:
                status = self._get_system_status()
                response_en = status
            
            # Memory - Remember
            elif "remember" in query_en and "that" in query_en:
                # Extract what to remember
                match = re.search(r'remember\s+that\s+(.+?)(?:\s*\.\s*|$)', query_en)
                if match:
                    fact = match.group(1).strip()
                    # Try to extract key-value pair
                    if "is" in fact:
                        parts = fact.split("is", 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            self._remember_fact(key, value)
                            response_en = f"I'll remember that your {key} is {value}."
                        else:
                            self._remember_fact("general", fact)
                            response_en = f"I'll remember that: {fact}"
                    else:
                        self._remember_fact("general", fact)
                        response_en = f"I'll remember that: {fact}"
                else:
                    response_en = "What should I remember? Try: 'remember that my name is Rico'"
            
            # Memory - Recall
            elif "what do you know about me" in query_en or "what do you remember" in query_en:
                if self.user_info:
                    facts = []
                    for key, value in self.user_info.items():
                        facts.append(f"• Your {key} is {value}")
                    response_en = f"Here's what I know about you:\n" + "\n".join(facts)
                else:
                    response_en = "I don't know much about you yet. Tell me something to remember!"
            
            # Memory - Specific recall
            elif "what is my" in query_en or "what's my" in query_en:
                # Extract the key
                match = re.search(r"what('s| is) my (.+?)(?:\?|$)", query_en)
                if match:
                    key = match.group(2).strip()
                    value = self._recall_fact(key)
                    if value:
                        response_en = f"Your {key} is {value}."
                    else:
                        response_en = f"I don't know your {key}. Tell me about it!"
                else:
                    response_en = "What would you like to know?"
            
            # Image Search (Web)
            elif "find images" in query_en or "search images" in query_en:
                match = re.search(r'(?:find|search)\s+images?\s+of\s+(.+?)(?:\s*\.\s*|$)', query_en)
                if match:
                    search_query = match.group(1).strip()
                    self.speak(f"Searching for images of {search_query}...", self.language_code)
                    images = self._search_web_images(search_query, limit=3)
                    if images:
                        response_en = f"Found {len(images)} images for '{search_query}'.\n" + "\n".join(images[:3])
                        # Open in browser
                        for img_url in images[:1]:
                            webbrowser.open(img_url)
                    else:
                        response_en = f"No images found for '{search_query}'."
                else:
                    response_en = "What images are you looking for?"
            
            # Local Photos by Date
            elif "photos from" in query_en:
                match = re.search(r'photos?\s+from\s+(.+?)(?:\s*\.\s*|$)', query_en)
                if match:
                    date_query = match.group(1).strip()
                    self.speak(f"Finding photos from {date_query}...", self.language_code)
                    photos = self._search_local_images(date_query)
                    if photos:
                        response_en = f"Found {len(photos)} photos from {date_query}:\n" + "\n".join(photos[:3])
                    else:
                        response_en = f"No photos found from {date_query}."
                else:
                    response_en = "What date should I search for?"
            
            # News
            elif "news" in query_en or "headlines" in query_en:
                self.speak("Getting the latest headlines...", self.language_code)
                response_en = self._get_news()
            
            # Wikipedia
            elif "wikipedia" in query_en:
                response_en = self._search_wikipedia(query_en)
            
            # General AI Query
            else:
                self.speak("Thinking...", self.language_code)
                response_en = self._process_ai_query(query_en)
            
            # Translate and speak response
            final_response = self._translate(response_en, 'en', self.language_code)
            self.speak(final_response, self.language_code)
            
            # Store in conversation history
            self.conversation_history.append({"assistant": final_response, "lang": self.language_code})
            
            # Update memory occasionally
            if len(self.conversation_history) % 10 == 0 and self.memory_enabled:
                # Store summary in database
                db_path = os.path.expanduser("~/rico_memory.db")
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                for entry in self.conversation_history[-5:]:
                    if 'user' in entry:
                        cursor.execute(
                            "INSERT INTO conversations (timestamp, user_input, response, language) VALUES (?, ?, ?, ?)",
                            (datetime.datetime.now().isoformat(), 
                             entry.get('user', ''), 
                             entry.get('assistant', ''), 
                             self.language_code)
                        )
                conn.commit()
                conn.close()
# --- Main Entry Point ---
if __name__ == "__main__":
    # Check if running in text mode
    import sys
    text_mode = "--text" in sys.argv or "--type" in sys.argv
    
    # Create and run Rico
    rico = RicoAssistant(text_mode=text_mode, memory_enabled=True)
    rico.run()
            
        



  



