import os
import time
from typing import Optional

import lcu_driver
import notifypy

searched_groups: Optional[list[str]] = None
# searched_groups: Optional[list[str]] = ["**Default"]

icon_path: str = "icon.png"

status_message: dict[str, str] = {
    "away": "{name} has come online.",
    "dnd": "{name} has finished their game.",
    "offline": "{name} has come online.",
    "mobile": "{name} has come online.",
}

connector = lcu_driver.Connector()


@connector.ready
async def connect(connection):
    print("Connected to LCU API.")

    global last_friends
    friends = await connection.request("get", "/lol-chat/v1/friends")
    last_friends = await friends.json()

    global last_me
    me = await connection.request("get", "/lol-chat/v1/me")
    last_me = await me.json()


@connector.close
async def disconnect(connection):
    print("Disconnected.")


@connector.ws.register("/lol-chat/v1/friend-counts")
async def friends_update(connection, event):
    friends = await connection.request("get", "/lol-chat/v1/friends")
    friends_json = await friends.json()

    global last_friends
    if len(friends_json) != len(last_friends):
        # Do nothing if there is a change in the length of the friends list.
        # This will miss some information if a friend changes state in this
        # exact hook timing but that's too unlikely to worry about.
        # Note: This will not miss anything if the client limits to a maximum
        # of one change per each "UPDATE" event, but that is unclear.
        return [last_friends := friends_json]

    for i, f in enumerate(friends_json):
        # Availability values represent the following.
        # - away: User is in the `Away` state.
        # - chat: User is in the `Online` state.
        # - dnd: User is in one of `In Queue`, `Champ Select`, or `In Game`.
        # - mobile: User is in the `League+` state.
        # - offline: User is in the `Offline` state.

        if searched_groups and f.get("groupName") not in searched_groups:
            continue
        if time.monotonic() < game_lockout_end and f.get("summonerId") in last_game_participants:
            continue

        last_availability = last_friends[i].get("availability")
        if f.get("availability") == "chat" and last_availability != "chat":
            notification = notifypy.Notify()
            notification.title = "LoLNotifier"
            notification.message = status_message[last_availability].format(name=f.get("name"))
            if os.path.isfile(icon_path):
                notification.icon = icon_path
            notification.send(block=False)

            print(notification.message)

    last_friends = friends_json


@connector.ws.register("/lol-champ-select/v1/session")
async def players_update(connection, event):
    session = await connection.request("get", "/lol-champ-select/v1/session")
    session_json = await session.json()

    if "myTeam" not in session_json:
        return

    global last_game_participants
    last_game_participants = set()
    for p in session_json["myTeam"] + session_json["theirTeam"]:
        last_game_participants.add(p.get("summonerId"))


@connector.ws.register("/lol-chat/v1/me")
async def status_update(connection, event):
    me = await connection.request("get", "/lol-chat/v1/me")
    me_json = await me.json()

    global last_me, game_lockout_end
    out_of_game = me_json.get("availability") == "chat" or me_json.get("availability") == "away"
    if out_of_game and last_me.get("availability") == "dnd":
        game_lockout_end = time.monotonic() + 60
    if me_json.get("availability") == "dnd":
        game_lockout_end = time.monotonic() + 3600

    last_me = me_json


last_friends = list()
last_game_participants = set()
last_me = dict()
game_lockout_end = 0.

connector.start()
