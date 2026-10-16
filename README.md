# 🎵 Fortnite Festival Extractor

![Fortnite Festival Extractor](https://i.ibb.co/BvQtR3j/logo2.png)

An advanced GUI-based tool that allows you to extract and download music tracks from **Fortnite Festival** into high-quality audio stems.

## 🚀 Features
✅ **Download Fortnite Festival songs** directly using their track IDs  
✅ **Extract audio stems** (Drums, Bass, Lead, Vocals, Other) in multiple formats (`wav`, `mp3`, `flac`)  
✅ **User-friendly GUI** with dark/light theme    
✅ **Search & Sort** tracks by name, artist, or last added  
✅ **Customizable settings**, including extraction folder and sorting options  

## 📸 Screenshot
![Fortnite Festival Extractor](https://us-east-1.tixte.net/uploads/milki.tixte.co/Example_(2).png)

## 🔧 Installation

Download the file for your system from the latest **[Release](https://github.com/ilayezra/Festival-Extractor/releases)** and unzip it.
Everything the program needs is built in - no ffmpeg or other files to install.

### Windows
Run `Festival Extractor.exe` (`FestivalExtractor-Windows-x64.zip`).

### macOS
Use `FestivalExtractor-macOS-AppleSilicon.zip` for M1/M2/M3/M4 Macs or `FestivalExtractor-macOS-Intel.zip` for Intel Macs.
The app isn't signed by Apple, so the first time **right-click `Festival Extractor` → Open → Open**.
If macOS says the app is damaged, run `xattr -cr "/path/to/Festival Extractor.app"` in Terminal once.

### Linux
Unzip `FestivalExtractor-Linux-x64.zip` and run `./"Festival Extractor"`.

### Build from source
```
pip install -r requirements.txt pyinstaller
pyinstaller FFR.spec
```
The program is written to `dist/`. To run without building: `python FFR.py`.

## 🎛 Usage
1. Launch **Fortnite Festival Extractor**
2. Search for a song or browse the list
3. Click on a track to view details
4. Press **Download** to start the extraction
5. Audio stems will be saved in your selected folder

## ⚙️ Settings
- **Sorting Options**: Sort tracks by name, artist, or last added  
- **Custom Naming**: you can choose if you want more details in your files name
- **Audio Format**: Export files as `wav`, `mp3`, or `flac`  
- **Extraction Mode**:  
  - **Stereo** (default) – Keeps left & right channels together  
  - **Mono** – Extracts individual channels separately  
  - **Single File** – Merges all channels into one master file

## ©️ Credits
Huge thanks to **[spiritascend](https://github.com/spiritascend)** for creating **[blurlconvert](https://github.com/spiritascend/blurlconvert/tree/main)**. thanks to his algorhythm this program exist

## 📜 License
This project is **open-source** and licensed under the **MIT License**.

## 🤝 Contributing
Feel free to **fork this project** and submit a pull request if you have improvements!

## 📧 Contact
For issues or feedback, open an **[Issue](https://github.com/ilayezra/Festival-Extractor/issues)** or reach out via **[Discord](https://discord.com/users/532594707692519425)**
