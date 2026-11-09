"""ការផ្លាស់ប្ដូរស្ថាប័នកងឯកភាព for many soldiers at once (military IDs pasted)."""

from datetime import date

from tests.test_flow import API, _lookups, _soldier, _units

TODAY = date.today().isoformat()


def _check(c, ids, **kw):
    r = c.post(f"{API}/strength-movements/bulk/check", json={"military_ids": ids, **kw})
    assert r.status_code == 200, r.text
    return {row["military_id"]: row for row in r.json()}


def _movements(c, soldier_id):
    return [(m["direction"], m["reason"], m["unit_id"]) for m in
            c.get(f"{API}/strength-movements", params={"soldier_id": soldier_id, "size": 50}).json()["items"]]


def test_in_moves_every_soldier_entered(admin):
    lk = _lookups(admin)
    root, child, other = _units(admin)
    second = admin.post(f"{API}/units", json={"name_kh": "ស្ថាប័នទីពីរ TEST", "level": 1}).json()
    a = _soldier(admin, lk, child["id"], mid="771001")
    b = _soldier(admin, lk, other["id"], mid="771002", national_id="TEST-NID-SB2")

    # ផ្លាស់ប្ដូរផ្ទៃក្នុង: within the same ស្ថាប័នកងឯកភាព only; a soldier already in the unit is refused
    rows = _check(admin, "771001\n771002", direction="in", reason="internal", unit_id=other["id"])
    assert rows["771001"]["status"] == "ok" and rows["771002"]["status"] == "error"
    rows = _check(admin, "771001", direction="in", reason="internal", unit_id=second["id"])
    assert rows["771001"]["status"] == "error" and "ស្ថាប័នកងឯកភាពតែមួយ" in rows["771001"]["errors"][0]
    # កើនក្រៅស្ថាប័នកងឯកភាព: from another ស្ថាប័នកងឯកភាព only
    assert _check(admin, "771001", direction="in", reason="outside_in", unit_id=root["id"])["771001"]["status"] == "error"

    # several IDs (Khmer digits, commas, an unknown one) into the other ស្ថាប័នកងឯកភាព
    rows = _check(admin, "៧៧១០០១, 771002 999999", direction="in", reason="outside_in", unit_id=second["id"])
    assert [r["status"] for r in rows.values()] == ["ok", "ok", "not_found"]
    r = admin.post(f"{API}/strength-movements/bulk", json={
        "soldier_ids": [a["id"], b["id"]], "direction": "in", "reason": "outside_in", "unit_id": second["id"],
        "movement_date": TODAY, "note": "លិខិតលេខ ១២"})
    assert r.status_code == 201 and r.json()["saved"] == 2, r.text
    for s, old in ((a, child), (b, other)):
        after = admin.get(f"{API}/soldiers/{s['id']}").json()
        assert (after["current_unit_id"], after["unit_transfer_date"]) == (second["id"], TODAY)
        assert ("out", "transfer_out", old["id"]) in _movements(admin, s["id"])
        assert ("in", "outside_in", second["id"]) in _movements(admin, s["id"])
    # all or none: one soldier that cannot move refuses the whole entry
    r = admin.post(f"{API}/strength-movements/bulk", json={
        "soldier_ids": [a["id"]], "direction": "in", "reason": "internal", "unit_id": second["id"], "movement_date": TODAY})
    assert r.status_code == 400 and "771001" in r.json()["detail"]


def test_out_records_only(admin):
    lk = _lookups(admin)
    root, child, _ = _units(admin)
    second = admin.post(f"{API}/units", json={"name_kh": "ស្ថាប័នទីពីរ TEST", "level": 1}).json()
    s = _soldier(admin, lk, child["id"], mid="772001")
    assert _check(admin, "772001", direction="out", reason="transfer_out", unit_id=second["id"])["772001"]["status"] == "error"
    # ផ្លាស់ប្ដូរផ្ទៃក្នុង is a កើន (its ថយ is written with it), not a reason to enter as ថយ
    assert admin.post(f"{API}/strength-movements/bulk/check", json={
        "military_ids": "772001", "direction": "out", "reason": "internal", "unit_id": root["id"]}).status_code == 400
    r = admin.post(f"{API}/strength-movements/bulk", json={
        "soldier_ids": [s["id"]], "direction": "out", "reason": "transfer_out", "unit_id": root["id"], "movement_date": TODAY})
    assert r.status_code == 201, r.text
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_unit_id"] == child["id"]  # unchanged
    assert ("out", "transfer_out", child["id"]) in _movements(admin, s["id"])
