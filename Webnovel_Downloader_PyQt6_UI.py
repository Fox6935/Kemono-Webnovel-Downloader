import sys
import json
import requests
import re
import os
import time
from datetime import datetime
from ebooklib import epub

from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QMenu, QFileDialog,
    QDialog, QMessageBox, QFormLayout, QLineEdit, QAbstractItemView
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QColor

# --- Constants ---
BASE_URL = "https://kemono.cr"
API_BASE = f"{BASE_URL}/api/v1"
DEFAULT_HEADERS = {
    "Accept": "text/css",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

# --- Login Dialog ---
class LoginWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login to Kemono")
        self.setModal(True)
        self.resize(300, 150)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        form.addRow("Username:", self.username_input)
        form.addRow("Password:", self.password_input)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.login_button = QPushButton("Login")
        self.cancel_button = QPushButton("Cancel")
        
        self.login_button.clicked.connect(self.attempt_login)
        self.cancel_button.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.login_button)
        btn_layout.addWidget(self.cancel_button)
        layout.addLayout(btn_layout)

    def attempt_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter credentials.")
            return
        if self.parent().login_to_kemono(username, password):
            self.accept()

# --- Main Window ---
class KemonoWebnovelDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kemono Webnovel Downloader")
        self.setGeometry(100, 100, 600, 500)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)
        
        self.setup_styles()
        
        self.default_directory = os.getcwd()
        self.cookies = {}
        self.logged_in = False
        self.profiles = {}
        
        # State for preview pagination
        self.current_preview_url = None
        self.current_preview_offset = 0
        self.preview_chapters_data = []
        self.preview_tree = None
        self.preview_dialog = None
        
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        
        self.setup_ui()
        self.load_defaults()
        
        if loaded_cookies := self.load_session():
            self.cookies = loaded_cookies
            self.session.cookies.update(self.cookies)
            self.logged_in = True
            
        self.profiles = self.load_profiles()
        self.update_profile_list()

        if self.logged_in:
            self.update_ui_for_login()

    def setup_styles(self):
        self.setStyleSheet("""
            QWidget { background-color: #dbdbdb; font-size: 13px; }
            QPushButton {
                background-color: #4287f5; border: none; color: white;
                padding: 8px 16px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1064e8; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
            QTreeWidget {
                background-color: #ffffff; color: black; border-radius: 4px;
            }
            QLineEdit {
                background-color: #ffffff; border: 1px solid #cccccc; padding: 4px; border-radius: 4px;
            }
        """)

    def setup_ui(self):
        # Top Controls
        top_layout = QHBoxLayout()
        ctrl_btn_style = "QPushButton { background-color: #333; }"
        
        btn_defaults = QPushButton("Defaults")
        btn_defaults.setStyleSheet(ctrl_btn_style)
        btn_defaults.clicked.connect(self.open_defaults_window)
        
        btn_refresh = QPushButton("Refresh")
        btn_refresh.setStyleSheet(ctrl_btn_style)
        btn_refresh.clicked.connect(self.refresh)
        
        self.btn_login = QPushButton("Login")
        self.btn_login.setStyleSheet(ctrl_btn_style)
        self.btn_login.clicked.connect(self.open_login_window)
        
        self.btn_logout = QPushButton("Logout")
        self.btn_logout.setStyleSheet(ctrl_btn_style)
        self.btn_logout.clicked.connect(self.logout)
        self.btn_logout.setVisible(False)
        
        top_layout.addWidget(btn_defaults)
        top_layout.addWidget(btn_refresh)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_login)
        top_layout.addWidget(self.btn_logout)
        self.layout.addLayout(top_layout)

        # Profile List
        self.profile_list = QTreeWidget()
        self.profile_list.setHeaderLabels(["Title", "Author", "URL"])
        self.profile_list.setColumnWidth(0, 200)
        self.profile_list.setColumnHidden(2, True)
        self.profile_list.itemSelectionChanged.connect(self.update_button_state)
        self.profile_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.profile_list.customContextMenuRequested.connect(self.show_context_menu)
        self.layout.addWidget(self.profile_list)

        # Action Buttons
        act_layout = QHBoxLayout()
        btn_add = QPushButton("Add Profile")
        btn_add.clicked.connect(self.add_profile)
        
        self.btn_dl_preview = QPushButton("Preview & Download")
        self.btn_dl_preview.clicked.connect(self.preview_chapters)
        self.btn_dl_preview.setEnabled(False)
        
        act_layout.addWidget(btn_add)
        act_layout.addWidget(self.btn_dl_preview)
        self.layout.addLayout(act_layout)

    # --- Networking ---

    def fetch_api(self, url, params=None):
        try:
            response = self.session.get(url, params=params)
            if response.status_code == 401:
                self.handle_session_expiry()
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API Error ({url}): {e}")
            return None

    def fetch_page(self, base_api_url, offset=0):
        """Fetches a single page (50 items) from the API."""
        if not base_api_url.endswith('/posts'):
             fetch_url = base_api_url.rstrip('/') + '/posts'
        else:
             fetch_url = base_api_url
             
        # q=<p> is critical to get content
        params = {'o': offset, 'q': '<p>'}
        print(f"Fetching offset {offset} from {fetch_url}")
        return self.fetch_api(fetch_url, params=params)

    # --- Data & Auth ---

    def open_login_window(self):
        LoginWindow(self).exec()

    def login_to_kemono(self, username, password):
        url = f"{API_BASE}/authentication/login"
        data = {"username": username, "password": password}
        try:
            response = self.session.post(url, json=data)
            response.raise_for_status()
            cookies_dict = self.session.cookies.get_dict()
            if not cookies_dict.get("session") and "session" in str(response.headers):
                 pass # requests usually handles this
            self.save_session(cookies_dict)
            self.logged_in = True
            self.update_ui_for_login()
            QMessageBox.information(self, "Success", "Logged in successfully!")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Login failed: {e}")
            return False

    def save_session(self, cookies):
        with open("session.json", "w") as file: json.dump(cookies, file)

    def load_session(self):
        try:
            with open("session.json", "r") as file: return json.load(file)
        except: return None

    def logout(self):
        if os.path.exists("session.json"): os.remove("session.json")
        self.logged_in = False
        self.session.cookies.clear()
        self.update_ui_for_logout()

    def update_ui_for_login(self):
        self.btn_login.setVisible(False)
        self.btn_logout.setVisible(True)
        self.refresh()

    def update_ui_for_logout(self):
        self.btn_login.setVisible(True)
        self.btn_logout.setVisible(False)
        self.refresh()

    def handle_session_expiry(self):
        self.logout()
        QMessageBox.warning(self, "Session Expired", "Please log in again.")

    def load_defaults(self):
        try:
            with open('defaults.json', 'r') as file:
                defaults = json.load(file)
                self.default_directory = defaults.get('directory', os.getcwd())
        except: pass

    def load_profiles(self):
        if self.logged_in: return self.load_preferences_from_api()
        return self.load_profiles_from_json()

    def load_profiles_from_json(self):
        try:
            with open("profiles.json", "r") as file:
                data = json.load(file)
                cleaned_data = {}
                for url, p in data.items():
                    # Clean out old keys
                    cleaned_data[url] = {
                        "title": p.get('title', 'Unknown'),
                        "author": p.get('author', 'Unknown'),
                        "directory": p.get('directory', self.default_directory),
                        "last_fetched": p.get('last_fetched', "")
                    }
                return cleaned_data
        except: return {}

    def load_preferences_from_api(self):
        url = f"{API_BASE}/account/favorites?type=artist"
        data = self.fetch_api(url)
        if not data: return {}
        local = self.load_preferences_json() or {}
        profiles = {}
        for p in data:
            p_url = f"{API_BASE}/{p['service']}/user/{p['id']}"
            existing = local.get(p_url, {})
            profiles[p_url] = {
                "title": existing.get('title', p.get('name', "Unknown")),
                "author": existing.get('author', p.get('public_id', "Unknown")),
                "last_fetched": existing.get('last_fetched', ""),
                "directory": existing.get('directory', self.default_directory),
                "updated": p.get('updated', "")
            }
        return profiles

    def load_preferences_json(self):
        try:
            with open("preferences.json", "r") as f: return json.load(f)
        except: return None

    def save_profiles(self):
        target = "preferences.json" if self.logged_in else "profiles.json"
        with open(target, "w") as file: json.dump(self.profiles, file, indent=4)

    def refresh(self):
        self.profiles = self.load_profiles()
        self.update_profile_list()
        QMessageBox.information(self, "Refreshed", "Profiles reloaded.")

    def update_profile_list(self):
        self.profile_list.clear()
        items = sorted(self.profiles.items(), key=lambda x: x[1].get('updated', ''), reverse=True)
        for url, p in items:
            item = QTreeWidgetItem([p['title'], p['author'], url])
            self.profile_list.addTopLevelItem(item)

    def update_button_state(self):
        self.btn_dl_preview.setEnabled(bool(self.profile_list.selectedItems()))

    def show_context_menu(self, pos):
        item = self.profile_list.itemAt(pos)
        if not item: return
        menu = QMenu(self)
        menu.addAction("Edit Profile", self.edit_profile)
        menu.addAction("Delete Profile", self.delete_profile)
        menu.exec(self.profile_list.mapToGlobal(pos))

    # --- Profile Mgmt ---

    def fix_link(self, link):
        if not link: return None
        link = link.strip()
        if "patreon.com" in link:
            try:
                r = requests.get(link, headers={"User-Agent": DEFAULT_HEADERS['User-Agent']})
                m = re.search(r'"creator":\s*{\s*"data":\s*{\s*"id":\s*"(\d+)"', r.text)
                if m: return f"{API_BASE}/patreon/user/{m.group(1)}"
            except: pass
            return None
        if not link.startswith("http"):
            link = f"https://{link}" if "kemono" in link else link
        if "kemono" in link:
            link = link.replace("kemono.su", "kemono.cr")
            if "/api/v1/" not in link:
                parts = link.split('kemono.cr/')[-1].split('/')
                if len(parts) >= 3 and parts[1] == 'user':
                    return f"{API_BASE}/{parts[0]}/user/{parts[2]}"
            else: return link
        return None

    def add_profile(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Profile")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        url_input = QLineEdit()
        title_input = QLineEdit()
        author_input = QLineEdit()
        form.addRow("URL:", url_input)
        form.addRow("Title:", title_input)
        form.addRow("Author:", author_input)
        layout.addLayout(form)
        btn = QPushButton("Add")
        
        def submit():
            api_url = self.fix_link(url_input.text())
            if not api_url:
                QMessageBox.critical(dialog, "Error", "Invalid URL.")
                return
            if api_url in self.profiles:
                QMessageBox.warning(dialog, "Exists", "Profile already exists.")
                return
            
            if self.logged_in:
                parts = api_url.split('/')
                try:
                    fav = f"{API_BASE}/favorites/creator/{parts[-3]}/{parts[-1]}"
                    self.session.post(fav)
                    self.refresh()
                    dialog.accept()
                except Exception as e:
                    QMessageBox.critical(dialog, "Error", str(e))
            else:
                self.profiles[api_url] = {
                    "title": title_input.text() or "Unknown",
                    "author": author_input.text() or "Unknown",
                    "directory": self.default_directory,
                    "last_fetched": ""
                }
                self.save_profiles()
                self.update_profile_list()
                dialog.accept()

        btn.clicked.connect(submit)
        layout.addWidget(btn)
        dialog.exec()

    def edit_profile(self):
        item = self.profile_list.currentItem()
        if not item: return
        url = item.text(2)
        profile = self.profiles[url]
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Profile")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        t_in = QLineEdit(profile.get('title', ''))
        a_in = QLineEdit(profile.get('author', ''))
        form.addRow("Title:", t_in)
        form.addRow("Author:", a_in)
        layout.addLayout(form)
        btn = QPushButton("Save")
        def save():
            self.profiles[url]['title'] = t_in.text()
            self.profiles[url]['author'] = a_in.text()
            self.save_profiles()
            self.update_profile_list()
            dialog.accept()
        btn.clicked.connect(save)
        layout.addWidget(btn)
        dialog.exec()

    def delete_profile(self):
        item = self.profile_list.currentItem()
        if not item: return
        url = item.text(2)
        if self.logged_in:
            parts = url.split('/')
            try:
                self.session.delete(f"{API_BASE}/favorites/creator/{parts[-3]}/{parts[-1]}")
                self.refresh()
            except Exception as e: QMessageBox.critical(self, "Error", str(e))
        else:
            del self.profiles[url]
            self.save_profiles()
            self.update_profile_list()

    # --- Pagination & Download ---

    def preview_chapters(self):
        item = self.profile_list.currentItem()
        if not item: return
        
        url = item.text(2)
        self.current_preview_url = url
        self.current_preview_offset = 0
        self.preview_chapters_data = [] # Reset data
        
        # Initial Fetch
        initial_data = self.fetch_page(url, 0)
        if initial_data is None: 
            return # Error handling in fetch
            
        self.preview_chapters_data = initial_data

        # UI Setup
        self.preview_dialog = QDialog(self)
        self.preview_dialog.setWindowTitle("Preview")
        self.preview_dialog.resize(550, 600)
        layout = QVBoxLayout(self.preview_dialog)
        
        self.preview_tree = QTreeWidget()
        self.preview_tree.setHeaderLabels(["Title", "Date"])
        self.preview_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.preview_tree.setColumnWidth(0, 350)
        layout.addWidget(self.preview_tree)
        
        self.add_to_preview_tree(initial_data)

        # Pagination Buttons
        pag_layout = QHBoxLayout()
        self.btn_load_next = QPushButton("Load Next 50")
        self.btn_load_next.clicked.connect(self.load_next_50)
        self.btn_load_all = QPushButton("Load All")
        self.btn_load_all.clicked.connect(self.load_all)
        pag_layout.addWidget(self.btn_load_next)
        pag_layout.addWidget(self.btn_load_all)
        layout.addLayout(pag_layout)
        
        btn_dl = QPushButton("Download Selected")
        btn_dl.setStyleSheet("background-color: #28a745; color: white;")
        btn_dl.clicked.connect(self.download_selected)
        layout.addWidget(btn_dl)
        
        self.preview_dialog.exec()

    def add_to_preview_tree(self, chapters):
        last_fetched = self.profiles[self.current_preview_url].get('last_fetched', '')
        
        for c in chapters:
            item = QTreeWidgetItem([c.get('title', 'No Title'), c.get('published', '')])
            if c.get('published') > last_fetched:
                item.setBackground(0, QColor(200, 255, 200)) # Highlight new
            self.preview_tree.addTopLevelItem(item)

    def load_next_50(self):
        self.current_preview_offset += 50
        self.btn_load_next.setText("Loading...")
        self.btn_load_next.setEnabled(False)
        QApplication.processEvents()
        
        data = self.fetch_page(self.current_preview_url, self.current_preview_offset)
        
        if data:
            self.preview_chapters_data.extend(data)
            self.add_to_preview_tree(data)
            self.btn_load_next.setText("Load Next 50")
            self.btn_load_next.setEnabled(True)
        else:
            self.btn_load_next.setText("No More Chapters")

    def load_all(self):
        self.btn_load_all.setEnabled(False)
        self.btn_load_next.setEnabled(False)
        
        while True:
            self.current_preview_offset += 50
            self.btn_load_all.setText(f"Loading (Offset {self.current_preview_offset})...")
            QApplication.processEvents()
            
            data = self.fetch_page(self.current_preview_url, self.current_preview_offset)
            if not data:
                break
            
            self.preview_chapters_data.extend(data)
            self.add_to_preview_tree(data)
            time.sleep(0.3) # Rate limit kindness
            
        self.btn_load_all.setText("All Loaded")

    def download_selected(self):
        selected_items = self.preview_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.preview_dialog, "Info", "No chapters selected.")
            return

        # Map tree items back to data based on title/date combination or index if sequential
        # To be safe, we match title and date
        to_download = []
        for item in selected_items:
            t = item.text(0)
            d = item.text(1)
            # Find in data
            for chap in self.preview_chapters_data:
                if chap.get('title') == t and chap.get('published') == d:
                    to_download.append(chap)
                    break
        
        if not to_download: return
        
        profile = self.profiles[self.current_preview_url]
        self.process_download(to_download, profile)
        self.preview_dialog.accept()

    def process_download(self, chapters, profile):
        chapters.sort(key=lambda x: x.get('published', ''))
        
        title = profile['title']
        author = profile['author']
        
        t1 = self.sanitize(chapters[0].get('title', ''))
        t2 = self.sanitize(chapters[-1].get('title', ''))
        fname = f"{t1}" if len(chapters) == 1 else f"{t1}-{t2}"
        fname = fname[:100]

        try:
            epub_path = self.create_epub(chapters, title, author, profile, fname)
            
            # Update last_fetched
            latest = chapters[-1]['published']
            if latest > profile.get('last_fetched', ''):
                profile['last_fetched'] = latest
                self.save_profiles()
            
            QMessageBox.information(self, "Success", f"EPUB saved:\n{epub_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create EPUB: {e}")

    def create_epub(self, chapters, title, author, profile, filename):
        book = epub.EpubBook()
        book.set_title(title)
        book.add_author(author)
        
        # CSS Style
        style = 'p { line-height: 1.2; text-indent: 0.75em; margin-bottom: 0.5em; } img { max-width: 100%; height: auto; }'
        css_item = epub.EpubItem(uid="style_nav", file_name="style.css", media_type="text/css", content=style)
        book.add_item(css_item)

        epub_chapters = []
        
        for idx, ch in enumerate(chapters):
            raw_title = ch.get('title', f"Chapter {idx+1}")
            clean_title = self.sanitize(raw_title)
            body = ch.get('content', '')
            
            # Image Processing
            images = re.findall(r'<img[^>]+src="([^"]+)"', body)
            for img_url in images:
                full_url = img_url if img_url.startswith('http') else BASE_URL + img_url
                
                try:
                    img_resp = self.session.get(full_url)
                    img_resp.raise_for_status()
                    
                    # Determine extension/media_type
                    ctype = img_resp.headers.get('Content-Type', '').lower()
                    if 'png' in ctype: 
                        ext, mime = 'png', 'image/png'
                    elif 'webp' in ctype: 
                        ext, mime = 'webp', 'image/webp'
                    elif 'gif' in ctype:
                        ext, mime = 'gif', 'image/gif'
                    else: 
                        ext, mime = 'jpg', 'image/jpeg'
                    
                    img_name = f"img_{hash(full_url)}.{ext}"
                    img_item = epub.EpubItem(
                        uid=img_name,
                        file_name=f"images/{img_name}",
                        media_type=mime,
                        content=img_resp.content
                    )
                    book.add_item(img_item)
                    body = body.replace(img_url, f"images/{img_name}")
                except Exception as e:
                    print(f"Img dl fail: {e}")

            # Create Chapter
            c_file_name = f"{clean_title}.xhtml"
            c_item = epub.EpubHtml(title=raw_title, file_name=c_file_name, lang='en')
            c_item.content = f'<h1>{raw_title}</h1>{body}'
            c_item.add_item(css_item) # Link CSS
            
            book.add_item(c_item)
            epub_chapters.append(c_item)

        book.toc = epub_chapters
        book.spine = ['nav'] + epub_chapters
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        out_dir = profile.get('directory', self.default_directory)
        if not os.path.exists(out_dir): os.makedirs(out_dir)
        full_path = os.path.join(out_dir, f"{filename}.epub")
        epub.write_epub(full_path, book)
        return full_path

    def sanitize(self, text):
        return re.sub(r'[^\w\-]', '_', text or "Untitled")

    def open_defaults_window(self):
        d = QDialog(self)
        l = QVBoxLayout(d)
        path = QLineEdit(self.default_directory)
        btn = QPushButton("Browse")
        btn.clicked.connect(lambda: path.setText(QFileDialog.getExistingDirectory(d, "Select Dir")))
        h = QHBoxLayout()
        h.addWidget(path)
        h.addWidget(btn)
        l.addLayout(h)
        save = QPushButton("Save")
        def save_defs():
            self.default_directory = path.text()
            with open("defaults.json", "w") as f: json.dump({'directory': path.text()}, f)
            d.accept()
        save.clicked.connect(save_defs)
        l.addWidget(save)
        d.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = KemonoWebnovelDownloader()
    w.show()
    sys.exit(app.exec())
