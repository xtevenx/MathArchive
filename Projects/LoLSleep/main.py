import datetime
import lcu_driver
import psutil

# Allowed start/end time windows by hour of the day.
START_HOUR: int = 5
END_HOUR: int = 23

connector = lcu_driver.Connector()


@connector.ws.register("/lol-chat/v1/me")
async def status_update(connection, event):
    if (await (await connection.request("get", "/lol-chat/v1/me")).json()).get("availability") != "dnd" \
            and not START_HOUR <= datetime.datetime.now().hour < END_HOUR:
        # connector.ws.registered_uris.clear()
        for p in psutil.process_iter():
            if p.name() == "LeagueClient.exe":
                p.kill()


connector.start()
