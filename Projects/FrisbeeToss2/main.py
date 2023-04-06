"""FrisbeeToss2

Second incarnation of a single purpose very clunky discord bot.
Much better than the first version but still horribly designed.
"""

import asyncio
import os
import time

import discord
import discord.ext.tasks
from yt_dlp import YoutubeDL

PLAY_FILE: str = 'processed.mka'
TEMP_FILE: str = 'download'

YDL_OPTIONS = {
    'default_search': 'auto',
    'format': 'bestaudio',
    'format_sort': 'quality,codec,ext,br'.split(','),
    'outtmpl': TEMP_FILE,
    'overwrites': True,
    # Maximum filesize to download (bytes).
    'max_filesize': 32 * (1024 * 1024),
}

# How often to check for commands or audio end (seconds).
LOOP_LATENCY: float = 0.618


class MyClient(discord.Client):

    async def on_ready(self):
        await tree.sync()

        if not self.manage_queue.is_running():
            self.manage_queue.start()

    @discord.ext.tasks.loop(seconds=0, count=1)
    async def manage_queue(self):
        while True:
            interaction, query = await music_queue.get()

            # TODO: Move these checks to the command function and respond to the user.
            # TODO: Add always updating queue at bottom of channel.
            if (channel := get_channel(interaction)) is None:
                continue

            # Get time before download. If file is not changed after this, then
            # download or normalize failed and don't play the file.
            download_time = time.time()

            with YoutubeDL(YDL_OPTIONS) as ydl:
                ydl.download([query])
            await normalize_audio()

            if not os.path.exists(PLAY_FILE):
                continue
            if os.path.getmtime(PLAY_FILE) < download_time:
                continue

            connection = await channel.connect()
            connection.play(discord.FFmpegOpusAudio(PLAY_FILE, codec='copy'))

            while connection.is_playing():
                try:
                    skip_channel = get_channel(skip_queue.get_nowait())
                    if skip_channel is not None and skip_channel.id == channel.id:
                        break
                except asyncio.QueueEmpty:
                    await asyncio.sleep(LOOP_LATENCY)

            await connection.disconnect()


skip_queue: asyncio.Queue[discord.Interaction] = asyncio.Queue()
music_queue: asyncio.Queue[tuple[discord.Interaction, str]] = asyncio.Queue()

intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)
tree = discord.app_commands.CommandTree(client)


@tree.command(name='play', description='Queue a piece of audio to be played.')
async def command_play(interaction: discord.Interaction, query: str):
    print('Received play command from user:', interaction.user.id)
    if interaction.user.id in get_play_users().union(get_skip_users()):
        await music_queue.put((interaction, query))


@tree.command(name='skip', description='Skip this current piece.')
async def command_skip(interaction: discord.Interaction):
    print('Received skip command from user:', interaction.user.id)
    if interaction.user.id in get_skip_users():
        await skip_queue.put(interaction)


async def normalize_audio():
    await (await asyncio.create_subprocess_shell(
        f'ffmpeg -y -i {TEMP_FILE} -c:a libopus -b:a 96k -filter:a loudnorm {PLAY_FILE}'
    )).wait()


def get_channel(interaction) -> discord.VoiceChannel | None:
    if not isinstance(user := interaction.user, discord.Member):
        return None
    if (voice := user.voice) is None:
        return None
    if not isinstance(channel := voice.channel, discord.VoiceChannel):
        return None
    return channel


def get_play_users() -> set[int]:
    with open('PLAY_USERS') as fp:
        return {int(s.strip()) for s in fp.readlines()}


def get_skip_users() -> set[int]:
    with open('SKIP_USERS') as fp:
        return {int(s.strip()) for s in fp.readlines()}


if __name__ == '__main__':
    with open('./DISCORD_TOKEN') as fp:
        DISCORD_TOKEN = fp.read().strip()
    client.run(DISCORD_TOKEN)
