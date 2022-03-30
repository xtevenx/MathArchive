from lcu_driver import Connector
from PIL import Image
from pystray import Icon
from threading import Thread

connector = Connector()


@connector.ready
async def connect(connection):
    print("Connected to LCU API.")

    global icon, icon_thread
    icon = Icon(name="cw2", icon=Image.open('chest_icon.webp'))
    icon_thread = Thread(target=lambda: icon.run())
    icon_thread.start()


@connector.close
async def disconnect(connection):
    print("Disconnected.")

    icon.stop()
    icon_thread.join()


@connector.ws.register("/lol-champ-select/v1/session")
async def on_champ_select(connection, event):
    available_champions = await get_available_champions(connection)
    if not available_champions:
        return

    summoner_id = await get_summoner_id(connection)
    chest_champions = await get_chest_champions(connection, summoner_id)
    owned_champions = await get_owned_champions(connection, summoner_id)

    available_champions = [c for c in available_champions if c in chest_champions]
    available_champions = [c for c in available_champions if c in owned_champions]
    available_champions.sort(key=lambda c: chest_champions[c], reverse=True)
    icon.title = "\n".join(owned_champions[cid] for cid in available_champions)


async def get_available_champions(connection) -> list[int]:
    session = await (
        await connection.request("get", "/lol-champ-select/v1/session")
    ).json()

    if "benchChampionIds" not in session:
        return []

    return session["benchChampionIds"] + [
        player["championId"] for player in session["myTeam"]
    ]


async def get_chest_champions(connection, summoner_id: int) -> dict[int, int]:
    """:returns: dictionary mapping champion id to mastery points."""
    return {champion["championId"]: champion["championPoints"] for champion in await (
        await connection.request(
            "get", f"/lol-collections/v1/inventories/{summoner_id}/champion-mastery"
        )
    ).json() if not champion["chestGranted"]}


async def get_owned_champions(connection, summoner_id: int) -> dict[int, str]:
    """:returns: dictionary mapping champion id to champion name."""
    return {champion["id"]: champion["name"] for champion in await (
        await connection.request(
            "get", f"/lol-champions/v1/inventories/{summoner_id}/champions-minimal"
        )
    ).json() if champion["ownership"]["owned"]}


async def get_summoner_id(connection) -> int:
    return (await (
        await connection.request("get", "/lol-chat/v1/me")
    ).json())["summonerId"]


if __name__ == "__main__":
    import time
    import lcu_driver.utils

    # Hack the library to burn less CPU when League is not running.
    # This makes the script check for League once every 60 seconds instead of constantly.
    _foo = lcu_driver.utils.return_process
    lcu_driver.utils.return_process = lambda *a, **k: [time.sleep(60), _foo(*a, **k)][1]

    connector.start()
