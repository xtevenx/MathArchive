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
    NotFound,
    TextChannel,
    VoiceChannel,
    VoiceClient,
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
# if True, then we want to send a new queue message (and delete old if necessary).
# we get a False in on_ready(), so if this is True, we assume that QUEUE_MESSAGE not None.
QUEUE_UPDATE: Queue[bool] = Queue()


class MusicApplet(discord.ui.View):

    async def interaction_check(self, interaction: discord.interactions.Interaction):
        if (channel := get_channel(interaction)) is None:
            return False
        return client.user in channel.members

    @discord.ui.button(emoji='⏪', style=discord.ButtonStyle.secondary)
    async def reverse_callback(self, interaction: discord.interactions.Interaction,
                               _: discord.ui.Button):
        await interaction.response.defer()
        await skip_queue.put(-15)

    @discord.ui.button(emoji='⏯️', style=discord.ButtonStyle.secondary)
    async def pause_callback(self, interaction: discord.interactions.Interaction,
                             _: discord.ui.Button):
        await interaction.response.defer()
        await skip_queue.put(0)

    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.secondary)
    async def forward_callback(self, interaction: discord.interactions.Interaction,
                               _: discord.ui.Button):
        await interaction.response.defer()
        await skip_queue.put(+15)

    @discord.ui.button(label='Skip', style=discord.ButtonStyle.secondary)
    async def skip_callback(self, interaction: discord.interactions.Interaction,
                            _: discord.ui.Button):
        await interaction.response.defer()
        await skip_queue.put(None)


class SmurfAbortion(Client):

    async def close(self):
        try:
            _ = QUEUE_MESSAGE is not None and await QUEUE_MESSAGE.delete()
        except NotFound:
            ...

        await super().close()

    async def on_message(self, message: Message):
        assert self.user is not None

        if message.channel == QUEUE_CHANNEL and message.author != self.user:
            await QUEUE_UPDATE.put(True)

    async def on_ready(self):
        global QUEUE_CHANNEL

        # Find the channel to put the queue.
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

        # This is quite important (see note by definition of QUEUE_UPDATE) for more info.
        await QUEUE_UPDATE.put(False)

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
        self._play_music(connection)

        # TODO: Add a currently playing (or paused) display to the queue.
        # We should also need to add stuff in the loop below.

        await QUEUE_UPDATE.put(False)

        try:
            while True:
                skip_queue.get_nowait()
                skip_queue.task_done()
        except asyncio.QueueEmpty:
            ...

        # Modify start_time to keep track of how much has been played.
        start_time = time.monotonic()
        pause_time = 0

        try:
            while True:
                remaining_time = (info['duration'] + start_time - time.monotonic(),
                                  None)[not connection.is_playing()]

                skip_amount = await asyncio.wait_for(skip_queue.get(), remaining_time)

                # NOTE: We can use a switch-case in Python 3.10

                if skip_amount is None:
                    skip_queue.task_done()
                    break

                if skip_amount:
                    start_time = max(start_time - skip_amount, time.monotonic() - info['duration'])
                    connection.stop()

                    self._play_music(connection, start_time)

                else:
                    if connection.is_playing():
                        pause_time = time.monotonic()
                        connection.stop()
                    else:
                        start_time += time.monotonic() - pause_time
                        self._play_music(connection, start_time)

                skip_queue.task_done()

        except asyncio.TimeoutError:
            ...

        # TODO: Make optimistically don't disconnect, then only disconnect when no more stuff.

        await connection.disconnect()
        music_queue.task_done()

        await QUEUE_UPDATE.put(False)

    def _play_music(self, connection: VoiceClient, start_time: float | None = None):
        seek_amount = time.monotonic() - (start_time or time.monotonic())
        connection.play(discord.FFmpegPCMAudio(PLAY_FILE, before_options=f'-ss {seek_amount:.3f}'))

    @discord.ext.tasks.loop(seconds=0)
    async def update_queue(self):
        global QUEUE_MESSAGE
        assert QUEUE_CHANNEL is not None

        resend = await QUEUE_UPDATE.get()

        lines = ('`{}` with duration `{}`'.format(info['title'], format_duration(info['duration']))
                 for _, info in music_list)
        queue_text = '**Queue**\n' + '\n'.join(f'{i + 1}. {line}' for i, line in enumerate(lines))

        send_coroutine = QUEUE_CHANNEL.send(content=queue_text,
                                            view=MusicApplet(timeout=None),
                                            silent=True)

        if resend:
            assert QUEUE_MESSAGE is not None
            msg, _ = await asyncio.gather(send_coroutine,
                                          QUEUE_MESSAGE.delete(),
                                          return_exceptions=True)
            QUEUE_MESSAGE = [None, msg][type(msg) is Message]

        elif QUEUE_MESSAGE is None:
            QUEUE_MESSAGE = await send_coroutine

        else:
            await QUEUE_MESSAGE.edit(content=queue_text)
            send_coroutine.close()


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


async def queue_get():
    await music_queue.get()
    element = music_list.pop(0)

    await QUEUE_UPDATE.put(False)

    return element


async def queue_put(element):
    music_list.append(element)
    await music_queue.put(None)

    await QUEUE_UPDATE.put(False)


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
    download_time = os.path.getmtime(PLAY_FILE) if os.path.exists(PLAY_FILE) else 0

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
