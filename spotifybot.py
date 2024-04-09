# this code is not optimized nor is it complete, it is just a simple example of how to create a bot that can interact with discord and spotify
# songs are upvoted and downvoted by users and the top 10 songs are displayed in the discord chat when the --top command is used
# you are free to use this code as you wish, but please remember to replace the bot token and the spotify client id and secret with your own in the config.json file
# you will also need to install the discord and spotipy libraries using pip
# you can install them by running the following commands in your terminal:
# pip install discord
# pip install spotipy

import discord
from discord.ext import commands
import re
import sqlite3
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json

intents = discord.Intents.default()
intents.message_content = True

with open('config.json', 'r') as config_file:
    config = json.load(config_file)

bot_token = config['bot_token'] # Replace with your bot token in the config.json file
spotify_client_id = config['client_id'] # Replace with your Spotify client ID in the config.json file
spotify_client_secret = config['client_secret'] # Replace with your Spotify client secret in the config.json file

bot = commands.Bot(command_prefix='--', intents=intents)

# Connect to database on startup
conn = sqlite3.connect('votes.db')
c = conn.cursor()
client_credentials_manager = SpotifyClientCredentials(client_id=spotify_client_id, client_secret=spotify_client_secret)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Create table (if it doesn't exist)
c.execute('''CREATE TABLE IF NOT EXISTS votes (song_link TEXT PRIMARY KEY, votes INTEGER)''')
conn.commit()

@bot.event
async def on_ready():
    print('Bot is ready!')

# Add upvote and downvote reactions to Spotify links
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    spotify_regex = r'https://open.spotify.com/(playlist|track)/[a-zA-Z0-9]+'
    if re.search(spotify_regex, message.content):
        await message.add_reaction('⬆️')
        await message.add_reaction('⬇️')

    await bot.process_commands(message)

# Handle upvote and downvote reactions
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if reaction.emoji in ('⬆️', '⬇️'):
        song_link = reaction.message.content

        # Use ON CONFLICT for efficient vote updates
        c.execute('''
            INSERT OR REPLACE INTO votes (song_link, votes)
            VALUES (?, COALESCE((SELECT votes FROM votes WHERE song_link=?), 0) + (?))
        ''', (song_link, song_link, 1 if reaction.emoji == '⬆️' else -1))
        conn.commit()

# Handle --top command
@bot.command()
async def top(ctx):
    lock = asyncio.Lock()

    async with lock:
        try:
            top_songs = []
            # Fetch top 10 songs in a single call
            for row in c.execute('SELECT * FROM votes ORDER BY votes DESC LIMIT 10').fetchall():
                song_link = row[0]
                votes = row[1]
                track_id = song_link.split('/')[-1].split('?')[0]  # Extract the track ID and remove any query parameters
                track_info = sp.track(track_id)
                song_name = track_info['name']
                song_url = track_info['external_urls']['spotify']
                top_songs.append(f"{len(top_songs)+1}. [{votes} votes] [{song_name}]({song_url})")

            # Create an embed with the list of top songs
            embed = discord.Embed(title="Top Songs", description="\n".join(top_songs), color=discord.Color.green())
            await ctx.message.delete()  # Delete the command message
            await ctx.send(embed=embed)
        except spotipy.SpotifyException as e:
            print(f"Spotify API error: {e}")
            await ctx.send("An error occurred while retrieving top songs. Please try again later.") # Send an error message to the channel
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            await ctx.send("An error occurred while retrieving top songs. Please try again later.") # Send an error message to the channel

bot.run(bot_token)