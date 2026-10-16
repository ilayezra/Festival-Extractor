import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import sv_ttk
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
import xml.parsers.expat
from Crypto.Cipher import AES
import threading
import queue
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
import pygame
from urllib.parse import quote, urlsplit, urlunsplit
from concurrent.futures import ThreadPoolExecutor
import struct
import math
import time
import tempfile
import av
import numpy as np
from requests.adapters import HTTPAdapter

STEM_NAMES = ["Drums", "Bass", "Lead", "Vocals", "Other"]
AUDIO_CODECS = {"wav": "pcm_s16le", "flac": "flac", "mp3": "libmp3lame"}


def resource_path(name):
    """Find a file bundled with the program: inside the exe when frozen, else next to the script (or in media/, alpha/)"""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, name)
    base = os.path.dirname(os.path.abspath(__file__))
    for folder in (base, os.path.join(base, 'media'), os.path.join(base, 'alpha')):
        candidate = os.path.join(folder, name)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(base, name)


def settings_path():
    """settings.json lives in the user's app data folder, not next to the program"""
    if os.name == 'nt':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config')
    folder = os.path.join(base, 'Festival Extractor')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, 'settings.json')


# One shared session so connections to the same servers are reused
http = requests.Session()
http.mount('https://', HTTPAdapter(pool_connections=10, pool_maxsize=16))
http.mount('http://', HTTPAdapter(pool_connections=10, pool_maxsize=16))

class SmartPreviewSystem:
    def __init__(self):
        self.is_playing = False
        self.current_audio = None
        self.preview_cache = {}  # (artist, title) -> mp3 bytes

        # Initialize pygame mixer for audio playback
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
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
                response = http.get(url, timeout=10)
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

    def fetch_preview(self, artist, title):
        """Find and download a song's 30-second preview (runs in a background thread)"""
        key = (artist.strip().lower(), title.strip().lower())
        if key not in self.preview_cache:
            preview_url = self.search_preview_ultimate(artist, title)
            if not preview_url:
                return None
            response = http.get(preview_url, timeout=15)
            response.raise_for_status()
            if len(self.preview_cache) >= 20:
                self.preview_cache.pop(next(iter(self.preview_cache)))
            self.preview_cache[key] = response.content
        return self.preview_cache[key]

    def play_preview(self, audio):
        """Play preview mp3 bytes straight from memory"""
        self.stop()
        self.current_audio = BytesIO(audio)
        pygame.mixer.music.load(self.current_audio, 'mp3')
        pygame.mixer.music.play()
        self.is_playing = True

    def stop(self):
        """Stop current playback"""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except pygame.error:
            pass
        self.is_playing = False
        self.current_audio = None

    def is_playing_status(self):
        """Check if currently playing"""
        try:
            return pygame.mixer.music.get_busy() and self.is_playing
        except pygame.error:
            return False

class FortniteTracksGUI:
    def __init__(self, root):
        self.root = root
        self.settings_file = settings_path()
        
        # Add queue for thread communication
        self.download_queue_thread = queue.Queue()
        self.downloading = False
        
        # Download queue: entries are {'song', 'status' (Waiting/Downloading/Done/Failed), 'error'}
        self.song_queue = []
        self.current_entry = None
        self.finished_this_run = []
        
        # Initialize preview system
        self.preview_system = SmartPreviewSystem()
        self.auto_stop_id = None
        self.current_song_info = None

        self.cover_cache = {}  # cover url -> PhotoImage
        self.cover_placeholder = tk.PhotoImage(width=200, height=200)
        self.search_after_id = None

        # Stop audio cleanly when the app closes
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
        self.root.geometry("1000x640")
        self.root.minsize(860, 560)

        try:
            self.root.iconphoto(False, tk.PhotoImage(file=resource_path("icon.png")))
        except Exception:
            pass

        self.style = ttk.Style()
        self.apply_theme()

        # Top bar - search, song count, settings
        top_bar = ttk.Frame(self.root, padding=(16, 14, 16, 10))
        top_bar.pack(fill=tk.X)
        ttk.Button(top_bar, text="⚙  Settings", command=self.open_settings_window).pack(side=tk.RIGHT)
        self.song_count_label = ttk.Label(top_bar, text="Loading songs...", style="Muted.TLabel")
        self.song_count_label.pack(side=tk.RIGHT, padx=14)

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top_bar, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self.schedule_search)
        self.search_entry.bind("<FocusIn>", self.hide_search_placeholder)
        self.search_entry.bind("<FocusOut>", self.show_search_placeholder)
        self.search_placeholder_shown = False
        self.show_search_placeholder()

        # Bottom bar - status and progress, visible from every tab
        status_bar = ttk.Frame(self.root, padding=(16, 10, 16, 14))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = ttk.Label(status_bar, text="Ready - pick a song to download")
        self.status_label.pack(side=tk.LEFT)
        self.percent_label = ttk.Label(status_bar, text="", style="Muted.TLabel", width=5, anchor="e")
        self.percent_label.pack(side=tk.RIGHT)
        self.progress = ttk.Progressbar(status_bar, orient="horizontal", length=260, mode="determinate", maximum=100)
        self.progress.pack(side=tk.RIGHT, padx=10)

        body = ttk.Frame(self.root, padding=(16, 0))
        body.pack(fill=tk.BOTH, expand=True)

        # Right side - Song / Queue tabs
        right_panel = ttk.Frame(body, width=380)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 0))
        right_panel.pack_propagate(False)

        # Left side - song table
        list_frame = ttk.Frame(body)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.song_tree = ttk.Treeview(list_frame, columns=("artist", "title"), show="headings", selectmode="browse")
        self.song_tree.heading("artist", text="Artist", anchor="w")
        self.song_tree.heading("title", text="Title", anchor="w")
        self.song_tree.column("artist", width=200, anchor="w")
        self.song_tree.column("title", width=280, anchor="w")
        song_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.song_tree.yview)
        self.song_tree.configure(yscrollcommand=song_scroll.set)
        song_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.song_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.song_tree.bind("<<TreeviewSelect>>", self.on_song_select)

        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.song_info_frame = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.song_info_frame, text="Song")

        self.queue_frame = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.queue_frame, text="Queue")

        queue_list = ttk.Frame(self.queue_frame)
        queue_list.pack(fill=tk.BOTH, expand=True)
        self.queue_tree = ttk.Treeview(queue_list, columns=("num", "song", "status"), show="headings", selectmode="extended")
        for column, text, width, stretch in (("num", "#", 34, False), ("song", "Song", 200, True), ("status", "Status", 80, False)):
            self.queue_tree.heading(column, text=text, anchor="w")
            self.queue_tree.column(column, width=width, anchor="w", stretch=stretch)
        queue_scroll = ttk.Scrollbar(queue_list, orient=tk.VERTICAL, command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=queue_scroll.set)
        queue_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.queue_tree.bind("<Double-1>", self.on_queue_double_click)

        ttk.Button(self.queue_frame, text="⬇  Download All", style="Accent.TButton",
                   command=self.download_all_queue).pack(fill=tk.X, pady=(10, 0))
        queue_buttons = ttk.Frame(self.queue_frame)
        queue_buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(queue_buttons, text="Remove", command=self.remove_selected_from_queue).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(queue_buttons, text="Clear", command=self.clear_queue).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        self.show_empty_song_info()

        # Load the song list in the background so the window opens right away
        self.songs = []
        self.filtered_songs = []
        threading.Thread(target=self.load_songs_worker, daemon=True).start()

        # Start checking the download queue
        self.check_download_queue()

        try:
            image = Image.open(resource_path("logo.png"))
            image = image.resize((200, 70), Image.LANCZOS)
            self.cached_logo = ImageTk.PhotoImage(image)
        except Exception:
            self.cached_logo = None

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

    def on_closing(self):
        """Handle app closing"""
        self.preview_system.stop()
        self.root.destroy()

    def play_song_preview(self, song):
        """Find, download and play the 30-second preview without blocking the UI"""
        self.preview_button.config(state="disabled")
        self.preview_status.config(text="Searching for preview...")

        def worker():
            try:
                audio = self.preview_system.fetch_preview(song['artist'], song['title'])
            except Exception as e:
                print(f"Preview error: {e}")
                audio = None
            self.run_on_ui(lambda: self.start_preview_playback(song, audio))

        threading.Thread(target=worker, daemon=True).start()

    def start_preview_playback(self, song, audio):
        """Start playing the preview"""
        # The user moved on to another song while this one was loading
        if song is not self.current_song_info:
            return
        if not audio:
            self.preview_not_found()
            return

        try:
            self.preview_system.play_preview(audio)
        except Exception as e:
            print(f"Playback error: {e}")
            self.preview_status.config(text="Playback failed")
            self.preview_button.config(text="▶  Preview", state="normal")
            return

        self.preview_status.config(text="Playing 30s preview...")
        self.preview_button.config(text="⏹  Stop", state="normal")

        # Auto-stop after 30 seconds
        self.cancel_auto_stop()
        self.auto_stop_id = self.root.after(30000, self.stop_preview)

    def cancel_auto_stop(self):
        if self.auto_stop_id:
            self.root.after_cancel(self.auto_stop_id)
            self.auto_stop_id = None

    def stop_preview(self):
        """Stop preview playback"""
        self.cancel_auto_stop()
        self.preview_system.stop()
        try:
            self.preview_status.config(text="")
            self.preview_button.config(text="▶  Preview", state="normal")
        except (AttributeError, tk.TclError):
            pass

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
        self.preview_status.config(text="No preview available")
        self.preview_button.config(text="▶  Preview", state="normal")

    def check_download_queue(self):
        """Handle messages from worker threads (runs on the Tk thread)"""
        try:
            while True:
                message = self.download_queue_thread.get_nowait()
                if message['type'] == 'progress':
                    self.set_progress(message['value'])
                elif message['type'] == 'status':
                    self.set_status(message['text'])
                elif message['type'] == 'error':
                    messagebox.showerror("Error", message['text'])
                elif message['type'] == 'call':
                    try:
                        message['func']()
                    except Exception as e:
                        print(f"UI update failed: {e}")
        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self.check_download_queue)

    def run_on_ui(self, func):
        """Run func on the Tk thread (Tk widgets must not be touched from worker threads)"""
        self.download_queue_thread.put({'type': 'call', 'func': func})

    def update_progress(self, value):
        """Thread-safe progress update"""
        self.download_queue_thread.put({'type': 'progress', 'value': value})

    def update_status(self, text):
        """Thread-safe status update"""
        self.download_queue_thread.put({'type': 'status', 'text': text})

    def show_error(self, text):
        """Thread-safe error display"""
        self.download_queue_thread.put({'type': 'error', 'text': text})

    def set_progress(self, value):
        self.progress["value"] = value
        self.percent_label.config(text=f"{int(value)}%" if value else "")
        if self.current_entry in self.song_queue:
            row = str(self.song_queue.index(self.current_entry))
            if self.queue_tree.exists(row):
                self.queue_tree.set(row, "status", self.queue_status_text(self.current_entry))

    def set_status(self, text):
        if self.current_entry:
            text = f"{self.current_entry['song']['title']}  ·  {text}"
        self.status_label.config(text=text)

    def find_queue_entry(self, song):
        return next((entry for entry in self.song_queue if entry['song']['sid'] == song['sid']), None)

    def is_song_in_queue(self, song):
        """Check if song is already in queue"""
        return self.find_queue_entry(song) is not None

    def queue_status_text(self, entry):
        if entry['status'] == 'Downloading':
            return f"{int(self.progress['value'])}%"
        return {'Done': "✓ Done", 'Failed': "✗ Failed"}.get(entry['status'], entry['status'])

    def refresh_queue_view(self):
        """Rebuild the queue table and the tab title"""
        self.queue_tree.delete(*self.queue_tree.get_children())
        for i, entry in enumerate(self.song_queue):
            song = entry['song']
            self.queue_tree.insert('', 'end', iid=str(i),
                                   values=(i + 1, f"{song['artist']} - {song['title']}", self.queue_status_text(entry)))
        pending = sum(1 for entry in self.song_queue if entry['status'] in ('Waiting', 'Downloading'))
        self.notebook.tab(self.queue_frame, text=f"Queue ({pending})" if pending else "Queue")

    def add_to_queue(self, song):
        """Add a song to the queue, or mark a finished/failed one to download again"""
        entry = self.find_queue_entry(song)
        if entry is None:
            self.song_queue.append({'song': song, 'status': 'Waiting', 'error': ''})
        elif entry['status'] in ('Done', 'Failed'):
            entry['status'], entry['error'] = 'Waiting', ''
        self.refresh_queue_view()
        self.update_song_info_display()

    def download_now(self, song):
        """Queue the song and start downloading right away if nothing is running"""
        self.add_to_queue(song)
        self.start_queue()

    def check_easter_egg(self, query):
        """Check for easter egg and handle it"""
        if query == "letmedownloadallthesongs":
            result = messagebox.askyesno("Easter Egg Found!",
                                    "Are you sure you want to add all of the songs into your queue list?")
            if result:
                # Add all songs to queue (not just filtered ones)
                added_count = 0
                for song in self.songs:
                    if not self.is_song_in_queue(song):
                        self.song_queue.append({'song': song, 'status': 'Waiting', 'error': ''})
                        added_count += 1

                self.refresh_queue_view()
                self.update_song_info_display()
                messagebox.showinfo("Songs Added", f"Added {added_count} songs to the queue!")
            return True
        return False

    def remove_selected_from_queue(self):
        """Remove the selected songs from the queue (except the one downloading)"""
        rows = sorted((int(row) for row in self.queue_tree.selection()), reverse=True)
        for row in rows:
            if self.song_queue[row] is not self.current_entry:
                del self.song_queue[row]
        if rows:
            self.refresh_queue_view()
            self.update_song_info_display()

    def clear_queue(self):
        """Clear all songs from queue (except the one downloading)"""
        if any(entry is not self.current_entry for entry in self.song_queue):
            if messagebox.askyesno("Clear Queue", "Remove all songs from the queue?"):
                self.song_queue = [entry for entry in self.song_queue if entry is self.current_entry]
                self.refresh_queue_view()
                self.update_song_info_display()

    def on_queue_double_click(self, event):
        """Show the double-clicked queue song in the Song tab"""
        row = self.queue_tree.identify_row(event.y)
        if row:
            self.notebook.select(self.song_info_frame)
            self.display_song_info(self.song_queue[int(row)]['song'])

    def download_all_queue(self):
        """Download every waiting song in the queue (failed ones are retried)"""
        if not self.song_queue:
            messagebox.showwarning("Empty Queue", "No songs in queue to download.")
            return

        for entry in self.song_queue:
            if entry['status'] == 'Failed':
                entry['status'], entry['error'] = 'Waiting', ''
        if not any(entry['status'] in ('Waiting', 'Downloading') for entry in self.song_queue):
            self.set_status("Everything in the queue is already downloaded")
            return
        self.start_queue()

    def start_queue(self):
        if self.downloading:
            self.refresh_queue_view()
            return
        self.downloading = True
        self.finished_this_run = []
        self.download_next_in_queue()

    def download_next_in_queue(self):
        """Start the next waiting song, or wrap up when none are left"""
        entry = next((entry for entry in self.song_queue if entry['status'] == 'Waiting'), None)
        if entry is None:
            self.queue_download_complete()
            return

        entry['status'] = 'Downloading'
        self.current_entry = entry
        self.set_progress(0)
        self.refresh_queue_view()
        self.update_song_info_display()
        threading.Thread(target=self.download_song_thread, args=(entry,), daemon=True).start()

    def song_download_finished(self, entry, error):
        entry['status'] = 'Failed' if error else 'Done'
        entry['error'] = error or ''
        self.finished_this_run.append(entry)
        self.current_entry = None
        self.download_next_in_queue()

    def queue_download_complete(self):
        """Handle completion of the queue"""
        self.downloading = False
        self.current_entry = None
        self.refresh_queue_view()
        self.update_song_info_display()

        done = [entry for entry in self.finished_this_run if entry['status'] == 'Done']
        failed = [entry for entry in self.finished_this_run if entry['status'] == 'Failed']
        self.finished_this_run = []

        if failed:
            self.set_progress(0)
            self.set_status(f"Finished - {len(done)} extracted, {len(failed)} failed")
            details = "\n".join(f"• {entry['song']['title']}: {entry['error']}" for entry in failed[:10])
            if len(failed) > 10:
                details += f"\n...and {len(failed) - 10} more"
            messagebox.showerror("Some downloads failed", f"{len(done)} extracted, {len(failed)} failed:\n\n{details}")
        else:
            self.set_progress(100)
            self.set_status(f"Done! {len(done)} song{'s' if len(done) != 1 else ''} extracted to {self.extract_folder}")

    def parse_blurl(self, data):
        """A .blurl is 8 header bytes followed by zlib-compressed JSON"""
        return json.loads(zlib.decompress(data[8:]))

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

    def get_keys_path(self):
        """keys.bin is bundled in the program; one placed next to the exe overrides it (for updated keys)"""
        if getattr(sys, 'frozen', False):
            override = os.path.join(os.path.dirname(sys.executable), 'keys.bin')
            if os.path.exists(override):
                return override
        keys_path = resource_path('keys.bin')
        if not os.path.exists(keys_path):
            raise Exception("keys.bin is missing from the program")
        return keys_path

    def http_get(self, url, byte_range=None, retries=3):
        """GET a url (optionally only a byte range of it) with a timeout and retries"""
        headers = {'Range': f"bytes={byte_range[0]}-{byte_range[1]}"} if byte_range else None
        for attempt in range(1, retries + 1):
            try:
                r = http.get(url, headers=headers, timeout=30)
                r.raise_for_status()
                if byte_range and r.status_code == 200:
                    # Server ignored the Range header and sent the whole file
                    return r.content[byte_range[0]:byte_range[1] + 1]
                return r.content
            except requests.exceptions.RequestException as e:
                not_found = getattr(e.response, 'status_code', None) == 404
                if not_found or attempt == retries:
                    raise
                time.sleep(2 * attempt)

    def remove_duplicate_path_segments(self, url):
        """New blurls can repeat a folder in the MPD url (/id/id/master.mpd) - keep only the first one"""
        parts = urlsplit(url)
        seen = set()
        kept = []
        for segment in parts.path.split('/'):
            if segment:
                if segment in seen:
                    continue
                seen.add(segment)
            kept.append(segment)
        return urlunsplit(parts._replace(path='/'.join(kept)))

    def get_base_url(self, url):
        parts = urlsplit(url)
        folder = parts.path.rsplit('/', 1)[0]
        return f"{parts.scheme}://{parts.netloc}{folder}/"

    def parse_iso_duration(self, value):
        """Convert an MPD duration like PT3M25.36S into seconds"""
        match = re.fullmatch(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?)?', value.strip())
        if not match:
            return 0
        days, hours, minutes, seconds = (float(g) if g else 0 for g in match.groups())
        return days * 86400 + hours * 3600 + minutes * 60 + seconds

    def parse_xml_without_namespaces(self, data):
        """Parse XML with namespace handling off (Epic's MPDs declare namespaces ElementTree rejects)"""
        def local(name):
            return name.split(':')[-1]

        builder = ET.TreeBuilder()
        parser = xml.parsers.expat.ParserCreate()
        parser.StartElementHandler = lambda name, attrs: builder.start(local(name), {
            local(k): v for k, v in attrs.items() if k != 'xmlns' and not k.startswith('xmlns:')})
        parser.EndElementHandler = lambda name: builder.end(local(name))
        parser.CharacterDataHandler = builder.data
        parser.Parse(data, True)
        return builder.close()

    def parse_mpd(self, mpd_xml):
        """Pick the audio track from the MPD and work out how its segments are laid out"""
        root = self.parse_xml_without_namespaces(mpd_xml)

        period = root.find('Period')
        adaptations = period.findall('AdaptationSet') if period is not None else []
        if not adaptations:
            raise Exception("No AdaptationSet found in MPD")

        def bandwidth(rep):
            try:
                return int(rep.get('bandwidth', ''))
            except ValueError:
                return -1

        for adaptation in adaptations:
            reps = adaptation.findall('Representation')
            if not reps:
                continue
            # Highest quality representation
            rep = max(reps, key=bandwidth)

            content_type = (adaptation.get('contentType') or '').strip()
            if not content_type:
                mime = (rep.get('mimeType') or adaptation.get('mimeType') or '').lower()
                content_type = 'video' if 'video/' in mime else 'audio'
            if content_type != 'audio':
                continue

            # SegmentTemplate can sit on the Representation or on the AdaptationSet
            rep_template = rep.find('SegmentTemplate')
            set_template = adaptation.find('SegmentTemplate')

            def template_attr(name):
                for template in (rep_template, set_template):
                    if template is not None and template.get(name):
                        return template.get(name)
                return ''

            rep_id = rep.get('id', '')
            file_name = (rep.findtext('BaseURL') or '').strip()
            segment_base = rep.find('SegmentBase')
            init_element = segment_base.find('Initialization') if segment_base is not None else None
            start_number = template_attr('startNumber')

            return {
                'init': template_attr('initialization').replace('$RepresentationID$', rep_id) or file_name,
                'media': template_attr('media').replace('$RepresentationID$', rep_id),
                'start_number': int(start_number) if start_number.isdigit() else 1,
                'segment_duration': template_attr('duration'),
                'timescale': template_attr('timescale'),
                'track_duration': self.parse_iso_duration(root.get('mediaPresentationDuration', '')),
                'file_name': file_name,
                'init_range': init_element.get('range', '') if init_element is not None else '',
                'index_range': segment_base.get('indexRange', '') if segment_base is not None else '',
            }

        raise Exception("No audio track found in MPD")

    def get_segment_count(self, seg_info):
        """Track length / segment length, rounded up"""
        if not seg_info['segment_duration'] or not seg_info['timescale']:
            return 1
        if seg_info['track_duration'] <= 0:
            raise Exception("Track duration is missing from MPD")
        segment_seconds = int(seg_info['segment_duration']) / int(seg_info['timescale'])
        return math.ceil(seg_info['track_duration'] / segment_seconds)

    def segment_name(self, media_template, number):
        # Supports both $Number$ and padded $Number%05d$
        return re.sub(r'\$Number(?:%0(\d+)d)?\$', lambda m: str(number).zfill(int(m.group(1) or 0)), media_template)

    def parse_byte_range(self, value):
        start, end = (int(part) for part in value.strip().split('-'))
        if start < 0 or end < start:
            raise Exception(f"Invalid byte range in MPD: {value}")
        return start, end

    def parse_sidx(self, data):
        """Find the sidx box and return (box offset in data, box size, first offset, segment sizes)"""
        i = 0
        while i + 8 <= len(data):
            box_size, box_type = struct.unpack('>I4s', data[i:i + 8])
            header = 8
            if box_size == 1:
                box_size = struct.unpack('>Q', data[i + 8:i + 16])[0]
                header = 16
            if box_size < header or i + box_size > len(data):
                raise Exception("Invalid box in MPD index range")

            if box_type == b'sidx':
                pos = i + header
                version = data[pos]
                pos += 4 + 8  # version/flags, reference_ID, timescale
                if version == 0:
                    first_offset = struct.unpack('>I', data[pos + 4:pos + 8])[0]
                    pos += 8
                else:
                    first_offset = struct.unpack('>Q', data[pos + 8:pos + 16])[0]
                    pos += 16
                reference_count = struct.unpack('>H', data[pos + 2:pos + 4])[0]
                pos += 4
                sizes = [struct.unpack('>I', data[pos + 12 * n:pos + 12 * n + 4])[0] & 0x7FFFFFFF
                         for n in range(reference_count)]
                return i, box_size, first_offset, sizes

            i += box_size
        raise Exception("sidx box not found in MPD index range")

    def build_download_list(self, base_url, seg_info):
        """Return the init download and the media downloads, each as (url, byte_range)"""
        if seg_info['media']:
            # Numbered segment files
            first = seg_info['start_number']
            count = self.get_segment_count(seg_info)
            segments = [(base_url + self.segment_name(seg_info['media'], n), None) for n in range(first, first + count)]
            return (base_url + seg_info['init'], None), segments

        if seg_info['file_name'] and seg_info['init_range'] and seg_info['index_range']:
            # One file addressed by byte ranges, the segment sizes come from its sidx box
            file_url = base_url + seg_info['file_name']
            index_start, index_end = self.parse_byte_range(seg_info['index_range'])
            box_offset, box_size, first_offset, sizes = self.parse_sidx(self.http_get(file_url, (index_start, index_end)))
            position = index_start + box_offset + box_size + first_offset
            segments = []
            for size in sizes:
                if size <= 0:
                    break
                segments.append((file_url, (position, position + size - 1)))
                position += size
            return (file_url, self.parse_byte_range(seg_info['init_range'])), segments

        if seg_info['init']:
            # Whole track is a single file
            return (base_url + seg_info['init'], None), []

        raise Exception("MPD has no downloadable audio")

    def download_segments(self, segments, numbered, out):
        """Download segments 8 at a time and append them to out in order"""
        total = len(segments)
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(self.http_get, url, byte_range) for url, byte_range in segments]
            try:
                missing_from = None
                for done, future in enumerate(futures, 1):
                    try:
                        data = future.result()
                    except requests.exceptions.RequestException as e:
                        # The MPD length can overshoot, so missing numbered segments are fine at the end only
                        if numbered and done > 1 and getattr(e.response, 'status_code', None) == 404:
                            missing_from = missing_from or done
                            continue
                        raise Exception(f"Failed to download segment {done}/{total}: {e}")
                    if missing_from:
                        raise Exception(f"Segment {missing_from}/{total} is missing")

                    out.write(data)
                    self.update_progress(10 + int(done / total * 60))
                    self.update_status(f"Downloading... {done}/{total} chunks")
            except Exception:
                for future in futures:
                    future.cancel()
                raise

    def download_track(self, blurl, work_dir):
        """Download the song's audio track into work_dir; returns (track path, decryption key hex or None)"""
        try:
            self.update_status("Loading song data...")
            self.update_progress(5)

            playlists = blurl.get('playlists') or []
            if not playlists:
                raise Exception("No playlists found in BLURL")
            media_url = self.remove_duplicate_path_segments(playlists[0]['url'])
            print("Media URL:", media_url)

            key_hex = None
            if blurl.get('ev'):
                nonce, key = self.parse_envelope(blurl['ev'])
                dec_key = self.get_encryption_key(self.get_keys_path(), nonce, key)
                if not dec_key:
                    raise Exception("No matching decryption key found in keys.bin")
                key_hex = dec_key.hex()
                print("Decryption key:", key_hex)

            seg_info = self.parse_mpd(self.http_get(media_url))
            init_download, segments = self.build_download_list(self.get_base_url(media_url), seg_info)
            print(f"Will download {len(segments)} segments.")

            self.update_status("Starting download...")
            self.update_progress(10)

            track_path = os.path.join(work_dir, 'track.mp4')
            with open(track_path, 'wb') as out:
                out.write(self.http_get(*init_download))
                self.download_segments(segments, bool(seg_info['media']), out)
            return track_path, key_hex

        except Exception as e:
            raise Exception(f"BLURL conversion failed: {str(e)}")

    def download_song_thread(self, entry):
        """Background thread: download one queued song and report the result to the UI"""
        error = None
        try:
            self.download_and_extract(entry['song'])
        except requests.exceptions.RequestException as e:
            error = f"Download failed: {str(e)}"
        except Exception as e:
            error = str(e)
        if error:
            print(f"Failed: {entry['song']['title']}: {error}")
        self.run_on_ui(lambda: self.song_download_finished(entry, error))

    def download_and_extract(self, song):
        """Download a song and extract its stems (raises on failure)"""
        if not song['sid']:
            raise Exception("No song ID available")

        api_url = f"https://cdn.qstv.on.epicgames.com/{song['sid']}"
        print(f"Fetching from API URL: {api_url}")

        self.update_status("Getting song info...")
        self.update_progress(0)

        response = http.get(api_url, timeout=15)
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

                    blurl_data = self.http_get(download_url)
                    self.update_progress(5)

                    # Temporary files go to the system temp folder and are removed afterwards
                    with tempfile.TemporaryDirectory(prefix="festival_extractor_") as work_dir:
                        track_path, key_hex = self.download_track(self.parse_blurl(blurl_data), work_dir)

                        self.update_status("Creating audio stems...")
                        self.update_progress(75)
                        self.extract_audio_stems(track_path, key_hex, song['title'], song['artist'])

                    self.update_status("Done!")
                    self.update_progress(100)
                    return

        raise Exception("Could not find valid download URL in the response")

    def open_settings_window(self):
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        window = self.settings_window = tk.Toplevel(self.root)
        window.title("Settings")
        window.transient(self.root)
        window.resizable(False, False)

        notebook = ttk.Notebook(window)
        notebook.pack(fill='both', expand=True, padx=12, pady=(12, 0))

        def page(title):
            frame = ttk.Frame(notebook, padding=16)
            frame.columnconfigure(1, weight=1)
            notebook.add(frame, text=title)
            return frame

        def field_label(frame, row, text):
            ttk.Label(frame, text=text).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=6)

        def dropdown(frame, row, variable, values, command, columnspan=1):
            box = ttk.Combobox(frame, textvariable=variable, values=values, state="readonly", width=24)
            box.grid(row=row, column=1, columnspan=columnspan, sticky='ew', pady=6)
            box.bind("<<ComboboxSelected>>", lambda e: command())
            return box

        # Display
        display = page('Display')
        field_label(display, 0, "Sort songs by")
        self.sorting_var = tk.StringVar(value=self.sorting_method)
        dropdown(display, 0, self.sorting_var, ["A-Z by Artist", "A-Z by Song Name", "Last Added"], self.update_sorting_method)
        self.sort_order_button = ttk.Button(display, text="⬆ Ascending" if self.sort_ascending else "⬇ Descending",
                                            width=13, command=self.toggle_sort_order)
        self.sort_order_button.grid(row=0, column=2, padx=(8, 0), pady=6)

        field_label(display, 1, "Theme")
        self.theme_var = tk.StringVar(value="Dark Mode" if self.dark_mode else "Light Mode")
        dropdown(display, 1, self.theme_var, ["Dark Mode", "Light Mode"], self.toggle_theme)

        # Files
        files = page('Files')
        field_label(files, 0, "Save stems in")
        self.folder_var = tk.StringVar(value=self.extract_folder)
        ttk.Entry(files, textvariable=self.folder_var, state="readonly", width=30).grid(row=0, column=1, sticky='ew', pady=6)
        ttk.Button(files, text="Browse...", command=self.choose_folder).grid(row=0, column=2, padx=(8, 0), pady=6)

        field_label(files, 1, "File naming")
        dropdown(files, 1, self.file_naming_var,
                 ["Only Stem Type", "Song Name - Stem Type", "Artist Name - Song Name - Stem Type"], self.save_settings, columnspan=2)

        self.auto_open_var = tk.BooleanVar(value=self.auto_open_folder)
        ttk.Checkbutton(files, text="Open the stems folder after extraction", variable=self.auto_open_var,
                        style="Switch.TCheckbutton", command=self.toggle_auto_open).grid(row=2, column=0, columnspan=3, sticky='w', pady=(12, 4))

        # Audio
        audio = page('Audio')
        field_label(audio, 0, "File format")
        dropdown(audio, 0, self.file_format_var, ["wav", "flac", "mp3"], self.save_settings)

        field_label(audio, 1, "Extracting method")
        method_help = ttk.Label(audio, style="Muted.TLabel", wraplength=380, justify="left")
        method_help.grid(row=2, column=0, columnspan=2, sticky='w', pady=(8, 0))

        def method_changed():
            self.save_settings()
            method_help.config(text={
                "Stereo": "5 files - one stereo file per part (Drums, Bass, Lead, Vocals, Other).",
                "Mono": "10 files - the left and right channel of every part separately.",
                "Single File": "1 file - the whole song mixed down to stereo.",
            }.get(self.extracting_method_var.get(), ""))

        dropdown(audio, 1, self.extracting_method_var, ["Stereo", "Mono", "Single File"], method_changed)
        method_changed()

        # About
        about = page('About & Help')
        about.columnconfigure(0, weight=1)
        if self.cached_logo:
            ttk.Label(about, image=self.cached_logo).grid(row=0, column=0, pady=(0, 10))
        ttk.Label(about, text="Fortnite Festival Extractor is an unofficial open-source\nprogram to download and extract FF songs into stems.",
                  justify="center").grid(row=1, column=0, pady=(0, 10))
        github_link = ttk.Label(about, text="Visit the GitHub page", style="Link.TLabel", cursor="hand2")
        github_link.grid(row=2, column=0, pady=(0, 10))
        github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/ilayezra/Festival-Extractor"))
        ttk.Label(about, text="Having issues? Contact me at ilayezra37@gmail.com", style="Muted.TLabel").grid(row=3, column=0)

        ttk.Button(window, text="Close", style="Accent.TButton", width=10, command=window.destroy).pack(side='right', padx=12, pady=12)

        # Center over the main window
        window.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - window.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - window.winfo_height()) // 3
        window.geometry(f"+{max(x, 0)}+{max(y, 0)}")

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
        # Re-apply current search filter with new sorting
        self.search_songs()

    def toggle_theme(self):
        self.dark_mode = (self.theme_var.get() == "Dark Mode")
        self.apply_theme()
        self.save_settings()

    def apply_theme(self):
        """Switch the Sun Valley theme and re-create our styles (ttk styles are per theme)"""
        sv_ttk.set_theme("dark" if self.dark_mode else "light")

        # sv-ttk calls tk_setPalette, which hard-codes a foreground on ttk widgets and hides
        # style colors (muted text, placeholder). Keep new widgets clear of it and reset existing ones.
        for widget_class in ("TLabel", "TEntry", "TButton", "TCheckbutton"):
            self.root.option_add(f"*{widget_class}.foreground", "", "interactive")
        self.root.after_idle(self.reset_widget_colors)

        muted = "#a0a0a0" if self.dark_mode else "#5f5f5f"
        link = "#57c8ff" if self.dark_mode else "#005fb8"
        if not hasattr(self, "link_font"):
            self.link_font = tkfont.nametofont("SunValleyBodyFont").copy()
            self.link_font.configure(underline=True)
        self.style.configure("Muted.TLabel", foreground=muted)
        self.style.configure("Placeholder.TEntry", foreground=muted)
        self.style.configure("Link.TLabel", foreground=link, font=self.link_font)
        self.style.configure("Title.TLabel", font="SunValleySubtitleFont")
        self.style.configure("Treeview", rowheight=30)

    def reset_widget_colors(self, widget=None):
        for child in (widget or self.root).winfo_children():
            if child.winfo_class().startswith("T"):
                try:
                    child.configure(foreground="")
                except tk.TclError:
                    pass
            self.reset_widget_colors(child)

    def choose_folder(self):
        folder_selected = filedialog.askdirectory(parent=self.settings_window, initialdir=self.extract_folder)
        if folder_selected:
            self.extract_folder = folder_selected
            self.folder_var.set(self.extract_folder)
            self.save_settings()

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
        settings_file = self.settings_file
        if not os.path.exists(settings_file) and os.path.exists("settings.json"):
            settings_file = "settings.json"  # settings from older versions, saved next to the program
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
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

    def schedule_search(self, event=None):
        """Filter once typing pauses instead of on every key"""
        if self.search_after_id:
            self.root.after_cancel(self.search_after_id)
        self.search_after_id = self.root.after(150, self.search_songs)

    def show_search_placeholder(self, event=None):
        if not self.search_var.get():
            self.search_placeholder_shown = True
            self.search_entry.configure(style="Placeholder.TEntry")
            self.search_var.set("Search songs or artists...")

    def hide_search_placeholder(self, event=None):
        if self.search_placeholder_shown:
            self.search_placeholder_shown = False
            self.search_entry.configure(style="TEntry")
            self.search_var.set("")

    def get_search_query(self):
        return "" if self.search_placeholder_shown else self.search_var.get().strip().lower()

    def search_songs(self, event=None):
        self.search_after_id = None
        query = self.get_search_query()

        # Check for easter egg first
        if self.check_easter_egg(query):
            self.search_var.set("")  # Clear the search box
            query = ""

        if query:
            self.filtered_songs = [song for song in self.songs if query in song['title'].lower() or query in song['artist'].lower()]
        else:
            self.filtered_songs = self.songs.copy()
        self.display_songs(self.filtered_songs)

    def fetch_json_data(self, url):
        try:
            response = http.get(url, timeout=15)
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

    def load_songs_worker(self):
        songs = self.fetch_and_extract_songs()
        self.run_on_ui(lambda: self.songs_loaded(songs))

    def songs_loaded(self, songs):
        self.songs = songs
        if songs:
            self.search_songs()
        else:
            self.song_count_label.config(text="Could not load songs - check your internet connection")

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
        self.song_tree.delete(*self.song_tree.get_children())
        for i, song in enumerate(sorted_songs):
            self.song_tree.insert('', 'end', iid=str(i), values=(song['artist'], song['title']))

        total = len(self.songs)
        shown = len(sorted_songs)
        self.song_count_label.config(text=f"{total:,} songs" if shown == total else f"{shown:,} of {total:,} songs")

    def seconds_to_minutes_seconds(self, seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

    def on_song_select(self, event=None):
        selection = self.song_tree.selection()
        if not selection or int(selection[0]) >= len(self.filtered_songs):
            return
        selected_song = self.filtered_songs[int(selection[0])]

        # Bring the Song tab forward if the Queue tab is showing
        self.notebook.select(self.song_info_frame)
        if selected_song is not self.current_song_info:
            self.display_song_info(selected_song)

    def show_empty_song_info(self):
        for widget in self.song_info_frame.winfo_children():
            widget.destroy()
        ttk.Label(self.song_info_frame, text="Pick a song from the list\nto see its details",
                  style="Muted.TLabel", justify="center").pack(expand=True)

    def song_meta_line(self, song):
        """'2013 · 4:08 · 116 BPM', skipping anything unknown"""
        parts = []
        if str(song['release_year']).isdigit():
            parts.append(str(song['release_year']))
        duration = song['duration'] if isinstance(song['duration'], int) else int(song['duration']) if str(song['duration']).isdigit() else 0
        if duration:
            parts.append(self.seconds_to_minutes_seconds(duration))
        if str(song['bpm']).isdigit():
            parts.append(f"{song['bpm']} BPM")
        return "  ·  ".join(parts)

    def display_song_info(self, song):
        """Display song information in the Song tab"""
        # Stop any current preview when switching songs (a refresh of the same song keeps it playing)
        same_song = song is self.current_song_info
        if not same_song:
            self.cancel_auto_stop()
            self.preview_system.stop()
        self.current_song_info = song

        # Clear existing widgets in song info frame
        for widget in self.song_info_frame.winfo_children():
            widget.destroy()

        if song['cover_art_url']:
            cover_label = ttk.Label(self.song_info_frame)
            cover_label.pack(pady=(4, 12))
            self.load_cover_art(song['cover_art_url'], cover_label)

        ttk.Label(self.song_info_frame, text=song['title'], style="Title.TLabel", wraplength=330, justify="center").pack()
        ttk.Label(self.song_info_frame, text=song['artist'], style="Muted.TLabel", wraplength=330, justify="center").pack()
        ttk.Label(self.song_info_frame, text=self.song_meta_line(song), style="Muted.TLabel").pack(pady=(4, 14))

        entry = self.find_queue_entry(song)
        status = entry['status'] if entry else None

        if status == 'Downloading':
            download_text = "Downloading..."
        elif status == 'Waiting' and self.downloading:
            download_text = "Waiting in queue..."
        else:
            download_text = {'Done': "⬇  Download Again", 'Failed': "⬇  Retry"}.get(status, "⬇  Download")
        download_button = ttk.Button(self.song_info_frame, text=download_text, style="Accent.TButton",
                                     command=lambda: self.download_now(song))
        download_button.pack(fill=tk.X, padx=10)
        if status == 'Downloading' or (status == 'Waiting' and self.downloading):
            download_button.state(['disabled'])

        buttons = ttk.Frame(self.song_info_frame)
        buttons.pack(fill=tk.X, padx=10, pady=(8, 0))
        in_queue = status in ('Waiting', 'Downloading')
        add_button = ttk.Button(buttons, text="✓  In Queue" if in_queue else "+  Add to Queue",
                                command=lambda: self.add_to_queue(song))
        if in_queue:
            add_button.state(['disabled'])

        # Check if this is an Epic Games song
        if self.is_epic_games_song(song['artist']):
            add_button.pack(fill=tk.X)
            ttk.Label(self.song_info_frame, text="Preview not available for Epic Games original tracks",
                      style="Muted.TLabel", wraplength=330, justify="center").pack(pady=(10, 0))
        else:
            add_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            playing = same_song and self.preview_system.is_playing_status()

            self.preview_button = ttk.Button(buttons, text="⏹  Stop" if playing else "▶  Preview",
                                             command=lambda: self.toggle_preview(song))
            self.preview_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

            # Preview status label (below the buttons)
            self.preview_status = ttk.Label(self.song_info_frame, text="Playing 30s preview..." if playing else "",
                                            style="Muted.TLabel")
            self.preview_status.pack(pady=(8, 0))

    def load_cover_art(self, url, label):
        """Show cover art from the cache, or download it in the background"""
        if url in self.cover_cache:
            label.image = self.cover_cache[url]
            label.config(image=label.image)
            return
        label.config(image=self.cover_placeholder)

        def worker():
            try:
                image = Image.open(BytesIO(http.get(url, timeout=10).content))
                image = image.resize((200, 200), Image.LANCZOS)
            except Exception:
                image = None
            self.run_on_ui(lambda: self.show_cover_art(url, image, label))

        threading.Thread(target=worker, daemon=True).start()

    def show_cover_art(self, url, image, label):
        if image is not None:
            if len(self.cover_cache) >= 100:
                self.cover_cache.pop(next(iter(self.cover_cache)))
            self.cover_cache[url] = ImageTk.PhotoImage(image)
        # The label is gone if the user already picked another song
        if not label.winfo_exists():
            return
        if image is None:
            label.config(image='', text="No Image Available")
        else:
            # Keep a reference on the label so a cache eviction can't blank it
            label.image = self.cover_cache[url]
            label.config(image=label.image)

    def update_song_info_display(self):
        """Refresh the Song tab (button states follow the queue)"""
        if self.current_song_info is not None:
            self.display_song_info(self.current_song_info)

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

    def stem_plan(self):
        """[(file name, channels to take)] for the chosen method; None means the stereo mix of everything"""
        method = self.extracting_method_var.get()
        if method == "Mono":
            return [(f"{name}_{side}", [2 * i + j]) for i, name in enumerate(STEM_NAMES)
                    for j, side in enumerate(("Left", "Right"))]
        if method == "Single File":
            return [("master", None)]
        return [(name, [2 * i, 2 * i + 1]) for i, name in enumerate(STEM_NAMES)]

    def extract_audio_stems(self, track_path, key_hex, song_title, artist_name):
        """Decrypt and decode the 10-channel track and write the stems, chunk by chunk to keep memory low"""
        os.makedirs(self.extract_folder, exist_ok=True)
        sanitized_title = self.sanitize_folder_name(song_title)
        stem_folder = os.path.join(self.extract_folder, f"{sanitized_title} - stems")
        os.makedirs(stem_folder, exist_ok=True)

        selected_format = self.file_format_var.get()
        plan = self.stem_plan()
        outputs = []

        try:
            with av.open(track_path, options={'decryption_key': key_hex} if key_hex else {}) as source:
                stream = source.streams.audio[0]
                channels = stream.codec_context.channels
                rate = stream.codec_context.sample_rate
                if channels < 10:
                    raise Exception(f"Expected 10 audio channels, the track has {channels}")
                duration = float(source.duration / av.time_base) if source.duration else 0

                for name, picks in plan:
                    filename = self.generate_filename(name, song_title, artist_name, selected_format)
                    container = av.open(os.path.join(stem_folder, filename), 'w')
                    out_stream = container.add_stream(AUDIO_CODECS[selected_format], rate=rate,
                                                      layout='mono' if picks and len(picks) == 1 else 'stereo')
                    if selected_format == "mp3":
                        out_stream.bit_rate = 320000
                    outputs.append((container, out_stream, picks))

                # Decoders give planar audio, which PyAV can't turn into arrays above 8 channels - use interleaved
                resampler = None
                pending, pending_samples, written = [], 0, 0

                def write_pending():
                    nonlocal pending, pending_samples, written
                    if not pending:
                        return
                    samples = np.concatenate(pending)
                    pending, pending_samples = [], 0
                    for container, out_stream, picks in outputs:
                        if picks is None:
                            # Even channels are the left sides, odd channels the right sides
                            data = np.stack([samples[:, 0::2].mean(axis=1), samples[:, 1::2].mean(axis=1)], axis=1)
                        else:
                            data = samples[:, picks]
                        frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(data, dtype=np.float32).reshape(1, -1),
                                                           format='flt', layout='mono' if data.shape[1] == 1 else 'stereo')
                        frame.sample_rate = rate
                        frame.pts = written
                        for packet in out_stream.encode(frame):
                            container.mux(packet)
                    written += len(samples)

                for frame in source.decode(stream):
                    if resampler is None:
                        resampler = av.AudioResampler(format='flt', layout=frame.layout, rate=frame.rate)
                    for packed in resampler.resample(frame):
                        pending.append(packed.to_ndarray().reshape(-1, channels))
                        pending_samples += packed.samples
                    if pending_samples >= rate:
                        write_pending()
                        if duration:
                            self.update_progress(75 + int(min(written / rate / duration, 1) * 20))
                write_pending()

                for container, out_stream, picks in outputs:
                    for packet in out_stream.encode(None):
                        container.mux(packet)
        except av.error.InvalidDataError as e:
            raise Exception(f"Could not decrypt or decode the audio: {e}")
        finally:
            for container, out_stream, picks in outputs:
                container.close()

        print(f"Audio extracted successfully into folder: {stem_folder}")
        self.update_progress(95)

        if self.auto_open_folder:
            if os.name == 'nt':
                os.startfile(stem_folder)
            elif sys.platform == 'darwin':
                subprocess.Popen(["open", stem_folder])
            else:
                subprocess.Popen(["xdg-open", stem_folder])


if __name__ == "__main__":
    root = tk.Tk()
    app = FortniteTracksGUI(root)
    root.mainloop()
