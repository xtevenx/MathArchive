import datetime
import lcu_driver.utils
import psutil

START_TIME = {"hour": 5, "minute": 0, "second": 0}
END_TIME = {"hour": 22, "minute": 30, "second": 0}

connector = lcu_driver.Connector()


# Hack the library to burn less CPU when League is not running.
from time import sleep
_foo = lcu_driver.utils.return_process
lcu_driver.utils.return_process = lambda *a, **k: [sleep(5), _foo(*a, **k)][1]


@connector.ws.register("/lol-chat/v1/me")
async def status_update(connection, event):
    now = datetime.datetime.now()
    start = now.replace(**START_TIME)
    end = now.replace(**END_TIME)

    if not start <= now < end \
            and (await (await connection.request(
        "get", "/lol-chat/v1/me"
    )).json()).get("availability") != "dnd":
        # connector.ws.registered_uris.clear()
        for p in psutil.process_iter():
            if p.name() == "LeagueClient.exe":
                p.kill()


connector.start()
