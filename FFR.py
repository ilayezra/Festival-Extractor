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
import io
import webbrowser
from urllib.request import urlopen

class FortniteTracksGUI:
    def __init__(self, root):
        self.root = root
        self.settings_file = "settings.json"

        # Load settings correctly
        settings = self.load_settings()
        self.extract_folder = settings.get("extract_folder", os.getcwd())
        self.dark_mode = settings.get("dark_mode", True)  # Load theme state
        self.sorting_method = settings.get("sorting_method", "Last Added")
        self.sort_ascending = settings.get("sort_ascending", True)
        self.auto_open_folder = settings.get("auto_open_folder", False)
        self.file_format = settings.get("file_format", "wav")
        self.file_format_var = tk.StringVar(value=self.file_format)  # Ensure it's initialized
        self.extracting_method = settings.get("extracting_method", "Stereo")
        self.extracting_method_var = tk.StringVar(value=self.extracting_method)  # Ensure it's initialized

        self.root.title("Fortnite Festival Extractor")
        self.root.geometry("900x600")
        if getattr(sys, 'frozen', False):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(application_path, "icon.png")
        self.root.iconphoto(False, tk.PhotoImage(file=icon_path))

        # Initialize UI theme
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Main layout
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Search Section
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=5)
        ttk.Label(search_frame, text="Search Song:").pack(side=tk.LEFT, padx=5)
        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self.search_songs)

        # Song List with Scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=15)  # Increase padding for better spacing
        self.song_listbox = tk.Listbox(list_frame, width=60, height=25, bg="#2E2E2E", fg="#FFFFFF", font=("Arial", 12))
        self.song_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.song_listbox.bind("<<ListboxSelect>>", self.on_song_select)

        scrollbar = Scrollbar(list_frame, orient=tk.VERTICAL, command=self.song_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.song_listbox.config(yscrollcommand=scrollbar.set)

        # Song Details Section (Restored)
        self.details_frame = ttk.Frame(main_frame, padding=10)
        self.details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.progress = ttk.Progressbar(self.details_frame, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10)

        self.status_label = ttk.Label(self.details_frame, text="", font=("Arial", 12))
        self.status_label.pack(pady=5)

        self.settings_button = ttk.Button(self.root, text="Settings", command=self.open_settings_window)
        self.settings_button.place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)  # Always in bottom-right

        # Apply theme correctly
        self.apply_theme()

        # Restore song fetching & display
        self.songs = self.fetch_and_extract_songs()
        self.sorting_method = settings.get("sorting_method", "Last Added")  # Load sorting method from settings.json
        self.filtered_songs = self.songs
        self.display_songs(self.filtered_songs)

        # Load the logo only once when the program starts
        try:
            if getattr(sys, 'frozen', False):
                logo_path = os.path.join(sys._MEIPASS, "logo.png")
            else:
                logo_path = "logo.png"
            image = Image.open(logo_path)
            image = image.resize((200, 70), Image.LANCZOS)
            self.cached_logo = ImageTk.PhotoImage(image)  # Store it for reuse
        except Exception:
            self.cached_logo = None  # Prevent crashes if file is missing


    def open_settings_window(self):
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.geometry("400x300")
        self.settings_window.attributes('-topmost', True)  # Ensure it's always on top
        self.settings_window.resizable(False, False)  # Disable resizing
        self.settings_window.attributes('-toolwindow', True)  # Make it like a properties window

        # Create notebook (tabbed interface)
        notebook = ttk.Notebook(self.settings_window)
        notebook.pack(fill='both', expand=True)

        # Display tab
        display_frame = ttk.Frame(notebook, padding=10)
        notebook.add(display_frame, text='Display')

        # Sorting section
        sorting_frame = ttk.Frame(display_frame)
        sorting_frame.pack(fill='x', pady=5)

        ttk.Label(sorting_frame, text="Sort songs by:").pack(side='left', padx=5)

        sorting_options = ["A-Z by Artist", "A-Z by Song Name", "Last Added"]
        self.sorting_var = tk.StringVar(value=self.sorting_method)
        sorting_dropdown = ttk.Combobox(sorting_frame, textvariable=self.sorting_var, values=sorting_options, state="readonly")
        sorting_dropdown.pack(side='left', padx=5)
        sorting_dropdown.bind("<<ComboboxSelected>>", lambda e: self.update_sorting_method())

        # Sorting order toggle button
        self.sort_order_asc = tk.BooleanVar(value=self.sort_ascending)
        self.sort_order_button = ttk.Button(
            sorting_frame,
            text="⬆ Ascending" if self.sort_ascending else "⬇ Descending",
            command=self.toggle_sort_order
        )
        self.sort_order_button.pack(side='left', padx=5)

        # Theme section (Dropdown)
        theme_frame = ttk.Frame(display_frame)
        theme_frame.pack(anchor="w", fill='x', padx=5, pady=5)

        ttk.Label(theme_frame, text="Theme:").pack(side='left', padx=5)

        theme_options = ["Dark Mode", "Light Mode"]
        self.theme_var = tk.StringVar(value="Dark Mode" if self.dark_mode else "Light Mode")
        theme_dropdown = ttk.Combobox(theme_frame, textvariable=self.theme_var, values=theme_options, state="readonly")
        theme_dropdown.pack(side='left', padx=5)
        theme_dropdown.bind("<<ComboboxSelected>>", lambda e: self.toggle_theme())

        # System tab
        system_frame = ttk.Frame(notebook, padding=10)
        notebook.add(system_frame, text='System')

        # Folder selection section
        folder_frame = ttk.Frame(system_frame)
        folder_frame.pack(anchor="w", fill="x", pady=5)

        ttk.Label(folder_frame, text="Save in:").pack(side="left", padx=5)

        self.folder_label = ttk.Label(system_frame, text=self.extract_folder, wraplength=350, anchor="w", justify="left")
        self.folder_label.pack(fill="x", padx=10, pady=2)

        ttk.Button(folder_frame, text="Browse...", command=self.choose_folder).pack(side="left", padx=5)

        # Auto-open folder checkbox section (Fixed)
        auto_open_frame = ttk.Frame(system_frame)
        auto_open_frame.pack(anchor="w", fill="x", padx=10, pady=5)

        ttk.Label(auto_open_frame, text="Automatically open stems folder after extraction").pack(side="left", padx=5)

        self.auto_open_var = tk.BooleanVar(value=self.auto_open_folder)
        auto_open_checkbox = ttk.Checkbutton(
            auto_open_frame, 
            variable=self.auto_open_var, 
            command=self.toggle_auto_open
        )
        auto_open_checkbox.pack(side="left", padx=5)  # ✅ Ensure close spacing

        # Audio tab
        audio_frame = ttk.Frame(notebook, padding=10)
        notebook.add(audio_frame, text='Audio')

        # File Format Selection
        format_frame = ttk.Frame(audio_frame)
        format_frame.pack(anchor="w", pady=5, fill="x")

        ttk.Label(format_frame, text="File Saving Format:").pack(side="left", padx=5)

        self.file_format_var = tk.StringVar(value=self.file_format)  # Load saved format
        format_options = ["wav", "flac", "mp3"]
        format_dropdown = ttk.Combobox(format_frame, textvariable=self.file_format_var, values=format_options, state="readonly")
        format_dropdown.pack(side="left", padx=5)
        format_dropdown.bind("<<ComboboxSelected>>", lambda e: self.save_settings())  # Save on selection

        # Extracting Method Selection
        extracting_method_frame = ttk.Frame(audio_frame)
        extracting_method_frame.pack(anchor="w", pady=5, fill="x")

        ttk.Label(extracting_method_frame, text="Extracting Method:").pack(side="left", padx=5)

        self.extracting_method_var = tk.StringVar()
        self.extracting_method_var.set(self.extracting_method)  # Ensure it's set correctly
        extracting_options = ["Stereo", "Mono", "Single File"]
        extracting_dropdown = ttk.Combobox(extracting_method_frame, textvariable=self.extracting_method_var, values=extracting_options, state="readonly")
        extracting_dropdown.pack(side="left", padx=5)
        extracting_dropdown.bind("<<ComboboxSelected>>", lambda e: self.save_settings())  # Save on selection

        # About & Help tab
        about_frame = ttk.Frame(notebook, padding=10)
        notebook.add(about_frame, text='About & Help')

        # Display the cached logo (only once)
        if self.cached_logo:
            logo_label = ttk.Label(about_frame, image=self.cached_logo)
            logo_label.pack(pady=(5, 10))
        else:
            ttk.Label(about_frame, text="[Logo failed to load]", foreground="red").pack(pady=(5, 10))

        # About text (Consistent spacing)
        about_text = """\
        Fortnite Festival Extractor is an unofficial open-source
        program to download and extract FF songs into stems.
        """
        about_label = ttk.Label(about_frame, text=about_text, justify="center", anchor="center")
        about_label.pack(pady=(0, 10))  # Consistent bottom padding

        # GitHub link (Normal text color, Underlined)
        github_link = ttk.Label(about_frame, text="Visit Fortnite Festival Extractor GitHub page", cursor="hand2", font=("TkDefaultFont", 10, "underline"))
        github_link.pack(pady=(0, 10))
        github_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/ilayezra/Festival-Extractor"))

        # Contact information (Consistent spacing)
        contact_text = "If you have any issues, contact me at: ilayezra37@gmail.com"
        contact_label = ttk.Label(about_frame, text=contact_text, justify="center", anchor="center")
        contact_label.pack(pady=(0, 5))


        # OK Button
        button_frame = ttk.Frame(self.settings_window)
        button_frame.pack(fill='x', side='bottom', pady=5)

        ttk.Button(button_frame, text="OK", command=self.settings_window.destroy).pack(side='right', padx=5)

    def toggle_auto_open(self):
        self.auto_open_folder = self.auto_open_var.get()
        self.save_settings()

    def update_sorting_method(self):
        self.sorting_method = self.sorting_var.get()
        self.save_settings()
        self.display_songs(self.filtered_songs)

    def toggle_sort_order(self):
        self.sort_ascending = not self.sort_ascending  # Flip sorting order
        self.sort_order_button.config(text="⬆ Ascending" if self.sort_ascending else "⬇ Descending")
        self.save_settings()
        # Clear any current selection before reordering
        self.song_listbox.selection_clear(0, tk.END)
        # Force a refresh of the song list
        self.display_songs(self.songs if not self.search_entry.get() else self.filtered_songs)

    def toggle_theme(self):
        # Update dark_mode based on the dropdown selection
        self.dark_mode = (self.theme_var.get() == "Dark Mode")

        # Apply theme change
        self.apply_theme()

        # Save theme state to settings.json
        self.save_settings()

        # Update theme button text
        if hasattr(self, "theme_button"):
            self.theme_button.config(text="Switch to Light Mode" if self.dark_mode else "Switch to Dark Mode")

        # Save theme state to settings.json
        self.save_settings()


        # Define colors
        bg_color = "#1E1E1E" if self.dark_mode else "#FFFFFF"
        fg_color = "#FFFFFF" if self.dark_mode else "#000000"
        listbox_bg = "#2E2E2E" if self.dark_mode else "#FFFFFF"
        listbox_fg = "#FFFFFF" if self.dark_mode else "#000000"
        progress_color = "#3A3A3A" if self.dark_mode else "#DDDDDD"
        button_bg = "#3A3A3A" if self.dark_mode else "#DDDDDD"

        # Update main window background
        self.root.configure(bg=bg_color)

        # Update settings window if it's open
        if hasattr(self, "settings_window") and self.settings_window.winfo_exists():
            self.settings_window.configure(bg=bg_color)

        # Apply theme to specific widgets
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Frame):  
                widget.configure(bg=bg_color)
            elif isinstance(widget, tk.Label):  
                widget.configure(bg=bg_color, fg=fg_color)

        # Update Listbox (Song List)
        self.song_listbox.configure(bg=listbox_bg, fg=listbox_fg)

        # Update Progress Bar Color
        self.style = ttk.Style()
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=fg_color)
        self.style.configure("TButton", background=button_bg, foreground=fg_color)
        self.style.configure("Horizontal.TProgressbar", background=progress_color, troughcolor=bg_color)

        # FIX: Update status label correctly
        self.style.configure("StatusLabel.TLabel", background=bg_color, foreground=fg_color)
        self.status_label.configure(style="StatusLabel.TLabel")  # Apply the updated style

        # Update Theme Toggle Button Text
        if hasattr(self, "theme_button"):
            self.theme_button.config(text="Switch to Light Mode" if self.dark_mode else "Switch to Dark Mode")

        # Save theme state to settings.json
        self.save_settings()

    def apply_theme(self):
        """Applies the saved theme directly without toggling."""
        bg_color = "#1E1E1E" if self.dark_mode else "#FFFFFF"
        fg_color = "#FFFFFF" if self.dark_mode else "#000000"
        listbox_bg = "#2E2E2E" if self.dark_mode else "#FFFFFF"
        listbox_fg = "#FFFFFF" if self.dark_mode else "#000000"
        progress_color = "#3A3A3A" if self.dark_mode else "#DDDDDD"
        button_bg = "#3A3A3A" if self.dark_mode else "#DDDDDD"

        self.root.configure(bg=bg_color)

        # Ensure status label updates properly
        self.style.configure("StatusLabel.TLabel", background=bg_color, foreground=fg_color)
        self.status_label.configure(style="StatusLabel.TLabel")

        # Update the listbox colors
        self.song_listbox.configure(bg=listbox_bg, fg=listbox_fg)

        # Apply style changes
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=fg_color)
        self.style.configure("TButton", background=button_bg, foreground=fg_color)
        self.style.configure("Horizontal.TProgressbar", background=progress_color, troughcolor=bg_color)


    def choose_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.extract_folder = folder_selected
            self.folder_label.config(text=self.extract_folder)  # Update label text
            self.save_settings()  # Save it to file
            messagebox.showinfo("Folder Selected", f"Files will now save to:\n{self.extract_folder}")


    def save_settings(self):
        self.file_format = self.file_format_var.get()  # Update format
        self.extracting_method = self.extracting_method_var.get()  # Update extracting method
        settings = {
            "extract_folder": self.extract_folder,
            "dark_mode": self.dark_mode,
            "sorting_method": self.sorting_method,
            "sort_ascending": self.sort_ascending,
            "auto_open_folder": self.auto_open_folder,
            "file_format": self.file_format,  # Save format
            "extracting_method": self.extracting_method  # Save extracting method
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
                    "file_format": settings.get("file_format", "wav"),  # Default to wav
                    "extracting_method": settings.get("extracting_method", "Stereo")  # Default to stereo
                }
        return {
            "extract_folder": os.getcwd(),
            "dark_mode": True,
            "sorting_method": "Last Added",
            "sort_ascending": True,
            "auto_open_folder": False,
            "file_format": "wav",  # Default to wav
            "extracting_method": "Stereo"  # Default to stereo
        }

    @staticmethod
    def get_resource_path(relative_path):
        if getattr(sys, 'frozen', False):
            # Running in a PyInstaller bundle
            return os.path.join(sys._MEIPASS, relative_path)
        # Running in normal Python environment
        return relative_path

    def search_songs(self, event=None):
        query = self.search_entry.get().lower()
        self.filtered_songs = [song for song in self.songs if query in song['title'].lower() or query in song['artist'].lower()]
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
        
        print(f"Songs fetched: {len(songs)}")  # Debugging
        return songs


    def display_songs(self, songs):
        # Create a new list to avoid modifying the original
        sorted_songs = songs.copy()
        
        if self.sorting_method == "A-Z by Artist":
            sorted_songs = sorted(sorted_songs, key=lambda s: s["artist"].lower(), reverse=not self.sort_ascending)
        elif self.sorting_method == "A-Z by Song Name":
            sorted_songs = sorted(sorted_songs, key=lambda s: s["title"].lower(), reverse=not self.sort_ascending)
        elif self.sorting_method == "Last Added":
            # For "Last Added", API returns newest first by default
            # So descending = newest first (API default), ascending = oldest first
            sorted_songs = songs.copy()
            if self.sort_ascending != True:  # Force explicit comparison
                sorted_songs.reverse()
            
        # Update the filtered_songs list to match the new order
        self.filtered_songs = sorted_songs

        self.song_listbox.delete(0, tk.END)
        for song in sorted_songs:
            self.song_listbox.insert(tk.END, f"{song['artist']} - {song['title']}")

        self.song_listbox.update_idletasks()

    def seconds_to_minutes_seconds(self, seconds):
        # Convert seconds to minutes:seconds format
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"  # Ensure seconds are two digits

    def on_song_select(self, event=None):
        for widget in self.details_frame.winfo_children():
            if widget != self.progress and widget != self.status_label:  # Keep the progress bar and status label
                widget.destroy()
        selection = self.song_listbox.curselection()
        if not selection:
            return
        selected_song = self.filtered_songs[selection[0]]
        
        if selected_song['cover_art_url']:
            try:
                response = requests.get(selected_song['cover_art_url'])
                image = Image.open(BytesIO(response.content))
                image = image.resize((200, 200), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                label = ttk.Label(self.details_frame, image=photo)
                label.image = photo
                label.pack(pady=10)
            except:
                ttk.Label(self.details_frame, text="No Image Available").pack(pady=10)
        
        # Convert duration to minutes:seconds format
        duration = selected_song['duration'] if isinstance(selected_song['duration'], int) else int(selected_song['duration']) if selected_song['duration'].isdigit() else 0
        formatted_duration = self.seconds_to_minutes_seconds(duration)
        
        details = [
            f"Title: {selected_song['title']}",
            f"Artist: {selected_song['artist']}",
            f"Release Year: {selected_song['release_year']}",
            f"Duration: {formatted_duration}",  # Use formatted duration
            f"BPM: {selected_song['bpm']}"
        ]
        for detail in details:
            ttk.Label(self.details_frame, text=detail).pack(anchor="w", pady=2)
        
        download_button = Button(self.details_frame, text="Download", command=lambda: self.download_song(selected_song))
        download_button.pack(pady=10)

    def sanitize_folder_name(self, name):
        # Remove invalid characters from folder names
        return re.sub(r'[<>:"/\\|?*]', '', name)

    def delete_temporary_files(self):
        # Delete temporary files if they exist
        if os.path.exists("master.blurl"):
            os.remove("master.blurl")
        if os.path.exists("master_audio.mp4"):
            os.remove("master_audio.mp4")

    def download_song(self, song):
        if not song['sid']:
            messagebox.showerror("Error", "No song ID available")
            return
        
        try:
            # Delete temporary files before starting the download
            self.delete_temporary_files()

            # Fetch the playlist API file
            api_url = f"https://cdn.qstv.on.epicgames.com/{song['sid']}"
            print(f"Fetching from API URL: {api_url}")
            
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            
            print(f"API Response data: {json.dumps(data, indent=2)}")  # Debug print
            
            # Navigate through the JSON structure to find baseUrls
            for key, value in data.items():
                if isinstance(value, dict) and 'baseUrls' in value:
                    base_urls = value['baseUrls']
                    if base_urls and len(base_urls) > 0:
                        # Get the first base URL
                        base_url = base_urls[0]
                        print(f"Found base URL: {base_url}")
                        
                        url_parts = base_url.rstrip('/').split('/')
                        if len(url_parts) < 4:
                            continue
                            
                        # Get the domain and unique code
                        domain = f"{url_parts[0]}//{url_parts[2]}"
                        unique_code = url_parts[3]
                        
                        # Construct the final download URL
                        download_url = f"{domain}/{unique_code}/master.blurl"
                        print(f"Download URL: {download_url}")
                        
                        # Update status label
                        self.status_label.config(text="Downloading song file...")
                        self.root.update_idletasks()
                        
                        # Download the file with progress
                        self.progress["value"] = 0
                        self.progress["maximum"] = 100
                        self.root.update_idletasks()
                        
                        with requests.get(download_url, stream=True) as r:
                            r.raise_for_status()
                            total_size = int(r.headers.get('content-length', 0))
                            downloaded_size = 0
                            chunk_size = 8192
                            
                            with open("master.blurl", "wb") as file:
                                for chunk in r.iter_content(chunk_size=chunk_size):
                                    file.write(chunk)
                                    downloaded_size += len(chunk)
                                    progress = int((downloaded_size / total_size) * 100)
                                    self.progress["value"] = progress
                                    self.root.update_idletasks()
                        
                        # Convert the file using blurlconvert.exe
                        self.status_label.config(text="Converting to Audio File...")
                        self.convert_blurl_to_mp4("master.blurl")
                        
                        # Extract audio stems using ffmpeg
                        self.status_label.config(text="Extracting audio stems...")
                        self.extract_audio_stems(song['title'])
                        
                        # Update status label
                        self.status_label.config(text="Done!")
                        messagebox.showinfo("Success", f"Downloaded, converted, and extracted stems for: {song['title']}")
                        return
                
            messagebox.showerror("Error", "Could not find valid download URL in the response")
            
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Download failed: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")
            print(f"Unexpected error: {str(e)}")

    def convert_blurl_to_mp4(self, blurl_file):
        try:
            # Ensure blurlconvert.exe is in the same directory
            if getattr(sys, 'frozen', False):
                blurlconvert_path = os.path.join(sys._MEIPASS, "blurlconvert.exe")
            else:
                blurlconvert_path = "blurlconvert.exe"
            if not os.path.exists(blurlconvert_path):
                messagebox.showerror("Error", "blurlconvert.exe not found in the current directory")
                return
            
            # Run the conversion command
            self.progress["value"] = 50  # Indicate conversion is in progress
            self.root.update_idletasks()

            # Copy keys.bin to working directory if it exists in the bundle
            keys_path = self.get_resource_path("keys.bin")
            if os.path.exists(keys_path):
                import shutil
                shutil.copy2(keys_path, "keys.bin")

            # Ensure keys.bin is deleted after conversion
            delete_keys_bin = True  # Flag to track if we need to delete keys.bin

            
            subprocess.run([blurlconvert_path, blurl_file], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            print(f"Conversion successful: {blurl_file} -> master_audio.mp4")
            
            self.progress["value"] = 100  # Indicate conversion is complete
            self.root.update_idletasks()
            # Delete keys.bin after conversion
            if delete_keys_bin and os.path.exists("keys.bin"):
                os.remove("keys.bin")
                print("Temporary file keys.bin deleted.")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Conversion failed: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error during conversion: {str(e)}")

    def extract_audio_stems(self, song_title):
        try:
            if not os.path.exists("master_audio.mp4"):
                messagebox.showerror("Error", "master_audio.mp4 not found")
                return

            # Ensure extraction folder exists
            os.makedirs(self.extract_folder, exist_ok=True)

            # Sanitize song title to create a valid folder name
            sanitized_title = self.sanitize_folder_name(song_title)

            # Save stems inside the selected folder
            stem_folder = os.path.join(self.extract_folder, f"{sanitized_title} - stems")
            os.makedirs(stem_folder, exist_ok=True)

            # Get the selected format
            selected_format = self.file_format_var.get()

            # Get extracting method
            extracting_method = self.extracting_method_var.get()

            # Base FFmpeg command
            base_command = ["ffmpeg", "-y", "-i", "master_audio.mp4"]

            # Ensure MP3 is always 320kbps
            extra_options = []
            if selected_format == "mp3":
                extra_options = ["-b:a", "320k"]

            if extracting_method == "Stereo":
                # Stereo mode (Default, combines left/right into stereo)
                ffmpeg_command = base_command + [
                    "-map_channel", "0.0.0", "-map_channel", "0.0.1", "-ac", "2", *extra_options, os.path.join(stem_folder, f"Drums.{selected_format}"),
                    "-map_channel", "0.0.2", "-map_channel", "0.0.3", "-ac", "2", *extra_options, os.path.join(stem_folder, f"Bass.{selected_format}"),
                    "-map_channel", "0.0.4", "-map_channel", "0.0.5", "-ac", "2", *extra_options, os.path.join(stem_folder, f"Lead.{selected_format}"),
                    "-map_channel", "0.0.6", "-map_channel", "0.0.7", "-ac", "2", *extra_options, os.path.join(stem_folder, f"Vocals.{selected_format}"),
                    "-map_channel", "0.0.8", "-map_channel", "0.0.9", "-ac", "2", *extra_options, os.path.join(stem_folder, f"Other.{selected_format}")
                ]

            elif extracting_method == "Mono":
                # Mono mode (extracts each channel separately)
                ffmpeg_command = base_command + [
                    "-map_channel", "0.0.0", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Drums_Left.{selected_format}"),
                    "-map_channel", "0.0.1", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Drums_Right.{selected_format}"),
                    "-map_channel", "0.0.2", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Bass_Left.{selected_format}"),
                    "-map_channel", "0.0.3", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Bass_Right.{selected_format}"),
                    "-map_channel", "0.0.4", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Lead_Left.{selected_format}"),
                    "-map_channel", "0.0.5", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Lead_Right.{selected_format}"),
                    "-map_channel", "0.0.6", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Vocals_Left.{selected_format}"),
                    "-map_channel", "0.0.7", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Vocals_Right.{selected_format}"),
                    "-map_channel", "0.0.8", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Other_Left.{selected_format}"),
                    "-map_channel", "0.0.9", "-ac", "1", *extra_options, os.path.join(stem_folder, f"Other_Right.{selected_format}")
                ]

            elif extracting_method == "Single File":
                # Single File mode (properly mixes all channels into stereo)
                ffmpeg_command = base_command + [
                    "-filter_complex", "[0:a]pan=stereo|c0<c0+c2+c4+c6+c8|c1<c1+c3+c5+c7+c9[out]", "-map", "[out]",
                    "-ac", "2", *extra_options, os.path.join(stem_folder, f"master.{selected_format}")
                ]

            # Run FFmpeg command
            subprocess.run(ffmpeg_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            print(f"Audio extracted successfully into folder: {stem_folder}")

            # Delete temporary files
            os.remove("master_audio.mp4")
            os.remove("master.blurl")
            print("Temporary files deleted.")

            # Automatically open folder if setting is enabled
            if self.auto_open_folder:
                import platform
                if platform.system() == "Windows":
                    subprocess.Popen(f'explorer "{os.path.normpath(stem_folder)}"')
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", stem_folder])
                else:  # Linux
                    subprocess.Popen(["xdg-open", stem_folder])

        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"FFmpeg extraction failed: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error during extraction: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = FortniteTracksGUI(root)
    root.mainloop()