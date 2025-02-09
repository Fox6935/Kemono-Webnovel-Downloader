import discord
from discord.ext import commands, tasks
from discord import Embed
import aiohttp
import asyncio
import requests
import re
import os
import json
import time
import getpass
from datetime import datetime, timezone
from ebooklib import epub
from discord import ButtonStyle, Interaction, ui

def load_config():
    try:
        with open('config.json', 'r') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        return {}

def save_config(config):
    with open('config.json', 'w') as config_file:
        json.dump(config, config_file)

def load_session():
    try:
        with open("session.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        print("No session file found.")
        return None
cookies = load_session()

def validate_session():
    cookies = load_session()
    if not cookies:
        return False
    async def validate():
        async with aiohttp.ClientSession(cookies=cookies) as session:
            response = await session.get("https://kemono.su/api/v1/account/favorites")
            return response.status == 200
    
    return asyncio.run(validate())

def setup_bot():
    config = load_config()
    
    # Bot Token
    if 'BOT_TOKEN' not in config:
        config['BOT_TOKEN'] = input("Enter your bot token: ")
        save_config(config)
    
    # Channel ID for Kemono updates
    if 'UPDATE_CHANNEL_ID' not in config:
        config['UPDATE_CHANNEL_ID'] = input("Enter the channel ID for Kemono updates: ")
        save_config(config)

    # Roles for command access
    if 'ALLOWED_ROLES' not in config:
        roles_input = input("Enter role names for command access, separated by commas: ")
        config['ALLOWED_ROLES'] = [role.strip() for role in roles_input.split(',') if role.strip()]
        save_config(config)
    
    # Check for session.json
    if not os.path.exists('session.json') or not validate_session():
        print("No valid session found. Please log in.")
        username = input("Enter your username: ")
        password = getpass.getpass("Enter your password: ")
        if login_to_kemono(username, password):
            print("Login successful. Session saved.")
            if not os.path.exists('creators_data.json'):
                with open('creators_data.json', 'w') as file:
                    json.dump({}, file)  # Create an empty JSON file for creators data
        else:
            print("Login failed. Exiting.")
            exit(1)
    else:
        print("Valid session found.")
    
    return config['BOT_TOKEN'], int(config['UPDATE_CHANNEL_ID']), config['ALLOWED_ROLES']

def login_to_kemono(username, password):
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

        cookies = response.cookies.get_dict()
        if not cookies.get("session"):
            set_cookie_header = response.headers.get("Set-Cookie", "")
            for cookie in set_cookie_header.split(","):
                if "session=" in cookie:
                    cookies["session"] = cookie.split("session=")[-1].split(";")[0]
                    break

        if "session" in cookies:
            save_session(cookies)
            return True
        else:
            print("Login successful, but no session cookie was extracted.")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Login failed: {e}")
        if e.response is not None:
            print(f"Response content: {e.response.text}")
        return False

def save_session(cookies):
    with open("session.json", "w") as file:
        json.dump(cookies, file)

# Update your main bot script
bot_token, channel_id, allowed_roles = setup_bot()
Channel_id = channel_id

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix='!kemono ', intents=intents, help_command=None)

@client.command()
async def help(ctx):
    embed = Embed(title="Kemono Update Bot Help", color=0x00ff00)
    embed.description = "The Kemono Update Bot keeps you informed about updates from creators on the Kemono platform. It automatically checks for updates every 5 minutes and sends notifications in a specified Discord channel when new posts are detected. Access to commands is restricted to certain roles and channels for security."

    # Add fields for each command
    embed.add_field(name="!kemono check [URL]", value="Fetches and displays a list of chapter titles from a given URL on Kemono. The response is ephemeral and includes a delete option.\n**Usage:** `!kemono check `", inline=False)
    embed.add_field(name="!kemono fetch [URL] [Number of Chapters] [Skip Chapters]", value="Downloads specified chapters from a Kemono creator's page into an EPUB file. You can skip chapters if needed.\n**Usage:** `!kemono fetch   [chapter_numbers_to_skip]`", inline=False)
    embed.add_field(name="!kemono add [URL]", value="Adds a creator from the given URL to your favorites list on Kemono. Updates local tracking.\n**Usage:** `!kemono add `", inline=False)
    embed.add_field(name="!kemono remove [URL]", value="Removes a creator from your favorites list on Kemono based on the provided URL. Updates local tracking.\n**Usage:** `!kemono remove `", inline=False)

    embed.set_footer(text=f"Help requested - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # Create a delete button
    delete_button = ui.Button(style=ButtonStyle.red, label="Delete")
    delete_button.custom_id = f"delete_help_{ctx.channel.id}_{ctx.message.id}"

    async def delete_callback(interaction: Interaction):
        if interaction.user == ctx.author:
            await interaction.message.delete()
        else:
            await interaction.response.send_message("Only the user who requested this can delete it.", ephemeral=True, delete_after=10)

    delete_button.callback = delete_callback

    # Create a view with the button
    view = ui.View()
    view.add_item(delete_button)

    await ctx.send(embed=embed, view=view, ephemeral=True)
    await auto_delete(ctx)

@client.command()
async def check(ctx, url: str):
    if not await check_role(ctx):
        return
    try:
        fixed_url = await fix_link(url)
        if not fixed_url:
            await ctx.send("Invalid URL. Please provide a valid kemono.su or Patreon URL.", ephemeral=True, delete_after=10)
            return

        # Fetch all chapters
        chapters = await fetch_chapters(fixed_url, 50)  # Fetches a list of chapters up to 50
        
        if not chapters:
            await ctx.send("No chapters found at this URL.", ephemeral=True, delete_after=10)
            return

        # Construct the message with all chapter titles
        chapter_list = "\n".join(f"#{i + 1} {chapter.get('title', 'Untitled')}" for i, chapter in enumerate(chapters))
        
        # Create an embed for formatting
        embed = Embed(title="Chapter List", description=chapter_list, color=0x00ff00)
        
        # Create a delete button
        delete_button = ui.Button(style=ButtonStyle.red, label="Delete")
        delete_button.custom_id = f"delete_{ctx.channel.id}_{ctx.message.id}"

        async def delete_callback(interaction: Interaction):
            if interaction.user == ctx.author:
                await interaction.message.delete()
            else:
                await interaction.response.send_message("Only the user who requested this can delete it.", ephemeral=True, delete_after=10)

        delete_button.callback = delete_callback

        # Create a view with the button
        view = ui.View()
        view.add_item(delete_button)

        # Send the message with the button
        message = await ctx.send(embed=embed, view=view, ephemeral=True)

    except Exception as e:
        await ctx.send(f"An error occurred while checking the URL: {str(e)}", ephemeral=True, delete_after=10)
    await auto_delete(ctx)

@client.command()
async def fetch(ctx, url: str, num_chapters: int, *skip_chapters):
    if not await check_role(ctx):
        return
    try:
        # Fix and validate the URL
        fixed_url = await fix_link(url)
        if not fixed_url:
            await ctx.send("Invalid URL. Please provide a valid kemono.su or Patreon URL.", delete_after=10)
            return

        # Parse URL for service and creator_id
        parts = fixed_url.split('/')
        if len(parts) >= 8 and parts[3] == 'api' and parts[4] == 'v1':
            service = parts[5]
            creator_id = parts[7]
        else:
            await ctx.send("The URL does not match the expected format for fetching chapters.", delete_after=10)
            return

        # Fetch creator profile to get name
        profile_url = f"https://kemono.su/api/v1/{service}/user/{creator_id}/profile"
        async with aiohttp.ClientSession() as session:
            async with session.get(profile_url) as response:
                if response.status == 200:
                    profile = await response.json()
                    creator_name = profile.get('name', 'Unknown')
                else:
                    creator_name = "Unknown"
                    print(f"Failed to fetch creator profile: {response.status}")

        # Fetch chapters, handle pagination, and skip specified chapters
        all_chapters = await fetch_chapters(fixed_url, num_chapters)
        chapters_to_process = []
        skip_set = set(map(int, skip_chapters[0].split(',')) if skip_chapters else [])

        for i, chapter in enumerate(all_chapters):
            if i + 1 not in skip_set:
                chapters_to_process.append(chapter)
            if len(chapters_to_process) == num_chapters:
                break

        # Generate filename
        filename = generate_filename(chapters_to_process)

        # Create EPUB with creator's name as title and author
        epub_file = await create_epub(chapters_to_process, creator_name, creator_name, url, filename)

        # Send the EPUB file in Discord with a message
        with open(epub_file, 'rb') as file:
            await ctx.send(f"Fetched from **[{creator_name}](<{fixed_url.replace('/api/v1/', '/')}>)**.", file=discord.File(file, f"{filename}.epub"))
        os.remove(epub_file)  # Clean up temporary file

    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}", delete_after=10)
    await auto_delete(ctx)

@client.command()
async def add(ctx, url: str):
    if not await check_role(ctx):
        return
    if not cookies:
        await ctx.send("Please log in first.", delete_after=10)
        return

    fixed_url = await fix_link(url)  # Await the async function here
    if not fixed_url:
        await ctx.send("Invalid URL. Please provide a valid kemono.su URL.", delete_after=10)
        return

    parts = fixed_url.split('/')
    if len(parts) >= 8 and parts[3] == 'api' and parts[4] == 'v1':  # Check for enough parts
        service = parts[5]
        creator_id = parts[7]
        favorites_url = f"https://kemono.su/api/v1/favorites/creator/{service}/{creator_id}"
        
        async with aiohttp.ClientSession(cookies=cookies) as session:
            try:
                async with session.post(favorites_url) as response:
                    if response.status == 200:
                        # Wait 3 seconds before checking the updated favorites list
                        await asyncio.sleep(3)
                        
                        favorites = await fetch_favorites(session)
                        new_creator = next((creator for creator in favorites if creator['id'] == creator_id), None)
                        if new_creator:
                            creator_name = new_creator['name']
                            await ctx.send(f"Added {creator_name} to favorites.", delete_after=10)
                            
                            try:
                                with open('creators_data.json', 'r') as file:
                                    creators_data = json.load(file)
                            except FileNotFoundError:
                                creators_data = {}
                            
                            creators_data[creator_id] = {
                                "id": creator_id,
                                "name": creator_name,
                                "service": service,
                                "updated": datetime.now().isoformat()
                            }
                            
                            with open('creators_data.json', 'w') as file:
                                json.dump(creators_data, file)
                        else:
                            await ctx.send(f"Failed to add to favorites. The creator does not exist.", delete_after=10)
                    else:
                        await ctx.send(f"Failed to add to favorites. Status code: {response.status}", delete_after=10)
            except aiohttp.ClientError as e:
                await ctx.send(f"Failed to connect or process the request: {str(e)}", delete_after=10)
            except Exception as e:
                await ctx.send(f"An unexpected error occurred: {str(e)}", delete_after=10)
    else:
        await ctx.send("The URL does not match the expected format for adding to favorites.", delete_after=10)
    await auto_delete(ctx)

@client.command()
async def remove(ctx, url: str):
    if not await check_role(ctx):
        return
    if not cookies:
        await ctx.send("Please log in first.", delete_after=10)
        return

    fixed_url = await fix_link(url)  # Await the async function here
    if not fixed_url:
        await ctx.send("Invalid URL. Please provide a valid kemono.su URL.", delete_after=10)
        return

    parts = fixed_url.split('/')
    if len(parts) >= 8 and parts[3] == 'api' and parts[4] == 'v1':  # Check for enough parts
        service = parts[5]
        creator_id = parts[7]
        favorites_url = f"https://kemono.su/api/v1/favorites/creator/{service}/{creator_id}"
        
        async with aiohttp.ClientSession(cookies=cookies) as session:
            try:
                # Fetch the current state of favorites to get the creator's name before removal
                favorites_before = await fetch_favorites(session)
                creator_before = next((creator for creator in favorites_before if creator['id'] == creator_id), None)
                
                if creator_before:
                    creator_name = creator_before['name']
                    async with session.delete(favorites_url) as response:
                        if response.status == 200:
                            # Wait for a moment to ensure the change is reflected
                            await asyncio.sleep(3)
                            # Fetch favorites again to confirm removal
                            favorites_after = await fetch_favorites(session)
                            creator_after = next((creator for creator in favorites_after if creator['id'] == creator_id), None)
                            
                            if creator_after is None:  # Confirm removal
                                await ctx.send(f"Removed {creator_name} from favorites.", delete_after=10)
                                
                                # Update creators_data.json
                                try:
                                    with open('creators_data.json', 'r') as file:
                                        creators_data = json.load(file)
                                except FileNotFoundError:
                                    creators_data = {}
                                
                                if creator_id in creators_data:
                                    del creators_data[creator_id]
                                    with open('creators_data.json', 'w') as file:
                                        json.dump(creators_data, file)
                            else:
                                await ctx.send("Failed to confirm removal from favorites. The creator might still be in the list.", delete_after=10)
                        else:
                            await ctx.send(f"Failed to remove from favorites. Status code: {response.status}", delete_after=10)
                else:
                    await ctx.send("Creator not found in favorites to remove.", delete_after=10)
            except aiohttp.ClientError as e:
                await ctx.send(f"Failed to connect or process the request: {str(e)}", delete_after=10)
            except Exception as e:
                await ctx.send(f"An unexpected error occurred: {str(e)}", delete_after=10)
    else:
        await ctx.send("The URL does not match the expected format for removing from favorites.", delete_after=10)
    await auto_delete(ctx)

async def fetch_favorites(session):
    url = "https://kemono.su/api/v1/account/favorites"
    async with session.get(url, cookies=cookies) as response:
        if response.status == 200:
            return await response.json()
        else:
            print(f"Failed to fetch favorites: {response.status}")
            return []

@tasks.loop(minutes=5)
async def check_for_updates():
    async with aiohttp.ClientSession() as session:
        try:
            favorites = await fetch_favorites(session)
            current_time = datetime.now().isoformat()

            try:
                with open('creators_data.json', 'r') as file:
                    previous_data = json.load(file)
            except FileNotFoundError:
                previous_data = {}

            new_data = {}
            for profile in favorites:
                creator_id = profile['id']
                new_data[creator_id] = {
                    "id": creator_id,
                    "name": profile['name'],
                    "service": profile['service'],
                    "updated": profile['updated']
                }

                if creator_id in previous_data:
                    if str(profile['updated']) != str(previous_data[creator_id]['updated']):
                        print(f"Update detected for {profile['name']} (ID: {creator_id})")
                        print(f"API timestamp: {profile['updated']}, Stored timestamp: {previous_data[creator_id]['updated']}")
                        channel = client.get_channel(Channel_id)  # Replace with your actual channel ID
                        if channel:
                            display_url = f"https://kemono.su/{profile['service']}/user/{profile['id']}"
                            detailed_profile_url = f"https://kemono.su/api/v1/{profile['service']}/user/{profile['id']}"
                            async with aiohttp.ClientSession() as session:
                                async with session.get(detailed_profile_url) as response:
                                    if response.status == 200:
                                        posts = await response.json()
                                        new_posts_count = sum(1 for post in posts 
                                                              if post.get('added', '') > previous_data[creator_id]['updated'])
                                        
                                        content = f"**[{profile['name']}](<{display_url}>)** has been updated with {new_posts_count} new posts."
                                        try:
                                            await channel.send(content)
                                        except discord.errors.HTTPException as e:
                                            print(f"Failed to send message for {profile['name']}: {e}")
                                        except Exception as e:
                                            print(f"An unexpected error occurred while sending message for {profile['name']}: {e}")
                                    else:
                                        print(f"Failed to fetch detailed profile data for {profile['name']}. Status: {response.status}")
                else:
                    print(f"New creator added: {profile['name']}")

            # Save new data
            with open('creators_data.json', 'w') as file:
                json.dump(new_data, file)
        except aiohttp.ClientError as e:
            print(f"An error occurred while fetching updates: {e}")
        except json.JSONDecodeError:
            print("Failed to parse JSON from creators_data.json. Resetting file.")
            with open('creators_data.json', 'w') as file:
                json.dump({}, file)
        except Exception as e:
            print(f"Error in update check: {e}")

    # Calculate time until next check
    next_check = check_for_updates.next_iteration
    now = datetime.now(timezone.utc)  # Make now timezone-aware using UTC
    time_until_next_check = next_check - now
    seconds_until_next = time_until_next_check.total_seconds()
    minutes, seconds = divmod(int(seconds_until_next), 60)
    print(f"Checked favorites at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")

async def fix_link(link):
    if not link or not isinstance(link, str):
        return None
    link = link.strip()

    if "patreon.com" in link.lower():
        user_id = await get_patreon_id(link)
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

async def get_patreon_id(url):
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

async def fetch_chapters(feed_url, max_chapters):
    chapters = []
    offset = 0
    pages_to_fetch = max((max_chapters - 1) // 50 + 1, 1)  # Calculate pages needed based on 50 chapters per page
    
    async with aiohttp.ClientSession() as session:
        for _ in range(pages_to_fetch):
            async with session.get(f"{feed_url}?o={offset}") as response:
                if response.status != 200:
                    break
                new_chapters = await response.json()
                if not new_chapters:
                    break
                chapters.extend(new_chapters)
                offset += 50
                if len(chapters) >= max_chapters:  # Stop fetching if we've got enough chapters
                    break

    return sorted(chapters[:max_chapters], key=lambda x: x.get('published', ''), reverse=True)

async def create_epub(chapters, title, author, profile_url, filename):
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
    default_filename = f"{sanitize_filename(lowermost_title[:15])}-{sanitize_filename(uppermost_title[:15])}" if len(chapters) > 1 else sanitize_filename(chapters[0]['title'][:15])
    return default_filename

async def auto_delete(ctx):
    try:
        await ctx.message.delete()
    except discord.errors.NotFound:
        pass

async def check_role(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.", delete_after=10)
        return False
    author_roles = [role.name for role in ctx.author.roles]
    for role in allowed_roles:
        if role.lower() in [r.lower() for r in author_roles]:
            return True
    await ctx.send("You do not have the required role to use this command.", delete_after=10)
    return False
    
@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send("You do not have permission to use this command.", delete_after=10)
    await auto_delete(ctx)

@client.event
async def on_ready():
    check_for_updates.start()
    print(f'{client.user} has connected to Discord!')
    if check_for_updates.next_iteration:
        next_check = check_for_updates.next_iteration
        now = datetime.now(timezone.utc)  # Make now timezone-aware using UTC
        time_until_next_check = next_check - now
        seconds_until_next = time_until_next_check.total_seconds()
        minutes, seconds = divmod(int(seconds_until_next), 60)
        print(f"First API check in {minutes:02d}:{seconds:02d}")
    else:
        print("Task not scheduled yet. First API check will be soon.")

@client.check
async def globally_check(ctx):
    return ctx.channel.id == Channel_id and await check_role(ctx)
    
client.run(bot_token)
