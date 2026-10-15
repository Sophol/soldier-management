"""Regression tests for bugs found in the project review (each test names the bug it guards)."""

from tests.test_flow import API, _lookups, _soldier, _units, publish


def _promote(c, lk, soldier_id, rank_id, no, eff="2025-01-01"):
    r = c.post(f"{API}/decisions", json={
        "kind": "promote", "decision_no": no, "decision_date": eff, "effective_date": eff,
        "items": [{"soldier_id": soldier_id, "new_rank_id": rank_id}]})
    assert r.status_code == 201, r.text
    return r.json()


def test_cancel_blocked_after_direct_correction(admin):
    """A direct profile edit after approval must block cancelling (it was ignored: NULL decision_id)."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    ranks = lk["ranks"]
    d = _promote(admin, lk, s["id"], ranks[-4]["id"], "R-1")
    publish(admin, d["id"])
    body = admin.get(f"{API}/soldiers/{s['id']}").json()
    body = {k: v for k, v in body.items() if k not in {"id"}}
    body["current_rank_id"] = ranks[-6]["id"]  # manual correction after the decision
    assert admin.put(f"{API}/soldiers/{s['id']}", json=body).status_code == 200
    assert admin.post(f"{API}/decisions/{d['id']}/cancel").status_code == 409
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == ranks[-6]["id"]


def test_approve_rechecks_rank_and_status(admin):
    """A stale promotion draft must not demote a soldier who was promoted higher meanwhile."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    ranks = lk["ranks"]
    low = _promote(admin, lk, s["id"], ranks[-4]["id"], "R-2")
    high = _promote(admin, lk, s["id"], ranks[-6]["id"], "R-3")
    publish(admin, high["id"])
    assert admin.post(f"{API}/decisions/{low['id']}/submit").status_code == 400
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == ranks[-6]["id"]


def test_leave_record_twice_rejected(admin):
    """Retiring an already retired/separated soldier double-counted the 'out' movement."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    body = {"soldier_id": s["id"], "type": "pension", "effective_date": "2025-01-01"}
    assert admin.post(f"{API}/retirements", json=body).status_code == 201
    assert admin.post(f"{API}/retirements", json=body).status_code == 400
    r = admin.post(f"{API}/separations", json={"soldier_id": s["id"], "effective_date": "2025-02-01"})
    assert r.status_code == 400


def test_auto_movement_cannot_be_deleted(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    mv = admin.get(f"{API}/strength-movements", params={"soldier_id": s["id"]}).json()["items"][0]
    assert admin.delete(f"{API}/strength-movements/{mv['id']}").status_code == 400


def test_system_lookup_protected(admin):
    """Deleting or re-coding a status the code relies on (e.g. 'category2') broke retirements."""
    lk = _lookups(admin)
    cat2 = next(x for x in lk["soldier_status"] if x["code"] == "category2")
    assert admin.delete(f"{API}/lookups/{cat2['id']}").status_code == 400
    r = admin.put(f"{API}/lookups/{cat2['id']}", json={**cat2, "category": "soldier_status", "code": "other"})
    assert r.status_code == 400
    # renaming is still allowed
    r = admin.put(f"{API}/lookups/{cat2['id']}", json={**cat2, "category": "soldier_status", "name_kh": "ប្រភេទ២"})
    assert r.status_code == 200


def test_draft_update_keeps_outgoing_document(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    doc = admin.post(f"{API}/documents/outgoing", json={"subject": "ប្រកាស", "doc_date": "2025-01-01"}).json()
    body = {"kind": "promote", "decision_no": "R-4", "decision_date": "2025-01-01", "effective_date": "2025-01-01",
            "outgoing_document_id": doc["id"], "items": [{"soldier_id": s["id"], "new_rank_id": lk["ranks"][-4]["id"]}]}
    d = admin.post(f"{API}/decisions", json=body).json()
    body.pop("outgoing_document_id")  # the UI does not send it
    r = admin.put(f"{API}/decisions/{d['id']}", json={**body, "notes": "edited"})
    assert r.status_code == 200 and r.json()["outgoing_document_id"] == doc["id"]


def test_role_rename_duplicate_is_409(admin):
    a = admin.post(f"{API}/roles", json={"name": "TEST-ROLE-A"}).json()
    admin.post(f"{API}/roles", json={"name": "TEST-ROLE-B"})
    assert admin.put(f"{API}/roles/{a['id']}", json={"name": "TEST-ROLE-B"}).status_code == 409


def test_unit_move_respects_max_depth(admin):
    root, child, other = _units(admin)
    l3 = admin.post(f"{API}/units", json={"name_kh": "L3", "parent_id": child["id"], "level": 1}).json()
    admin.post(f"{API}/units", json={"name_kh": "L4", "parent_id": l3["id"], "level": 1})
    # moving `child` (which has 2 levels below it) under `other` would create a level-5 unit
    r = admin.put(f"{API}/units/{child['id']}", json={"name_kh": "x", "parent_id": other["id"], "level": 1})
    assert r.status_code == 400


def test_dashboard_total_respects_unit_scope(admin, client):
    lk = _lookups(admin)
    root, unit, other = _units(admin)
    _soldier(admin, lk, unit["id"], mid="TEST-S1")
    _soldier(admin, lk, other["id"], mid="TEST-S2", national_id=None)
    roles = {r["name"]: r["id"] for r in admin.get(f"{API}/roles").json()["items"]}
    admin.post(f"{API}/users", json={"username": "scoped.test", "full_name": "x", "role_id": roles["Viewer"],
                                     "unit_scope_id": unit["id"], "password": "Scoped@123"})
    tok = client.post(f"{API}/auth/login", json={"username": "scoped.test", "password": "Scoped@123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"
    d = client.get(f"{API}/dashboard/summary").json()
    assert d["total_all"] == d["total_active"] == 1


def test_deleted_soldier_leaves_strength_reports(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], unit_transfer_date="2025-03-01")
    params = {"date_from": "2025-03-01", "date_to": "2025-03-01", "unit_id": unit["id"]}
    assert len(admin.get(f"{API}/reports/movements", params=params).json()["rows"]) == 1
    admin.delete(f"{API}/soldiers/{s['id']}")
    assert admin.get(f"{API}/reports/movements", params=params).json()["rows"] == []
    assert admin.get(f"{API}/strength-movements", params={"soldier_id": s["id"]}).json()["total"] == 0


def test_profile_unit_change_writes_movements(admin):
    """Changing the unit on the profile counts as leaving one unit and joining the other."""
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    s = _soldier(admin, lk, unit["id"], unit_transfer_date="2024-01-01")
    body = {k: v for k, v in admin.get(f"{API}/soldiers/{s['id']}").json().items() if k != "id"}
    body.update(current_unit_id=other["id"], unit_transfer_date="2025-05-01")
    assert admin.put(f"{API}/soldiers/{s['id']}", json=body).status_code == 200
    mv = admin.get(f"{API}/strength-movements", params={"soldier_id": s["id"]}).json()["items"]
    moves = sorted((m["direction"], m["reason"], m["unit_id"], m["movement_date"]) for m in mv)
    assert moves == [("in", "recruit", unit["id"], "2024-01-01"), ("in", "transfer_in", other["id"], "2025-05-01"),
                     ("out", "transfer_out", unit["id"], "2025-05-01")]
    # editing something else does not add movements
    body["phone"] = "012 000 000"
    admin.put(f"{API}/soldiers/{s['id']}", json=body)
    assert admin.get(f"{API}/strength-movements", params={"soldier_id": s["id"]}).json()["total"] == 3


def test_decisions_respect_unit_scope(admin, client):
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    mine = _soldier(admin, lk, unit["id"], mid="TEST-S3")
    theirs = _soldier(admin, lk, other["id"], mid="TEST-S4", national_id=None)
    d_mine = _promote(admin, lk, mine["id"], lk["ranks"][-4]["id"], "R-5")
    d_theirs = _promote(admin, lk, theirs["id"], lk["ranks"][-4]["id"], "R-6")
    roles = {r["name"]: r["id"] for r in admin.get(f"{API}/roles").json()["items"]}
    admin.post(f"{API}/users", json={"username": "scoped.approver", "full_name": "x", "role_id": roles["Admin"],
                                     "unit_scope_id": unit["id"], "password": "Scoped@123"})
    tok = client.post(f"{API}/auth/login", json={"username": "scoped.approver", "password": "Scoped@123"}).json()
    client.headers["Authorization"] = f"Bearer {tok['access_token']}"
    listed = {d["id"] for d in client.get(f"{API}/decisions", params={"kind": "promote", "size": 200}).json()["items"]}
    assert d_mine["id"] in listed and d_theirs["id"] not in listed
    assert client.get(f"{API}/decisions/{d_theirs['id']}").status_code == 403
    assert client.post(f"{API}/decisions/{d_theirs['id']}/submit").status_code == 403
    assert client.post(f"{API}/decisions/{d_mine['id']}/submit").status_code == 200
