import datetime
import lcu_driver
import psutil

# Allowed start/end time windows by hour of the day.
START_TIME = {"hour": 5, "minute": 0, "second": 0}
END_TIME = {"hour": 10, "minute": 30, "second": 0}

connector = lcu_driver.Connector()


@connector.ws.register("/lol-chat/v1/me")
async def status_update(connection, event):
    now = datetime.datetime.now()
    start = now.replace(**START_TIME)
    end = now.replace(**END_TIME)
    if (await (await connection.request("get", "/lol-chat/v1/me")).json()).get("availability") != "dnd" \
            and not start <= now < end:
        # connector.ws.registered_uris.clear()
        for p in psutil.process_iter():
            if p.name() == "LeagueClient.exe":
                p.kill()


connector.start()
