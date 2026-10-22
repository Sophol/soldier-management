"""Features from the updated structure spec (001រចនាសម្ព័ន្ធ (2).txt)."""

from tests.test_flow import API, _lookups, _soldier, _units, approve_all


def _transfer(c, body_items, no="S-1", **kw):
    return c.post(f"{API}/decisions", json={"kind": "transfer", "decision_no": no, "decision_date": "2025-01-01",
                                            "effective_date": "2025-01-01", "items": body_items, **kw})


def test_staffing_table_quota_and_rank_warnings(admin):
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    pos = lk["positions"][0]["id"]
    ranks = lk["ranks"]  # highest first
    s1 = _soldier(admin, lk, other["id"], mid="TEST-ST1", current_position_id=pos)
    s2 = _soldier(admin, lk, unit["id"], mid="TEST-ST2", national_id=None)
    r = admin.post(f"{API}/unit-positions", json={"unit_id": other["id"], "position_id": pos, "quota": 1,
                                                  "min_rank_id": ranks[0]["id"]})
    assert r.status_code == 201, r.text
    up = r.json()
    assert (up["filled"], up["vacant"]) == (1, 0)
    # moving s2 into the full position is refused: quota reached and rank below the minimum (New.txt §4)
    r = _transfer(admin, [{"soldier_id": s2["id"], "new_unit_id": other["id"], "new_position_id": pos}])
    assert r.status_code == 400 and "ពេញក្របខណ្ឌ" in r.json()["detail"] and "មិនស្រប" in r.json()["detail"]
    # with room in the table and the right rank it is accepted; two soldiers into one vacancy are refused
    admin.put(f"{API}/unit-positions/{up['id']}", json={**up, "quota": 2, "min_rank_id": None})
    ok = _transfer(admin, [{"soldier_id": s2["id"], "new_unit_id": other["id"], "new_position_id": pos}], no="S-9")
    assert ok.status_code == 201, ok.text
    s3 = _soldier(admin, lk, unit["id"], mid="TEST-ST3", national_id="TEST-NID-ST3")
    both = _transfer(admin, [{"soldier_id": sid, "new_unit_id": other["id"], "new_position_id": pos}
                             for sid in (s2["id"], s3["id"])], no="S-10")
    assert both.status_code == 400
    # min rank above max rank is rejected
    bad = admin.put(f"{API}/unit-positions/{up['id']}", json={**up, "min_rank_id": ranks[0]["id"], "max_rank_id": ranks[-1]["id"]})
    assert bad.status_code == 400
    assert s1["id"]


def test_transfer_can_promote(admin):
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    higher = lk["ranks"][-4]["id"]
    d = _transfer(admin, [{"soldier_id": s["id"], "new_unit_id": other["id"], "new_rank_id": higher}]).json()
    approve_all(admin, d["id"])
    after = admin.get(f"{API}/soldiers/{s['id']}").json()
    assert (after["current_unit_id"], after["current_rank_id"], after["rank_date"]) == (other["id"], higher, "2025-01-01")
    # a lower rank in a transfer is still refused
    low = _transfer(admin, [{"soldier_id": s["id"], "new_rank_id": lk["ranks"][-1]["id"]}], no="S-2")
    assert low.status_code == 400


def test_rank_branch_and_quota(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    cur = next(r for r in lk["ranks"] if r["id"] == s["current_rank_id"])
    navy = admin.post(f"{API}/ranks", json={"rank_class_id": cur["rank_class_id"], "name_kh": "នាវា TEST",
                                            "sort_order": cur["sort_order"] + 1, "branch": "navy"}).json()
    r = admin.post(f"{API}/decisions", json={"kind": "promote", "decision_no": "S-3", "decision_date": "2025-01-01",
                                             "effective_date": "2025-01-01",
                                             "items": [{"soldier_id": s["id"], "new_rank_id": navy["id"]}]})
    assert r.status_code == 400  # army -> navy
    admin.put(f"{API}/ranks/{cur['id']}", json={**{k: cur[k] for k in ("rank_class_id", "name_kh", "sort_order")}, "quota": 1})
    rank = admin.get(f"{API}/ranks/{cur['id']}").json()
    assert rank["quota"] == 1 and rank["filled"] >= 1 and rank["vacant"] <= 0


def test_rank_retirement_age_overrides_gender_setting(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], date_of_birth="1975-01-01")  # 51: not due under the 60-year default
    params = {"unit_id": unit["id"]}
    assert admin.get(f"{API}/reports/retirement_due", params=params).json()["rows"] == []
    cur = next(r for r in lk["ranks"] if r["id"] == s["current_rank_id"])
    admin.put(f"{API}/ranks/{cur['id']}", json={**{k: cur[k] for k in ("rank_class_id", "name_kh", "sort_order")},
                                               "retirement_age": 50})
    rows = admin.get(f"{API}/reports/retirement_due", params=params).json()["rows"]
    assert [r["military_id"] for r in rows] == [s["military_id"]] and rows[0]["retire_date"] == "2025-01-01"


def test_soldier_list_fields_and_unit_path(admin):
    lk = _lookups(admin)
    root, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], position_date="2020-01-01", current_position_id=lk["positions"][0]["id"])
    assert s["unit_path"] == f"{root['name_kh']} › {unit['name_kh']}" and s["institution_name"] == root["name_kh"]
    assert s["time_in_position"].endswith("ខែ")
    rep = admin.get(f"{API}/reports/soldier_list", params={"unit_id": unit["id"], "fields": "name_kh,unit_path,bogus"}).json()
    assert [c["key"] for c in rep["columns"]] == ["no", "name_kh", "unit_path"]
    assert rep["rows"][0]["unit_path"] == s["unit_path"]


def test_decision_links_incoming_document(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    doc = admin.post(f"{API}/documents/incoming", json={"incoming_no": "IN-T1", "subject": "សំណើ", "doc_date": "2025-01-01"}).json()
    d = admin.post(f"{API}/decisions", json={"kind": "promote", "decision_no": "S-4", "decision_date": "2025-01-01",
                                             "effective_date": "2025-01-01", "incoming_document_id": doc["id"],
                                             "items": [{"soldier_id": s["id"], "new_rank_id": lk["ranks"][-4]["id"]}]}).json()
    assert d["incoming_no"] == "IN-T1"


def test_specialty_category_and_course_level(admin):
    sp = admin.post(f"{API}/specialties", json={"name_kh": "ច្បាប់ TEST", "category": "civil"}).json()
    assert sp["category"] == "civil"
    assert all(x["category"] == "civil" for x in admin.get(f"{API}/specialties", params={"category": "civil"}).json()["items"])
    c = admin.post(f"{API}/training/courses", json={"name": "វគ្គបំប៉ន TEST", "course_type": "short", "level": "refresher"}).json()
    assert c["level"] == "refresher"
