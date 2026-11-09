"""Update ស័ក្តិ និងមុខតំណែង: many soldiers' rank / position (and dates) at once, by military ID."""

from datetime import date, timedelta

from tests.test_flow import API, _lookups, _soldier, _units

TODAY = date.today().isoformat()


def _check(c, ids="", **kw):
    r = c.post(f"{API}/rank-position-updates/check", json={"military_ids": ids, **kw})
    assert r.status_code == 200, r.text
    return {row["military_id"]: row for row in r.json()}


def test_update_many_soldiers(admin):
    lk = _lookups(admin)
    _, child, other = _units(admin)
    ranks, position = lk["ranks"], lk["positions"][0]
    a = _soldier(admin, lk, child["id"], mid="781001")
    b = _soldier(admin, lk, child["id"], mid="781002", national_id="TEST-NID-RP2")
    doc = admin.post(f"{API}/documents/incoming", json={
        "incoming_no": "៤៥៦", "year": date.today().year, "subject": "សំណើ Update ស័ក្តិ", "doc_date": TODAY}).json()

    # the IDs added get the values "for all"; an empty value keeps the soldier's own; unknown IDs are listed
    rows = _check(admin, "៧៨១០០១, 781002 999998",
                  defaults={"rank_id": ranks[-4]["id"], "rank_date": "2024-01-01", "position_id": position["id"]})
    assert [r["status"] for r in rows.values()] == ["warning", "warning", "not_found"]  # no position date
    assert rows["781001"]["changed"] == ["rank_id", "rank_date", "position_id"]
    assert "ខ្វះថ្ងៃមុខតំណែង" in rows["781001"]["warnings"]
    # a row's own values; a future date is refused, nothing changed is left alone
    items = [{"soldier_id": a["id"], "rank_id": ranks[-4]["id"], "rank_date": "2024-01-01",
              "position_id": position["id"], "position_date": "2024-02-01"},
             {"soldier_id": b["id"], "rank_date": (date.today() + timedelta(days=3)).isoformat()}]
    rows = _check(admin, items=items)
    assert rows["781002"]["status"] == "error" and "អនាគត" in rows["781002"]["errors"][0]
    r = admin.post(f"{API}/rank-position-updates", json={"incoming_document_id": doc["id"], "items": items})
    assert r.status_code == 400 and "781002" in r.json()["detail"]  # all or none
    items[1] = {"soldier_id": b["id"]}
    assert _check(admin, items=items)["781002"]["status"] == "unchanged"
    # the unit too (a soldier who has moved): within one ស្ថាប័នកងឯកភាព, so a ផ្លាស់ប្ដូរផ្ទៃក្នុង
    items[1] = {"soldier_id": b["id"], "unit_id": other["id"], "unit_date": "2025-06-01"}
    assert _check(admin, items=items)["781002"]["changed"] == ["unit_id", "unit_date"]

    r = admin.post(f"{API}/rank-position-updates", json={"incoming_document_id": doc["id"], "note": "តាមបញ្ជា", "items": items})
    assert r.status_code == 201 and r.json()["saved"] == 2, r.text
    after = admin.get(f"{API}/soldiers/{a['id']}").json()
    assert (after["current_rank_id"], after["rank_date"], after["current_position_id"], after["position_date"]) == \
        (ranks[-4]["id"], "2024-01-01", position["id"], "2024-02-01")
    h = next(x for x in admin.get(f"{API}/soldiers/{a['id']}/history").json() if x["kind"] == "update")
    assert h["new_rank_id"] == ranks[-4]["id"] and h["old_rank_id"] == ranks[-3]["id"] and "៤៥៦" in h["note"]
    moved = admin.get(f"{API}/soldiers/{b['id']}").json()
    assert (moved["current_rank_id"], moved["current_unit_id"], moved["unit_transfer_date"]) == \
        (ranks[-3]["id"], other["id"], "2025-06-01")  # rank unchanged
    movements = [(m["direction"], m["reason"], m["unit_id"]) for m in admin.get(
        f"{API}/strength-movements", params={"soldier_id": b["id"], "size": 50}).json()["items"]]
    assert ("out", "internal", child["id"]) in movements and ("in", "internal", other["id"]) in movements


def test_own_permission(admin, client):
    """The page has its own permission (rank_position_update.update), given to the roles that edit soldiers."""
    from tests.test_workflow import _login_as

    officer, viewer = _login_as(admin, client, "rp.officer", "Officer"), _login_as(admin, client, "rp.viewer", "Viewer")
    body = {"military_ids": "000001"}
    assert client.post(f"{API}/rank-position-updates/check", json=body, headers=officer).status_code == 200
    assert client.post(f"{API}/rank-position-updates/check", json=body, headers=viewer).status_code == 403
    roles = {r["name"]: r for r in admin.get(f"{API}/roles").json()["items"]}
    officer_perms = [p for p in roles["Officer"]["permissions"] if p != "rank_position_update.update"]
    admin.put(f"{API}/roles/{roles['Officer']['id']}/permissions", json={"permissions": officer_perms})
    assert "soldiers.update" in officer_perms
    assert client.post(f"{API}/rank-position-updates/check", json=body, headers=officer).status_code == 403
