"""
This only works for one voice channel
Downloaded file locations are in the variables PLAY_FILE and TEMP_FILE
Channel name for the queue is defined in the variable QUEUE_NAME
"""

import asyncio
import json
import os
import time
from asyncio import Queue

import discord
import discord.ext.tasks
from discord import (
    Client,
    Intents,
    Interaction,
    Member,
    Message,
    TextChannel,
    VoiceChannel,
)
from ffmpeg_normalize import FFmpegNormalize
from yt_dlp import YoutubeDL

PLAY_FILE: str = '/tmp/FrisbeeToss2-processed.mka'
TEMP_FILE: str = '/tmp/FrisbeeToss2-temporary'

# Options for yt_dlp.
YDL_OPTIONS = {
    'default_search': 'auto',
    'format': 'bestaudio',
    'format_sort': ['quality', 'codec', 'br'],
    'outtmpl': TEMP_FILE,
    'overwrites': True,
    'quiet': True,
}

# Sticky queue message
QUEUE_NAME: str = 'music'
QUEUE_CHANNEL: TextChannel | None = None
QUEUE_MESSAGE: Message | None = None
QUEUE_UPDATE: Queue[None] = Queue()


class MusicApplet(discord.ui.View):

    @discord.ui.button(label='Skip')
    async def skip_callback(self, interaction: discord.interactions.Interaction,
                            _: discord.ui.Button):
        await interaction.response.send_message('Skipping...', ephemeral=True, silent=True)
        await skip_queue.put(0)


class SmurfAbortion(Client):

    async def on_ready(self):
        global QUEUE_CHANNEL

        for guild in client.guilds:
            for channel in guild.text_channels:
                if channel.name == QUEUE_NAME:
                    QUEUE_CHANNEL = channel

        await tree.sync()

        try:
            self.play_music.start()
        except RuntimeError:
            ...

        try:
            self.update_queue.start()
        except RuntimeError:
            ...

        await QUEUE_UPDATE.put(None)

    @discord.ext.tasks.loop(seconds=0)
    async def play_music(self):
        interaction, info = await queue_get()

        # Don't do anything if the user is not in a channel.
        if (channel := get_channel(interaction)) is None:
            return

        # TODO: Move this to the command function and download beforehand.
        if not await ydl_download(info['webpage_url']):
            return

        connection = await channel.connect()
        connection.play(discord.FFmpegPCMAudio(PLAY_FILE))

        await QUEUE_UPDATE.put(None)

        try:
            while True:
                skip_queue.get_nowait()
        except asyncio.QueueEmpty:
            ...

        try:
            # TODO: Make this manage skip types.
            await asyncio.wait_for(skip_queue.get(), info['duration'])
            skip_queue.task_done()
        except asyncio.TimeoutError:
            ...

        await connection.disconnect()
        music_queue.task_done()

        await QUEUE_UPDATE.put(None)

    @discord.ext.tasks.loop(seconds=0)
    async def update_queue(self):
        global QUEUE_MESSAGE
        assert QUEUE_CHANNEL is not None

        await QUEUE_UPDATE.get()

        # Delete the old message if necessary.

        if QUEUE_MESSAGE is not None:
            is_latest = False
            async for message in QUEUE_CHANNEL.history(limit=1):
                is_latest = message.id == QUEUE_MESSAGE.id

            if not is_latest:
                try:
                    await QUEUE_MESSAGE.delete()
                finally:
                    QUEUE_MESSAGE = None

        # Time to make a new message!

        queue_text = '**Queue**\n' + '\n'.join('{}. `{}` with duration `{}`'.format(
            i + 1, info['title'], format_duration(info['duration']))
                                               for i, (_, info) in enumerate(music_list[:5]))

        if QUEUE_MESSAGE is None:
            QUEUE_MESSAGE = await QUEUE_CHANNEL.send(content=queue_text,
                                                     view=MusicApplet(),
                                                     silent=True)
        else:
            await QUEUE_MESSAGE.edit(content=queue_text)


# music_queue and music_list are coupled, hence should always have the same number of elements.
# music_queue is used to efficiently wait for something to play.
# music_list carries the actual information, and is used to display the queue.
# please append to music_list before pushing to music_queue.
# there's probably a better way to do this, but I do not know it.
music_queue: Queue[None] = Queue()
music_list: list[tuple[Interaction, dict]] = []

# carries the number of seconds to skip forwards/backwards.
# if None, then skip the entire thing.
# if 0, then toggle play or pause.
skip_queue: Queue[float | None] = Queue()

intents = Intents.default()
intents.message_content = True

client = SmurfAbortion(intents=intents)
tree = discord.app_commands.CommandTree(client)


@tree.command(name='play', description='Queue a piece of audio to be played.')
async def command_play(interaction: Interaction, query: str):
    await interaction.response.send_message('Querying...', ephemeral=True, silent=True)

    info = await ydl_extract_info(query)

    # The 'duration' value is in seconds.
    if info['duration'] > 18000:
        # Give no error message. :)
        return

    try:
        await interaction.edit_original_response(content='Added `{}` with duration `{}`.'.format(
            info['title'], format_duration(info['duration'])))
    finally:
        await queue_put((interaction, info))


@tree.command(name='skip', description='Skip this current piece of audio.')
async def command_skip(interaction: Interaction):
    await interaction.response.send_message('Skipping...', ephemeral=True, silent=True)
    await skip_queue.put(0)


async def queue_get():
    await music_queue.get()
    element = music_list.pop(0)

    await QUEUE_UPDATE.put(None)

    return element


async def queue_put(element):
    music_list.append(element)
    await music_queue.put(None)

    await QUEUE_UPDATE.put(None)


async def ydl_extract_info(query: str) -> dict:
    loop = asyncio.get_running_loop()

    with YoutubeDL(YDL_OPTIONS) as ydl:
        info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        info = json.loads(json.dumps(ydl.sanitize_info(info)))

    if 'entries' in info:
        info = info['entries'][0]
    return info


async def ydl_download(url: str) -> bool:
    loop = asyncio.get_running_loop()

    # If file not changed later, then download or normalize failed, so return the failure.
    download_time = time.time()

    with YoutubeDL(YDL_OPTIONS) as ydl:
        await loop.run_in_executor(None, ydl.download, [url])

    normalizer = FFmpegNormalize(keep_loudness_range_target=True)
    normalizer.add_media_file(TEMP_FILE, PLAY_FILE)
    await loop.run_in_executor(None, normalizer.run_normalization)

    return os.path.exists(PLAY_FILE) and os.path.getmtime(PLAY_FILE) > download_time


def format_duration(duration: float) -> str:
    hour, remainder = divmod(duration, 3600)
    return ['', f'{hour}:'][hour > 0] + '{:02d}:{:02d}'.format(*divmod(round(remainder), 60))


def get_channel(interaction: Interaction) -> VoiceChannel | None:
    if not isinstance(user := interaction.user, Member):
        return None
    if (voice := user.voice) is None:
        return None
    if not isinstance(channel := voice.channel, VoiceChannel):
        return None
    return channel


if __name__ == '__main__':
    with open('./DISCORD_TOKEN') as fp:
        DISCORD_TOKEN = fp.read().strip()
    client.run(DISCORD_TOKEN)
