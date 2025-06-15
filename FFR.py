import tkinter as tk
from tkinter import ttk, Scrollbar, Button, messagebox, filedialog
import requests
from PIL import Image, ImageTk
from io import BytesIO
import os
import sys
import json
import subprocess 
import re  
import webbrowser
import zlib
import base64
import hashlib
import xml.etree.ElementTree as ET
from Crypto.Cipher import AES
import shutil
import threading
import queue
import platform
import urllib.request
import zipfile
import tarfile
import stat
import pygame
from urllib.parse import quote
import time
import random

class SmartPreviewSystem:
    def __init__(self):
        self.current_url = None
        self.is_playing = False
        self.position = 0
        self.parent_app = None
        self.current_temp_file = None
        
        # Initialize pygame mixer for audio playback
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
        except pygame.error as e:
            print(f"Audio initialization failed: {e}")

    def normalize_text(self, text):
        """Smart text normalization for matching"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove common variations that don't affect song identity
        text = re.sub(r'\bfeat\.?\s+.*$', '', text)  # Remove featuring
        text = re.sub(r'\bft\.?\s+.*$', '', text)    # Remove ft.
        text = re.sub(r'\(feat\.?\s+.*?\)', '', text)  # Remove (feat...)
        text = re.sub(r'\(ft\.?\s+.*?\)', '', text)    # Remove (ft...)
        text = re.sub(r'\s*\(.*remix.*\)', '', text)   # Remove remix info
        text = re.sub(r'\s*\(.*version.*\)', '', text) # Remove version info
        text = re.sub(r'\s*\[.*?\]\s*', '', text)      # Remove brackets
        
        # Clean up punctuation and spaces
        text = re.sub(r'[^\w\s]', ' ', text)  # Replace punctuation with spaces
        text = re.sub(r'\s+', ' ', text)      # Normalize spaces
        text = text.strip()
        
        return text

    def calculate_similarity(self, search_text, result_text):
        """Calculate similarity between search and result text"""
        search_norm = self.normalize_text(search_text)
        result_norm = self.normalize_text(result_text)
        
        if not search_norm or not result_norm:
            return 0.0
        
        # Exact match after normalization
        if search_norm == result_norm:
            return 1.0
        
        # Check if one contains the other
        if search_norm in result_norm or result_norm in search_norm:
            return 0.9
        
        # Word-based similarity
        search_words = set(search_norm.split())
        result_words = set(result_norm.split())
        
        if not search_words or not result_words:
            return 0.0
        
        intersection = search_words.intersection(result_words)
        union = search_words.union(result_words)
        
        return len(intersection) / len(union) if union else 0.0

    def is_good_match(self, search_artist, search_title, result_artist, result_title):
        """Determine if a result is a good match for the search"""
        artist_sim = self.calculate_similarity(search_artist, result_artist)
        title_sim = self.calculate_similarity(search_title, result_title)
        
        # For very short titles (like "i"), require higher artist similarity
        if len(search_title.strip()) <= 2:
            return artist_sim >= 0.8 and title_sim >= 0.9
        
        # For normal titles, be more flexible
        return artist_sim >= 0.7 and title_sim >= 0.8

    def search_deezer_comprehensive(self, artist, title):
        """Comprehensive Deezer search"""
        search_strategies = [
            f'artist:"{artist}" track:"{title}"',
            f"{artist} {title}",
            f'track:"{title}"'
        ]
        
        for strategy in search_strategies:
            try:
                url = f"https://api.deezer.com/search?q={quote(strategy)}&limit=50"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if 'data' in data and data['data']:
                    for track in data['data']:
                        if not track.get('preview'):
                            continue
                        
                        track_artist = track['artist']['name']
                        track_title = track['title']
                        
                        if self.is_good_match(artist, title, track_artist, track_title):
                            print(f"✓ Deezer success: '{track_artist}' - '{track_title}'")
                            return track['preview']
            except Exception as e:
                print(f"Deezer strategy failed: {e}")
                continue
        
        return None

    def search_preview_ultimate(self, artist, title):
        """Ultimate preview search using Deezer only"""
        print(f"\n🔍 Searching preview for: '{artist}' - '{title}'")
        
        # Clean the inputs
        clean_artist = artist.strip()
        clean_title = title.strip()
        
        if not clean_artist or not clean_title:
            print("❌ Empty artist or title")
            return None
        
        try:
            print("Trying Deezer...")
            preview_url = self.search_deezer_comprehensive(clean_artist, clean_title)
            if preview_url:
                print(f"✅ Found preview via Deezer!")
                return preview_url
        except Exception as e:
            print(f"❌ Deezer failed: {e}")
        
        print(f"❌ No preview found for: '{clean_artist}' - '{clean_title}'")
        return None

    def play_preview(self, preview_url):
        """Play 30-second preview from URL"""
        try:
            if self.is_playing:
                self.stop()
            
            # Download the preview temporarily
            response = requests.get(preview_url, timeout=15)
            response.raise_for_status()
            
            # Use unique filenames to avoid conflicts
            timestamp = str(int(time.time() * 1000))  # milliseconds timestamp
            temp_mp3_file = f"temp_preview_{timestamp}.mp3"
            temp_wav_file = f"temp_preview_{timestamp}.wav"
            
            # Write the downloaded content
            with open(temp_mp3_file, 'wb') as f:
                f.write(response.content)
            
            # Convert MP3 to WAV using FFmpeg for better compatibility
            ffmpeg_path = getattr(self.parent_app, 'ffmpeg_path', 'ffmpeg')
            
            # Convert to WAV
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            subprocess.run([
                ffmpeg_path, '-y', '-i', temp_mp3_file, 
                '-acodec', 'pcm_s16le', '-ar', '22050', '-ac', '2',
                temp_wav_file
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
            
            # Clean up the MP3 file
            os.remove(temp_mp3_file)
            
            # Play the WAV file
            pygame.mixer.music.load(temp_wav_file)
            pygame.mixer.music.play()
            self.is_playing = True
            self.current_url = preview_url
            self.current_temp_file = temp_wav_file  # Store for cleanup
                
            # Clean up temp file after a delay
            def cleanup():
                time.sleep(40)  # Wait for playback to complete
                try:
                    if os.path.exists(temp_wav_file):
                        os.remove(temp_wav_file)
                except:
                    pass
            
            threading.Thread(target=cleanup, daemon=True).start()
            
        except Exception as e:
            print(f"Error playing preview: {e}")
            # Clean up on error
            try:
                if 'temp_mp3_file' in locals() and os.path.exists(temp_mp3_file):
                    os.remove(temp_mp3_file)
                if 'temp_wav_file' in locals() and os.path.exists(temp_wav_file):
                    os.remove(temp_wav_file)
            except:
                pass
            raise e
    
    def stop(self):
        """Stop current playback"""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            self.is_playing = False
            
            # Clean up current temp file if it exists
            if hasattr(self, 'current_temp_file') and self.current_temp_file and os.path.exists(self.current_temp_file):
                try:
                    os.remove(self.current_temp_file)
                except:
                    pass
        except:
            pass
    
    def is_playing_status(self):
        """Check if currently playing"""
        return pygame.mixer.music.get_busy() and self.is_playing

class FortniteTracksGUI:
    def __init__(self, root):
        self.root = root
        self.settings_file = "settings.json"
        
        # Add queue for thread communication
        self.download_queue_thread = queue.Queue()
        self.downloading = False
        self.ffmpeg_ready = False
        
        # Add song queue for downloads
        self.song_queue = []
        self.current_download_index = 0
        
        # Initialize preview system
        self.preview_system = SmartPreviewSystem()
        self.preview_system.parent_app = self

        # Register cleanup to delete WAV files when app closes
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        settings = self.load_settings()
        self.extract_folder = settings.get("extract_folder", os.getcwd())
        self.dark_mode = settings.get("dark_mode", True)
        self.sorting_method = settings.get("sorting_method", "Last Added")
        self.sort_ascending = settings.get("sort_ascending", True)
        self.auto_open_folder = settings.get("auto_open_folder", False)
        self.file_format = settings.get("file_format", "wav")
        self.file_format_var = tk.StringVar(value=self.file_format)
        self.extracting_method = settings.get("extracting_method", "Stereo")
        self.extracting_method_var = tk.StringVar(value=self.extracting_method)
        self.file_naming = settings.get("file_naming", "Only Stem Type")
        self.file_naming_var = tk.StringVar(value=self.file_naming)

        self.root.title("Fortnite Festival Extractor")
        self.root.geometry("900x600")
        
        if getattr(sys, 'frozen', False):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        
        try:
            icon_path = os.path.join(application_path, "icon.png")
            if os.path.exists(icon_path):
                self.root.iconphoto(False, tk.PhotoImage(file=icon_path))
        except Exception:
            pass

        self.style = ttk.Style()
        self.style.theme_use("clam")

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left side - Song list with search
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))

        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_frame, text="Search Song:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self.search_songs)

        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.song_listbox = tk.Listbox(list_frame, width=60, height=25, bg="#2E2E2E", fg="#FFFFFF", font=("Arial", 12))
        self.song_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.song_listbox.bind("<<ListboxSelect>>", self.on_song_select)

        scrollbar = Scrollbar(list_frame, orient=tk.VERTICAL, command=self.song_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.song_listbox.config(yscrollcommand=scrollbar.set)

        # Right side - Tabs
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Song Info tab
        self.song_info_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.song_info_frame, text="Song Info")

        # Queue tab
        self.queue_frame = ttk.Frame(self.notebook, padding=(10, 5, 10, 10))  # top, right, bottom, left
        self.notebook.add(self.queue_frame, text="Queue")

        # Progress bar (shared, but only visible in queue tab initially)
        self.progress = ttk.Progressbar(self.queue_frame, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=2)  # Reduced from 10 to 2
        self.progress["maximum"] = 100

        self.status_label = ttk.Label(self.queue_frame, text="Getting things ready...", font=("Arial", 12))
        self.status_label.pack(pady=2)  # Reduced from 5 to 2

        # Queue listbox
        queue_list_frame = ttk.Frame(self.queue_frame)
        queue_list_frame.pack(fill=tk.X, expand=False, pady=(5, 2))
        
        ttk.Label(queue_list_frame, text="Download Queue:", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 5))
        
        self.queue_listbox = tk.Listbox(queue_list_frame, height=20, bg="#2E2E2E", fg="#FFFFFF", font=("Arial", 11))
        self.queue_listbox.pack(fill=tk.BOTH, expand=True)
        self.queue_listbox.bind("<<ListboxSelect>>", self.on_queue_select)

        # Queue buttons frame - Triangle layout
        queue_buttons_frame = ttk.Frame(self.queue_frame)
        queue_buttons_frame.pack(fill=tk.X, pady=(5, 5))

        # Top row - Download All button (centered)
        top_button_frame = ttk.Frame(queue_buttons_frame)
        top_button_frame.pack(pady=(0, 3))

        self.download_all_button = ttk.Button(top_button_frame, text="Download All", command=self.download_all_queue)
        self.download_all_button.pack()

        # Bottom row - Clear Queue and Remove Selected buttons (side by side, centered)
        bottom_button_frame = ttk.Frame(queue_buttons_frame)
        bottom_button_frame.pack(pady=(0, 0))

        self.clear_queue_button = ttk.Button(bottom_button_frame, text="Clear Queue", command=self.clear_queue)
        self.clear_queue_button.pack(side=tk.LEFT)

        self.remove_selected_button = ttk.Button(bottom_button_frame, text="Remove Selected", command=self.remove_selected_from_queue)
        self.remove_selected_button.pack(side=tk.LEFT)

        # Settings button
        self.settings_button = ttk.Button(self.root, text="Settings", command=self.open_settings_window)
        self.settings_button.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)

        self.apply_theme()
        
        # Initialize FFmpeg first
        self.setup_ffmpeg()
        
        self.songs = self.fetch_and_extract_songs()
        self.filtered_songs = self.songs
        self.display_songs(self.filtered_songs)

        # Start checking the download queue
        self.check_download_queue()

        try:
            if getattr(sys, 'frozen', False):
                logo_path = os.path.join(sys._MEIPASS, "logo.png")
            else:
                logo_path = "logo.png"
            if os.path.exists(logo_path):
                image = Image.open(logo_path)
                image = image.resize((200, 70), Image.LANCZOS)
                self.cached_logo = ImageTk.PhotoImage(image)
            else:
                self.cached_logo = None
        except Exception:
            self.cached_logo = None

    def setup_ffmpeg(self):
        """Setup FFmpeg in background thread"""
        setup_thread = threading.Thread(target=self.setup_ffmpeg_worker, daemon=True)
        setup_thread.start()

    def setup_ffmpeg_worker(self):
        """Background worker to setup FFmpeg"""
        try:
            self.ffmpeg_path = self.get_or_download_ffmpeg()
            self.ffmpeg_ready = True
            self.update_status("All set! Pick songs and add to queue 🎵")
            self.update_progress(0)
        except Exception as e:
            self.show_error(f"FFmpeg setup failed: {str(e)}")
            self.ffmpeg_ready = False

    def get_or_download_ffmpeg(self):
        """Get FFmpeg path or download if needed"""
        # Determine the correct directory for FFmpeg
        if getattr(sys, 'frozen', False):
            # Running as executable
            base_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        ffmpeg_dir = os.path.join(base_dir, "ffmpeg_bin")
        
        system = platform.system()
        if system == "Windows":
            ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
        else:
            ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg")
        
        # Check if FFmpeg already exists
        if os.path.exists(ffmpeg_exe):
            return ffmpeg_exe
        
        # Download FFmpeg
        self.update_status("First time setup - downloading tools...")
        return self.download_ffmpeg_for_platform(ffmpeg_dir)

    def download_ffmpeg_for_platform(self, ffmpeg_dir):
        """Download FFmpeg for the current platform"""
        system = platform.system()
        machine = platform.machine().lower()
        
        # Create directory
        os.makedirs(ffmpeg_dir, exist_ok=True)
        
        if system == "Windows":
            if "64" in machine or "amd64" in machine or "x86_64" in machine:
                url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            else:
                # Fallback for 32-bit (rare these days)
                url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            
            return self.download_and_extract_windows(url, ffmpeg_dir)
            
        elif system == "Darwin":  # macOS
            # Use homebrew static builds
            url = "https://evermeet.cx/ffmpeg/ffmpeg-6.0.zip"
            return self.download_and_extract_macos(url, ffmpeg_dir)
            
        else:  # Linux
            if "64" in machine or "amd64" in machine or "x86_64" in machine:
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            else:
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"
            
            return self.download_and_extract_linux(url, ffmpeg_dir)

    def download_and_extract_windows(self, url, ffmpeg_dir):
        """Download and extract FFmpeg for Windows"""
        self.update_status("Downloading audio processor...")
        self.update_progress(5)
        
        # Download
        zip_path = os.path.join(ffmpeg_dir, "ffmpeg.zip")
        self.download_with_progress(url, zip_path, 5, 70)
        
        self.update_status("Setting up audio processor...")
        self.update_progress(75)
        
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith('ffmpeg.exe'):
                    # Extract just the ffmpeg.exe
                    with zip_ref.open(file_info) as source:
                        ffmpeg_path = os.path.join(ffmpeg_dir, "ffmpeg.exe")
                        with open(ffmpeg_path, 'wb') as target:
                            shutil.copyfileobj(source, target)
                    break
        
        os.remove(zip_path)
        self.update_progress(100)
        return ffmpeg_path

    def download_and_extract_macos(self, url, ffmpeg_dir):
        """Download and extract FFmpeg for macOS"""
        self.update_status("Downloading audio processor...")
        self.update_progress(5)
        
        # Download
        zip_path = os.path.join(ffmpeg_dir, "ffmpeg.zip")
        self.download_with_progress(url, zip_path, 5, 70)
        
        self.update_status("Setting up audio processor...")
        self.update_progress(75)
        
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)
        
        ffmpeg_path = os.path.join(ffmpeg_dir, "ffmpeg")
        os.chmod(ffmpeg_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        
        os.remove(zip_path)
        self.update_progress(100)
        return ffmpeg_path

    def download_and_extract_linux(self, url, ffmpeg_dir):
        """Download and extract FFmpeg for Linux"""
        self.update_status("Downloading audio processor...")
        self.update_progress(5)
        
        # Download
        tar_path = os.path.join(ffmpeg_dir, "ffmpeg.tar.xz")
        self.download_with_progress(url, tar_path, 5, 70)
        
        self.update_status("Setting up audio processor...")
        self.update_progress(75)
        
        # Extract
        with tarfile.open(tar_path, 'r:xz') as tar_ref:
            for member in tar_ref.getmembers():
                if member.name.endswith('ffmpeg') and not '/' in member.name.split('/')[-1]:
                    # Extract the ffmpeg binary
                    member.name = "ffmpeg"  # Rename to just ffmpeg
                    tar_ref.extract(member, ffmpeg_dir)
                    break
        
        ffmpeg_path = os.path.join(ffmpeg_dir, "ffmpeg")
        os.chmod(ffmpeg_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        
        os.remove(tar_path)
        self.update_progress(100)
        return ffmpeg_path

    def is_epic_games_song(self, artist):
        """Check if song is made by Epic Games"""
        # Clean the artist name and check for exact match
        clean_artist = re.sub(r'[^\w\s]', '', artist.strip().lower())
        clean_artist = re.sub(r'\s+', ' ', clean_artist).strip()
        
        # Only block previews for songs where the artist is literally "Epic Games"
        epic_variants = [
            "epic games",
            "epicgames"
        ]
        
        return clean_artist in epic_variants

    def delete_all_wav_files(self):
        """Delete all WAV files with 'temp' in the name when program closes"""
        try:
            import glob
            
            # Stop any playing audio first
            if hasattr(self, 'preview_system'):
                self.preview_system.stop()
            
            # Wait for pygame to release files
            time.sleep(1)
            
            # Find and delete only WAV files with 'temp' in their name
            wav_files = glob.glob("*temp*.wav")
            deleted_count = 0
            
            for wav_file in wav_files:
                try:
                    if os.path.exists(wav_file):
                        os.remove(wav_file)
                        deleted_count += 1
                        print(f"Deleted: {wav_file}")
                except Exception as e:
                    print(f"Could not delete {wav_file}: {e}")
            
            if deleted_count > 0:
                print(f"Deleted {deleted_count} temporary WAV files")
            
        except Exception as e:
            print(f"Error deleting temporary WAV files: {e}")

    def on_closing(self):
        """Handle app closing - delete all WAV files"""
        print("Closing application and deleting WAV files...")
        
        # Delete all WAV files
        self.delete_all_wav_files()
        
        # Close the application
        self.root.destroy()

    def play_song_preview(self, song):
        """Play 30-second preview of the song"""
        if hasattr(self, 'preview_button'):
            self.preview_button.config(state="disabled")
        try:
            if hasattr(self, 'preview_status'):
                self.preview_status.config(text="Searching for preview...")
            
            # Search for preview in a background thread
            def search_and_play():
                preview_url = self.preview_system.search_preview_ultimate(song['artist'], song['title'])
                
                if preview_url:
                    # Update UI in main thread
                    self.root.after(0, lambda: self.start_preview_playback(preview_url))
                else:
                    self.root.after(0, lambda: self.preview_not_found())
            
            threading.Thread(target=search_and_play, daemon=True).start()
            
        except Exception as e:
            if hasattr(self, 'preview_status'):
                self.preview_status.config(text="Preview error")
            if hasattr(self, 'preview_button'):
                self.preview_button.config(text="▶ Play Preview", state="normal")
            print(f"Preview error: {e}")

    def start_preview_playback(self, preview_url):
        """Start playing the preview"""
        try:
            self.preview_system.play_preview(preview_url)
            if hasattr(self, 'preview_status'):
                self.preview_status.config(text="Playing 30s preview...")
            if hasattr(self, 'preview_button'):
                self.preview_button.config(text="⏹ Stop Preview", state="normal")
            
            # Cancel any existing auto-stop timer
            if hasattr(self, 'auto_stop_timer'):
                try:
                    self.auto_stop_timer.cancel()
                except:
                    pass
            
            # Auto-stop after 30 seconds
            def auto_stop_check():
                self.stop_preview()

            self.auto_stop_timer = threading.Timer(30.0, auto_stop_check)
            self.auto_stop_timer.daemon = True
            self.auto_stop_timer.start()
            
        except Exception as e:
            if hasattr(self, 'preview_status'):
                self.preview_status.config(text="Playback failed")
            if hasattr(self, 'preview_button'):
                self.preview_button.config(text="▶ Play Preview", state="normal")
            print(f"Playback error: {e}")

    def stop_preview(self):
        """Stop preview playback"""
        # Cancel auto-stop timer
        if hasattr(self, 'auto_stop_timer'):
            try:
                self.auto_stop_timer.cancel()
            except:
                pass
        
        self.preview_system.stop()
        if hasattr(self, 'preview_status'):
            self.preview_status.config(text="")
        if hasattr(self, 'preview_button'):
            self.preview_button.config(text="▶ Play Preview", state="normal")

    def toggle_preview(self, song):
        """Toggle preview playback"""
        if self.preview_system.is_playing_status():
            # Currently playing, so stop
            self.stop_preview()
        else:
            # Not playing, so start
            self.play_song_preview(song)

    def preview_not_found(self):
        """Handle when no preview is found"""
        if hasattr(self, 'preview_status'):
            self.preview_status.config(text="No preview available")
        if hasattr(self, 'preview_button'):
            self.preview_button.config(text="▶ Play Preview", state="normal")

    def download_with_progress(self, url, output_path, start_progress, end_progress):
        """Download file with progress updates"""
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded_size += len(chunk)
                if total_size > 0:
                    progress = start_progress + int((downloaded_size / total_size) * (end_progress - start_progress))
                    self.update_progress(progress)

    def check_download_queue(self):
        """Check for messages from download thread"""
        try:
            while True:
                message = self.download_queue_thread.get_nowait()
                if message['type'] == 'progress':
                    self.progress["value"] = message['value']
                elif message['type'] == 'status':
                    self.status_label.config(text=message['text'])
                elif message['type'] == 'error':
                    messagebox.showerror("Error", message['text'])
                    self.downloading = False
                elif message['type'] == 'success':
                    messagebox.showinfo("Success", message['text'])
                    self.downloading = False
                elif message['type'] == 'done':
                    self.downloading = False
                elif message['type'] == 'next_song':
                    self.current_download_index += 1
                    if self.current_download_index < len(self.song_queue):
                        self.download_next_in_queue()
                    else:
                        self.queue_download_complete()
                self.root.update_idletasks()
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.check_download_queue)

    def update_progress(self, value):
        """Thread-safe progress update"""
        self.download_queue_thread.put({'type': 'progress', 'value': value})

    def update_status(self, text):
        """Thread-safe status update"""
        self.download_queue_thread.put({'type': 'status', 'text': text})

    def show_error(self, text):
        """Thread-safe error display"""
        self.download_queue_thread.put({'type': 'error', 'text': text})

    def show_success(self, text):
        """Thread-safe success display"""
        self.download_queue_thread.put({'type': 'success', 'text': text})

    def download_complete(self):
        """Signal download completion"""
        self.download_queue_thread.put({'type': 'done'})

    def next_song_signal(self):
        """Signal to move to next song in queue"""
        self.download_queue_thread.put({'type': 'next_song'})

    def add_to_queue(self, song):
        """Add song to download queue"""
        # Check if song is already in queue
        for queued_song in self.song_queue:
            if queued_song['sid'] == song['sid']:
                messagebox.showinfo("Already in Queue", f"{song['title']} is already in the download queue.")
                return
        
        self.song_queue.append(song)
        self.update_queue_display()
        self.update_song_info_display()  # Refresh to update button state

    def check_easter_egg(self, query):
        """Check for easter egg and handle it"""
        if query == "letmedownloadallthesongs":
            result = messagebox.askyesno("Easter Egg Found!", 
                                    "Are you sure you want to add all of the songs into your queue list?")
            if result:
                # Add all songs to queue (not just filtered ones)
                added_count = 0
                for song in self.songs:  # Changed from self.filtered_songs to self.songs
                    if not self.is_song_in_queue(song):
                        self.song_queue.append(song)
                        added_count += 1
                
                self.update_queue_display()
                self.update_song_info_display()
                messagebox.showinfo("Songs Added", f"Added {added_count} songs to the queue!")
            return True
        return False

    def remove_selected_from_queue(self):
        """Remove selected song from queue"""
        selection = self.queue_listbox.curselection()
        if selection:
            index = selection[0]
            removed_song = self.song_queue.pop(index)
            self.update_queue_display()
            self.update_song_info_display()  # Refresh to update button state
            messagebox.showinfo("Removed", f"Removed {removed_song['title']} from queue.")

    def clear_queue(self):
        """Clear all songs from queue"""
        if self.song_queue:
            if messagebox.askyesno("Clear Queue", "Are you sure you want to clear the entire queue?"):
                self.song_queue.clear()
                self.update_queue_display()
                self.update_song_info_display()  # Refresh to update button state

    def update_queue_display(self):
        """Update the queue listbox display"""
        self.queue_listbox.delete(0, tk.END)
        for i, song in enumerate(self.song_queue):
            display_text = f"{i+1}. {song['artist']} - {song['title']}"
            if self.downloading and i == self.current_download_index:
                display_text += " (Downloading...)"
            self.queue_listbox.insert(tk.END, display_text)

    def on_queue_select(self, event=None):
        """Handle queue selection - switch to song info tab and show selected song"""
        selection = self.queue_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.song_queue):
                selected_song = self.song_queue[index]
                
                # Switch to Song Info tab
                self.notebook.select(0)  # Select first tab (Song Info)
                
                # Display the song info
                self.display_song_info(selected_song)

    def download_all_queue(self):
        """Start downloading all songs in queue"""
        if not self.song_queue:
            messagebox.showwarning("Empty Queue", "No songs in queue to download.")
            return
            
        if self.downloading:
            messagebox.showwarning("Download in Progress", "A download is already in progress. Please wait for it to complete.")
            return
        
        if not self.ffmpeg_ready:
            messagebox.showwarning("FFmpeg is Not Ready", "Still setting up tools. Please wait a moment and try again.")
            return
        
        self.downloading = True
        self.current_download_index = 0
        self.update_queue_display()
        self.download_next_in_queue()

    def download_next_in_queue(self):
        """Download the next song in queue"""
        if self.current_download_index < len(self.song_queue):
            song = self.song_queue[self.current_download_index]
            self.update_queue_display()  # Update to show current downloading
            download_thread = threading.Thread(target=self.download_song_thread, args=(song, True), daemon=True)
            download_thread.start()

    def queue_download_complete(self):
        """Handle completion of entire queue download"""
        self.downloading = False
        self.current_download_index = 0
        self.song_queue.clear()  # Clear queue after successful download
        self.update_queue_display()
        self.update_song_info_display()
        self.show_success(f"Queue download completed! All songs have been extracted.")

    def decompress_blurl(self, filepath):
        with open(filepath, 'rb') as f:
            f.seek(8)
            decompressed = zlib.decompress(f.read())
            return json.loads(decompressed)

    def parse_envelope(self, ev_b64):
        b = base64.b64decode(ev_b64)
        if b[0] != 1:
            raise Exception("Invalid envelope")
        string_length = b[2]
        nonce = b[5:5+string_length].decode()
        key = b[5+string_length:5+string_length+16]
        return nonce, key

    def aes_decrypt(self, key, data):
        cipher = AES.new(key, AES.MODE_ECB)
        if len(data) % 16 != 0:
            raise Exception("Ciphertext not multiple of block size")
        return cipher.decrypt(data)

    def get_encryption_key(self, keys_path, nonce, encryptedkey):
        with open(keys_path, 'rb') as f:
            offset = 0
            while True:
                f.seek(offset)
                first5 = f.read(5)
                if len(first5) < 5:
                    break
                md5 = hashlib.md5()
                md5.update(first5[:4])
                md5.update(nonce.encode())
                result = md5.digest()
                if result[0] == first5[4]:
                    f.seek(15, 1)
                    encryption_key = f.read(32)
                    if len(encryption_key) < 32:
                        break
                    try:
                        return self.aes_decrypt(encryption_key, encryptedkey)
                    except Exception as e:
                        print("Failed to decrypt encryption key:", e)
                offset += 0x34
        return None

    def download_file(self, url, out_path):
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

    def parse_mpd(self, mpd_xml):
        root = ET.fromstring(mpd_xml)
        ns = {'mpd': 'urn:mpeg:dash:schema:mpd:2011'}
        for period in root.findall('mpd:Period', ns):
            for adaptation in period.findall('mpd:AdaptationSet', ns):
                content_type = adaptation.get('contentType')
                if content_type != 'audio':
                    continue
                for representation in adaptation.findall('mpd:Representation', ns):
                    seg_template = representation.find('mpd:SegmentTemplate', ns)
                    if seg_template is not None:
                        init = seg_template.get('initialization')
                        media = seg_template.get('media')
                        start_number = int(seg_template.get('startNumber', '1'))
                        duration = int(seg_template.get('duration'))
                        timescale = int(seg_template.get('timescale'))
                        return {
                            'init': init.replace('$RepresentationID$', representation.get('id')),
                            'media': media.replace('$RepresentationID$', representation.get('id')),
                            'start_number': start_number,
                            'duration': duration,
                            'timescale': timescale,
                            'segment_count': None
                        }
        raise Exception("No suitable audio segment template found in MPD.")

    def estimate_segment_count(self, mpd_xml, duration, timescale):
        match = re.search(r'mediaPresentationDuration="PT([\d\.]+)S"', mpd_xml)
        if match:
            total_seconds = float(match.group(1))
            segment_length = duration / timescale
            estimated_count = int(total_seconds / segment_length + 0.5)
            return estimated_count
        return 100  # Keep reasonable fallback

    def find_actual_segment_count(self, base_url, seg_info, mpd_xml):
        print("Finding actual segment count...")
        
        # Start with MPD estimate
        estimated_count = self.estimate_segment_count(mpd_xml, seg_info['duration'], seg_info['timescale'])
        print(f"MPD estimate: {estimated_count} segments")
        
        # Always be aggressive - check well beyond the estimate
        # Use a smart exponential search to find the upper bound quickly
        return self.exponential_then_binary_search(base_url, seg_info, estimated_count)

    def exponential_then_binary_search(self, base_url, seg_info, estimated_count):
        """Use exponential search to find upper bound, then binary search for exact count"""
        
        # Step 1: Start from the estimate and expand exponentially to find upper bound
        print("Phase 1: Finding upper bound with exponential search...")
        
        # Always start checking from at least the estimate
        current = estimated_count
        last_valid = estimated_count
        step_size = 10  # Start with steps of 10
        
        # First, verify our starting point (the estimate) actually works
        test_seg_num = seg_info['start_number'] + current - 1
        test_url = base_url + seg_info['media'].replace('$Number$', str(test_seg_num))
        
        try:
            test_response = requests.head(test_url, timeout=4)
            if test_response.status_code == 200:
                last_valid = current
                print(f"Estimate segment {test_seg_num} exists")
            else:
                print(f"Estimate segment {test_seg_num} doesn't exist, searching backwards first...")
                # If estimate doesn't work, binary search downward
                return self.binary_search_segments(base_url, seg_info, 1, estimated_count - 1)
        except:
            print(f"Failed to check estimate segment, searching backwards...")
            return self.binary_search_segments(base_url, seg_info, 1, estimated_count - 1)
        
        # Step 2: Exponential search upward to find where segments stop existing
        max_checks = 15  # Limit exponential checks to prevent too much delay
        checks_done = 0
        
        while checks_done < max_checks:
            current += step_size
            test_seg_num = seg_info['start_number'] + current - 1
            test_url = base_url + seg_info['media'].replace('$Number$', str(test_seg_num))
            
            try:
                test_response = requests.head(test_url, timeout=3)
                if test_response.status_code == 200:
                    last_valid = current
                    print(f"Segment {test_seg_num} exists, expanding search...")
                    step_size = min(step_size * 2, 50)  # Exponentially increase step, but cap at 50
                else:
                    print(f"Segment {test_seg_num} doesn't exist, found upper bound around {current}")
                    break
            except:
                print(f"Failed to check segment {test_seg_num}, found upper bound around {current}")
                break
                
            checks_done += 1
        
        # If we hit max_checks, we might have a very long song
        if checks_done >= max_checks:
            print(f"Hit maximum exponential checks, using upper bound of {current}")
        
        # Step 3: Binary search between last_valid and current for exact count
        print(f"Phase 2: Binary search between {last_valid} and {current}")
        final_count = self.binary_search_segments(base_url, seg_info, last_valid, current)
        
        # Step 4: Final verification - check a few segments after our result
        print("Phase 3: Final verification...")
        verified_count = self.verify_and_extend(base_url, seg_info, final_count)
        
        return verified_count

    def verify_and_extend(self, base_url, seg_info, found_count):
        """Verify the found count and check a few more segments just to be sure"""
        
        # Check the found segment exists
        test_seg_num = seg_info['start_number'] + found_count - 1
        test_url = base_url + seg_info['media'].replace('$Number$', str(test_seg_num))
        
        try:
            test_response = requests.head(test_url, timeout=4)
            if test_response.status_code != 200:
                print(f"Warning: Found count {found_count} segment doesn't exist!")
                return found_count - 1
        except:
            print(f"Warning: Cannot verify found count {found_count}")
            return found_count - 1
        
        # Check 5 more segments beyond our found count to be absolutely sure
        for extra in range(1, 6):
            test_seg_num = seg_info['start_number'] + found_count + extra - 1
            test_url = base_url + seg_info['media'].replace('$Number$', str(test_seg_num))
            
            try:
                test_response = requests.head(test_url, timeout=3)
                if test_response.status_code == 200:
                    found_count += 1
                    print(f"Found additional segment {test_seg_num}, new count: {found_count}")
                else:
                    break
            except:
                break
        
        print(f"Final verified segment count: {found_count}")
        return found_count
    
    def aggressive_search_from_high(self, base_url, seg_info, start_estimate):
        """Start from a high estimate and work backwards to find the true end"""
        print(f"Starting aggressive search from segment {start_estimate}")
        
        # First, find a reasonable upper bound by going even higher
        upper_bound = start_estimate
        while upper_bound < start_estimate + 100:  # Limit to prevent infinite searching
            test_seg_num = seg_info['start_number'] + upper_bound - 1
            test_url = base_url + seg_info['media'].replace('$Number$', str(test_seg_num))
            
            try:
                test_response = requests.head(test_url, timeout=4)
                if test_response.status_code == 200:
                    print(f"Segment {test_seg_num} exists, expanding search...")
                    upper_bound += 20  # Jump by larger chunks
                else:
                    print(f"Found upper bound at segment {upper_bound}")
                    break
            except:
                print(f"Found upper bound at segment {upper_bound}")
                break
        
        # Now binary search between start_estimate and upper_bound
        return self.binary_search_segments(base_url, seg_info, start_estimate, upper_bound)
    
    def standard_segment_search(self, base_url, seg_info, estimated_count):
        """Standard search for songs under 3:58"""
        test_seg_num = seg_info['start_number'] + estimated_count - 1
        test_url = base_url + seg_info['media'].replace('$Number$', str(test_seg_num))
        
        try:
            test_response = requests.head(test_url, timeout=5)
            if test_response.status_code == 200:
                # Estimate was correct or too low, check a few more
                print(f"Segment {test_seg_num} exists, checking for additional segments...")
                for extra in range(1, 21):  # Check up to 20 more
                    test_url = base_url + seg_info['media'].replace('$Number$', str(test_seg_num + extra))
                    try:
                        test_response = requests.head(test_url, timeout=3)
                        if test_response.status_code != 200:
                            final_count = estimated_count + extra - 1
                            print(f"Found actual segment count: {final_count}")
                            return final_count
                    except:
                        final_count = estimated_count + extra - 1
                        print(f"Found actual segment count: {final_count}")
                        return final_count
                # If all 20 extra segments exist, there might be more
                return estimated_count + 20
            else:
                # Estimate was too high, binary search downward
                print(f"Segment {test_seg_num} doesn't exist, searching backwards...")
                return self.binary_search_segments(base_url, seg_info, 1, estimated_count)
                
        except Exception as e:
            print(f"Error testing segments: {e}")
            return estimated_count

    def binary_search_segments(self, base_url, seg_info, low_count, high_count):
        """Efficiently find the actual segment count using binary search"""
        print(f"Binary searching segments between {low_count} and {high_count}")
        
        low = low_count
        high = high_count
        last_valid = low_count
        
        while low <= high:
            mid = (low + high) // 2
            test_seg_num = seg_info['start_number'] + mid - 1
            test_url = base_url + seg_info['media'].replace('$Number$', str(test_seg_num))
            
            try:
                test_response = requests.head(test_url, timeout=4)
                if test_response.status_code == 200:
                    last_valid = mid
                    low = mid + 1
                else:
                    high = mid - 1
            except:
                high = mid - 1
        
        print(f"Binary search found segment count: {last_valid}")
        return last_valid

    def convert_blurl_to_mp4(self, blurl_file, total_segments):
        try:
            self.update_status("Loading song data...")
            self.update_progress(5)

            blurl = self.decompress_blurl(blurl_file)
            print("BLURL loaded.")

            media_url = blurl['playlists'][0]['url']
            print("Media URL:", media_url)

            if blurl.get('ev'):
                nonce, key = self.parse_envelope(blurl['ev'])
                dec_key = self.get_encryption_key('keys.bin', nonce, key)
                if not dec_key:
                    print("Failed to get decryption key.")
                    return
                key_hex = dec_key.hex()
                print("Decryption key:", key_hex)
            else:
                key_hex = None

            r = requests.get(media_url)
            r.raise_for_status()
            mpd_xml = r.text

            try:
                seg_info = self.parse_mpd(mpd_xml)
            except Exception as e:
                print("MPD parsing failed:", e)
                return

            base_url = '/'.join(media_url.split('/')[:-1]) + '/'
            
            # Find actual segment count
            actual_count = self.find_actual_segment_count(base_url, seg_info, mpd_xml)
            # Verify the count is accurate
            seg_info['segment_count'] = actual_count
            print(f"Will download {seg_info['segment_count']} segments.")

            self.update_status("Starting download...")
            self.update_progress(10)

            os.makedirs('downloads', exist_ok=True)

            init_path = os.path.join('downloads', 'init.mp4')
            self.download_file(base_url + seg_info['init'], init_path)
            output_path = os.path.join('downloads', 'track.mp4')
            
            with open(output_path, 'wb') as out:
                with open(init_path, 'rb') as f:
                    out.write(f.read())
                os.remove(init_path)

                for i in range(seg_info['start_number'], seg_info['start_number'] + seg_info['segment_count']):
                    seg_url = base_url + seg_info['media'].replace('$Number$', str(i))
                    seg_path = os.path.join('downloads', f'segment_{i}.m4s')
                    try:
                        self.download_file(seg_url, seg_path)
                        with open(seg_path, 'rb') as segf:
                            out.write(segf.read())
                        os.remove(seg_path)
                        print(f"Downloaded and appended segment {i}")
                        
                        # Calculate progress: 10% to 70% for downloading segments
                        segments_done = i - seg_info['start_number'] + 1
                        download_progress = 10 + int((segments_done / seg_info['segment_count']) * 60)
                        self.update_progress(download_progress)
                        self.update_status(f"Downloading... {segments_done}/{seg_info['segment_count']} chunks")
                        
                    except Exception as e:
                        print(f"Failed to download segment {i}: {e}")
                        break

            self.update_status("Processing audio file...")
            self.update_progress(75)

            if key_hex:
                creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                subprocess.run([
                    self.ffmpeg_path, '-y', '-decryption_key', key_hex,
                    '-i', output_path, '-c', 'copy', 'master_audio.mp4'
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
            else:
                os.rename(output_path, 'master_audio.mp4')

            shutil.rmtree('downloads', ignore_errors=True)
            print("Done! Output: master_audio.mp4")

        except Exception as e:
            raise Exception(f"BLURL conversion failed: {str(e)}")

    def download_song_thread(self, song, is_queue_download=False):
        """Background thread function for downloading"""
        try:
            if not self.ffmpeg_ready:
                self.update_status("Hang tight, setting up tools...")
                # Wait for FFmpeg to be ready
                while not self.ffmpeg_ready:
                    import time
                    time.sleep(0.5)
                
            if not song['sid']:
                self.show_error("No song ID available")
                if is_queue_download:
                    self.next_song_signal()
                return
            
            self.delete_temporary_files()
            api_url = f"https://cdn.qstv.on.epicgames.com/{song['sid']}"
            print(f"Fetching from API URL: {api_url}")
            
            self.update_status("Getting song info...")
            self.update_progress(0)
            
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            
            for key, value in data.items():
                if isinstance(value, dict) and 'baseUrls' in value:
                    base_urls = value['baseUrls']
                    if base_urls and len(base_urls) > 0:
                        base_url = base_urls[0]
                        url_parts = base_url.rstrip('/').split('/')
                        if len(url_parts) < 4:
                            continue
                            
                        domain = f"{url_parts[0]}//{url_parts[2]}"
                        unique_code = url_parts[3]
                        download_url = f"{domain}/{unique_code}/master.blurl"
                        
                        self.update_status("Downloading song data...")
                        self.update_progress(2)
                        
                        with requests.get(download_url, stream=True) as r:
                            r.raise_for_status()
                            total_size = int(r.headers.get('content-length', 0))
                            downloaded_size = 0
                            chunk_size = 8192
                            
                            with open("master.blurl", "wb") as file:
                                for chunk in r.iter_content(chunk_size=chunk_size):
                                    file.write(chunk)
                                    downloaded_size += len(chunk)
                                    if total_size > 0:
                                        # BLURL download is 2% to 5%
                                        progress = 2 + int((downloaded_size / total_size) * 3)
                                        self.update_progress(progress)
                        
                        # Get segment count first for accurate progress
                        blurl = self.decompress_blurl("master.blurl")
                        media_url = blurl['playlists'][0]['url']
                        r = requests.get(media_url)
                        mpd_xml = r.text
                        seg_info = self.parse_mpd(mpd_xml)
                        base_url = '/'.join(media_url.split('/')[:-1]) + '/'
                        actual_count = self.find_actual_segment_count(base_url, seg_info, mpd_xml)
                        
                        self.convert_blurl_to_mp4("master.blurl", actual_count)
                        
                        self.update_status("Creating audio stems...")
                        self.update_progress(80)
                        self.extract_audio_stems(song['title'], song['artist'])
                        
                        self.update_status("Download completed! 🎉")
                        self.update_progress(100)
                        
                        if is_queue_download:
                            self.next_song_signal()
                        else:
                            self.show_success(f"Successfully downloaded and extracted stems for: {song['title']}")
                            self.download_complete()
                        return
                
            error_msg = "Could not find valid download URL in the response"
            self.show_error(error_msg)
            if is_queue_download:
                self.next_song_signal()
            else:
                self.download_complete()
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Download failed: {str(e)}"
            self.show_error(error_msg)
            if is_queue_download:
                self.next_song_signal()
            else:
                self.download_complete()
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.show_error(error_msg)
            if is_queue_download:
                self.next_song_signal()
            else:
                self.download_complete()

    def download_song(self, song):
        """Start download in background thread for single song"""
        if self.downloading:
            messagebox.showwarning("Download in Progress", "A download is already in progress. Please wait for it to complete.")
            return
        
        if not self.ffmpeg_ready:
            messagebox.showwarning("FFmpeg Not Ready", "Still setting up tools. Please wait a moment and try again.")
            return
        
        self.downloading = True
        download_thread = threading.Thread(target=self.download_song_thread, args=(song, False), daemon=True)
        download_thread.start()

    def open_settings_window(self):
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.geometry("400x300")
        self.settings_window.attributes('-topmost', True)
        self.settings_window.resizable(False, False)
        if os.name == 'nt':
            self.settings_window.attributes('-toolwindow', True)

        notebook = ttk.Notebook(self.settings_window)
        notebook.pack(fill='both', expand=True)

        display_frame = ttk.Frame(notebook, padding=10)
        notebook.add(display_frame, text='Display')

        sorting_frame = ttk.Frame(display_frame)
        sorting_frame.pack(fill='x', pady=5)
        ttk.Label(sorting_frame, text="Sort songs by:").pack(side='left', padx=5)
        sorting_options = ["A-Z by Artist", "A-Z by Song Name", "Last Added"]
        self.sorting_var = tk.StringVar(value=self.sorting_method)
        sorting_dropdown = ttk.Combobox(sorting_frame, textvariable=self.sorting_var, values=sorting_options, state="readonly")
        sorting_dropdown.pack(side='left', padx=5)
        sorting_dropdown.bind("<<ComboboxSelected>>", lambda e: self.update_sorting_method())

        self.sort_order_asc = tk.BooleanVar(value=self.sort_ascending)
        self.sort_order_button = ttk.Button(sorting_frame, text="⬆ Ascending" if self.sort_ascending else "⬇ Descending", command=self.toggle_sort_order)
        self.sort_order_button.pack(side='left', padx=5)

        theme_frame = ttk.Frame(display_frame)
        theme_frame.pack(anchor="w", fill='x', padx=5, pady=5)
        ttk.Label(theme_frame, text="Theme:").pack(side='left', padx=5)
        theme_options = ["Dark Mode", "Light Mode"]
        self.theme_var = tk.StringVar(value="Dark Mode" if self.dark_mode else "Light Mode")
        theme_dropdown = ttk.Combobox(theme_frame, textvariable=self.theme_var, values=theme_options, state="readonly")
        theme_dropdown.pack(side='left', padx=5)
        theme_dropdown.bind("<<ComboboxSelected>>", lambda e: self.toggle_theme())

        system_frame = ttk.Frame(notebook, padding=10)
        notebook.add(system_frame, text='System')

        folder_frame = ttk.Frame(system_frame)
        folder_frame.pack(anchor="w", fill="x", pady=5)
        ttk.Label(folder_frame, text="Save in:").pack(side="left", padx=5)
        self.folder_label = ttk.Label(system_frame, text=self.extract_folder, wraplength=350, anchor="w", justify="left")
        self.folder_label.pack(fill="x", padx=10, pady=2)
        ttk.Button(folder_frame, text="Browse...", command=self.choose_folder).pack(side="left", padx=5)

        auto_open_frame = ttk.Frame(system_frame)
        auto_open_frame.pack(anchor="w", fill="x", padx=10, pady=5)
        ttk.Label(auto_open_frame, text="Automatically open stems folder after extraction").pack(side="left", padx=5)
        self.auto_open_var = tk.BooleanVar(value=self.auto_open_folder)
        auto_open_checkbox = ttk.Checkbutton(auto_open_frame, variable=self.auto_open_var, command=self.toggle_auto_open)
        auto_open_checkbox.pack(side="left", padx=5)

        # File naming frame in System tab
        naming_frame = ttk.Frame(system_frame)
        naming_frame.pack(anchor="w", pady=5, fill="x")
        ttk.Label(naming_frame, text="File Naming:").pack(side="left", padx=5)
        naming_options = ["Only Stem Type", "Song Name - Stem Type", "Artist Name - Song Name - Stem Type"]
        naming_dropdown = ttk.Combobox(naming_frame, textvariable=self.file_naming_var, values=naming_options, state="readonly", width=35)
        naming_dropdown.pack(side="left", padx=5)
        naming_dropdown.bind("<<ComboboxSelected>>", lambda e: self.save_settings())

        audio_frame = ttk.Frame(notebook, padding=10)
        notebook.add(audio_frame, text='Audio')

        format_frame = ttk.Frame(audio_frame)
        format_frame.pack(anchor="w", pady=5, fill="x")
        ttk.Label(format_frame, text="File Saving Format:").pack(side="left", padx=5)
        format_options = ["wav", "flac", "mp3"]
        format_dropdown = ttk.Combobox(format_frame, textvariable=self.file_format_var, values=format_options, state="readonly")
        format_dropdown.pack(side="left", padx=5)
        format_dropdown.bind("<<ComboboxSelected>>", lambda e: self.save_settings())

        extracting_method_frame = ttk.Frame(audio_frame)
        extracting_method_frame.pack(anchor="w", pady=5, fill="x")
        ttk.Label(extracting_method_frame, text="Extracting Method:").pack(side="left", padx=5)
        extracting_options = ["Stereo", "Mono", "Single File"]
        extracting_dropdown = ttk.Combobox(extracting_method_frame, textvariable=self.extracting_method_var, values=extracting_options, state="readonly")
        extracting_dropdown.pack(side="left", padx=5)
        extracting_dropdown.bind("<<ComboboxSelected>>", lambda e: self.save_settings())

        about_frame = ttk.Frame(notebook, padding=10)
        notebook.add(about_frame, text='About & Help')

        if self.cached_logo:
            logo_label = ttk.Label(about_frame, image=self.cached_logo)
            logo_label.pack(pady=(5, 10))
        else:
            ttk.Label(about_frame, text="[Logo failed to load]", foreground="red").pack(pady=(5, 10))

        about_text = "Fortnite Festival Extractor is an unofficial open-source\nprogram to download and extract FF songs into stems."
        about_label = ttk.Label(about_frame, text=about_text, justify="center", anchor="center")
        about_label.pack(pady=(0, 10))

        github_link = ttk.Label(about_frame, text="Visit Fortnite Festival Extractor GitHub page", cursor="hand2", font=("TkDefaultFont", 10, "underline"))
        github_link.pack(pady=(0, 10))
        github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/ilayezra/Festival-Extractor"))

        contact_text = "If you have any issues, contact me at: ilayezra37@gmail.com"
        contact_label = ttk.Label(about_frame, text=contact_text, justify="center", anchor="center")
        contact_label.pack(pady=(0, 5))

        button_frame = ttk.Frame(self.settings_window)
        button_frame.pack(fill='x', side='bottom', pady=5)
        ttk.Button(button_frame, text="OK", command=self.settings_window.destroy).pack(side='right', padx=5)

    def toggle_auto_open(self):
        self.auto_open_folder = self.auto_open_var.get()
        self.save_settings()

    def update_sorting_method(self):
        self.sorting_method = self.sorting_var.get()
        self.save_settings()
        self.search_songs()  # This will re-filter and re-sort

    def toggle_sort_order(self):
        self.sort_ascending = not self.sort_ascending
        self.sort_order_button.config(text="⬆ Ascending" if self.sort_ascending else "⬇ Descending")
        self.save_settings()
        self.song_listbox.selection_clear(0, tk.END)
        # Re-apply current search filter with new sorting
        self.search_songs()  # This will re-filter and re-sort

    def toggle_theme(self):
        self.dark_mode = (self.theme_var.get() == "Dark Mode")
        self.apply_theme()
        self.save_settings()

    def apply_theme(self):
        bg_color = "#1E1E1E" if self.dark_mode else "#FFFFFF"
        fg_color = "#FFFFFF" if self.dark_mode else "#000000"
        listbox_bg = "#2E2E2E" if self.dark_mode else "#FFFFFF"
        listbox_fg = "#FFFFFF" if self.dark_mode else "#000000"
        progress_color = "#3A3A3A" if self.dark_mode else "#DDDDDD"
        button_bg = "#3A3A3A" if self.dark_mode else "#DDDDDD"

        self.root.configure(bg=bg_color)
        self.style.configure("StatusLabel.TLabel", background=bg_color, foreground=fg_color)
        self.status_label.configure(style="StatusLabel.TLabel")
        self.song_listbox.configure(bg=listbox_bg, fg=listbox_fg)
        self.queue_listbox.configure(bg=listbox_bg, fg=listbox_fg)
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=fg_color)
        self.style.configure("TButton", background=button_bg, foreground=fg_color)
        self.style.configure("Horizontal.TProgressbar", background=progress_color, troughcolor=bg_color)

    def choose_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.extract_folder = folder_selected
            self.folder_label.config(text=self.extract_folder)
            self.save_settings()
            messagebox.showinfo("Folder Selected", f"Files will now save to:\n{self.extract_folder}")

    def save_settings(self):
        self.file_format = self.file_format_var.get()
        self.extracting_method = self.extracting_method_var.get()
        self.file_naming = self.file_naming_var.get()
        settings = {
            "extract_folder": self.extract_folder,
            "dark_mode": self.dark_mode,
            "sorting_method": self.sorting_method,
            "sort_ascending": self.sort_ascending,
            "auto_open_folder": self.auto_open_folder,
            "file_format": self.file_format,
            "extracting_method": self.extracting_method,
            "file_naming": self.file_naming
        }
        with open(self.settings_file, "w") as f:
            json.dump(settings, f, indent=4)

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as f:
                settings = json.load(f)
                return {
                    "extract_folder": settings.get("extract_folder", os.getcwd()),
                    "dark_mode": settings.get("dark_mode", True),
                    "sorting_method": settings.get("sorting_method", "Last Added"),
                    "sort_ascending": settings.get("sort_ascending", True),
                    "auto_open_folder": settings.get("auto_open_folder", False),
                    "file_format": settings.get("file_format", "wav"),
                    "extracting_method": settings.get("extracting_method", "Stereo"),
                    "file_naming": settings.get("file_naming", "Only Stem Type")
                }
        return {
            "extract_folder": os.getcwd(),
            "dark_mode": True,
            "sorting_method": "Last Added",
            "sort_ascending": True,
            "auto_open_folder": False,
            "file_format": "wav",
            "extracting_method": "Stereo",
            "file_naming": "Only Stem Type"
        }

    @staticmethod
    def get_resource_path(relative_path):
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, relative_path)
        return relative_path

    def search_songs(self, event=None):
        query = self.search_entry.get().lower()
        
        # Check for easter egg first
        if self.check_easter_egg(query):
            self.search_entry.delete(0, tk.END)  # Clear the search box
            # Reset to show all songs after easter egg
            self.filtered_songs = self.songs.copy()
            self.display_songs(self.filtered_songs)
            return
        
        # Normal search functionality
        if query:
            self.filtered_songs = [song for song in self.songs if query in song['title'].lower() or query in song['artist'].lower()]
        else:
            self.filtered_songs = self.songs.copy()
        self.display_songs(self.filtered_songs)

    def fetch_json_data(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    def extract_songs(self, data):
        songs = []
        if not data:
            return songs
        
        for key, value in data.items():
            if isinstance(value, dict) and 'track' in value:
                track = value['track']
                qi = track.get('qi', '{}')
                try:
                    qi = json.loads(qi) if isinstance(qi, str) else qi
                except json.JSONDecodeError:
                    qi = {}
                sid = qi.get('sid', '')
                songs.append({
                    'title': track.get('tt', 'Unknown Title'),
                    'artist': track.get('an', 'Unknown Artist'),
                    'cover_art_url': track.get('au', ''),
                    'release_year': track.get('ry', 'Unknown Year'),
                    'duration': track.get('dn', 'Unknown Duration'),
                    'bpm': track.get('mt', 'Unknown BPM'),
                    'sid': sid
                })
        return songs

    def fetch_and_extract_songs(self):
        url = "https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/spark-tracks"
        data = self.fetch_json_data(url)
        songs = self.extract_songs(data) if data else []
        print(f"Songs fetched: {len(songs)}")
        return songs

    def display_songs(self, songs):
        sorted_songs = songs.copy()
        
        if self.sorting_method == "A-Z by Artist":
            sorted_songs = sorted(sorted_songs, key=lambda s: s["artist"].lower(), reverse=not self.sort_ascending)
        elif self.sorting_method == "A-Z by Song Name":
            sorted_songs = sorted(sorted_songs, key=lambda s: s["title"].lower(), reverse=not self.sort_ascending)
        elif self.sorting_method == "Last Added":
            sorted_songs = songs.copy()
            if self.sort_ascending != True:
                sorted_songs.reverse()
            
        self.filtered_songs = sorted_songs
        self.song_listbox.delete(0, tk.END)
        for song in sorted_songs:
            self.song_listbox.insert(tk.END, f"{song['artist']} - {song['title']}")
        self.song_listbox.update_idletasks()

    def seconds_to_minutes_seconds(self, seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

    def is_song_in_queue(self, song):
        """Check if song is already in queue"""
        for queued_song in self.song_queue:
            if queued_song['sid'] == song['sid']:
                return True
        return False

    def on_song_select(self, event=None):
        selection = self.song_listbox.curselection()
        if not selection:
            return
        selected_song = self.filtered_songs[selection[0]]
        
        # Check if Queue tab is currently selected
        current_tab = self.notebook.select()
        queue_tab_id = self.notebook.tabs()[1]  # Queue tab is the second tab (index 1)
        
        # If Queue tab is active, switch to Song Info tab
        if current_tab == queue_tab_id:
            self.notebook.select(0)  # Select Song Info tab (index 0)
        
        self.display_song_info(selected_song)

    def display_song_info(self, song):
        """Display song information in the Song Info tab"""
        # Stop any current preview when switching songs
        if hasattr(self, 'preview_system'):
            # Cancel auto-stop timer
            if hasattr(self, 'auto_stop_timer'):
                try:
                    self.auto_stop_timer.cancel()
                except:
                    pass
            self.preview_system.stop()
        
        # Clear existing widgets in song info frame
        for widget in self.song_info_frame.winfo_children():
            widget.destroy()
        
        if song['cover_art_url']:
            try:
                response = requests.get(song['cover_art_url'])
                image = Image.open(BytesIO(response.content))
                image = image.resize((200, 200), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                label = ttk.Label(self.song_info_frame, image=photo)
                label.image = photo
                label.pack(pady=10)
            except:
                ttk.Label(self.song_info_frame, text="No Image Available").pack(pady=10)
        
        duration = song['duration'] if isinstance(song['duration'], int) else int(song['duration']) if song['duration'].isdigit() else 0
        formatted_duration = self.seconds_to_minutes_seconds(duration)
        
        details = [
            f"Title: {song['title']}",
            f"Artist: {song['artist']}",
            f"Release Year: {song['release_year']}",
            f"Duration: {formatted_duration}",
            f"BPM: {song['bpm']}"
        ]
        for detail in details:
            ttk.Label(self.song_info_frame, text=detail).pack(anchor="w", pady=2)
        
        # Check if FFmpeg is ready before showing buttons
        if not self.ffmpeg_ready:
            self.show_ffmpeg_loading_message()
        else:
            # Add to queue button
            if self.is_song_in_queue(song):
                add_button = ttk.Button(self.song_info_frame, text="Already in Queue", state="disabled")
            else:
                add_button = ttk.Button(self.song_info_frame, text="Add to Queue", command=lambda: self.add_to_queue(song))
            add_button.pack(pady=10)
        
        # Only show preview button if FFmpeg is ready
        if self.ffmpeg_ready:
                # Check if this is an Epic Games song
            if self.is_epic_games_song(song['artist']):
                    # Show Epic Games message
                epic_label = ttk.Label(self.song_info_frame, text="Preview not available for Epic Games original tracks", 
                                        font=("Arial", 9), foreground="gray")
                epic_label.pack(pady=(10, 0))
            else:
                    # Single toggle button (centered like Add to Queue)
                self.preview_button = ttk.Button(self.song_info_frame, text="▶ Play Preview", 
                                                    command=lambda: self.toggle_preview(song))
                self.preview_button.pack(pady=(10, 0))

                    # Preview status label (below button, centered)
                self.preview_status = ttk.Label(self.song_info_frame, text="", font=("Arial", 9))
                self.preview_status.pack(pady=(2, 0))

    def update_song_info_display(self):
        """Update the song info display to refresh button state"""
        selection = self.song_listbox.curselection()
        if selection:
            selected_song = self.filtered_songs[selection[0]]
            self.display_song_info(selected_song)

    def show_ffmpeg_loading_message(self):
        """Show loading message when FFmpeg is not ready"""
        loading_frame = ttk.Frame(self.song_info_frame)
        loading_frame.pack(pady=(20, 10))
        
        ttk.Label(loading_frame, text="⏳ Setting up audio tools...", 
                font=("Arial", 11, "bold")).pack()
        ttk.Label(loading_frame, text="Please wait while we download required components.", 
                font=("Arial", 9)).pack()
        ttk.Label(loading_frame, text="This only happens on first run.", 
                font=("Arial", 9), foreground="gray").pack()

    def sanitize_folder_name(self, name):
        return re.sub(r'[<>:"/\\|?*]', '', name)

    def generate_filename(self, stem_name, song_title, artist_name, file_extension):
        """Generate filename based on user's naming preference"""
        naming_method = self.file_naming_var.get()
        
        # Sanitize all components
        safe_stem = self.sanitize_folder_name(stem_name)
        safe_title = self.sanitize_folder_name(song_title)
        safe_artist = self.sanitize_folder_name(artist_name)
        
        if naming_method == "Only Stem Type":
            return f"{safe_stem}.{file_extension}"
        elif naming_method == "Song Name - Stem Type":
            return f"{safe_title} - {safe_stem}.{file_extension}"
        elif naming_method == "Artist Name - Song Name - Stem Type":
            return f"{safe_artist} - {safe_title} - {safe_stem}.{file_extension}"
        else:
            # Fallback to default
            return f"{safe_stem}.{file_extension}"

    def delete_temporary_files(self):
        if os.path.exists("master.blurl"):
            os.remove("master.blurl")
        if os.path.exists("master_audio.mp4"):
            os.remove("master_audio.mp4")

    def extract_audio_stems(self, song_title, artist_name):
        try:
            if not os.path.exists("master_audio.mp4"):
                self.show_error("master_audio.mp4 not found")
                return

            os.makedirs(self.extract_folder, exist_ok=True)
            sanitized_title = self.sanitize_folder_name(song_title)
            stem_folder = os.path.join(self.extract_folder, f"{sanitized_title} - stems")
            os.makedirs(stem_folder, exist_ok=True)

            selected_format = self.file_format_var.get()
            extracting_method = self.extracting_method_var.get()

            extra_options = []
            if selected_format == "mp3":
                extra_options = ["-b:a", "320k"]

            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

            if extracting_method == "Stereo":
                # Use filter_complex for modern FFmpeg versions (7.x+)
                filter_complex = "[0:a]channelsplit=channel_layout=5.1.4[FL][FR][FC][LFE][BL][BR][SL][SR][TFL][TFR];" \
                               "[FL][FR]amerge=inputs=2[drums];" \
                               "[FC][LFE]amerge=inputs=2[bass];" \
                               "[BL][BR]amerge=inputs=2[lead];" \
                               "[SL][SR]amerge=inputs=2[vocals];" \
                               "[TFL][TFR]amerge=inputs=2[other]"
                
                # Generate filenames based on user preference
                drums_filename = self.generate_filename("Drums", song_title, artist_name, selected_format)
                bass_filename = self.generate_filename("Bass", song_title, artist_name, selected_format)
                lead_filename = self.generate_filename("Lead", song_title, artist_name, selected_format)
                vocals_filename = self.generate_filename("Vocals", song_title, artist_name, selected_format)
                other_filename = self.generate_filename("Other", song_title, artist_name, selected_format)
                
                ffmpeg_command = [
                    self.ffmpeg_path, "-y", "-i", "master_audio.mp4",
                    "-filter_complex", filter_complex,
                    "-map", "[drums]", *extra_options, os.path.join(stem_folder, drums_filename),
                    "-map", "[bass]", *extra_options, os.path.join(stem_folder, bass_filename),
                    "-map", "[lead]", *extra_options, os.path.join(stem_folder, lead_filename),
                    "-map", "[vocals]", *extra_options, os.path.join(stem_folder, vocals_filename),
                    "-map", "[other]", *extra_options, os.path.join(stem_folder, other_filename)
                ]
                
            elif extracting_method == "Mono":
                # Extract individual channels for mono
                filter_complex = "[0:a]channelsplit=channel_layout=5.1.4[FL][FR][FC][LFE][BL][BR][SL][SR][TFL][TFR]"
                
                # Generate filenames for mono channels
                drums_left_filename = self.generate_filename("Drums_Left", song_title, artist_name, selected_format)
                drums_right_filename = self.generate_filename("Drums_Right", song_title, artist_name, selected_format)
                bass_left_filename = self.generate_filename("Bass_Left", song_title, artist_name, selected_format)
                bass_right_filename = self.generate_filename("Bass_Right", song_title, artist_name, selected_format)
                lead_left_filename = self.generate_filename("Lead_Left", song_title, artist_name, selected_format)
                lead_right_filename = self.generate_filename("Lead_Right", song_title, artist_name, selected_format)
                vocals_left_filename = self.generate_filename("Vocals_Left", song_title, artist_name, selected_format)
                vocals_right_filename = self.generate_filename("Vocals_Right", song_title, artist_name, selected_format)
                other_left_filename = self.generate_filename("Other_Left", song_title, artist_name, selected_format)
                other_right_filename = self.generate_filename("Other_Right", song_title, artist_name, selected_format)
                
                ffmpeg_command = [
                    self.ffmpeg_path, "-y", "-i", "master_audio.mp4",
                    "-filter_complex", filter_complex,
                    "-map", "[FL]", *extra_options, os.path.join(stem_folder, drums_left_filename),
                    "-map", "[FR]", *extra_options, os.path.join(stem_folder, drums_right_filename),
                    "-map", "[FC]", *extra_options, os.path.join(stem_folder, bass_left_filename),
                    "-map", "[LFE]", *extra_options, os.path.join(stem_folder, bass_right_filename),
                    "-map", "[BL]", *extra_options, os.path.join(stem_folder, lead_left_filename),
                    "-map", "[BR]", *extra_options, os.path.join(stem_folder, lead_right_filename),
                    "-map", "[SL]", *extra_options, os.path.join(stem_folder, vocals_left_filename),
                    "-map", "[SR]", *extra_options, os.path.join(stem_folder, vocals_right_filename),
                    "-map", "[TFL]", *extra_options, os.path.join(stem_folder, other_left_filename),
                    "-map", "[TFR]", *extra_options, os.path.join(stem_folder, other_right_filename)
                ]
                
            elif extracting_method == "Single File":
                # Mix all channels to stereo
                master_filename = self.generate_filename("master", song_title, artist_name, selected_format)
                ffmpeg_command = [
                    self.ffmpeg_path, "-y", "-i", "master_audio.mp4",
                    "-filter_complex", "[0:a]pan=stereo|c0<c0+c2+c4+c6+c8|c1<c1+c3+c5+c7+c9[out]",
                    "-map", "[out]", "-ac", "2", *extra_options, 
                    os.path.join(stem_folder, master_filename)
                ]

            subprocess.run(ffmpeg_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
            print(f"Audio extracted successfully into folder: {stem_folder}")

            self.update_progress(95)
            self.update_status("Cleaning up...")

            os.remove("master_audio.mp4")
            os.remove("master.blurl")
            print("Temporary files deleted.")

            if self.auto_open_folder:
                system = platform.system()
                if system == "Windows":
                    subprocess.Popen(f'explorer "{os.path.normpath(stem_folder)}"')
                elif system == "Darwin":
                    subprocess.Popen(["open", stem_folder])
                else:
                    subprocess.Popen(["xdg-open", stem_folder])

        except subprocess.CalledProcessError as e:
            self.show_error(f"FFmpeg extraction failed: {str(e)}")
        except Exception as e:
            self.show_error(f"Unexpected error during extraction: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = FortniteTracksGUI(root)
    root.mainloop()
