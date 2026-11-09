"""Regression tests for bugs found in the project review (each test names the bug it guards)."""

from tests.test_flow import API, _lookups, _soldier, _units, approve_all


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
    approve_all(admin, d["id"])
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
    approve_all(admin, high["id"])
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


def test_separated_soldier_leaves_the_register(admin):
    """A separated soldier stayed in the soldier list (and in the pickers) with only a status change."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-SEP1")
    sep = admin.post(f"{API}/separations", json={"soldier_id": s["id"], "effective_date": "2025-02-01"}).json()
    listed = admin.get(f"{API}/soldiers", params={"military_ids": "TEST-SEP1"}).json()
    assert listed["total"] == 0
    # the profile and history stay readable, but read-only
    assert admin.get(f"{API}/soldiers/{s['id']}/profile").json()["separated"] is True
    assert admin.get(f"{API}/soldiers/{s['id']}/history").status_code == 200
    assert admin.put(f"{API}/soldiers/{s['id']}", json={**s, "phone": "099"}).status_code == 400
    assert admin.delete(f"{API}/soldiers/{s['id']}").status_code == 400
    r = admin.post(f"{API}/awards", json={"soldier_id": s["id"], "decision_date": "2025-03-01"})
    assert r.status_code == 400
    # deleting the separation record puts the soldier back in the list
    assert admin.delete(f"{API}/separations/{sep['id']}").status_code == 200
    assert admin.get(f"{API}/soldiers", params={"military_ids": "TEST-SEP1"}).json()["total"] == 1


def test_category2_soldier_leaves_the_serving_strength(admin):
    """យោធិនប្រភេទ២ (ពលី, ពលី-មរណ, ពិការ) is counted out of the serving soldiers but stays in the list."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-CAT2")
    before = admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()
    r = admin.post(f"{API}/category2", json={"soldier_id": s["id"], "type": "fallen", "effective_date": "2025-02-01"})
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["type_name"] == "ពលី"
    after = admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()
    assert after["total_active"] == before["total_active"] - 1
    assert after["categories"]["category2"] == before["categories"]["category2"] + 1
    assert after["categories"]["category2_by_type"]["fallen"] == before["categories"]["category2_by_type"]["fallen"] + 1
    # still in the soldier list, but not among the serving soldiers
    assert admin.get(f"{API}/soldiers", params={"military_ids": "TEST-CAT2"}).json()["total"] == 1
    assert admin.get(f"{API}/soldiers", params={"military_ids": "TEST-CAT2", "serving": True}).json()["total"] == 0
    # counted out once only
    r = admin.post(f"{API}/category2", json={"soldier_id": s["id"], "type": "disabled", "effective_date": "2025-03-01"})
    assert r.status_code == 400
    assert admin.delete(f"{API}/category2/{rec['id']}").status_code == 200
    assert admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()["total_active"] == before["total_active"]


def test_retired_soldier_leaves_the_serving_strength(admin):
    """A retirement record did not reduce the serving soldiers when the 'retired' status lookup was missing."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-RET1")
    before = admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()["total_active"]
    r = admin.post(f"{API}/retirements", json={"soldier_id": s["id"], "type": "pension", "effective_date": "2025-01-01"})
    assert r.status_code == 201, r.text
    assert admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()["total_active"] == before - 1
    serving = admin.get(f"{API}/soldiers", params={"military_ids": "TEST-RET1", "serving": True}).json()
    assert serving["total"] == 0
    assert admin.delete(f"{API}/retirements/{r.json()['id']}").status_code == 200
    assert admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()["total_active"] == before


def test_military_id_has_six_digits(admin):
    """អត្តលេខ is shown with 6 digits: a shorter numeric ID gets leading zeros (652 -> 000652)."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="77")
    assert s["military_id"] == "000077"
    # the short form still finds the soldier, and is refused as a duplicate
    assert admin.get(f"{API}/soldiers", params={"military_ids": "77"}).json()["total"] == 1
    r = admin.post(f"{API}/soldiers", json={**s, "military_id": "0077", "national_id": None})
    assert r.status_code == 409


def test_dashboard_studying_counts(admin):
    """កំពុងសិក្សាក្រៅប្រទេស stayed 0: a course without a start date was skipped, and with no 'Cambodia'
    country every course counted as in Cambodia. Participants who finished or dropped are not studying."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    a, b, c = (_soldier(admin, lk, unit["id"], mid=f"TEST-ST{i}") for i in range(3))
    before = admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()["studying"]
    china = admin.post(f"{API}/countries", json={"name_kh": "ប្រទេសចិន TEST"}).json()
    r = admin.post(f"{API}/training/courses", json={
        "name": "វគ្គ ST abroad", "course_type": "short", "country_id": china["id"],
        "participants": [{"soldier_id": a["id"], "status": "studying"}, {"soldier_id": b["id"], "status": "dropped"}]})
    assert r.status_code == 201, r.text
    r = admin.post(f"{API}/training/courses", json={
        "name": "វគ្គ ST home", "course_type": "long", "start_date": "2025-01-01",
        "participants": [{"soldier_id": c["id"], "status": "studying"}]})
    assert r.status_code == 201, r.text
    after = admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()["studying"]
    assert after == {"in_country": before["in_country"] + 1, "abroad": before["abroad"] + 1}
    abroad = admin.get(f"{API}/training/courses", params={"abroad": "yes", "q": "វគ្គ ST"}).json()["items"]
    assert [x["name"] for x in abroad] == ["វគ្គ ST abroad"]


def test_bulk_retirement_moves_unit(admin):
    """ការងារសោធននិវត្តន៍: several soldiers by military ID with one letter, all moved to one unit."""
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    a = _soldier(admin, lk, unit["id"], mid="TEST-BR1")
    b = _soldier(admin, lk, unit["id"], mid="TEST-BR2")
    rows = admin.post(f"{API}/retirements/bulk/check", json={"military_ids": "TEST-BR1, TEST-BR2\nTEST-NONE"}).json()
    assert [r["status"] for r in rows] == ["ok", "ok", "not_found"]
    body = {"soldier_ids": [a["id"], b["id"]], "type": "pension", "effective_date": "2025-01-01",
            "decision_no": "R-BULK", "unit_id": other["id"]}
    r = admin.post(f"{API}/retirements/bulk", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 2
    listed = admin.get(f"{API}/soldiers", params={"military_ids": "TEST-BR1 TEST-BR2"}).json()["items"]
    assert {x["unit_id"] for x in listed} == {other["id"]}
    hist = admin.get(f"{API}/soldiers/{a['id']}/history").json()
    assert any(h.get("new_unit_id") == other["id"] for h in hist)
    # the "out" movement is from the unit the soldier left
    mv = admin.get(f"{API}/strength-movements", params={"soldier_id": a["id"], "direction": "out"}).json()["items"]
    assert [m["unit_id"] for m in mv] == [unit["id"]]
    # all or none: an already retired soldier refuses the whole batch
    c = _soldier(admin, lk, unit["id"], mid="TEST-BR3")
    r = admin.post(f"{API}/retirements/bulk", json={**body, "soldier_ids": [c["id"], a["id"]]})
    assert r.status_code == 400 and "TEST-BR1" in r.json()["detail"]
    assert admin.get(f"{API}/retirements", params={"soldier_id": c["id"]}).json()["total"] == 0


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
