# Discord music player bot. Only works with one server and voice channel.

# Basic design overview:
#  * Global variables:
#      * DEQUE - queue for what to play (popleft, pushright) [collections.deque]
#      * VC - the current voice channel [discord.VoiceClient]
#  * Bot functions:
#      * play() - Adds an item to the queue and initializes it.
#      * skip() - Stops the current item that's playing.

import asyncio
import collections
from typing import Optional
from urllib.parse import urlparse

import colorlog
import discord
from discord.ext import commands
# import youtube_dl
import yt_dlp as youtube_dl

from _env import *

MAX_FILE_SIZE = 32 * 1024 * 1024  # bytes
BOT_LATENCY = 2.0  # seconds
REQUEST_DELAY = 2.0  # seconds

# ``logging'' configurations --------------------------------------------------

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s[%(levelname)s] %(message)s",
    log_colors={
        "DEBUG": "light_black",
        "INFO": "white",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    }
))

logger = colorlog.getLogger()
logger.addHandler(handler)
logger.setLevel(colorlog.DEBUG)


# Environment set up code -----------------------------------------------------

class Music:
    ytdl_opts: dict = {
        "format": "bestaudio",
        "audio_format": "m4a",
        "audio_quality": 0,
        "outtmpl": "download.m4a",
        "overwrites": True,
        "sleep_interval_requests": REQUEST_DELAY,
    }

    async def initialize(self, ctx, *args):
        # Sanity check the user sending the message.
        voice = ctx.author.voice
        if voice is None:  # todo: check if user is in the same voice channel.
            return await ctx.send(f"{ctx.author.mention} is not in a channel.")
        voice_channel = voice.channel

        # Set up the embed message.
        embed = discord.Embed(title=surround_message("Processing request", ":arrows_counterclockwise:"))
        embed.add_field(name="Request", value=" ".join(args))
        embed.add_field(name="From", value=ctx.author.name)
        message = await ctx.send(embed=embed)
        embed.clear_fields()

        # Process the arguments.
        url = args[0] if urlparse(args[0]).scheme else "ytsearch1:" + " ".join(args)

        # Preprocess the url.
        with youtube_dl.YoutubeDL(Music.ytdl_opts) as ytdl:
            info = ytdl.extract_info(url, download=False)
            if "entries" in info:
                info = info["entries"][0]

            embed.title = surround_message("In queue", ":arrows_counterclockwise:")
            embed.add_field(name="Title", value=info["title"], inline=True)
            embed.add_field(name="Uploader", value=info["uploader"], inline=True)
            embed.set_image(url=info["thumbnail"])
            embed.set_footer(text="Retrieved from: " + info["webpage_url"])
            await message.edit(embed=embed)

            if info["filesize"] > MAX_FILE_SIZE:
                embed.title = surround_message("Sorry; item too large.", ":no_entry_sign:")
                return await message.edit(embed=embed)

        # Wait until it's my turn.
        while DEQUE[0] != self:
            await asyncio.sleep(BOT_LATENCY)

        # Download the item.
        with youtube_dl.YoutubeDL(Music.ytdl_opts) as ytdl:
            embed.title = surround_message("Downloading item", ":arrow_double_down:")
            await message.edit(embed=embed)

            ytdl.download([info["webpage_url"]])

        # Join the voice channel and play the item.
        embed.title = surround_message("Now playing", ":musical_note:")
        await message.edit(embed=embed)

        global VC
        if VC is None:
            VC = await voice_channel.connect()
        VC.play(discord.FFmpegPCMAudio("download.m4a", options="-maxrate 96k -bufsize 192k"))

        # Sleep while audio is playing.
        while VC.is_playing():
            await asyncio.sleep(BOT_LATENCY)

        # Clean up.
        embed.title = surround_message("Finished playing", ":white_check_mark:")
        await message.edit(embed=embed)

        DEQUE.popleft()
        if len(DEQUE) == 0:
            await VC.disconnect()
            VC = None


DEQUE: collections.deque[Music] = collections.deque()
VC: Optional[discord.VoiceClient] = None

# ``discord'' configurations --------------------------------------------------

activity = discord.Activity(type=discord.ActivityType.listening, name="the abyss' howling.")
bot = commands.Bot(command_prefix="!", case_insensitive=True, activity=activity)


@bot.event
async def on_ready() -> None:
    logger.info(f"{bot.user.name} has connected to Discord!")


@bot.command()
async def play(ctx, *args):
    DEQUE.append(obj := Music())
    await obj.initialize(ctx, *args)


@bot.command()
async def skip(ctx):
    VC.stop()


# Utility functions.
def surround_message(msg: str, surr: str, times: int = 1) -> str:
    return f"{surr * times}  {msg}  {surr * times}"


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
