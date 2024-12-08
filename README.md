# Kemono Webnovel Downloader

This Python application provides a graphical interface for downloading and managing webnovels from Kemono.su. It allows users to add, edit, and delete profiles of webnovels authors, preview chapters, and create EPUB files.

## Features

- **Profile Management:** Add, edit, or delete webnovel profiles with details like URL, title, and author.
- **Chapter Preview:** Fetch and display chapters, highlighting new chapters since last fetch.
- **EPUB Creation:** Convert selected chapters into an EPUB file with customizable metadata.

## Prerequisites

- Python 3.x
- Required Python libraries:
  - `tkinter` (usually included with Python)
  - `requests`
  - `ebooklib`
  - `json`

To install the required packages, run:

```bash
pip install requests ebooklib

EDIT: The Kemono_Webnovel_Downloader.py will only fetch up to 50 chapters. The Kemono_Webnovel_Downloader_More_Chapters.py will fetch all chapters.
