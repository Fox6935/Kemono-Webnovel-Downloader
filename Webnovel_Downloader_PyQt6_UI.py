from PyQt6.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QTreeWidget, QTreeWidgetItem, QLabel, QCheckBox, QMenu, QFileDialog, QDialog, QMessageBox, QFormLayout, QLineEdit, QProgressDialog, QAbstractItemView, QButtonGroup, QGridLayout
from PyQt6.QtCore import Qt, QSize, QTimer, QTime, QCoreApplication, QEvent, QRect, pyqtProperty, QPropertyAnimation, QPoint, QEasingCurve
from PyQt6.QtGui import QIcon, QFont, QPalette, QColor, QAction, QFontMetrics, QPainter, QPainterPath, QBrush, QPen
import json
import requests
from datetime import datetime, timedelta
from ebooklib import epub
import re
import os
import time

class QTogglePagination(QCheckBox):
    bg_color = pyqtProperty(QColor, lambda self: self._bg_color, lambda self, col: setattr(self, '_bg_color', col))
    circle_color = pyqtProperty(QColor, lambda self: self._circle_color, lambda self, col: setattr(self, '_circle_color', col))
    active_color = pyqtProperty(QColor, lambda self: self._active_color, lambda self, col: setattr(self, '_active_color', col))
    text_color = pyqtProperty(QColor, lambda self: self._text_color, lambda self, col: setattr(self, '_text_color', col))

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_color, self._circle_color, self._active_color, self._text_color = QColor("#CCC"), QColor("#FFF"), QColor('#4287f5'), QColor("#000")
        self._circle_pos = None
        self.setFixedHeight(18)
        self._animation_duration = 500
        self.stateChanged.connect(self.update_colors_and_position)
        self._user_checked = False
        self.stateChanged.connect(self.start_transition)

    circle_pos = pyqtProperty(float, lambda self: self._circle_pos, lambda self, pos: (setattr(self, '_circle_pos', pos), self.update()))

    def update_colors_and_position(self, state):
        if state == 2:  # Qt.CheckState.Checked is 2
            self._bg_color = self._active_color
            self._circle_pos = self.height() * 1.1
        else:
            self._bg_color = QColor("#CCC")
            self._circle_pos = self.height() * 0.1
        self.update()
        
    def mousePressEvent(self, event):
        self._user_checked = True
        super().mousePressEvent(event)

    def create_animation(self, state):
        animation = QPropertyAnimation(self, b'circle_pos', self)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.setDuration(self._animation_duration)
        animation.setStartValue(self.height() * 0.1 if state else self.height() * 1.1)
        animation.setEndValue(self.height() * 1.1 if state else self.height() * 0.1)
        print("Animation created")
        return animation

    def start_transition(self, state):
        animation = self.create_animation(state)
        if self._user_checked:
            animation.start()
            print("Animation started")
        else:
            self.update_colors_and_position(state)
        self._user_checked = False

    def showEvent(self, event):
        super().showEvent(event)
        self.update_colors_and_position(self.isChecked())

    def resizeEvent(self, event):
        self.update_colors_and_position(self.isChecked())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_color = QColor(self._bg_color)  # Use the dynamic property here
        circle_color = QColor(self._circle_color)
        text_color = QColor(self._text_color)

        bordersradius = self.height() / 2
        togglewidth = self.height() * 2
        circlesize = self.height() * 0.8

        bg_path = QPainterPath()
        bg_path.addRoundedRect(0, 0, togglewidth, self.height(), bordersradius, bordersradius)
        painter.fillPath(bg_path, QBrush(bg_color))  # This should now reflect the state's color

        circle = QPainterPath()
        circle.addEllipse(self._circle_pos, self.height() * 0.1, circlesize, circlesize)
        painter.fillPath(circle, QBrush(circle_color))

        painter.setPen(QPen(QColor(text_color)))
        painter.setFont(self.font())
        text_rect = QRect(int(togglewidth), 0, self.width() - int(togglewidth), self.height())
        text_rect.adjust(0, (self.height() - painter.fontMetrics().height()) // 2, 0, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        painter.end()

class QToggleAutomatic(QTogglePagination):
    def __init__(self, parent=None):
        super().__init__(parent)

class LoginWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login to Kemono")
        self.setModal(True)
        self.resize(300, 150)

        layout = QVBoxLayout(self)

        # Username input
        username_label = QLabel("Username:")
        self.username_input = QLineEdit()
        layout.addWidget(username_label)
        layout.addWidget(self.username_input)

        # Password input
        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(password_label)
        layout.addWidget(self.password_input)

        # Buttons
        button_layout = QHBoxLayout()
        self.login_button = QPushButton("Login")
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.login_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # Connect buttons
        self.login_button.clicked.connect(self.attempt_login)
        self.cancel_button.clicked.connect(self.reject)

    def attempt_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "Error", "Please enter both username and password.")
            return

        success = self.parent().login_to_kemono(username, password)
        if success:
            self.accept()  # This will close the login window
        else:
            QMessageBox.critical(self, "Error", "Login failed. Please check your credentials.")

class KemonoWebnovelDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Window settings
        self.setWindowTitle("Kemono Webnovel Downloader")
        self.setGeometry(100, 100, 500, 500)  # Position and size
        
        # Set up the central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #dbdbdb;
                font-size: 13px;  /* Double the font size */
            }
            QPushButton {
                background-color: #4287f5;
                border: none;
                color: white;
                padding: 13px 6px; /* Double the padding vertically, keep horizontal padding */
                text-align: center;
                text-decoration: none;
                font-size: 15px;  /* Double the font size */
                border-radius: 4px;
                font-family: 'Helvetica', sans-serif;
            }
            QPushButton:hover {
                background-color: #1064e8;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTreeWidget {
                background-color: #ffffff;
                color: black;
                font-size: 13px;  /* Double the font size */
                selection-background-color: #3470e6;
            }
            QLineEdit {
                background-color: #ffffff;  /* Entry background color, e.g., white */
                border: 1px solid #cccccc;  /* Light gray border */
                padding: 2px;
                font-size: 13px;  /* Match with general font size */
            }
        """)

        # Initialize all variables that might be needed during setup_ui or load_defaults
        self.default_directory = os.getcwd()
        self.default_webhook_url = ''
        self.output_directory = self.default_directory  # Set a default, will be updated by load_defaults
        self.automatic_mode = False  # Needed for UI setup
        self.cookies = {}  # Default empty cookies
        self.logged_in = False  # Default not logged in
        self.profiles = {}  # Default empty profiles

        # Initialize timer_label before setup_ui is called
        self.timer_label = QLabel("00:00")

        # Setup UI - this will create UI elements that might need the above variables
        self.setup_ui(layout)

        # Load session after UI setup but before loading profiles
        self.cookies = self.load_session() or self.cookies
        self.logged_in = bool(self.cookies)

        # Load defaults after UI setup so we can adjust UI elements like webhook_switch
        self.load_defaults()
        self.output_directory = self.default_directory  # Update with loaded defaults

        # Load profiles - now that defaults are loaded and UI is set up
        self.profiles = self.load_profiles()
        self.update_profile_list()

        # Initialize other variables that don't affect the initial setup
        self.profile_directories = {}
        self.is_fetching = False
        self.stop_fetching = False
        self.current_chapters = []
        self.current_url = ""
        self.automatic_mode_running = False
        self.timer_start_time = None
        self.sleep_time_seconds = 1800  # Change this value for a different "automatic mode" time interval

        # Update UI for login if logged in - called after all initializations
        if self.logged_in:
            self.update_ui_for_login()

    def setup_ui(self, layout):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        layout.addLayout(main_layout)
        
        # Create a layout for buttons at the top
        top_controls_layout = QHBoxLayout()
        main_layout.addLayout(top_controls_layout)

        # Common style for both buttons
        button_style = """
            QPushButton {
                background-color: #000000;
                color: white;
                border: none;
                padding: 7px 20px; /* Adjust padding for size */
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5b5b5b;
            }
        """

        # Defaults button on the left
        defaults_button = QPushButton("Defaults")
        defaults_button.setStyleSheet(button_style)
        defaults_button.clicked.connect(self.open_defaults_window)
        top_controls_layout.addWidget(defaults_button)

        # Refresh button in the middle
        refresh_button = QPushButton("Refresh")
        refresh_button.setStyleSheet(button_style)
        refresh_button.clicked.connect(self.refresh)
        top_controls_layout.addWidget(refresh_button)

        # Add stretch to push buttons apart
        top_controls_layout.addStretch(1)

        # Login button on the right
        self.login_button = QPushButton("Login")
        self.login_button.setStyleSheet(button_style)
        self.login_button.clicked.connect(self.open_login_window)
        top_controls_layout.addWidget(self.login_button)

        # Logout button, initially hidden
        self.logout_button = QPushButton("Logout")
        self.logout_button.setStyleSheet(button_style)
        self.logout_button.clicked.connect(self.logout)
        self.logout_button.setVisible(False)
        top_controls_layout.addWidget(self.logout_button)

        # Profile List
        self.profile_list = QTreeWidget()
        self.profile_list.setHeaderLabels(["Title", "Author", "URL"])
        self.profile_list.setColumnWidth(0, 150)  # Width for Title column
        self.profile_list.setColumnWidth(1, 150)  # Width for Author column
        self.profile_list.setColumnHidden(2, True)  # Hide URL column for aesthetics
        self.profile_list.itemClicked.connect(self.on_treeview_click)
        self.profile_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.profile_list.customContextMenuRequested.connect(self.show_context_menu)
        self.profile_list.itemSelectionChanged.connect(self.update_button_state)
        self.profile_list.viewport().installEventFilter(self)  # Add this to catch mouse events
        self.profile_list.setStyleSheet("""
            QTreeWidget::item:selected { 
                background: #3470e6;  /* Or any color you prefer for selection */
                color: white;  /* Ensure text is readable against the background */
            }
            QTreeWidget::item:hover {
                background: #e0e0e0;  /* Hover effect */
            }
            QTreeWidget::item:selected:hover {
                background: #205aa5;  /* Darker shade for selected and hovered */
                color: white;
            }
        """)
        main_layout.addWidget(self.profile_list)

        # Automatic Mode section
        automatic_layout = QHBoxLayout()
        main_layout.addLayout(automatic_layout)

        self.automatic_mode_switch = QToggleAutomatic(self)
        self.automatic_mode_switch.setText("Automatic Mode")
        self.automatic_mode_switch.setChecked(self.automatic_mode)
        self.automatic_mode_switch.setStyleSheet("""
            QToggleAutomatic {
                qproperty-bg_color: #CCC;  
                qproperty-circle_color: #FFF;
                qproperty-active_color: #4287f5;  
                qproperty-text_color: #000;
            }
        """)
        self.automatic_mode_switch.toggled.connect(self.toggle_automatic_mode)
        automatic_layout.addWidget(self.automatic_mode_switch)
        
        # Timer label is already initialized in __init__, just add it here.
        automatic_layout.addWidget(self.timer_label)

        # Webhook Toggle Switch (initially hidden)
        self.webhook_switch = QToggleAutomatic(self)
        self.webhook_switch.setText("Send to Discord Webhook")
        self.webhook_switch.setChecked(False)
        self.webhook_switch.setVisible(False)  # Initially hidden
        main_layout.addWidget(self.webhook_switch)

        # Buttons layout
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)

        add_profile_button = QPushButton("Add Profile")
        add_profile_button.clicked.connect(self.add_profile)
        button_layout.addWidget(add_profile_button)

        self.download_button = QPushButton("Download Preview")
        self.download_button.clicked.connect(self.preview_chapters)
        self.download_button.setEnabled(False)  # Initially disabled until a profile is selected
        button_layout.addWidget(self.download_button)

        # New one-click download button
        self.one_click_download_button = QPushButton("One-Click Download")
        self.one_click_download_button.clicked.connect(self.one_click_download)
        self.one_click_download_button.setEnabled(False)  # Initially disabled until a profile is selected
        button_layout.addWidget(self.one_click_download_button)

        # Update profile list
        self.update_profile_list()

        # Start automatic mode if it's on at startup
        if self.automatic_mode:
            self.start_automatic_mode()

    def login_to_kemono(self, username, password):
        url = "https://kemono.su/api/v1/authentication/login"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        data = {
            "username": username,
            "password": password
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            # Debugging response details
            print(f"Response headers: {response.headers}")
            print(f"Response cookies: {response.cookies.get_dict()}")
            print(f"Response content: {response.json()}")

            # Manually extract the session cookie from the Set-Cookie header
            cookies = response.cookies.get_dict()
            if not cookies.get("session"):
                # Parse the Set-Cookie header for the session cookie
                set_cookie_header = response.headers.get("Set-Cookie", "")
                for cookie in set_cookie_header.split(","):
                    if "session=" in cookie:
                        session_value = cookie.split("session=")[-1].split(";")[0]
                        cookies["session"] = session_value
                        break

            if "session" in cookies:
                self.save_session(cookies)  # Save the session for future use
                time.sleep(1)
                self.logged_in = True
                self.update_ui_for_login()
                QMessageBox.information(self, "Success", "Logged in successfully!")
                return True
            else:
                print("Login successful, but no session cookie was extracted.")
                QMessageBox.critical(self, "Error", "Login failed due to missing session cookie.")
                return False
        except requests.exceptions.RequestException as e:
            print(f"Login failed: {e}")
            if e.response is not None:
                print(f"Response content: {e.response.text}")
            QMessageBox.critical(self, "Error", "Login failed. Please check your credentials.")
            return False
            
    def open_login_window(self):
        login_window = LoginWindow(self)
        login_window.exec()

    def save_session(self, cookies):
        with open("session.json", "w") as file:
            json.dump(cookies, file)
        print("Session saved successfully.")

    def load_session(self):
        try:
            with open("session.json", "r") as file:
                cookies = json.load(file)
                print("Session loaded successfully.")
                return cookies
        except FileNotFoundError:
            print("No session file found.")
            return None

    def logout(self):
        try:
            os.remove("session.json")
        except FileNotFoundError:
            pass
        self.logged_in = False
        self.update_ui_for_logout()
        QMessageBox.information(self, "Logged Out", "You have been logged out.")

    def update_ui_for_login(self):
        self.login_button.setVisible(False)
        self.logout_button.setVisible(True)
        self.profiles = self.load_profiles()  # This now uses preferences.json if logged in
        self.update_profile_list()
        if self.logged_in:  # Save preferences after successful login
            self.save_preferences()

    def update_ui_for_logout(self):
        self.login_button.setVisible(True)
        self.logout_button.setVisible(False)
        self.profiles = self.load_profiles()  # This will now use profiles.json
        self.update_profile_list()

    def refresh(self):
        if self.logged_in:
            # Reload session
            self.cookies = self.load_session() or {}
            if not self.cookies:
                self.logged_in = False
                self.update_ui_for_logout()
                QMessageBox.warning(self, "Session Expired", "Your session has expired. Please log in again.")
            else:
                # Refresh profiles from API and update preferences.json
                try:
                    self.profiles = self.load_preferences_from_api()
                    self.save_preferences()  # Save the updated preferences back to preferences.json
                    QMessageBox.information(self, "Success", "Session and profiles refreshed from API.")
                except requests.exceptions.RequestException as e:
                    QMessageBox.critical(self, "Error", f"Failed to refresh from API: {e}")
        else:
            # Refresh profiles from profiles.json
            try:
                self.profiles = self.load_profiles_from_json()
                # No need to save since we're just reloading from the same file
                QMessageBox.information(self, "Success", "Profiles refreshed from JSON.")
            except json.JSONDecodeError as e:
                QMessageBox.critical(self, "Error", f"Failed to refresh from JSON: {e}")
        
        # Update UI to reflect changes
        self.update_profile_list()

    def fetch_from_kemono(self, url):
        try:
            response = requests.get(url, cookies=self.cookies)
            if response.status_code == 401:
                self.handle_session_expiry()
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch data: {e}")
            return None
            
    def load_defaults(self):
        try:
            with open('defaults.json', 'r') as file:
                defaults = json.load(file)
                self.default_directory = defaults.get('directory', '')
                if not self.default_directory:  # If directory is empty string or not set
                    self.default_directory = os.getcwd()  # Use current directory
                self.default_webhook_url = defaults.get('webhook_url', '')
                if self.is_valid_webhook_url(self.default_webhook_url):
                    self.webhook_switch.setVisible(True)
                else:
                    self.webhook_switch.setVisible(False)
        except FileNotFoundError:
            print("Defaults file not found, using current settings.")
            self.default_directory = os.getcwd()
            self.default_webhook_url = ''
            self.webhook_switch.setVisible(False)
        except json.JSONDecodeError:
            print("Error decoding defaults.json. Using default values.")
            self.default_directory = os.getcwd()
            self.default_webhook_url = ''
            self.webhook_switch.setVisible(False)

    def open_defaults_window(self):
        defaults_window = QDialog(self)
        defaults_window.setWindowTitle("Defaults")
        defaults_window.setModal(True)
        defaults_window.resize(350, 200)

        layout = QVBoxLayout(defaults_window)
        form_layout = QFormLayout()

        # Directory
        directory_input = QLineEdit(self.default_directory if self.default_directory is not None else '')
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(lambda: self.select_directory(directory_input))
        directory_layout = QHBoxLayout()
        directory_layout.addWidget(directory_input)
        directory_layout.addWidget(browse_button)
        form_layout.addRow("Directory:", directory_layout)

        # Webhook URL
        webhook_input = QLineEdit(self.default_webhook_url)
        form_layout.addRow("Webhook URL:", webhook_input)
        
        layout.addLayout(form_layout)

        # Save button
        save_button = QPushButton("Save Defaults")
        save_button.clicked.connect(lambda: self.save_defaults(directory_input.text(), webhook_input.text()))
        layout.addWidget(save_button)

        defaults_window.exec()

    def save_defaults(self, directory, webhook_url):
        defaults = {
            'directory': directory if directory else '',
            'webhook_url': webhook_url
        }
        with open('defaults.json', 'w') as file:
            json.dump(defaults, file, indent=4)

        # Reload the defaults immediately after saving
        self.load_defaults()

        # Validate webhook URL
        if self.is_valid_webhook_url(webhook_url):
            self.webhook_switch.setVisible(True)
        else:
            self.webhook_switch.setVisible(False)

        QMessageBox.information(self, "Success", "Defaults saved successfully.")

    def handle_session_expiry(self):
        QMessageBox.warning(self, "Session Expired", "Your session has expired. Please log in again.")
        self.logout()

    def is_valid_webhook_url(self, url):
        return re.match(r"^https://discord.com/api/webhooks/\d+/[\w-]+$", url) is not None

    def toggle_webhook_switch_visibility(self):
        webhook_url = self.webhook_input.text().strip()
        if self.is_valid_webhook_url(webhook_url):
            self.webhook_switch.setVisible(True)
        else:
            self.webhook_switch.setVisible(False)

    def send_epub_to_discord(self, epub_filepath, profile, force_send=False):
        if force_send or self.webhook_switch.isChecked():
            webhook_url = self.default_webhook_url.strip()
            if not webhook_url:
                print("No webhook URL provided.")
                return

            # Use the `with` statement to ensure the file is closed after reading
            with open(epub_filepath, 'rb') as file:
                files = {
                    'file': (os.path.basename(epub_filepath), file, 'application/epub+zip'),
                }
                payload = {
                    'content': f"New EPUB for **{profile['title']}** by {profile['author']}.",
                }
                try:
                    response = requests.post(webhook_url, data=payload, files=files)
                    response.raise_for_status()
                    print(f"Successfully sent EPUB '{os.path.basename(epub_filepath)}' to Discord.")
                except requests.exceptions.RequestException as e:
                    print(f"Failed to send EPUB '{os.path.basename(epub_filepath)}' to Discord: {e}")
            
            # Ensure the file handle is closed before attempting to delete the file
            try:
                self.safe_delete(epub_filepath)
                print(f"Temporary file '{epub_filepath}' deleted.")
            except PermissionError as e:
                print(f"Failed to delete temporary file '{epub_filepath}': {e}")
        else:
            print("Webhook sending is disabled.")
        
    def send_notification_to_discord(self, profile, new_chapters, force_send=False):
        print(f"Force send: {force_send}, Toggle checked: {self.webhook_switch.isChecked()}")
        if force_send or self.webhook_switch.isChecked():
            webhook_url = self.default_webhook_url.strip()
            if not webhook_url:
                print("No webhook URL provided.")
                return

        # Convert API URL to display URL
        original_url = next((key for key, val in self.profiles.items() if val.get('title') == profile['title'] and val.get('author') == profile['author']), None)
        if original_url:
            display_url = original_url.replace('/api/v1/', '/')
        else:
            print("Could not find matching profile URL.")
            display_url = "URL not found"

        # Create the message content
        content = f"**[{profile['author']}](<{display_url}>)** has been updated with {len(new_chapters)} new posts."

        payload = {
            'content': content
        }

        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            print(f"Successfully sent notification for {len(new_chapters)} new chapters to Discord.")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send notification to Discord: {e}")

    def safe_delete(self, filepath, retries=3, delay=1):
        for attempt in range(retries):
            try:
                os.remove(filepath)
                print(f"Successfully deleted temporary file: {filepath}")
                return
            except PermissionError as e:
                print(f"Attempt {attempt + 1} to delete {filepath} failed: {e}")
                time.sleep(delay)  # Wait before retrying
        print(f"Failed to delete temporary file: {filepath} after {retries} attempts.")
    
    def one_click_download(self):
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            QMessageBox.critical(self, "Error", "No profile selected.")
            return

        item = selected_items[0]
        url = item.text(2)  # Assuming URL is in the third column (index 2)
        profile = self.profiles.get(url)

        if not profile:
            QMessageBox.critical(self, "Error", "Profile not found.")
            return

        popup = self.show_loading_popup_with_cancel()
        self.stop_fetching = False  # Reset this since we're using it as a flag

        # Fetch all chapters in one go
        initial_chapters = self.fetch_kemono_chapters_silent(url)
        new_chapters = [ch for ch in initial_chapters if ch["published"] > profile.get("last_fetched", "")]

        if new_chapters:
            filename = self.generate_filename(new_chapters)
            epub_filepath = self.create_epub(new_chapters, profile["title"], profile["author"], url, filename)

            if self.webhook_switch.isChecked():
                # Send EPUB to Discord webhook
                self.send_epub_to_discord(epub_filepath, profile)
            else:
                QMessageBox.information(self, "Success", f"EPUB created at: {epub_filepath}")
            
            # Update `last_fetched` and save profiles
            profile["last_fetched"] = max(chap["published"] for chap in new_chapters)
            if self.logged_in:
                profile['AMU'] = profile['updated']  # Update AMU
                self.save_preferences()
            else:
                self.save_profiles()
        else:
            QMessageBox.information(self, "Info", "No new chapters to download.")

        if popup:
            popup.close()

    def toggle_automatic_mode(self, checked):
        self.automatic_mode = checked
        if checked:
            self.start_automatic_mode()
        else:
            self.stop_automatic_mode()

    def start_automatic_mode(self):
        self.automatic_mode_running = True
        self.automatic_fetch_cycle()
        self.update_timer()

    def stop_automatic_mode(self):
        self.automatic_mode_running = False

    def automatic_fetch_cycle(self):
        if not self.automatic_mode_running:
            return
        if self.logged_in:
            self.sleep_time_seconds = 300  # 5 minutes for logged in users
        popup = self.show_loading_popup_with_cancel()
        QTimer.singleShot(100, lambda: self.perform_automatic_fetch(popup))

    def perform_automatic_fetch(self, popup):
        if self.logged_in:
            profiles_to_update = []
            try:
                # Fetch favorites list to compare timestamps
                url = "https://kemono.su/api/v1/account/favorites?type=artist"
                response = requests.get(url, cookies=self.cookies)
                response.raise_for_status()
                latest_favorites = response.json()
                
                for api_profile in latest_favorites:
                    profile_url = f"https://kemono.su/api/v1/{api_profile['service']}/user/{api_profile['id']}/"
                    local_profile = self.profiles.get(profile_url)
                    if local_profile and local_profile.get('automatic_mode') != 'ignore':
                        api_updated = api_profile.get('updated', '')
                        local_amu = local_profile.get('AMU', '')
                        if api_updated > local_amu:
                            profiles_to_update.append(profile_url)
                
                for url in profiles_to_update:
                    if not self.automatic_mode_running or self.stop_fetching:
                        popup.close()
                        return
                    profile = self.profiles[url]
                    try:
                        self.fetch_new_chapters(url, profile)
                        # Delay only if chapters were fetched
                        time.sleep(3)  # Adjust delay as needed
                    except Exception as e:
                        print(f"Error fetching chapters for {profile['title']}: {e}")
                    QApplication.processEvents()  # Keep UI responsive
                    
                    # Update AMU after fetching
                    profile['AMU'] = profile['updated']
                    self.save_preferences()  # Since we know we're logged in, directly save preferences
                    
            except requests.exceptions.RequestException as e:
                print(f"Failed to fetch favorites list: {e}")

        else:  # Logged out mode remains the same
            for url, profile in self.profiles.items():
                if not self.automatic_mode_running or self.stop_fetching:
                    popup.close()
                    return
                if profile.get('automatic_mode') != 'ignore':
                    try:
                        self.fetch_new_chapters(url, profile)
                        # Delay only if chapters were fetched
                        time.sleep(3)  # Adjust delay as needed
                    except Exception as e:
                        print(f"Error fetching chapters for {profile['title']} (logged out): {e}")
                    QApplication.processEvents()  # Keep UI responsive
                    
                    if self.stop_fetching:
                        popup.close()
                        return

        popup.close()
        self.timer_start_time = datetime.now() + timedelta(seconds=self.sleep_time_seconds)
        self.update_timer()

    def update_timer(self):
        if self.automatic_mode_running:
            if self.timer_start_time is None:
                self.timer_start_time = datetime.now() + timedelta(seconds=self.sleep_time_seconds)
            
            current_qtime = QTime.currentTime()
            target_qtime = QTime.fromString(self.timer_start_time.strftime("%H:%M:%S"))
            remaining = current_qtime.secsTo(target_qtime)

            if remaining <= 0:
                self.timer_label.setText("00:00")
                self.timer_start_time = None
                # Restart the automatic fetch cycle
                self.automatic_fetch_cycle()
            else:
                minutes, seconds = divmod(remaining, 60)
                self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")
                
                # Schedule the next update
                QTimer.singleShot(1000, self.update_timer)
        else:
            self.timer_label.setText("00:00")

    def generate_filename(self, chapters):
        lowermost_title = chapters[-1]['title']
        uppermost_title = chapters[0]['title']
        default_filename = f"{self.sanitize_filename(lowermost_title)}-{self.sanitize_filename(uppermost_title)}" if len(chapters) > 1 else self.sanitize_filename(chapters[0]['title'])
        return default_filename

    def fetch_new_chapters(self, url, profile):
        last_fetched = profile.get("last_fetched", "")
        chapters = self.fetch_kemono_chapters_silent_auto(url, last_fetched)  # Fetch chapters
        new_chapters = [ch for ch in chapters if ch['published'] > last_fetched]

        if not new_chapters:
            print(f"No new chapters found for {profile['title']}.")  # Debug log
            return  # Exit early if no new chapters are found

        auto_mode = profile.get('automatic_mode', 'ignore')

        if auto_mode == 'ignore':
            return

        elif auto_mode == 'save_locally':
            filename = self.generate_filename(new_chapters)
            filepath = self.create_epub(new_chapters, profile['title'], profile['author'], url, filename)
            print(f"EPUB saved locally at: {filepath}")

        elif auto_mode == 'send_to_discord' or auto_mode == 'notification_only':
            if self.is_valid_webhook_url(self.default_webhook_url):
                if auto_mode == 'send_to_discord':
                    filename = self.generate_filename(new_chapters)
                    epub_filepath = self.create_epub(new_chapters, profile['title'], profile['author'], url, filename)
                    self.send_epub_to_discord(epub_filepath, profile, force_send=True)  # Ensure force_send is True
                else:  # notification_only
                    self.send_notification_to_discord(profile, new_chapters, force_send=True)  # Ensure force_send is True
            else:
                print("Webhook URL not valid or not set for automatic mode; skipping Discord actions.")

        # Update last_fetched only if a mode other than 'ignore' is selected
        if new_chapters and auto_mode != 'ignore':
            profile["last_fetched"] = max(chap['published'] for chap in new_chapters)
            profile['AMU'] = profile['updated']  # Update AMU
            if self.logged_in:
                self.save_preferences()
            else:
                self.save_profiles()

    def fetch_kemono_chapters_silent(self, feed_url):
        try:
            response = requests.get(feed_url)
            response.raise_for_status()
            data = response.json()
            print(f"Fetched {len(data)} chapters from URL: {feed_url}")
            return sorted(data, key=lambda x: x.get('published', ''), reverse=True)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching chapters: {e}")
            return []

    def fetch_kemono_chapters_silent_auto(self, feed_url, last_fetched=""):
        all_chapters = []
        max_retries = 3

        for attempt in range(max_retries):
            try:
                response = requests.get(feed_url)
                response.raise_for_status()
                data = response.json()

                # Filter out chapters older than `last_fetched`
                for chapter in data:
                    if last_fetched and chapter['published'] <= last_fetched:
                        print(f"Encountered chapter older than last_fetched. Stopping early.")
                        return sorted(all_chapters, key=lambda x: x.get('published', ''), reverse=True)
                    all_chapters.append(chapter)

                return sorted(all_chapters, key=lambda x: x.get('published', ''), reverse=True)

            except requests.exceptions.HTTPError as e:
                if response.status_code == 403:
                    print(f"403 Forbidden for URL: {feed_url}")
                    break
                elif attempt < max_retries - 1:
                    time.sleep(1 * (2 ** attempt))  # Exponential backoff
                else:
                    raise
            except Exception as e:
                print(f"Unexpected error while fetching chapters from {feed_url}: {e}")
                if attempt == max_retries - 1:
                    return sorted(all_chapters, key=lambda x: x.get('published', ''), reverse=True)

        return sorted(all_chapters, key=lambda x: x.get('published', ''), reverse=True)

    def update_button_state(self):
        selected_items = self.profile_list.selectedItems()
        state = bool(selected_items)
        self.download_button.setEnabled(state)
        self.one_click_download_button.setEnabled(state)
    
    def eventFilter(self, source, event):
        if source is self.profile_list.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                item = self.profile_list.itemAt(event.pos())
                if item is None:
                    self.profile_list.clearSelection()
                    return True  # Event handled
        return super().eventFilter(source, event)

    def show_context_menu(self, pos):
        item = self.profile_list.itemAt(pos)
        if item:
            self.profile_list.setCurrentItem(item)  # Similar to focus in Tkinter
            
            context_menu = QMenu(self)
            edit_action = QAction("Edit Profile", self)
            edit_action.triggered.connect(self.edit_profile)
            context_menu.addAction(edit_action)
            
            delete_action = QAction("Delete Profile", self)
            delete_action.triggered.connect(self.delete_profile)
            context_menu.addAction(delete_action)
            
            context_menu.exec(self.profile_list.mapToGlobal(pos))

    def on_treeview_click(self, item):
        if isinstance(item, QTreeWidgetItem):
            self.profile_list.setCurrentItem(item)
        else:
            self.profile_list.clearSelection()

    def sanitize_filename(self, filename):
        return re.sub(r'[^\w\s-]', '', filename).strip().replace(" ", "_")

    def fix_link(self, link):
        if not link or not isinstance(link, str):
            return None
        link = link.strip()

        # Check if it's a raw Patreon URL
        if "patreon.com" in link.lower():
            user_id = self.get_patreon_user_id(link)
            if user_id:
                link = f"https://kemono.su/api/v1/patreon/user/{user_id}"
            else:
                return None  # If we can't get the user ID, return None
        else:
            # Handle other links, ensuring they start with 'http' if they don't
            if not link.startswith("http"):
                link = f"https://{link.lstrip('/')}" if link.startswith("kemono.su") else f"https://kemono.su/{link.lstrip('/')}"
            
            # Normalize URL to ensure it uses the full path for kemono links
            if link.startswith("www."):
                link = f"https://{link}"
            if link.startswith("https://kemono.su/") and not link.startswith("https://kemono.su/api/v1/"):
                link = link.replace("https://kemono.su/", "https://kemono.su/api/v1/")
        
        return link if "kemono.su/api/v1/" in link else None

    def get_patreon_user_id(self, url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            # Look for the creator ID pattern directly in the response text
            match = re.search(r'"creator":\s*{\s*"data":\s*{\s*"id":\s*"(\d+)"', response.text)
            return match.group(1) if match else None
        except requests.RequestException:
            return None

    def show_loading_popup_with_cancel(self):
        popup = QDialog(self)
        popup.setWindowTitle("Loading")
        popup.setFixedSize(300, 100)

        layout = QVBoxLayout(popup)
        
        popup.progress_label = QLabel("0 chapters fetched", popup)  # Make it an attribute of popup
        layout.addWidget(popup.progress_label)
        
        cancel_button = QPushButton("Cancel", popup)
        cancel_button.clicked.connect(self.cancel_fetch)
        layout.addWidget(cancel_button)
        
        popup.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        # Center the dialog
        parent_rect = self.frameGeometry()
        center_point = parent_rect.center()
        popup.move(center_point.x() - popup.width() // 2, center_point.y() - popup.height() // 2)

        popup.show()
        return popup

    def cancel_fetch(self):
        self.stop_fetching = True
        # Optionally, close the popup immediately
        self.sender().parent().close()

    def create_epub(self, chapters, title, author, profile_url, filename):
        chapters = sorted(chapters, key=lambda x: x['published'])
        
        book = epub.EpubBook()
        book.set_language("en")
        book.set_title(title)
        book.add_author(author)

        epub_chapters = []
        for i, chapter in enumerate(chapters, start=1):
            chapter_title = chapter['title']
            content = f"<h1>{chapter_title}</h1>\n<p>{chapter.get('content', '')}</p>"

            # regex for images
            base_url = "https://n4.kemono.su/data"
            pattern = r'<img[^>]+src="([^"]+)"'
            matches = re.findall(pattern, content)
            for i2, match in enumerate(matches):
                full_url = base_url + match
                try:
                    print(f"Downloading {full_url}")
                    response = requests.get(full_url)
                    response.raise_for_status()
                    # Detect media type from headers
                    media_type = response.headers.get('Content-Type', 'image/jpeg')
                    image_name = match.split('/')[-1]  # Use last part of URL as filename
                    image_item = epub.EpubItem(
                        uid=f"img{i2 + 1}",
                        file_name=f"images/{image_name}",
                        media_type=media_type,
                        content=response.content
                    )
                    book.add_item(image_item)
                    print(f"Added {image_name} to the EPUB.")
                    # Replace image src to point to the correct internal path
                    content = content.replace(match, f"images/{image_name}")
                except requests.exceptions.RequestException as e:
                    print(f"Failed to download {full_url}: {e}")

            chapter_epub = epub.EpubHtml(title=chapter_title, file_name=f'chap_{i:02}.xhtml', lang='en')
            chapter_epub.content = content
            epub_chapters.append(chapter_epub)
            book.add_item(chapter_epub)

        book.toc = tuple(epub_chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav'] + epub_chapters

        # Check webhook switch
        if self.webhook_switch.isChecked():
            # Temporary file storage to send to Discord webhook
            temp_filepath = os.path.join(os.getcwd(), f"{self.sanitize_filename(filename)}.epub")
            epub.write_epub(temp_filepath, book)
            return temp_filepath
        else:
            # Save locally in the directory
            profile = self.profiles[profile_url]
            directory = profile.get('directory', self.default_directory)  # Use default if directory is empty or not set
            if not directory:
                directory = self.default_directory  # If it's an empty string, use default
            filename = f"{self.sanitize_filename(filename)}.epub"
            filepath = os.path.join(directory, filename)
            epub.write_epub(filepath, book)
            return filepath

    def load_profiles(self):
        if self.logged_in:
            return self.load_preferences_from_api()
        else:
            return self.load_profiles_from_json()

    def load_preferences_from_api(self):
        try:
            url = "https://kemono.su/api/v1/account/favorites?type=artist"
            response = requests.get(url, cookies=self.cookies)
            response.raise_for_status()
            profiles = response.json()
            
            # Load existing preferences
            existing_preferences = self.load_preferences_json() or {}

            preferences = {}
            for profile in profiles:
                profile_url = f"https://kemono.su/api/v1/{profile['service']}/user/{profile['id']}/"
                # Merge default values with existing preferences if any
                preferences[profile_url] = {
                    "title": existing_preferences.get(profile_url, {}).get('title', profile.get('name', "Unknown Title")),
                    "author": existing_preferences.get(profile_url, {}).get('author', profile.get('name', "Unknown Author")),
                    "last_fetched": existing_preferences.get(profile_url, {}).get('last_fetched', profile.get('updated', "")),
                    "directory": existing_preferences.get(profile_url, {}).get('directory', self.output_directory),
                    "automatic_mode": existing_preferences.get(profile_url, {}).get('automatic_mode', 'ignore'),
                    "updated": profile.get('updated', ""),
                    "AMU": existing_preferences.get(profile_url, {}).get('AMU', "")
                }
            return preferences
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch favorites: {e}")
            QMessageBox.critical(self, "Error", f"Failed to fetch favorites. Please try again. Error: {e}")
            return {}

    def load_preferences_json(self):
        try:
            with open("preferences.json", "r") as file:
                return json.load(file)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error for preferences.json: {e}")
            return None

    def load_profiles_from_json(self):
        try:
            with open("profiles.json", "r") as file:
                data = json.load(file)
                for url, profile in data.items():
                    if 'directory' not in profile or not profile['directory']:
                        profile['directory'] = self.output_directory
                    # Ensure automatic_mode exists with a default value
                    profile['automatic_mode'] = profile.get('automatic_mode', 'ignore')
                return data
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            QMessageBox.critical(self, "Error", f"The profiles.json file is not valid JSON. Error: {e}")
            return {}

    def save_profiles(self):
        for url, profile in self.profiles.items():
            # Ensure directory is included and is string type
            profile['directory'] = str(profile.get('directory', self.output_directory))
        with open("profiles.json", "w") as file:
            json.dump(self.profiles, file, indent=4)

    def save_preferences(self):
        with open("preferences.json", "w") as file:
            json.dump(self.profiles, file, indent=4)

    def add_profile(self):
        add_window = QDialog(self)
        add_window.setWindowTitle("Add New Profile")
        add_window.setModal(True)

        # Calculate position relative to parent window
        parent_rect = self.frameGeometry()
        center_point = parent_rect.center()
        add_window.setGeometry(center_point.x() - 225, center_point.y() - 125, 450, 250)  # Adjusted for PyQt's different coordinate system

        layout = QVBoxLayout()

        # Profile data dictionary
        profile_data = {
            'url': QLineEdit(),
            'title': QLineEdit(),
            'author': QLineEdit(),
            'directory': QLineEdit(),
            'automatic_mode_options': {
                'ignore': QCheckBox("Ignore"),
                'save_locally': QCheckBox("Save locally"),
                'send_to_discord': QCheckBox("Send to discord"),
                'notification_only': QCheckBox("Send notification only")
            }
        }

        # Helper functions
        def submit_profile():
            url = profile_data['url'].text()
            title = profile_data['title'].text()
            author = profile_data['author'].text()
            directory = profile_data['directory'].text().strip()  # Remove whitespace
            if not directory:  # If directory is blank after stripping, consider it None
                directory = None
            
            fixed_url = self.fix_link(url)
            if not fixed_url:
                QMessageBox.critical(self, "Error", "Invalid or unrecognized URL.")
                return
            
            # Check which automatic mode option is selected
            auto_mode = None
            for key, checkbox in profile_data['automatic_mode_options'].items():
                if checkbox.isChecked():
                    auto_mode = key
                    break
            if auto_mode is None:
                auto_mode = 'ignore'  # Default to 'ignore' if no checkbox is checked
            
            if self.logged_in:
                # Convert the URL to the format needed for favorites API
                parts = fixed_url.split('/')
                if len(parts) >= 6 and parts[3] == 'api' and parts[4] == 'v1' and parts[5] in ['patreon', 'fanbox', 'pixiv', 'fantia', 'dlsite', 'gumroad', 'subscribestar']:
                    service = parts[5]
                    if len(parts) >= 8 and parts[6] == 'user':
                        creator_id = parts[7]
                        favorites_url = f"https://kemono.su/api/v1/favorites/creator/{service}/{creator_id}"
                        try:
                            response = requests.post(
                                favorites_url,
                                headers={'accept': '*/*'},
                                cookies=self.cookies
                            )
                            response.raise_for_status()
                            # After adding, fetch updated favorites to ensure it's included
                            self.profiles = self.load_profiles()
                            self.update_profile_list()
                            QMessageBox.information(self, "Success", "Creator added to favorites.")
                        except requests.exceptions.RequestException as e:
                            print(f"Failed to add to favorites: {e}")
                            QMessageBox.critical(self, "Error", f"Failed to add creator to favorites: {e}")
                    else:
                        QMessageBox.critical(self, "Error", "URL does not specify a user.")
                else:
                    QMessageBox.critical(self, "Error", "URL does not match expected format for adding to favorites.")
            else:
                # Add to local profiles.json
                if fixed_url in self.profiles:
                    QMessageBox.warning(self, "Warning", "This profile already exists.")
                    return
                
                self.profiles[fixed_url] = {
                    "title": title if title else "Unknown Title", 
                    "author": author if author else "Unknown Author", 
                    "last_fetched": "", 
                    "directory": directory if directory else '',  # Save empty string if directory is blank
                    "automatic_mode": auto_mode
                }
                self.update_profile_list()
                self.save_profiles()
            
            add_window.accept()  # Closes the dialog

        # Form layout for entries
        form_layout = QFormLayout()
        form_layout.addRow("URL:", profile_data['url'])
        form_layout.addRow("Title:", profile_data['title'])
        form_layout.addRow("Author:", profile_data['author'])
        
        directory_layout = QHBoxLayout()
        directory_layout.addWidget(profile_data['directory'])
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(lambda: self.select_directory(profile_data['directory']))
        directory_layout.addWidget(browse_button)
        form_layout.addRow("Directory:", directory_layout)
        
        layout.addLayout(form_layout)

        # Automatic mode checkbox group
        auto_mode_group = QButtonGroup(add_window)
        auto_mode_layout = QGridLayout()
        auto_mode_layout.addWidget(QLabel("Automatic mode:"), 0, 0, 1, 4, alignment=Qt.AlignmentFlag.AlignCenter)

        col = 0
        for i, (key, checkbox) in enumerate(profile_data['automatic_mode_options'].items()):
            checkbox.setChecked(key == 'ignore')  # Default to 'ignore'
            auto_mode_layout.addWidget(checkbox, 1, col)
            auto_mode_group.addButton(checkbox)
            col += 1
            checkbox.toggled.connect(lambda checked, cb=checkbox: [b.setChecked(False) for b in auto_mode_group.buttons() if b != cb] if checked else None)

        layout.addLayout(auto_mode_layout)

        # Submit button
        submit_button = QPushButton("Submit")
        submit_button.clicked.connect(submit_profile)
        layout.addWidget(submit_button, alignment=Qt.AlignmentFlag.AlignCenter)

        add_window.setLayout(layout)
        add_window.exec()

    def select_directory(self, directory_var):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory for EPUBs")
        if directory:
            directory_var.setText(directory)

    def edit_profile(self):
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            QMessageBox.critical(self, "Error", "No profile selected.")
            return
        
        item = selected_items[0]
        url = item.text(2)  # Assuming URL is in the third column (index 2)
        profile = self.profiles.get(url)

        if not profile:
            QMessageBox.critical(self, "Error", "Profile not found.")
            return

        edit_window = QDialog(self)
        edit_window.setWindowTitle("Edit Profile")
        edit_window.setModal(True)

        # Calculate position relative to parent window
        parent_rect = self.frameGeometry()
        center_point = parent_rect.center()
        edit_window.setGeometry(center_point.x() - 225, center_point.y() - 125, 450, 250)

        layout = QVBoxLayout()

        # Profile data dictionary
        profile_data = {
            'url': QLineEdit(url),
            'title': QLineEdit(profile.get('title', "")),
            'author': QLineEdit(profile.get('author', "")),
            'directory': QLineEdit(profile.get('directory', self.output_directory)),
            'automatic_mode_options': {
                'ignore': QCheckBox("Ignore"),
                'save_locally': QCheckBox("Save locally"),
                'send_to_discord': QCheckBox("Send to discord"),
                'notification_only': QCheckBox("Send notification only")
            }
        }
        for key, checkbox in profile_data['automatic_mode_options'].items():
            checkbox.setChecked(profile.get('automatic_mode', 'ignore') == key)

        # Disable URL editing when logged in
        if self.logged_in:
            profile_data['url'].setReadOnly(True)
            profile_data['url'].setStyleSheet("color: gray;")  # Optional: make it visually clear it's not editable

        # Helper functions
        def update_profile():
            new_url = profile_data['url'].text()
            new_title = profile_data['title'].text()
            new_author = profile_data['author'].text()
            new_directory = profile_data['directory'].text().strip()  # Remove whitespace
            
            # Check which automatic mode option is selected
            auto_mode = None
            for key, checkbox in profile_data['automatic_mode_options'].items():
                if checkbox.isChecked():
                    auto_mode = key
                    break
            if auto_mode is None:
                auto_mode = 'ignore'  # Default to 'ignore' if no checkbox is checked

            if self.logged_in:
                # URL cannot be changed, so we keep the original URL
                new_fixed_url = url
            else:
                new_fixed_url = self.fix_link(new_url)
                if not new_fixed_url:
                    QMessageBox.critical(self, "Error", "Invalid or unrecognized URL.")
                    return

            if new_fixed_url != url and new_fixed_url in self.profiles:
                QMessageBox.warning(self, "Warning", "This profile URL already exists.")
                return
            
            if new_fixed_url != url:
                last_fetched = profile.get("last_fetched", "")
                del self.profiles[url]
                self.profiles[new_fixed_url] = {
                    "title": new_title if new_title else "Unknown Title", 
                    "author": new_author if new_author else "Unknown Author", 
                    "last_fetched": last_fetched, 
                    "directory": new_directory if new_directory else '',  # Save empty string if directory is blank
                    "automatic_mode": auto_mode
                }
            else:
                self.profiles[url].update({
                    "title": new_title if new_title else "Unknown Title",
                    "author": new_author if new_author else "Unknown Author",
                    "directory": new_directory if new_directory else '',
                    "automatic_mode": auto_mode
                })

            self.update_profile_list()
            if self.logged_in:
                self.save_preferences()
            else:
                self.save_profiles()
            edit_window.accept()

        # Form layout for entries
        form_layout = QFormLayout()
        form_layout.addRow("URL:", profile_data['url'])
        form_layout.addRow("Title:", profile_data['title'])
        form_layout.addRow("Author:", profile_data['author'])
        
        directory_layout = QHBoxLayout()
        directory_layout.addWidget(profile_data['directory'])
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(lambda: self.select_directory(profile_data['directory']))
        directory_layout.addWidget(browse_button)
        form_layout.addRow("Directory:", directory_layout)
        
        layout.addLayout(form_layout)

        # Automatic mode checkbox group
        auto_mode_group = QButtonGroup(edit_window)
        auto_mode_layout = QGridLayout()
        auto_mode_layout.addWidget(QLabel("Automatic mode:"), 0, 0, 1, 4, alignment=Qt.AlignmentFlag.AlignCenter)

        col = 0
        for i, (key, checkbox) in enumerate(profile_data['automatic_mode_options'].items()):
            auto_mode_layout.addWidget(checkbox, 1, col)
            auto_mode_group.addButton(checkbox)
            col += 1
            checkbox.toggled.connect(lambda checked, cb=checkbox: [b.setChecked(False) for b in auto_mode_group.buttons() if b != cb] if checked else None)

        layout.addLayout(auto_mode_layout)

        # Update button
        update_button = QPushButton("Update")
        update_button.clicked.connect(update_profile)
        layout.addWidget(update_button, alignment=Qt.AlignmentFlag.AlignCenter)

        edit_window.setLayout(layout)
        edit_window.exec()

    def delete_profile(self):
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            QMessageBox.critical(self, "Error", "No profile selected.")
            return
        
        item = selected_items[0]
        url = item.text(2)  # Assuming URL is in the third column (index 2)
        
        if self.logged_in:
            # Convert the URL to the format needed for favorites API
            fixed_url = self.fix_link(url)
            if not fixed_url:
                QMessageBox.critical(self, "Error", "Invalid or unrecognized URL.")
                return

            parts = fixed_url.split('/')
            if len(parts) >= 6 and parts[3] == 'api' and parts[4] == 'v1' and parts[5] in ['patreon', 'fanbox', 'pixiv', 'fantia', 'dlsite', 'gumroad', 'subscribestar']:
                service = parts[5]
                if len(parts) >= 8 and parts[6] == 'user':
                    creator_id = parts[7]
                    favorites_url = f"https://kemono.su/api/v1/favorites/creator/{service}/{creator_id}"
                    try:
                        response = requests.delete(
                            favorites_url,
                            headers={'accept': '*/*'},
                            cookies=self.cookies
                        )
                        response.raise_for_status()
                        # After removing, fetch updated favorites to ensure it's removed
                        self.profiles = self.load_profiles()
                        self.update_profile_list()
                        QMessageBox.information(self, "Success", "Creator removed from favorites.")
                    except requests.exceptions.RequestException as e:
                        print(f"Failed to remove from favorites: {e}")
                        QMessageBox.critical(self, "Error", f"Failed to remove creator from favorites: {e}")
                else:
                    QMessageBox.critical(self, "Error", "URL does not specify a user.")
            else:
                QMessageBox.critical(self, "Error", "URL does not match expected format for removing from favorites.")
        else:
            if url in self.profiles:
                del self.profiles[url]
                self.update_profile_list()
                self.save_profiles()
            else:
                QMessageBox.warning(self, "Warning", "Profile not found.")

    def update_profile_list(self):
        self.profile_list.clear()  # Clear all items before updating
        
        if self.logged_in:
            sorted_profiles = sorted(self.profiles.items(), key=lambda x: x[1].get('updated', ''), reverse=True)
        else:
            # If not logged in, you might want to keep the order as it is or sort by something else if needed
            sorted_profiles = list(self.profiles.items())

        for url, details in sorted_profiles:
            item = QTreeWidgetItem([details['title'], details['author'], url])
            self.profile_list.addTopLevelItem(item)
        
        # Update button state based on selection
        has_selection = bool(self.profile_list.selectedItems())
        self.download_button.setEnabled(has_selection)
        self.one_click_download_button.setEnabled(has_selection)

    def preview_chapters(self):
        if self.is_fetching:
            QMessageBox.information(self, "Fetching", "Already fetching chapters. Please wait.")
            print("Fetch already in progress.")  # Debug log
            return

        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            QMessageBox.critical(self, "Error", "No profile selected.")
            print("No profile selected.")  # Debug log
            return

        item = selected_items[0]
        url = item.text(2)  # Assuming the URL is in the third column (index 2)
        print(f"Starting fetch for URL: {url}")  # Debug log
        
        # Fetch chapters
        chapters = self.fetch_kemono_chapters_silent(url)
        profile = self.profiles.get(url)
        last_fetched = profile.get("last_fetched", "")
        
        # Set the 'is_new' flag for all chapters
        for chapter in chapters:
            chapter['is_new'] = chapter["published"] > last_fetched
        
        # Use a single shot timer to delay the preview operation, allowing the UI to update
        QTimer.singleShot(100, lambda: self.preview_chapters_with_data(chapters))

    def preview_chapters_with_data(self, chapters):
        try:
            print(f"Displaying preview for {len(chapters)} chapters.")  # Debug log
            self.current_chapters = chapters
            self.current_offset = 0  # Initialize offset for pagination
            self.current_url = None  # URL of the currently previewed profile

            if not chapters:
                QMessageBox.critical(self, "Error", "No chapters found for this profile.")
                print("No chapters found.")  # Debug log
                return

            selected_items = self.profile_list.selectedItems()
            if not selected_items:
                print("No profile selected.")  # Debug log
                return

            item = selected_items[0]
            self.current_url = item.text(2)  # Assuming URL is in the third column (index 2)
            profile = self.profiles.get(self.current_url)
            if not profile:
                QMessageBox.critical(self, "Error", "Profile not found.")
                print("Profile not found.")  # Debug log
                return

            # Prepare the preview window
            self.preview_window = QDialog(self)
            self.preview_window.setWindowTitle("Chapter Preview")
            self.preview_window.setModal(True)
            self.preview_window.resize(500, 500)

            layout = QVBoxLayout(self.preview_window)

            # Tree widget for displaying chapters
            self.tree = QTreeWidget()
            self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Changed here
            self.tree.setHeaderLabels(["Title", "Published Date"])
            self.tree.setStyleSheet("""
                QTreeWidget::item:selected {
                    background: #3470e6;
                    color: white;
                }
                QTreeWidget::item:hover {
                    background: #e0e0e0;
                }
                QTreeWidget::item:selected:hover {
                    background: #205aa5;  /* Darker shade for selected and hovered */
                    color: white;
                }
            """)
            
            def adjust_column_widths():
                total_width = self.tree.width() - 25
                self.tree.setColumnWidth(0, total_width // 2)  # Title
                self.tree.setColumnWidth(1, total_width // 2)  # Published Date

            # Use a timer to adjust widths when the dialog is shown
            QTimer.singleShot(100, adjust_column_widths)  # Adjust once when the dialog is shown

            # Populate the tree widget
            for chapter in chapters:
                item = QTreeWidgetItem([chapter['title'], chapter['published']])
                if chapter.get('is_new', False):
                    item.setBackground(0, QColor(144, 238, 144))  # Highlight new chapters
                self.tree.addTopLevelItem(item)
            
            layout.addWidget(self.tree)

            # Buttons for loading additional chapters
            button_layout = QHBoxLayout()

            load_next_button = QPushButton("Load Next 50 Chapters")
            load_next_button.clicked.connect(self.load_next_50_chapters)
            button_layout.addWidget(load_next_button)

            load_all_button = QPushButton("Load All Chapters")
            load_all_button.clicked.connect(self.load_all_chapters)
            button_layout.addWidget(load_all_button)

            layout.addLayout(button_layout)

            # Download button
            download_button = QPushButton("Download")
            download_button.clicked.connect(self.save_and_edit_metadata)
            layout.addWidget(download_button)

            self.preview_window.exec()

        except Exception as e:
            print(f"Error in preview_chapters_with_data: {e}")
            import traceback
            traceback.print_exc()
            
    def add_chapters_to_preview(self, chapters):
        for chapter in chapters:
            item = QTreeWidgetItem([chapter['title'], chapter['published']])
            self.tree.addTopLevelItem(item)

    def load_next_50_chapters(self):
        if not self.current_url:
            print("No profile URL found for loading next chapters.")
            return

        self.current_offset += 50  # Increment offset
        paginated_url = f"{self.current_url}?o={self.current_offset}"

        try:
            response = requests.get(paginated_url)
            response.raise_for_status()
            new_chapters = response.json()

            if not new_chapters:
                QMessageBox.information(self.preview_window, "Info", "No more chapters to load.")
                self.current_offset -= 50  # Revert offset if no new chapters
                return

            self.current_chapters.extend(new_chapters)  # Add new chapters to the current list
            self.add_chapters_to_preview(new_chapters)  # Update the preview dynamically
            print(f"Loaded next 50 chapters. Total chapters: {len(self.current_chapters)}.")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self.preview_window, "Error", f"Failed to load next chapters: {e}")
            
    def load_all_chapters(self):
        if not self.current_url:
            print("No profile URL found for loading all chapters.")
            return

        while True:
            self.current_offset += 50
            paginated_url = f"{self.current_url}?o={self.current_offset}"

            try:
                response = requests.get(paginated_url)
                response.raise_for_status()
                new_chapters = response.json()

                if not new_chapters:
                    QMessageBox.information(self.preview_window, "Info", "All chapters have been loaded.")
                    return

                self.current_chapters.extend(new_chapters)  # Add new chapters to the current list
                self.add_chapters_to_preview(new_chapters)  # Update the preview dynamically
                print(f"Loaded 50 more chapters. Total chapters: {len(self.current_chapters)}.")

            except requests.exceptions.RequestException as e:
                QMessageBox.critical(self.preview_window, "Error", f"Failed to load chapters: {e}")
                break

    def save_and_edit_metadata(self):
        selected_items = self.sender().parent().findChild(QTreeWidget).selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "No chapters selected for download.")
            return

        selected_chapters = []
        for item in selected_items:
            chapter = next((ch for ch in self.current_chapters if ch['title'] == item.text(0) and ch['published'] == item.text(1)), None)
            if chapter:
                selected_chapters.append(chapter)

        if not selected_chapters:
            QMessageBox.warning(self, "No Selection", "No chapters matched the selection.")
            return

        # Sort chapters by publication date
        sorted_chapters = sorted(selected_chapters, key=lambda x: x['published'])
        
        if sorted_chapters:
            lowermost_title = sorted_chapters[0]['title']
            uppermost_title = sorted_chapters[-1]['title']
            default_filename = f"{self.sanitize_filename(lowermost_title)}-{self.sanitize_filename(uppermost_title)}" if len(sorted_chapters) > 1 else self.sanitize_filename(sorted_chapters[0]['title'])
            metadata = {
                "title": self.profiles[self.current_url]["title"],
                "author": self.profiles[self.current_url]["author"],
                "filename": default_filename
            }

            metadata_window = QDialog(self)
            metadata_window.setWindowTitle("Edit Metadata")
            metadata_window.setModal(True)
            metadata_window.resize(300, 100)

            # Positioning the metadata window
            parent_rect = self.frameGeometry()
            center_point = parent_rect.center()
            metadata_window.move(center_point.x() - metadata_window.width() // 2, center_point.y() - metadata_window.height() // 2)

            layout = QVBoxLayout(metadata_window)
            
            form_layout = QFormLayout()
            title_entry = QLineEdit(metadata["title"])
            author_entry = QLineEdit(metadata["author"])
            filename_entry = QLineEdit(metadata["filename"])
            form_layout.addRow("Title:", title_entry)
            form_layout.addRow("Author:", author_entry)
            form_layout.addRow("Filename:", filename_entry)
            layout.addLayout(form_layout)

            save_button = QPushButton("Save and Download")
            save_button.clicked.connect(lambda: self.save_metadata_and_download(metadata_window, title_entry, author_entry, filename_entry, sorted_chapters))
            layout.addWidget(save_button)

            metadata_window.exec()
        else:
            QMessageBox.warning(self, "Error", "Failed to sort chapters for filename.")

    def save_metadata_and_download(self, window, title_entry, author_entry, filename_entry, chapters):
        new_title = title_entry.text()
        new_author = author_entry.text()  # Corrected to use author_entry
        new_filename = filename_entry.text()

        # Create the EPUB
        epub_filepath = self.create_epub(chapters, new_title, new_author, self.current_url, new_filename)
        
        if self.webhook_switch.isChecked():
            # Send to Discord webhook and delete temporary file after upload
            self.send_epub_to_discord(epub_filepath, self.profiles[self.current_url])
        else:
            # Notify the user that the EPUB has been saved locally
            QMessageBox.information(self, "Success", f"EPUB created at: {epub_filepath}")

        # Update `last_fetched` after creating/sending the EPUB
        profile = self.profiles[self.current_url]  # Fetch the profile
        profile["last_fetched"] = max(chap["published"] for chap in chapters)
        if self.logged_in:
            profile['AMU'] = profile["last_fetched"]  # Update AMU with the new last_fetched
            self.save_preferences()
        else:
            self.save_profiles()
        window.accept()

    def resizeEvent(self, event):
        # Adjust width for profile list
        total_width = self.profile_list.width() - 2  # -2 for possible border or margin
        self.profile_list.setColumnWidth(0, total_width // 2)  # Title
        self.profile_list.setColumnWidth(1, total_width // 2)  # Author
        
        super().resizeEvent(event)  # Call the base class implementation

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)  # Initialize QApplication
    main_window = KemonoWebnovelDownloader()
    main_window.show()
    sys.exit(app.exec())  # Run the event loop
