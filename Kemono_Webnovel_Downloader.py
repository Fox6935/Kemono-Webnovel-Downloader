import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import requests
from datetime import datetime, timedelta
from ebooklib import epub
import re
import os
import threading
import time

class KemonoWebnovelDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kemono Webnovel Downloader")
        self.geometry("500x500")
        
        self.style = ttk.Style(self)
        self.style.theme_use("default")
        self.style.configure("Green.TButton", background="green", padding=6, relief="flat", font=('Helvetica', 10))
        self.style.configure("TButton", padding=6, relief="flat", font=('Helvetica', 10))
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("Treeview", background="#ffffff", foreground="black", fieldbackground="#ffffff")
        self.style.map("Treeview", background=[('selected', '#3470e6')])

        self.profiles = self.load_profiles()
        self.profile_directories = {}  # New dictionary to store custom directories
        self.output_directory = os.getcwd()

        self.is_fetching = False
        self.stop_fetching = threading.Event()
        self.paginate_chapters = tk.BooleanVar(value=False)  # New variable for pagination toggle
        
        self.automatic_mode_running = False
        self.timer_start_time = None
        self.timer_label = None
        self.automatic_mode = tk.BooleanVar(value=False)
        self.sleep_time_seconds = 1800  # Change this value for a different "automatic mode" time interval
        
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Profile list
        self.profile_list = ttk.Treeview(main_frame, columns=("Title", "Author", "URL"), show="headings")
        self.profile_list.heading("Title", text="Title", anchor=tk.W)
        self.profile_list.heading("Author", text="Author", anchor=tk.W)
        self.profile_list.heading("URL", text="URL", anchor=tk.W)
        self.profile_list.column("#0", width=0, stretch=tk.NO)
        self.profile_list.column("Title", anchor=tk.W, width=150)
        self.profile_list.column("Author", anchor=tk.W, width=150)
        self.profile_list.column("URL", width=0, stretch=tk.NO)
        self.profile_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))

        self.profile_list.bind('<Button-1>', self.on_treeview_click)
        self.profile_list.bind('<Button-3>', self.show_context_menu)
        self.profile_list.bind('<<TreeviewSelect>>', self.update_button_state)

        # Pagination toggle checkbox
        self.pagination_checkbox = tk.Checkbutton(
            main_frame, text="Fetch all chapters (will take longer)", variable=self.paginate_chapters
        )
        self.pagination_checkbox.pack(anchor=tk.W, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Profile", command=self.add_profile, style="TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.download_button = ttk.Button(button_frame, text="Download Preview", command=self.preview_chapters, style="TButton")
        self.download_button.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Initially disabled until a profile is selected
        self.download_button.config(state='disabled')
        self.update_profile_list()
        
        # New
        automatic_frame = ttk.Frame(main_frame)
        automatic_frame.pack(anchor=tk.W, pady=5)
        
        self.automatic_mode_button = ttk.Button(automatic_frame, text="Automatic Mode", command=self.toggle_automatic_mode)
        self.automatic_mode_button.pack(side=tk.LEFT)
        
        self.timer_label = ttk.Label(automatic_frame, text="00:00")
        self.timer_label.pack(side=tk.LEFT, padx=(10, 0))

        # Bind to start automatic mode if it's on at startup
        if self.automatic_mode.get():
            self.start_automatic_mode()

    def toggle_automatic_mode(self):
        if self.automatic_mode.get():
            self.automatic_mode.set(False)
            self.stop_automatic_mode()
            self.automatic_mode_button.config(style="TButton")  # Back to default style
        else:
            self.automatic_mode.set(True)
            self.start_automatic_mode()
            self.automatic_mode_button.config(style="Green.TButton")  # Green style when on

    def start_automatic_mode(self):
        self.automatic_mode_running = True
        threading.Thread(target=self.automatic_fetch_loop, daemon=True).start()
        self.update_timer()
        self.automatic_mode_button.config(style="Green.TButton")  # Set to green when started

    def stop_automatic_mode(self):
        self.automatic_mode_running = False
        self.automatic_mode_button.config(style="TButton")  # Back to default when stopped

    def automatic_fetch_loop(self):
        while self.automatic_mode_running:
            start_time = time.time()
            for url, profile in self.profiles.items():
                if not self.automatic_mode_running or self.stop_fetching.is_set():
                    return
                if profile.get('opt_in_for_automatic_mode', False):
                    self.fetch_new_chapters(url, profile)

            # Calculate elapsed time and sleep the remaining time to hit the interval
            elapsed_time = time.time() - start_time
            sleep_time = max(0, self.sleep_time_seconds - elapsed_time)  # Ensure no negative sleep time
            time.sleep(sleep_time)

            # Reset timer for next cycle
            self.timer_start_time = datetime.now() + timedelta(seconds=self.sleep_time_seconds)

    def update_timer(self):
        if self.automatic_mode_running:
            if self.timer_start_time is None:
                self.timer_start_time = datetime.now() + timedelta(seconds=self.sleep_time_seconds)
            remaining = (self.timer_start_time - datetime.now()).total_seconds()
            if remaining <= 0:
                self.timer_label.config(text="00:00")
                self.timer_start_time = None
            else:
                minutes, seconds = divmod(int(remaining), 60)
                self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
                self.after(1000, self.update_timer)  # Update every second 

    def generate_filename(self, chapters):
        lowermost_title = chapters[-1]['title']
        uppermost_title = chapters[0]['title']
        default_filename = f"{self.sanitize_filename(lowermost_title)}-{self.sanitize_filename(uppermost_title)}" if len(chapters) > 1 else self.sanitize_filename(chapters[0]['title'])
        return default_filename

    def fetch_new_chapters(self, url, profile):
        last_fetched = profile.get("last_fetched", "")
        chapters = self.fetch_kemono_chapters_silent(url)
        new_chapters = [ch for ch in chapters if ch['published'] > last_fetched]
        if new_chapters:
            filename = self.generate_filename(new_chapters)
            filepath = self.create_epub(new_chapters, profile['title'], profile['author'], url, filename)
            # Update last_fetched
            profile["last_fetched"] = max(chap['published'] for chap in new_chapters)
            self.save_profiles()  # Save updated profiles

    def fetch_kemono_chapters_silent(self, feed_url):
        all_chapters = []
        offset = 0
        while True:
            paginated_url = f"{feed_url}?o={offset}" if self.paginate_chapters.get() else feed_url
            response = requests.get(paginated_url)
            response.raise_for_status()
            data = response.json()
            if not data:
                break
            all_chapters.extend(data)
            if not self.paginate_chapters.get():
                break
            offset += 50
        return sorted(all_chapters, key=lambda x: x.get('published', ''), reverse=True)

    def update_button_state(self, event):
        selected = self.profile_list.selection()
        state = 'normal' if selected else 'disabled'
        self.download_button.config(state=state)
    
    def deselect_on_empty_click(self, event):
        # Check if the click was on an empty part of the Treeview
        item = self.profile_list.identify_row(event.y)
        if item == '':
            self.profile_list.selection_remove(self.profile_list.selection())
        else:
            self.on_treeview_click(event)  # If clicked on an item, select it

    def show_context_menu(self, event):
        item = self.profile_list.identify_row(event.y)
        if item:
            self.profile_list.selection_set(item)
            self.profile_list.focus(item)
            
            context_menu = tk.Menu(self, tearoff=0)
            context_menu.add_command(label='Edit Profile', command=self.edit_profile)
            context_menu.add_command(label='Delete Profile', command=self.delete_profile)
            context_menu.tk_popup(event.x_root, event.y_root)
        else:
            # If no item is under the cursor, don't show the menu
            return

    def on_treeview_click(self, event):
        item = self.profile_list.identify_row(event.y)
        if item == '':
            self.profile_list.selection_remove(self.profile_list.selection())
        else:
            self.profile_list.selection_set(item)

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
        self.stop_fetching.clear()

        def fetch_chapters():
            all_chapters = []
            offset = 0
            max_retries = 3

            popup = self.show_loading_popup()
            try:
                while True:
                    if self.stop_fetching.is_set():
                        return

                    paginated_url = f"{feed_url}?o={offset}" if self.paginate_chapters.get() else feed_url
                    for attempt in range(max_retries + 1):
                        if self.stop_fetching.is_set():
                            return

                        try:
                            response = requests.get(paginated_url)
                            response.raise_for_status()
                            data = response.json()
                            
                            if not data:  # Stop if no data returned
                                self.chapters_fetched(all_chapters)
                                return

                            all_chapters.extend(data)

                            if not self.paginate_chapters.get():  # If pagination is disabled, stop after the first fetch
                                self.chapters_fetched(all_chapters)
                                return

                            offset += 50  # Increment by 50 for the next batch of chapters
                            break  # Successful fetch, move to next batch

                        except requests.exceptions.RequestException as e:
                            if attempt == max_retries or self.stop_fetching.is_set():
                                self.chapters_error(f"Failed to fetch chapters after {max_retries} retries: {e}")
                                return
                            else:
                                time.sleep(1 * (2 ** attempt))  # Exponential backoff
                                continue
            finally:
                self.is_fetching = False
                self.after(0, popup.destroy)  # Ensure popup is closed in the main thread

        # Start the fetching in a new thread
        threading.Thread(target=fetch_chapters, daemon=True).start()

    def chapters_fetched(self, chapters):
        if not self.stop_fetching.is_set():  # Only update if not cancelled
            chapters = sorted(chapters, key=lambda x: x.get('published', ''), reverse=True)
            self.after(0, lambda: self.preview_chapters_with_data(chapters))

    def chapters_error(self, error_message):
        self.is_fetching = False
        self.after(0, lambda: messagebox.showerror("Error", error_message))

    def chapters_cancelled(self):
        self.is_fetching = False
        self.after(0, lambda: messagebox.showinfo("Info", "Chapter fetching was cancelled."))

    def show_loading_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Loading")
        popup.geometry("300x100")
        popup.resizable(False, False)
        popup.grab_set()

        frame = ttk.Frame(popup, padding="5")
        frame.pack(fill=tk.BOTH, expand=True)

        label = ttk.Label(frame, text="This might take a while...")
        label.pack(pady=5)

        def cancel_fetch():
            self.stop_fetching.set()
            popup.destroy()

        cancel_button = ttk.Button(frame, text="Cancel", command=cancel_fetch)
        cancel_button.pack(pady=5)

        popup.update_idletasks()
        width = popup.winfo_width()
        height = popup.winfo_height()
        x = self.winfo_x() + (self.winfo_width() // 2) - (width // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (height // 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")

        popup.protocol("WM_DELETE_WINDOW", cancel_fetch)
        return popup

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
            messagebox.showerror("Error", f"The profiles.json file is not valid JSON. Error: {e}")
            return {}

    def save_profiles(self):
        for url, profile in self.profiles.items():
            # Ensure directory is included and is string type
            profile['directory'] = str(profile.get('directory', self.output_directory))
        with open("profiles.json", "w") as file:
            json.dump(self.profiles, file, indent=4)

    def add_profile(self):
        add_window = tk.Toplevel(self)
        add_window.title("Add New Profile")
        add_window.transient(self)
        
        # Calculate position relative to the parent window
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()

        add_width = 450
        add_height = 250

        # Center the metadata window relative to the parent
        x = parent_x + (parent_width // 2) - (add_width // 2)
        y = parent_y + (parent_height // 2) - (add_height // 2)

        add_window.geometry(f"{add_width}x{add_height}+{x}+{y}")

        profile_data = {}
        profile_data['opt_in_for_automatic_mode'] = tk.BooleanVar(value=False)

        def submit_profile():
            url = profile_data['url'].get()
            title = profile_data['title'].get()
            author = profile_data['author'].get()
            directory = profile_data['directory'].get() or self.output_directory  # Default to current working directory if not specified
            opt_in_automatic = profile_data['opt_in_for_automatic_mode'].get()  # New property
            
            fixed_url = self.fix_link(url)
            if not fixed_url:
                messagebox.showerror("Error", "Invalid or unrecognized URL.")
                return
            
            if fixed_url in self.profiles:
                messagebox.showwarning("Warning", "This profile already exists.")
                return
            
            self.profiles[fixed_url] = {
                "title": title or "Unknown Title", 
                "author": author or "Unknown Author", 
                "last_fetched": "", 
                "directory": directory,
                "opt_in_for_automatic_mode": opt_in_automatic  # Include new property
            }
            self.update_profile_list()
            self.save_profiles()
            add_window.destroy()
        
        # URL Entry
        tk.Label(add_window, text="URL:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        profile_data['url'] = ttk.Entry(add_window, width=40)
        profile_data['url'].grid(row=0, column=1, padx=(5, 20), pady=2, sticky="ew")

        # Title Entry
        tk.Label(add_window, text="Title:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        profile_data['title'] = ttk.Entry(add_window, width=40)
        profile_data['title'].grid(row=1, column=1, padx=(5, 20), pady=2, sticky="ew")

        # Author Entry
        tk.Label(add_window, text="Author:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        profile_data['author'] = ttk.Entry(add_window, width=40)
        profile_data['author'].grid(row=2, column=1, padx=(5, 20), pady=2, sticky="ew")

        # Directory Entry
        tk.Label(add_window, text="Directory:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        profile_data['directory'] = ttk.Entry(add_window, width=40)
        profile_data['directory'].grid(row=3, column=1, padx=(5, 20), pady=2, sticky="ew")
        ttk.Button(add_window, text="Browse", command=lambda: self.select_directory(profile_data['directory'])).grid(row=3, column=2, padx=10, pady=5, sticky='w')

        # Submit Button
        submit_button = ttk.Button(add_window, text="Submit", command=submit_profile, width=15)
        submit_button.grid(row=5, column=0, columnspan=4, pady=10)

        # Configure grid to expand columns if window is resized, but keep a margin
        add_window.grid_columnconfigure(1, weight=1)
        
        # Opt in for automatic mode
        tk.Label(add_window, text="Automatic mode:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        tk.Checkbutton(add_window, variable=profile_data['opt_in_for_automatic_mode']).grid(row=4, column=1, padx=5, pady=2, sticky="w")

    # New method for directory selection
    def select_directory(self, directory_var):
        directory = filedialog.askdirectory(title="Select Directory for EPUBs")
        if directory:
            directory_var.set(directory)

    def edit_profile(self):
        selected = self.profile_list.selection()
        if not selected:
            messagebox.showerror("Error", "No profile selected.")
            return
        
        url = self.profile_list.item(selected[0])['values'][2]
        edit_window = tk.Toplevel(self)
        edit_window.title("Edit Profile")
        edit_window.transient(self)
        
        # Calculate position relative to the parent window
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()

        edit_width = 450
        edit_height = 250

        # Center the metadata window relative to the parent
        x = parent_x + (parent_width // 2) - (edit_width // 2)
        y = parent_y + (parent_height // 2) - (edit_height // 2)

        edit_window.geometry(f"{edit_width}x{edit_height}+{x}+{y}")

        profile_data = {}
        profile = self.profiles[url]
        profile_data['opt_in_for_automatic_mode'] = tk.BooleanVar(value=profile.get('opt_in_for_automatic_mode', False))
        
        # Pre-fill entries with current profile data
        profile_data['url'] = tk.StringVar(value=url)
        profile_data['title'] = tk.StringVar(value=profile.get('title', ""))
        profile_data['author'] = tk.StringVar(value=profile.get('author', ""))
        profile_data['directory'] = tk.StringVar(value=profile.get('directory', self.output_directory))

        def update_profile():
            new_url = profile_data['url'].get()
            new_title = profile_data['title'].get()
            new_author = profile_data['author'].get()
            new_directory = profile_data['directory'].get() or self.output_directory
            opt_in_automatic = profile_data['opt_in_for_automatic_mode'].get()
            
            new_fixed_url = self.fix_link(new_url)
            if not new_fixed_url:
                messagebox.showerror("Error", "Invalid or unrecognized URL.")
                return

            if new_fixed_url != url and new_fixed_url in self.profiles:
                messagebox.showwarning("Warning", "This profile URL already exists.")
                return
            
            # Update or replace profile
            if new_fixed_url != url:
                last_fetched = profile.get("last_fetched", "")
                del self.profiles[url]
                self.profiles[new_fixed_url] = {
                    "title": new_title or "Unknown Title", 
                    "author": new_author or "Unknown Author", 
                    "last_fetched": last_fetched, 
                    "directory": new_directory,
                    "opt_in_for_automatic_mode": opt_in_automatic
                }
            else:
                self.profiles[url].update({
                    "title": new_title or "Unknown Title",
                    "author": new_author or "Unknown Author",
                    "directory": new_directory,
                    "opt_in_for_automatic_mode": opt_in_automatic
                })

            self.update_profile_list()
            self.save_profiles()
            edit_window.destroy()

        # URL Entry
        tk.Label(edit_window, text="URL:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(edit_window, textvariable=profile_data['url'], width=40).grid(row=0, column=1, padx=(5, 20), pady=2, sticky="ew")

        # Title Entry
        tk.Label(edit_window, text="Title:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(edit_window, textvariable=profile_data['title'], width=40).grid(row=1, column=1, padx=(5, 20), pady=2, sticky="ew")

        # Author Entry
        tk.Label(edit_window, text="Author:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(edit_window, textvariable=profile_data['author'], width=40).grid(row=2, column=1, padx=(5, 20), pady=2, sticky="ew")

        # Directory Entry
        tk.Label(edit_window, text="Directory:").grid(row=3, column=0, sticky="e", padx=5, pady=2)
        ttk.Entry(edit_window, textvariable=profile_data['directory'], width=40).grid(row=3, column=1, padx=(5, 20), pady=2, sticky="ew")
        ttk.Button(edit_window, text="Browse", command=lambda: self.select_directory(profile_data['directory'])).grid(row=3, column=2, padx=10, pady=5, sticky='w')


        # Update Button
        update_button = ttk.Button(edit_window, text="Update", command=update_profile, width=15)
        update_button.grid(row=5, column=0, columnspan=4, pady=10)

        # Configure grid to expand columns if window is resized, but keep a margin
        edit_window.grid_columnconfigure(1, weight=1)
        
        # Opt in for automatic mode
        tk.Label(edit_window, text="Automatic mode:").grid(row=4, column=0, sticky="e", padx=5, pady=2)
        tk.Checkbutton(edit_window, variable=profile_data['opt_in_for_automatic_mode']).grid(row=4, column=1, padx=5, pady=2, sticky="w")

    def delete_profile(self):
        selected = self.profile_list.selection()
        if not selected:
            messagebox.showerror("Error", "No profile selected.")
            return
        url = self.profile_list.item(selected[0])['values'][2]  # Changed index due to column order
        del self.profiles[url]
        self.update_profile_list()
        self.save_profiles()

    def update_profile_list(self):
        self.profile_list.delete(*self.profile_list.get_children())
        for url, details in self.profiles.items():
            self.profile_list.insert("", "end", values=(details['title'], details['author'], url))
        
        # Update button state based on selection
        selected = self.profile_list.selection()
        state = 'normal' if selected else 'disabled'
        self.download_button.config(state=state)

    def preview_chapters(self):
        if self.is_fetching:
            messagebox.showinfo("Fetching", "Already fetching chapters. Please wait.")
            return

        selected = self.profile_list.selection()
        if not selected:
            messagebox.showerror("Error", "No profile selected.")
            return
        
        url = self.profile_list.item(selected[0])['values'][2]
        self.fetch_kemono_chapters(url)

    def preview_chapters_with_data(self, chapters):
        if not chapters:
            messagebox.showerror("Error", "No chapters found for this profile.")
            return

        selected = self.profile_list.selection()
        if not selected:
            return

        url = self.profile_list.item(selected[0])['values'][2]
        profile = self.profiles[url]
        last_fetched = profile.get("last_fetched", "")
        for chapter in chapters:
            chapter['is_new'] = chapter['published'] > last_fetched

        preview_window = tk.Toplevel(self)
        preview_window.title("Chapter Preview")
        preview_window.transient(self)
        preview_window.resizable(True, True)
        
        # Calculate position relative to the parent window
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()

        preview_width = 600
        preview_height = 400

        # Center the metadata window relative to the parent
        x = parent_x + (parent_width // 2) - (preview_width // 2)
        y = parent_y + (parent_height // 2) - (preview_height // 2)

        preview_window.geometry(f"{preview_width}x{preview_height}+{x}+{y}")

        tree_frame = ttk.Frame(preview_window)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        tree = ttk.Treeview(tree_frame, columns=("Title", "Published", "New"), show="headings", yscrollcommand=tree_scroll.set)
        tree.heading("Title", text="Title")
        tree.heading("Published", text="Published Date")
        tree.heading("New", text="New")
        tree.pack(fill=tk.BOTH, expand=True)

        tree_scroll.config(command=tree.yview)

        for chapter in chapters:
            is_new = "Yes" if chapter['is_new'] else "No"
            tree.insert("", "end", values=(chapter['title'], chapter['published'], is_new), tags=("new" if chapter['is_new'] else ""))
        tree.tag_configure("new", background="lightgreen")

        def save_and_edit_metadata():
            selected_chapters = []
            for item in tree.selection():
                chapter_data = tree.item(item)['values']
                chapter = next((ch for ch in chapters if ch['title'] == chapter_data[0] and ch['published'] == chapter_data[1]), None)
                if chapter:
                    selected_chapters.append(chapter)
            if not selected_chapters:
                messagebox.showwarning("No Selection", "No chapters selected for download.")
                return

            lowermost_title = selected_chapters[-1]['title']
            uppermost_title = selected_chapters[0]['title']
            default_filename = f"{self.sanitize_filename(lowermost_title)}-{self.sanitize_filename(uppermost_title)}" if len(selected_chapters) > 1 else self.sanitize_filename(selected_chapters[0]['title'])
            metadata = {
                "title": self.profiles[url]["title"],
                "author": self.profiles[url]["author"],
                "filename": default_filename
            }

            def save_metadata_and_download():
                new_title = metadata_window.title_entry.get()
                new_author = metadata_window.author_entry.get()
                new_filename = metadata_window.filename_entry.get()
                filepath = self.create_epub(selected_chapters, new_title, new_author, url, new_filename)
                messagebox.showinfo("Success", f"EPUB created at: {filepath}")
                self.profiles[url]["last_fetched"] = max(chap['published'] for chap in selected_chapters)
                self.save_profiles()
                metadata_window.destroy()
                preview_window.destroy()

            metadata_window = tk.Toplevel(self)
            metadata_window.title("Edit Metadata")
            metadata_window.transient(self)
            
            # Calculate position relative to the parent window
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_width = self.winfo_width()
            parent_height = self.winfo_height()

            metadata_width = 300
            metadata_height = 100

            # Center the metadata window relative to the parent
            x = parent_x + (parent_width // 2) - (metadata_width // 2)
            y = parent_y + (parent_height // 2) - (metadata_height // 2)

            metadata_window.geometry(f"{metadata_width}x{metadata_height}+{x}+{y}")
            
            ttk.Label(metadata_window, text="Title:").grid(row=0, column=0, sticky="w")
            metadata_window.title_entry = ttk.Entry(metadata_window, width=40)
            metadata_window.title_entry.grid(row=0, column=1)
            metadata_window.title_entry.insert(0, metadata["title"])

            ttk.Label(metadata_window, text="Author:").grid(row=1, column=0, sticky="w")
            metadata_window.author_entry = ttk.Entry(metadata_window, width=40)
            metadata_window.author_entry.grid(row=1, column=1)
            metadata_window.author_entry.insert(0, metadata["author"])

            ttk.Label(metadata_window, text="Filename:").grid(row=2, column=0, sticky="w")
            metadata_window.filename_entry = ttk.Entry(metadata_window, width=40)
            metadata_window.filename_entry.grid(row=2, column=1)
            metadata_window.filename_entry.insert(0, metadata["filename"])

            ttk.Button(metadata_window, text="Save and Download", command=save_metadata_and_download).grid(row=3, column=0, columnspan=2, pady=10)

        ttk.Button(preview_window, text="Download", command=save_and_edit_metadata).pack(pady=10)

if __name__ == "__main__":
    app = KemonoWebnovelDownloader()
    app.mainloop()
