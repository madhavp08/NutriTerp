"""Meal diary, calorie totals, and the photo calendar (no network)."""

CREDS = {"email": "logger@umd.edu", "password": "correct-horse-battery"}

# 1x1 PNG. Tests check magic bytes, not pixels.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def signup(client):
    client.post("/api/auth/signup", json=CREDS)
    client.put("/api/profile", json={"dietary_pattern": "none", "goal": "maintain"})


def test_log_from_typed_entry_sums_calories(client):
    signup(client)
    client.post("/api/logs", json={"meal": "breakfast", "name": "Oatmeal", "calories": 350})
    body = client.post("/api/logs", json={"meal": "lunch", "name": "Bowl", "calories": 600}).json()
    assert body["calories_eaten"] == 950
    assert len(body["entries"]) == 2


def test_delete_log_recalculates_total(client):
    signup(client)
    day = client.post("/api/logs", json={"meal": "snack", "name": "Apple", "calories": 80}).json()
    log_id = day["entries"][0]["id"]
    after = client.delete(f"/api/logs/{log_id}").json()
    assert after["calories_eaten"] == 0
    assert after["entries"] == []


def test_cannot_delete_someone_elses_log(client):
    signup(client)
    log_id = client.post("/api/logs", json={"meal": "lunch", "name": "Wrap", "calories": 400}).json()["entries"][0]["id"]
    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "other@umd.edu", "password": "correct-horse-battery"})
    assert client.delete(f"/api/logs/{log_id}").status_code == 404


def test_photo_log_turns_calendar_green(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.logs.UPLOAD_ROOT", tmp_path)
    signup(client)
    resp = client.post(
        "/api/logs/photo",
        data={"meal": "dinner", "name": "Tray"},
        files={"photo": ("tray.png", PNG, "image/png")},
    )
    assert resp.status_code == 200
    entry = resp.json()["entries"][0]
    assert entry["has_photo"] is True

    today = resp.json()["date"]
    year, month, _ = today.split("-")
    cal = client.get(f"/api/calendar?year={year}&month={int(month)}").json()
    assert today in cal["photo_days"]

    photo = client.get(f"/api/logs/{entry['id']}/photo")
    assert photo.status_code == 200
    assert photo.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_text_log_does_not_fill_calendar(client):
    signup(client)
    day = client.post("/api/logs", json={"meal": "lunch", "name": "Salad", "calories": 200}).json()["date"]
    year, month, _ = day.split("-")
    cal = client.get(f"/api/calendar?year={year}&month={int(month)}").json()
    assert day not in cal["photo_days"]


def test_rejects_non_image_upload(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.logs.UPLOAD_ROOT", tmp_path)
    signup(client)
    resp = client.post(
        "/api/logs/photo",
        data={"meal": "snack", "name": "Nope"},
        files={"photo": ("x.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 400
