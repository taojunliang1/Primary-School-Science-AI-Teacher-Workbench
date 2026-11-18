from backend.tests.test_chat_artifacts import API, login, server


def test_weekly_schedule_sync_and_stale_write(server):
    client, password, _, _ = server
    url = API + "/courses"
    assert client.get(url).status_code == 401
    headers = login(client, password)
    assert client.get(url, headers=headers).json() == {"version": None, "cells": []}
    cells = [
        {"day": 1, "period": "08:30–09:10", "text": "三（1）班", "courseType": "regular", "important": True},
        {"day": 2, "period": "15:45–16:15", "text": "无人机足球训练", "courseType": "contest", "important": False},
        {"day": 3, "period": "09:45–10:25", "text": "", "courseType": "empty", "important": False},
    ]
    response = client.put(url, headers=headers, json={"version": None, "cells": cells})
    assert response.status_code == 200, response.text
    snapshot = response.json()
    assert snapshot["version"] and snapshot["cells"] == cells
    assert client.get(url, headers=headers).json() == snapshot
    assert client.put(url, headers=headers, json={"version": None, "cells": cells}).status_code == 409
    assert client.put(url, headers=headers, json={
        "version": snapshot["version"], "cells": [cells[0], cells[0]],
    }).status_code == 422
    changed = [{**cells[0], "text": "三（2）班"}, *cells[1:]]
    response = client.put(url, headers=headers, json={"version": snapshot["version"], "cells": changed})
    assert response.status_code == 200, response.text
    assert response.json()["version"] != snapshot["version"]
    assert response.json()["cells"] == changed
