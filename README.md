# Kemono Webnovel Downloader

A Python application designed to download web novels from the Kemono.su, featuring an easy-to-use GUI for managing profiles, fetching chapters, and creating EPUB files.

## Features

- **Profile Management**: Add, edit, or delete profiles for different web novels.
- **Chapter Fetching**: Fetch chapters from Kemono. Includes options to fetch all chapters beyond the top 50 posts from the kemono page.
- **EPUB Creation**: Convert fetched chapters into EPUB format with customizable metadata.
- **Automatic Mode**: Automatically fetch new chapters for selected profiles at set intervals.
- **User-Friendly Interface**: Utilizes Tkinter for a simple, intuitive GUI with context menus for profile actions.

## Prerequisites

Before you start, ensure you have the following installed:

- Python 3.11+ (or any version supporting the libraries used)
- `tkinter` (usually comes pre-installed with Python)
- `requests` for HTTP requests
- `ebooklib` for EPUB creation
- `json` for profile data storage

You can install the required Python packages using:

```bash
pip install requests ebooklib
```

## Installation

Download and run the `Kemono_Webnovel_Downloader.py`.

## Usage

- **Add a Profile**: Click "Add Profile" to input the URL, title, author, and directory for saving EPUB files. You can also opt into automatic mode for that profile if you want.
- **Edit or Delete Profiles**: Right-click on a profile in the list to edit or delete it.
- **Fetch Chapters**: Select a profile and click "Download Preview". Choose chapters to download or preview them first.
- **Automatic Mode**: Toggle to start automatic fetching of new chapters for opted-in profiles. The interval can be adjusted by changing `self.sleep_time_seconds` value in the source code. The default is "1800" or 30 minutes.
  - Automatic mode checks for NEW posts and will only fetch the EPUB if there are new posts.
  - NEW posts are defined in the code based on the last chapter you downloaded. That means downloading an older chapter will cause all posts after that to show as NEW again, even if previously downloaded. This is intentional.

## Security

For your security, this application is provided as source code without an executable. Users are responsible for reviewing the code and compiling the software on their own systems.

### Creating an EXE File (for personal use)

If you want to create an executable from this Python script for personal use, here are the steps:

1. **Install PyInstaller**:

   ```bash
   pip install pyinstaller
   ```
2. **Navigate to the directory with your script and open terminal**:

- Make sure terminal is open to the correct directory containing the Kemono_Webnovel_Downloader.py
- For the EXE image icon, ensure that an icon.ico file is present in the same directory. You can use the one provided in this git or use your own.

3. **Use PyInstaller to create the EXE**:

Run:
```bash
pyinstaller --onefile --noconsole --icon=icon.ico Kemono_Webnovel_Downloader.py
```

- --onefile creates a single executable file.
- --noconsole prevents a console window from appearing with the application.
- --icon=icon.ico Uses the icon.ico image file for the EXE icon.

Find the executable in the dist folder created by PyInstaller once its finished.
