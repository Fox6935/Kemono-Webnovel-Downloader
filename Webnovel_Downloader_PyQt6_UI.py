from PyQt6.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QTreeWidget, QTreeWidgetItem, QLabel, QCheckBox, QMenu, QFileDialog, QDialog, QMessageBox, QFormLayout, QLineEdit, QProgressDialog, QAbstractItemView
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
        
        # Initialize PyQt equivalents of the variables
        self.profiles = self.load_profiles()
        self.profile_directories = {}  # New dictionary to store custom directories
        self.output_directory = os.getcwd()

        self.is_fetching = False
        self.stop_fetching = False
        self.paginate_chapters = False  # PyQt6 uses bool instead of BooleanVar
        self.current_chapters = []
        self.current_url = ""
        
        self.automatic_mode_running = False
        self.timer_start_time = None
        self.timer_label = QLabel("00:00")
        self.automatic_mode = False
        self.sleep_time_seconds = 30  # Change this value for a different "automatic mode" time interval
        
        # Setup UI
        self.setup_ui(layout)

    def setup_ui(self, layout):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        layout.addLayout(main_layout)

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

        # Pagination toggle switch
        self.pagination_switch = QTogglePagination(self)
        self.pagination_switch.setText("Fetch All Chapters")
        self.pagination_switch.setChecked(self.paginate_chapters)
        self.pagination_switch.setStyleSheet("""
            QTogglePagination {
                qproperty-bg_color: #CCC;  
                qproperty-circle_color: #FFF;
                qproperty-active_color: #4287f5;  
                qproperty-text_color: #000;
            }
        """)
        self.pagination_switch.toggled.connect(self.toggle_paginate)
        main_layout.addWidget(self.pagination_switch)

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
        
        # Ensure the timer label is still in the layout
        self.timer_label = QLabel("00:00")
        automatic_layout.addWidget(self.timer_label)

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
    
    def toggle_paginate(self, checked):
        self.paginate_chapters = checked
        print(f"paginate_chapters changed to: {self.paginate_chapters}")
        print(f"QTogglePagination checked state: {self.pagination_switch.isChecked()}")
        self.pagination_switch.update()  # Force repaint
    
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

        # Fetch only the first batch of chapters without pagination
        initial_chapters = self.fetch_kemono_chapters_silent(url, paginate=False)
        new_chapters = [ch for ch in initial_chapters if ch['published'] > profile.get("last_fetched", "")]

        if new_chapters:
            QTimer.singleShot(100, lambda: self.check_and_download_new_chapters(popup, url, profile, new_chapters))
        else:
            QMessageBox.information(self, "Info", "No new chapters to download.")
            if popup:
                popup.close()

    def check_and_download_new_chapters(self, popup, url, profile, paginate=False):
        try:
            last_fetched = profile.get("last_fetched", "")
            new_chapters = []
            offset = 0
            max_retries = 3

            while True:
                if self.stop_fetching:
                    print("Fetching canceled.")
                    break

                paginated_url = f"{url}?o={offset}" if paginate else url
                for attempt in range(max_retries + 1):
                    if self.stop_fetching:
                        print("Fetch stopped during retry.")
                        break

                    try:
                        response = requests.get(paginated_url)
                        response.raise_for_status()
                        data = response.json()
                        
                        # Only add new chapters
                        batch_new_chapters = [ch for ch in data if ch['published'] > last_fetched]
                        if batch_new_chapters:
                            new_chapters.extend(batch_new_chapters)
                        else:
                            # If no new chapters in this batch, stop fetching
                            if not paginate or not data:
                                break

                        if not data:  # No more chapters returned
                            break

                        offset += 50  # Move to the next batch of chapters
                        break  # Successful fetch, move to next batch

                    except requests.exceptions.RequestException as e:
                        print(f"Error fetching chapters: {e}")
                        if attempt == max_retries:
                            raise
                        time.sleep(1 * (2 ** attempt))  # Exponential backoff

                if not data or (paginate and not batch_new_chapters):  # Stop if no more data or no new chapters when paginating
                    break

            if new_chapters:
                filename = self.generate_filename(new_chapters)
                filepath = self.create_epub(new_chapters, profile['title'], profile['author'], url, filename)
                QMessageBox.information(self, "Success", f"New chapters downloaded and saved at: {filepath}")
                profile["last_fetched"] = max(chap['published'] for chap in new_chapters)
                self.save_profiles()  # Save updated profiles
            else:
                QMessageBox.information(self, "Info", "No new chapters to download.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while downloading: {e}")

        finally:
            self.stop_fetching = False  # Reset for next use
            if popup:
                popup.close()  # Close the popup when done or cancelled

    def toggle_automatic_mode(self, checked):
        self.automatic_mode = checked
        if checked:
            self.start_automatic_mode()
        else:
            self.stop_automatic_mode()

    def start_automatic_mode(self):
        self.automatic_mode_running = True
        self.automatic_fetch_cycle()

    def stop_automatic_mode(self):
        self.automatic_mode_running = False

    def automatic_fetch_cycle(self):
        if not self.automatic_mode_running:
            return
        popup = self.show_loading_popup_with_cancel()
        QTimer.singleShot(100, lambda: self.perform_automatic_fetch(popup))

    def perform_automatic_fetch(self, popup):
        for url, profile in self.profiles.items():
            if not self.automatic_mode_running or self.stop_fetching:
                popup.close()
                return
            if profile.get('opt_in_for_automatic_mode', False):
                self.fetch_new_chapters(url, profile)
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
            
            # Convert datetime to QTime for comparison
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
                
                # Use QTimer for scheduling updates
                QTimer.singleShot(1000, self.update_timer)  # Update every second

    def generate_filename(self, chapters):
        lowermost_title = chapters[-1]['title']
        uppermost_title = chapters[0]['title']
        default_filename = f"{self.sanitize_filename(lowermost_title)}-{self.sanitize_filename(uppermost_title)}" if len(chapters) > 1 else self.sanitize_filename(chapters[0]['title'])
        return default_filename

    def fetch_new_chapters(self, url, profile):
        last_fetched = profile.get("last_fetched", "")
        chapters = self.fetch_kemono_chapters_silent_auto(url)
        new_chapters = [ch for ch in chapters if ch['published'] > last_fetched]
        if new_chapters:
            filename = self.generate_filename(new_chapters)
            filepath = self.create_epub(new_chapters, profile['title'], profile['author'], url, filename)
            # Update last_fetched
            profile["last_fetched"] = max(chap['published'] for chap in new_chapters)
            self.save_profiles()  # Save updated profiles

    def fetch_kemono_chapters_silent(self, feed_url, paginate=None):
        if paginate is None:
            paginate = self.paginate_chapters  # Use the instance variable if not specified

        all_chapters = []
        offset = 0
        while True:
            paginated_url = f"{feed_url}?o={offset}" if paginate else feed_url
            response = requests.get(paginated_url)
            response.raise_for_status()
            data = response.json()
            if not data:
                break
            all_chapters.extend(data)
            if not paginate:  # Stop after the first fetch if not paginating
                break
            offset += 50
        return sorted(all_chapters, key=lambda x: x.get('published', ''), reverse=True)

    def fetch_kemono_chapters_silent_auto(self, feed_url):
        response = requests.get(feed_url)
        response.raise_for_status()
        data = response.json()
        return sorted(data, key=lambda x: x.get('published', ''), reverse=True) 

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

    def fetch_kemono_chapters(self, feed_url):
        self.is_fetching = True
        self.stop_fetching = False

        # Show a popup that can be cancelled
        popup = self.show_loading_popup_with_cancel()

        # Use a single shot timer to delay the fetch operation, allowing the UI to update
        QTimer.singleShot(100, lambda: self.start_fetching(popup, feed_url))

    def start_fetching(self, popup, feed_url):
        all_chapters = []
        offset = 0
        max_retries = 3

        try:
            while True:
                if self.stop_fetching:
                    print("Fetching canceled.")
                    break

                paginated_url = f"{feed_url}?o={offset}" if self.paginate_chapters else feed_url
                print(f"Fetching URL: {paginated_url}")

                for attempt in range(max_retries + 1):
                    if self.stop_fetching:
                        print("Fetch stopped during retry.")
                        break

                    try:
                        response = requests.get(paginated_url)
                        response.raise_for_status()

                        data = response.json()
                        if not data:  # No more chapters returned
                            print("No more chapters to fetch.")
                            self.chapters_fetched(all_chapters)
                            return

                        all_chapters.extend(data)
                        print(f"Fetched {len(data)} chapters. Total: {len(all_chapters)}")

                        # Update UI after each successful fetch
                        popup.progress_label.setText(f"{len(all_chapters)} chapters fetched")
                        QApplication.processEvents()

                        if not self.paginate_chapters:  
                            self.chapters_fetched(all_chapters)
                            return

                        offset += 50  # Move to the next batch of chapters
                        break

                    except requests.exceptions.RequestException as e:
                        print(f"Error fetching chapters: {e}")
                        if attempt == max_retries:
                            QMessageBox.critical(self, "Error", f"Failed to fetch chapters: {e}")
                            return
                        time.sleep(1 * (2 ** attempt))  # Exponential backoff
                        QApplication.processEvents()  # Process events even during retries

        finally:
            self.is_fetching = False
            if popup:
                popup.close()  # Close the popup when done or cancelled

    def chapters_fetched(self, chapters):
        print(f"chapters_fetched called with {len(chapters)} chapters")  # Debug log
        if not self.stop_fetching:  # Only update if not cancelled
            print("Calling preview_chapters_with_data")  # Debug log
            chapters = sorted(chapters, key=lambda x: x.get('published', ''), reverse=True)
            QTimer.singleShot(100, lambda: self.preview_chapters_with_data(chapters))
        else:
            print("Fetching was cancelled before chapters could be processed.")  # Debug log

    def chapters_error(self, error_message):
        self.is_fetching = False
        QTimer.singleShot(100, lambda: QMessageBox.critical(self, "Error", error_message))

    def chapters_cancelled(self):
        self.is_fetching = False
        QTimer.singleShot(100, lambda: QMessageBox.information(self, "Info", "Chapter fetching was cancelled."))

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

        directory = self.profiles[profile_url].get('directory', self.output_directory)  
        filename = f"{self.sanitize_filename(filename)}.epub"
        filepath = os.path.join(directory, filename)
        epub.write_epub(filepath, book)
        return filepath

    def load_profiles(self):
        try:
            with open("profiles.json", "r") as file:
                data = json.load(file)
                for url, profile in data.items():
                    # Only update directory if it's not in the JSON
                    if 'directory' not in profile or not profile['directory']:
                        profile['directory'] = self.output_directory
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

    def add_profile(self):
        add_window = QDialog(self)
        add_window.setWindowTitle("Add New Profile")
        add_window.setModal(True)  # Similar to transient in Tkinter

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
            'opt_in_for_automatic_mode': QCheckBox()
        }

        # Helper functions
        def submit_profile():
            url = profile_data['url'].text()
            title = profile_data['title'].text()
            author = profile_data['author'].text()
            directory = profile_data['directory'].text() or self.output_directory
            opt_in_automatic = profile_data['opt_in_for_automatic_mode'].isChecked()
            
            fixed_url = self.fix_link(url)
            if not fixed_url:
                QMessageBox.critical(self, "Error", "Invalid or unrecognized URL.")
                return
            
            if fixed_url in self.profiles:
                QMessageBox.warning(self, "Warning", "This profile already exists.")
                return
            
            self.profiles[fixed_url] = {
                "title": title if title else "Unknown Title", 
                "author": author if author else "Unknown Author", 
                "last_fetched": "", 
                "directory": directory,
                "opt_in_for_automatic_mode": opt_in_automatic
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

        # Automatic mode checkbox
        layout.addWidget(QLabel("Automatic mode:"))
        layout.addWidget(profile_data['opt_in_for_automatic_mode'])

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
            'opt_in_for_automatic_mode': QCheckBox()
        }
        profile_data['opt_in_for_automatic_mode'].setChecked(profile.get('opt_in_for_automatic_mode', False))

        # Helper functions
        def update_profile():
            new_url = profile_data['url'].text()
            new_title = profile_data['title'].text()
            new_author = profile_data['author'].text()
            new_directory = profile_data['directory'].text() or self.output_directory
            opt_in_automatic = profile_data['opt_in_for_automatic_mode'].isChecked()
            
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
                    "directory": new_directory,
                    "opt_in_for_automatic_mode": opt_in_automatic
                }
            else:
                self.profiles[url].update({
                    "title": new_title if new_title else "Unknown Title",
                    "author": new_author if new_author else "Unknown Author",
                    "directory": new_directory,
                    "opt_in_for_automatic_mode": opt_in_automatic
                })

            self.update_profile_list()
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

        # Automatic mode checkbox
        layout.addWidget(QLabel("Automatic mode:"))
        layout.addWidget(profile_data['opt_in_for_automatic_mode'])

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
        
        if url in self.profiles:
            del self.profiles[url]
            self.update_profile_list()
            self.save_profiles()
        else:
            QMessageBox.warning(self, "Warning", "Profile not found.")

    def update_profile_list(self):
        self.profile_list.clear()  # Clear all items before updating
        
        for url, details in self.profiles.items():
            item = QTreeWidgetItem([details['title'], details['author'], url])
            self.profile_list.addTopLevelItem(item)
        
        # Update button state based on selection
        has_selection = bool(self.profile_list.selectedItems())
        self.download_button.setEnabled(has_selection)

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
        self.fetch_kemono_chapters(url)

    def preview_chapters_with_data(self, chapters):
        try:
            print(f"Displaying preview for {len(chapters)} chapters.")  # Debug log
            self.current_chapters = chapters

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

            last_fetched = profile.get("last_fetched", "")
            for chapter in chapters:
                chapter['is_new'] = chapter['published'] > last_fetched

            preview_window = QDialog(self)
            preview_window.setWindowTitle("Chapter Preview")
            preview_window.setModal(True)
            preview_window.resize(600, 400)

            layout = QVBoxLayout(preview_window)

            tree = QTreeWidget()
            tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            tree.setHeaderLabels(["Title", "Published Date"])
            tree.setStyleSheet("""
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
            layout.addWidget(tree)
            
            def adjust_column_widths():
                total_width = tree.width() - 2  # -2 for possible border or margin
                tree.setColumnWidth(0, total_width // 2)  # Title
                tree.setColumnWidth(1, total_width // 2)  # Published Date

            # Use a timer to adjust widths when the dialog is shown
            QTimer.singleShot(100, adjust_column_widths)  # Adjust once when the dialog is shown

            
            # Populate the tree widget
            for chapter in chapters:
                item = QTreeWidgetItem([chapter['title'], chapter['published']])
                if chapter.get('is_new'):
                    item.setBackground(0, QColor(144, 238, 144))  # Highlight new chapters
                tree.addTopLevelItem(item)

            # Download Button
            download_button = QPushButton("Download")
            download_button.clicked.connect(self.save_and_edit_metadata)
            layout.addWidget(download_button)

            preview_window.exec()
            
        except Exception as e:
            print(f"Error in preview_chapters_with_data: {e}")
            import traceback
            traceback.print_exc()
            
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
        new_author = author_entry.text()
        new_filename = filename_entry.text()
        filepath = self.create_epub(chapters, new_title, new_author, self.current_url, new_filename)
        QMessageBox.information(self, "Success", f"EPUB created at: {filepath}")
        self.profiles[self.current_url]["last_fetched"] = max(chap['published'] for chap in chapters)
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