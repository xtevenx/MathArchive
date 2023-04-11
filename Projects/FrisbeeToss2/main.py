import asyncio
import json
import os
import time
from asyncio import Queue
from concurrent.futures import ThreadPoolExecutor

import discord
import discord.ext.tasks
from discord import Client, Intents, Interaction, Member, VoiceChannel
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
}


class SmurfAbortion(Client):

    async def on_ready(self):
        await tree.sync()

        try:
            self.play_music.start()
        except RuntimeError:
            ...

    @discord.ext.tasks.loop(seconds=0)
    async def play_music(self):
        interaction, info = await music_queue.get()

        # Don't do anything if the user is not in a channel.
        if (channel := get_channel(interaction)) is None:
            return

        # TODO: Move this to the command function and download beforehand.
        if not await ydl_download(info['webpage_url']):
            return

        connection = await channel.connect()
        connection.play(discord.FFmpegOpusAudio(PLAY_FILE, codec='copy'))

        try:
            await asyncio.wait_for(skip_queue.get(), info['duration'])
            skip_queue.task_done()
        except asyncio.TimeoutError:
            ...

        await connection.disconnect()
        music_queue.task_done()


music_queue: Queue[tuple[Interaction, dict]] = Queue()
skip_queue: Queue[Interaction] = Queue()

intents = Intents.default()
intents.message_content = True

# TODO: Add always updating queue at bottom of channel.
client = SmurfAbortion(intents=intents)
tree = discord.app_commands.CommandTree(client)


@tree.command(name='play', description='Queue a piece of audio to be played.')
async def command_play(interaction: Interaction, query: str):
    print('Received play command from user:', interaction.user.id)

    if interaction.user.id in get_play_users().union(get_skip_users()):
        await interaction.response.send_message('Querying...', ephemeral=True, silent=True)

        info = await ydl_extract_info(query)

        # The 'duration' values are in seconds.
        if info['duration'] > 900 and interaction.user.id not in get_skip_users():
            await interaction.edit_original_response(content='Stop griefing me (too long).')
            return
        if info['duration'] > 18000:
            await interaction.edit_original_response(content='Stop griefing me (too long).')
            return

        await interaction.edit_original_response(
            content='Added `{}` with duration `{:02d}:{:02d}`.'.format(
                info['title'], *divmod(round(info['duration']), 60)))
        await music_queue.put((interaction, info))

    else:
        await interaction.response.send_message("I'm not listening, lil' bro.",
                                                ephemeral=True,
                                                silent=True)


@tree.command(name='skip', description='Skip this current piece of audio.')
async def command_skip(interaction: Interaction):
    print('Received skip command from user:', interaction.user.id)

    if interaction.user.id in get_skip_users():
        await interaction.response.send_message('Attempting to skip this piece of audio.',
                                                ephemeral=True,
                                                silent=True)
        await skip_queue.put(interaction)

    else:
        await interaction.response.send_message("I'm not listening, lil' bro.",
                                                ephemeral=True,
                                                silent=True)


def get_channel(interaction: Interaction) -> VoiceChannel | None:
    if not isinstance(user := interaction.user, Member):
        return None
    if (voice := user.voice) is None:
        return None
    if not isinstance(channel := voice.channel, VoiceChannel):
        return None
    return channel


async def ydl_extract_info(query: str) -> dict:
    loop = asyncio.get_running_loop()

    with ThreadPoolExecutor() as pool, YoutubeDL(YDL_OPTIONS) as ydl:
        info = await loop.run_in_executor(pool, lambda: ydl.extract_info(query, download=False))
        info = json.loads(json.dumps(ydl.sanitize_info(info)))

    if 'entries' in info:
        info = info['entries'][0]
    return info


async def ydl_download(url: str) -> bool:
    loop = asyncio.get_running_loop()

    # If file not changed later, then download or normalize failed, so return the failure.
    download_time = time.time()

    with ThreadPoolExecutor() as pool, YoutubeDL(YDL_OPTIONS) as ydl:
        await loop.run_in_executor(pool, ydl.download, [url])
    await (await asyncio.create_subprocess_shell(
        f'ffmpeg-normalize -o {PLAY_FILE} -f --keep-loudness-range-target -c:a libopus {TEMP_FILE}'
    )).wait()

    return os.path.exists(PLAY_FILE) and os.path.getmtime(PLAY_FILE) > download_time


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
