# Kemono Webnovel Downloader

A clean, modern Python GUI application for downloading web novels from **Kemono.cr** and converting them into formatted EPUB files.

## Features

- **Profile Management**: Save and manage your favorite novels locally or sync via login.
- **Post/Chapter Fetching**: Handles pagination and retrieves full chapter content.
- **EPUB Generator**: Creates EPUBs with proper CSS styling and embedded images (supports PNG, WebP, JPG).
- **Modern UI**: Built with PyQt6 for a responsive user experience.

## Installation

1. **Install Python 3.11+**
2. **Install dependencies**:

'''bash
pip install PyQt6 requests EbookLib
'''

3. **Run the script**:

'''bash
python Kemono_Webnovel_Downloader.py
'''

## Usage

1. **Add a Profile**: Click "Add Profile" and paste the novel's Kemono URL.
   - *Note: If you log in, you can add/remove favorites directly to your Kemono account.*
2. **Preview**: Select a profile and click **"Preview Download"**.
3. **Fetch Chapters**: Click "Load Next 50" (or "Load All") to populate the list.
4. **Download**: Select the specific chapters you want (or select all) and click **"Download Selected"**.
5. **Result**: The app will generate a clean EPUB file in your selected directory.

## Requirements

- Python 3.11 or higher
- `PyQt6`, `requests`, `EbookLib`
