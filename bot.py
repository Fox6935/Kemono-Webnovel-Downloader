import discord
from discord.ext import commands
import aiohttp
import asyncio
import re
import os
from ebooklib import epub

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix='!', intents=intents)

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@client.command()
async def check(ctx, url: str):
    try:
        # Fix and validate the URL
        fixed_url = await async_fix_link(url)
        if not fixed_url:
            await ctx.send("Invalid URL. Please provide a valid kemono.su or Patreon URL.")
            return

        # Fetch chapters
        chapters = await async_fetch_chapters(fixed_url)
        
        if not chapters:
            await ctx.send("No chapters found at this URL.")
            return

        # Get the most recent post title
        most_recent_chapter = chapters[0]  # Assuming chapters are sorted with the most recent first
        title = most_recent_chapter.get('title', 'Untitled')
        
        await ctx.send(f"The most recent post title is: **{title}**.")

    except Exception as e:
        await ctx.send(f"An error occurred while checking the URL: {str(e)}")

@client.command()
async def fetch(ctx, url: str, num_chapters: int, *skip_chapters):
    try:
        # Fix and validate the URL
        fixed_url = await async_fix_link(url)
        if not fixed_url:
            await ctx.send("Invalid URL. Please provide a valid kemono.su or Patreon URL.")
            return

        # Fetch chapters, handle pagination, and skip specified chapters
        all_chapters = await async_fetch_chapters(fixed_url)
        chapters_to_process = []
        skip_set = set(map(int, skip_chapters[0].split(',')) if skip_chapters else [])

        for i, chapter in enumerate(all_chapters[:num_chapters]):
            if i + 1 not in skip_set:
                chapters_to_process.append(chapter)
            if len(chapters_to_process) == num_chapters:
                break

        # Generate filename
        filename = generate_filename(chapters_to_process)

        # Create EPUB
        title = filename
        author = "Unknown"
        profile_url = url

        epub_file = await async_create_epub(chapters_to_process, title, author, profile_url, filename)

        # Send the EPUB file in Discord
        with open(epub_file, 'rb') as file:
            await ctx.send(file=discord.File(file, f"{filename}.epub"))
        os.remove(epub_file)  # Clean up temporary file

    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

async def async_fix_link(link):
    if not link or not isinstance(link, str):
        return None
    link = link.strip()

    if "patreon.com" in link.lower():
        user_id = await async_get_patreon_user_id(link)
        if user_id:
            return f"https://kemono.su/api/v1/patreon/user/{user_id}"
        return None
    else:
        if not link.startswith("http"):
            link = f"https://{link.lstrip('/')}" if link.startswith("kemono.su") else f"https://kemono.su/{link.lstrip('/')}"
        
        if link.startswith("www."):
            link = f"https://{link}"
        if link.startswith("https://kemono.su/") and not link.startswith("https://kemono.su/api/v1/"):
            link = link.replace("https://kemono.su/", "https://kemono.su/api/v1/")
    
    return link if "kemono.su/api/v1/" in link else None

async def async_get_patreon_user_id(url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    match = re.search(r'"creator":\s*{\s*"data":\s*{\s*"id":\s*"(\d+)"', text)
                    return match.group(1) if match else None
        except:
            return None
    return None

async def async_fetch_chapters(feed_url):
    chapters = []
    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(f"{feed_url}?o={offset}") as response:
                if response.status != 200:
                    break
                new_chapters = await response.json()
                if not new_chapters:
                    break
                chapters.extend(new_chapters)
                offset += 50
                if len(new_chapters) < 50:
                    break
    return sorted(chapters, key=lambda x: x.get('published', ''), reverse=True)

async def async_create_epub(chapters, title, author, profile_url, filename):
    chapters = sorted(chapters, key=lambda x: x['published'])
    
    book = epub.EpubBook()
    book.set_language("en")
    book.set_title(title)
    book.add_author(author)

    epub_chapters = []
    async with aiohttp.ClientSession() as session:
        for i, chapter in enumerate(chapters, start=1):
            chapter_title = chapter['title']
            content = f"<h1>{chapter_title}</h1>\n<p>{chapter.get('content', '')}</p>"

            pattern = r'<img[^>]+src="([^"]+)"'
            matches = re.findall(pattern, content)
            for i2, match in enumerate(matches):
                full_url = "https://n4.kemono.su/data" + match
                try:
                    async with session.get(full_url) as img_response:
                        if img_response.status == 200:
                            media_type = img_response.headers.get('Content-Type', 'image/jpeg')
                            image_name = match.split('/')[-1]
                            image_content = await img_response.read()
                            image_item = epub.EpubItem(
                                uid=f"img{i2 + 1}",
                                file_name=f"images/{image_name}",
                                media_type=media_type,
                                content=image_content
                            )
                            book.add_item(image_item)
                            content = content.replace(match, f"images/{image_name}")
                except:
                    print(f"Failed to download {full_url}")

            chapter_epub = epub.EpubHtml(title=chapter_title, file_name=f'chap_{i:02}.xhtml', lang='en')
            chapter_epub.content = content
            epub_chapters.append(chapter_epub)
            book.add_item(chapter_epub)

    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + epub_chapters

    temp_filepath = os.path.join(os.getcwd(), f"{filename}.epub")
    epub.write_epub(temp_filepath, book)
    return temp_filepath

def sanitize_filename(filename):
    return re.sub(r'[^\w\s-]', '', filename).strip().replace(" ", "_")

def generate_filename(chapters):
    if not chapters:
        return "empty_chapters"
    
    lowermost_title = chapters[-1]['title']
    uppermost_title = chapters[0]['title']
    default_filename = f"{sanitize_filename(lowermost_title)}-{sanitize_filename(uppermost_title)}" if len(chapters) > 1 else sanitize_filename(chapters[0]['title'])
    return default_filename

client.run('YOUR_BOT_TOKEN')