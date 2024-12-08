import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import requests
from datetime import datetime
from ebooklib import epub
import re
import os

class KemonoWebnovelDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Kemono Webnovel Downloader")
        self.geometry("800x600")
        
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TButton", padding=6, relief="flat", font=('Helvetica', 10))
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("Treeview", background="#ffffff", foreground="black", fieldbackground="#ffffff")
        self.style.map("Treeview", background=[('selected', '#3470e6')])

        self.profiles = self.load_profiles()
        self.output_directory = os.getcwd()

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
        self.profile_list.column("URL", anchor=tk.W, width=200)
        self.profile_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 0))

        self.profile_list.bind('<Button-1>', self.on_treeview_click)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        buttons = [
            ("Add Profile", self.add_profile),
            ("Edit Profile", self.edit_profile),
            ("Delete Profile", self.delete_profile),
            ("Download Preview", self.preview_chapters)
        ]
        for text, command in buttons:
            ttk.Button(button_frame, text=text, command=command, style="TButton").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        self.update_profile_list()

    def on_treeview_click(self, event):
        if self.profile_list.identify_region(event.x, event.y) == "cell":
            self.profile_list.selection_add(self.profile_list.identify_row(event.y))

    def sanitize_filename(self, filename):
        return re.sub(r'[^\w\s-]', '', filename).strip().replace(" ", "_")

    def fix_link(self, link):
        if not link or not isinstance(link, str):
            return None
        link = link.strip()

        # Handle relative links
        if not link.startswith("http"):
            link = f"https://kemono.su/{link.lstrip('/')}"
        
        # Normalize URL
        if link.startswith("www."):
            link = f"https://{link}"
        if link.startswith("https://kemono.su/") and not link.startswith("https://kemono.su/api/v1/"):
            link = link.replace("https://kemono.su/", "https://kemono.su/api/v1/")
        
        return link if "kemono.su/api/v1/" in link else None

    def fetch_kemono_chapters(self, feed_url):
        try:
            response = requests.get(feed_url)
            response.raise_for_status()
            data = response.json()
            return sorted(data, key=lambda x: x.get('published', ''), reverse=True)
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch chapters: {e}")
            return []

    def create_epub(self, chapters, title, author, directory, filename):
        chapters = sorted(chapters, key=lambda x: x['published'])
        
        book = epub.EpubBook()
        book.set_language("en")
        book.set_title(title)
        book.add_author(author)

        epub_chapters = []
        for i, chapter in enumerate(chapters, start=1):
            chapter_title = chapter['title']
            content = f"<h1>{chapter_title}</h1>\n<p>{chapter.get('content', '')}</p>"

            chapter_epub = epub.EpubHtml(title=chapter_title, file_name=f'chap_{i:02}.xhtml', lang='en')
            chapter_epub.content = content
            epub_chapters.append(chapter_epub)
            book.add_item(chapter_epub)

        book.toc = tuple(epub_chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav'] + epub_chapters

        filename = f"{self.sanitize_filename(filename)}.epub"
        filepath = os.path.join(directory, filename)
        epub.write_epub(filepath, book)
        return filepath

    def load_profiles(self):
        try:
            with open("profiles.json", "r") as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def save_profiles(self):
        with open("profiles.json", "w") as file:
            json.dump(self.profiles, file, indent=4)

    def add_profile(self):
        add_window = tk.Toplevel(self)
        add_window.title("Add New Profile")
        add_window.geometry("300x200")
        
        profile_data = {}

        def submit_profile():
            url = profile_data['url'].get()
            title = profile_data['title'].get()
            author = profile_data['author'].get()
            
            fixed_url = self.fix_link(url)
            if not fixed_url:
                messagebox.showerror("Error", "Invalid or unrecognized URL.")
                return
            
            if fixed_url in self.profiles:
                messagebox.showwarning("Warning", "This profile already exists.")
                return
            
            self.profiles[fixed_url] = {"title": title or "Unknown Title", "author": author or "Unknown Author", "last_fetched": ""}
            self.update_profile_list()
            self.save_profiles()
            add_window.destroy()

        # URL Entry
        ttk.Label(add_window, text="URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        profile_data['url'] = ttk.Entry(add_window, width=30)
        profile_data['url'].grid(row=0, column=1, padx=5, pady=5)

        # Title Entry
        ttk.Label(add_window, text="Title:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        profile_data['title'] = ttk.Entry(add_window, width=30)
        profile_data['title'].grid(row=1, column=1, padx=5, pady=5)

        # Author Entry
        ttk.Label(add_window, text="Author:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        profile_data['author'] = ttk.Entry(add_window, width=30)
        profile_data['author'].grid(row=2, column=1, padx=5, pady=5)

        # Submit Button
        ttk.Button(add_window, text="Submit", command=submit_profile).grid(row=3, column=0, columnspan=2, pady=10)

    def edit_profile(self):
        selected = self.profile_list.selection()
        if not selected:
            messagebox.showerror("Error", "No profile selected.")
            return
        
        url = self.profile_list.item(selected[0])['values'][2]  # Changed index due to column order
        edit_window = tk.Toplevel(self)
        edit_window.title("Edit Profile")
        edit_window.geometry("300x200")
        
        profile_data = {}

        # Populate entries with current profile data
        profile_data['url'] = tk.StringVar(value=url)
        profile_data['title'] = tk.StringVar(value=self.profiles[url]['title'])
        profile_data['author'] = tk.StringVar(value=self.profiles[url]['author'])

        def update_profile():
            new_title = profile_data['title'].get()
            new_author = profile_data['author'].get()
            new_url = profile_data['url'].get()
            
            new_fixed_url = self.fix_link(new_url)
            if not new_fixed_url:
                messagebox.showerror("Error", "Invalid or unrecognized URL.")
                return

            # Handle URL change
            if new_fixed_url != url:
                if new_fixed_url in self.profiles:
                    messagebox.showwarning("Warning", "This profile URL already exists.")
                    return
                # Remove old profile and add new one
                last_fetched = self.profiles[url].get("last_fetched", "")
                del self.profiles[url]  # Remove old profile
                self.profiles[new_fixed_url] = {"title": new_title, "author": new_author, "last_fetched": last_fetched}
            else:
                self.profiles[url]['title'] = new_title
                self.profiles[url]['author'] = new_author

            self.update_profile_list()
            self.save_profiles()
            edit_window.destroy()

        # URL Entry
        ttk.Label(edit_window, text="URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(edit_window, textvariable=profile_data['url'], width=30).grid(row=0, column=1, padx=5, pady=5)

        # Title Entry
        ttk.Label(edit_window, text="Title:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(edit_window, textvariable=profile_data['title'], width=30).grid(row=1, column=1, padx=5, pady=5)

        # Author Entry
        ttk.Label(edit_window, text="Author:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(edit_window, textvariable=profile_data['author'], width=30).grid(row=2, column=1, padx=5, pady=5)

        # Update Button
        ttk.Button(edit_window, text="Update", command=update_profile).grid(row=3, column=0, columnspan=2, pady=10)

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

    def preview_chapters(self):
        selected = self.profile_list.selection()
        if not selected:
            messagebox.showerror("Error", "No profile selected.")
            return
        
        url = self.profile_list.item(selected[0])['values'][2]  # Changed index due to column order
        chapters = self.fetch_kemono_chapters(url)
        if not chapters:
            messagebox.showerror("Error", "No chapters found for this profile.")
            return

        profile = self.profiles[url]
        last_fetched = profile.get("last_fetched", "")
        for chapter in chapters:
            chapter['is_new'] = chapter['published'] > last_fetched

        preview_window = tk.Toplevel(self)
        preview_window.title("Chapter Preview")
        preview_window.geometry("600x400")
        preview_window.resizable(True, True)

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
                filepath = self.create_epub(selected_chapters, new_title, new_author, self.output_directory, new_filename)
                messagebox.showinfo("Success", f"EPUB created at: {filepath}")
                self.profiles[url]["last_fetched"] = max(chap['published'] for chap in selected_chapters)
                self.save_profiles()
                metadata_window.destroy()
                preview_window.destroy()

            metadata_window = tk.Toplevel(self)
            metadata_window.title("Edit Metadata")
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