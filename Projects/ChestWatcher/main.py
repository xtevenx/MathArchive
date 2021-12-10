import lcu_driver

connector = lcu_driver.Connector()


@connector.ready
async def connect(connection):
    print("Connected to LCU API.")


@connector.close
async def disconnect(connection):
    print("Disconnected.")


@connector.ws.register("/lol-champ-select/v1/session")
async def on_champ_select(connection, event):
    available_champions = await get_available_champions(connection)
    if not available_champions:
        return

    summoner_id = await get_summoner_id(connection)
    chest_champions = await get_chest_champions(connection, summoner_id)
    owned_champions = await get_owned_champions(connection, summoner_id)

    # <clear_screen>
    import platform, os
    os.system("cls" if platform.system() == "Windows" else "clear")
    # </clear_screen

    available_champions = [c for c in available_champions if c in chest_champions]
    available_champions = [c for c in available_champions if c in owned_champions]
    available_champions.sort(key=lambda c: chest_champions[c], reverse=True)
    for champion_id in available_champions:
        print(f"Chest available on {owned_champions[champion_id]}.")


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
    """:returns: summoner ID of the current user."""
    return (await (
        await connection.request("get", "/lol-chat/v1/me")
    ).json())["summonerId"]


connector.start()
