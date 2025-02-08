import os
import requests
import re
import subprocess
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import threading
import time

def sanitize_filename(filename):
    """
    Convert filename to a valid filename by removing/replacing invalid characters
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.rstrip('. ') or "unnamed_song"

class FortniteExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Fortnite Festival Song Extractor")
        self.root.geometry("600x500")
        
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.create_gui_elements()
        self.song_data = []
        self.processing = False
        self.load_songs()

    def create_gui_elements(self):
        title_label = ttk.Label(self.main_frame, text="Fortnite Festival Song Extractor", font=('Helvetica', 14, 'bold'))
        title_label.pack(pady=10)

        search_frame = ttk.Frame(self.main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        search_label = ttk.Label(search_frame, text="Search song:")
        search_label.pack(side=tk.LEFT, padx=5)

        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_songs)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        list_frame = ttk.Frame(self.main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.song_listbox = tk.Listbox(list_frame, width=50, height=15)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.song_listbox.yview)
        self.song_listbox.configure(yscrollcommand=scrollbar.set)
        self.song_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        progress_frame = ttk.Frame(self.main_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, length=300, mode='determinate', variable=self.progress_var)
        self.progress_bar.pack(pady=5)

        self.status_label = ttk.Label(progress_frame, text="Ready")
        self.status_label.pack()

        self.extract_button = ttk.Button(self.main_frame, text="Extract Selected Song", command=self.start_extraction)
        self.extract_button.pack(pady=10)

    def filter_songs(self, *args):
        search_term = self.search_var.get().lower()
        self.song_listbox.delete(0, tk.END)
        for description, _ in self.song_data:
            if search_term in description.lower():
                self.song_listbox.insert(tk.END, description)

    def load_songs(self):
        try:
            song_list = self.fetch_song_list()
            self.song_data = [(f"{song['an']} - {song['tt']}", song['sid']) for song in song_list if song.get('an') and song.get('tt')]
            self.song_data.sort(key=lambda x: x[0].lower())  # Sort alphabetically by artist and song name

            # Populate the listbox with all songs
            self.song_listbox.delete(0, tk.END)
            for description, _ in self.song_data:
                self.song_listbox.insert(tk.END, description)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load songs: {str(e)}")

    def fetch_song_list(self):
        url = "https://fortnitecontent-website-prod07.ol.epicgames.com/content/api/pages/fortnite-game/spark-tracks"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('bSongs', [])
        raise Exception(f"Failed to fetch song list, status code: {response.status_code}")

    def start_extraction(self):
        if self.processing:
            messagebox.showwarning("Warning", "Already processing a song")
            return

        selected_indices = self.song_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select a song first")
            return

        self.processing = True
        self.extract_button.state(['disabled'])

        selected_description = self.song_listbox.get(selected_indices[0])
        selected_data = next((data for data in self.song_data if data[0] == selected_description), None)
        if not selected_data:
            messagebox.showerror("Error", "Could not find song data")
            return

        threading.Thread(target=self.process_song, args=selected_data, daemon=True).start()

    def process_song(self, description, sid):
        try:
            self.update_progress(20, "Fetching song data...")
            api_url = f"https://cdn.qstv.on.epicgames.com/{sid}"
            response = requests.get(api_url)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch song data, status code: {response.status_code}")

            base_url = response.json().get('baseUrls', [None])[0]
            if not base_url:
                raise Exception("Invalid song data received")

            blurl_url = f"{base_url}master.blurl"
            self.update_progress(40, "Downloading master.blurl...")

            blurl_file = f"{sid}.blurl"
            with open(blurl_file, 'wb') as file:
                file.write(requests.get(blurl_url).content)

            self.update_progress(60, "Converting to audio...")
            subprocess.run(["blurlconvert.exe", blurl_file], check=True)

            self.update_progress(100, "Extraction complete!")
            messagebox.showinfo("Success", f"Successfully extracted: {description}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process song: {str(e)}")
        finally:
            self.processing = False
            self.extract_button.state(['!disabled'])

    def update_progress(self, value, status):
        self.progress_var.set(value)
        self.status_label.config(text=status)
        self.root.update_idletasks()

if __name__ == "__main__":
    root = tk.Tk()
    app = FortniteExtractorGUI(root)
    root.mainloop()