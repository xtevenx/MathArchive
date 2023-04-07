import asyncio
import json
import os
import time
from asyncio import Queue

import discord
import discord.ext.tasks
from discord import Client, Intents, Interaction, Member, VoiceChannel
from yt_dlp import YoutubeDL

PLAY_FILE: str = 'processed.mka'
TEMP_FILE: str = 'download'

# Options for yt_dlp.
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


class SmurfAbortion(Client):

    async def on_ready(self):
        await tree.sync()

        try:
            self.play_music.start()
        except RuntimeError:
            ...

    @discord.ext.tasks.loop(seconds=LOOP_LATENCY)
    async def play_music(self):
        interaction, info_dict = await music_queue.get()
        await clear_queue(skip_queue)

        # TODO: Add always updating queue at bottom of channel.
        if (channel := get_channel(interaction)) is None:
            return

        # Get time before download. If file is not changed after this, then
        # download or normalize failed and don't play the file.
        download_time = time.time()

        # TODO: Move this to the command function and download beforehand.
        with YoutubeDL(YDL_OPTIONS) as ydl:
            ydl.download([info_dict['entries'][0]['webpage_url']])
        await normalize_audio()

        if not os.path.exists(PLAY_FILE):
            return
        if os.path.getmtime(PLAY_FILE) < download_time:
            return

        connection = await channel.connect()
        connection.play(discord.FFmpegOpusAudio(PLAY_FILE, codec='copy'))

        try:
            await asyncio.wait_for(skip_queue.get(), info_dict['entries'][0]['duration'])
            skip_queue.task_done()
        except asyncio.TimeoutError:
            ...

        await connection.disconnect()
        music_queue.task_done()


music_queue: Queue[tuple[Interaction, dict]] = Queue()
skip_queue: Queue[Interaction] = Queue()

intents = Intents.default()
intents.message_content = True

client = SmurfAbortion(intents=intents)
tree = discord.app_commands.CommandTree(client)


@tree.command(name='play', description='Queue a piece of audio to be played.')
async def command_play(interaction: Interaction, query: str):
    print('Received play command from user:', interaction.user.id)
    if interaction.user.id in get_play_users().union(get_skip_users()):
        with YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.sanitize_info(ydl.extract_info(query, download=False))
        info_dict = json.loads(json.dumps(info))
        # TODO: React to the user.
        await music_queue.put((interaction, info_dict))


@tree.command(name='skip', description='Skip this current piece of audio.')
async def command_skip(interaction: Interaction):
    print('Received skip command from user:', interaction.user.id)
    if interaction.user.id in get_skip_users():
        # TODO: React to the user.
        await skip_queue.put(interaction)


async def clear_queue(q: Queue) -> None:
    while not q.empty():
        await q.get()
        q.task_done()


async def normalize_audio() -> None:
    await (await asyncio.create_subprocess_shell(
        f'ffmpeg -y -i {TEMP_FILE} -c:a libopus -b:a 96k -filter:a loudnorm {PLAY_FILE}')).wait()


def get_channel(interaction: Interaction) -> VoiceChannel | None:
    if not isinstance(user := interaction.user, Member):
        return None
    if (voice := user.voice) is None:
        return None
    if not isinstance(channel := voice.channel, VoiceChannel):
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
