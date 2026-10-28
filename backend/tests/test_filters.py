"""Interactive filters (New (2).txt): shared list filters, soldier filters, saved filters, export by filter."""

from datetime import date

from tests.test_flow import API, _lookups, _soldier, _units


def _ids(c, **params):
    r = c.get(f"{API}/soldiers", params={"size": 500, **params})
    assert r.status_code == 200, r.text
    return {x["id"] for x in r.json()["items"]}


def test_soldier_filters(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    old = _soldier(admin, lk, unit["id"], mid="TEST-F1", date_of_birth=f"{date.today().year - 59}-01-01",
                   enlistment_date="1990-03-01", phone="012345678")
    young = _soldier(admin, lk, unit["id"], mid="TEST-F2", national_id="NID-F2", date_of_birth="2000-01-01",
                     enlistment_date="2020-06-01", rank_date=None, birth_village_id=None, languages=[])
    scope = {"unit_id": unit["id"]}

    assert _ids(admin, **scope, dob_from="1999-01-01", dob_to="2001-12-31") == {young["id"]}
    assert _ids(admin, **scope, enlist_to="1995-01-01") == {old["id"]}
    assert _ids(admin, **scope, service_min=30) == {old["id"]}
    assert _ids(admin, **scope, missing="rank_date") == {young["id"]}
    assert _ids(admin, **scope, missing="national_id,photo") == {old["id"]}
    assert _ids(admin, **scope, has_attachments="no") == {old["id"], young["id"]}
    assert _ids(admin, **scope, phone="2345") == {old["id"]}
    assert _ids(admin, **scope, serving="true") == {old["id"], young["id"]}
    assert _ids(admin, **scope, language_id=lk["language"][0]["id"]) == {old["id"]}
    assert _ids(admin, **scope, retire_within=2) == {old["id"]}
    assert _ids(admin, **scope, birth_province_id=1) == {old["id"]}  # village 1020101: province 1, district 102
    assert _ids(admin, **scope, birth_district_id=102) == {old["id"]}
    assert _ids(admin, **scope, birth_district_id=103) == set()
    me = admin.get(f"{API}/auth/me").json()["id"]
    today = date.today().isoformat()
    assert _ids(admin, **scope, created_by=me, created_from=today, created_to=today) == {old["id"], young["id"]}
    assert _ids(admin, **scope, created_from="2000-01-01", created_to="2000-12-31") == set()


def test_crud_lists_share_audit_filters(admin):
    doc = admin.post(f"{API}/documents/incoming", json={"incoming_no": "IN-F1", "subject": "តេស្ត", "doc_date": "2026-01-02"})
    assert doc.status_code == 201, doc.text
    me = admin.get(f"{API}/auth/me").json()["id"]
    today = date.today().isoformat()
    found = admin.get(f"{API}/documents/incoming", params={"q": "IN-F1", "created_by": me, "created_from": today,
                                                            "created_to": today}).json()
    assert [x["id"] for x in found["items"]] == [doc.json()["id"]]
    assert admin.get(f"{API}/documents/incoming", params={"q": "IN-F1", "updated_to": "2000-01-01"}).json()["total"] == 0
    users = admin.get(f"{API}/users/options").json()
    assert any(u["id"] == me for u in users) and set(users[0]) == {"id", "full_name", "username"}


def test_saved_filters(admin):
    body = {"module": "soldiers", "name": "ជិតនិវត្ត TEST", "params": {"retire_within": 2, "q": "", "unit_id": None}}
    saved = admin.post(f"{API}/saved-filters", json=body).json()
    assert saved["params"] == {"retire_within": 2} and saved["mine"]  # empty values are dropped
    again = admin.post(f"{API}/saved-filters", json={**body, "params": {"retire_within": 5}, "shared": True}).json()
    assert again["id"] == saved["id"] and again["shared"]  # same name replaces
    mine = admin.get(f"{API}/saved-filters", params={"module": "soldiers"}).json()
    assert [f["params"] for f in mine if f["id"] == saved["id"]] == [{"retire_within": 5}]
    assert admin.get(f"{API}/saved-filters", params={"module": "docIn"}).json() == []
    assert admin.delete(f"{API}/saved-filters/{saved['id']}").status_code == 200


def test_export_table(admin):
    r = admin.post(f"{API}/export/table", json={"module": "doc_in", "title": "ឯកសារចូល", "columns": ["លេខ", "ខ្លឹមសារ"],
                                                 "rows": [["IN-1", "តេស្ត"], ["IN-2", None]]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_record_statuses_and_filters(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-R1")
    today = date.today()
    d = lambda days: date.fromordinal(today.toordinal() + days).isoformat()  # noqa: E731

    # discipline: in force / expired / cancelled, year
    active = admin.post(f"{API}/discipline", json={"soldier_id": s["id"], "decision_date": "2025-03-01", "level": "ធ្ងន់",
                                                   "end_date": d(10), "decided_by": "មេបញ្ជាការ"}).json()
    expired = admin.post(f"{API}/discipline", json={"soldier_id": s["id"], "decision_date": "2024-03-01", "end_date": d(-1)}).json()
    cancelled = admin.post(f"{API}/discipline", json={"soldier_id": s["id"], "decision_date": "2024-05-01", "cancelled": True}).json()
    assert (active["status"], expired["status"], cancelled["status"]) == ("active", "expired", "cancelled")
    ids = lambda url, **p: {x["id"] for x in admin.get(f"{API}/{url}", params={"soldier_id": s["id"], **p}).json()["items"]}  # noqa: E731
    assert ids("discipline", status="expired") == {expired["id"]}
    assert ids("discipline", status="active") == {active["id"]}
    assert ids("discipline", year=2024) == {expired["id"], cancelled["id"]}
    assert ids("discipline", level="ធ្ងន់") == {active["id"]}

    # awards: level, giver, year
    aw = admin.post(f"{API}/awards", json={"soldier_id": s["id"], "decision_date": "2023-01-05", "level": "ថ្នាក់ទី១",
                                           "awarded_by": "ក្រសួង"}).json()
    assert ids("awards", year=2023, awarded_by="ក្រសួ") == {aw["id"]} and ids("awards", year=2022) == set()

    # military ID cards: expired is computed; expiring within N days
    soon = admin.post(f"{API}/military-cards", json={"soldier_id": s["id"], "card_no": "C-1", "status": "issued",
                                                     "issue_date": "2024-01-01", "expiry_date": d(20)}).json()
    old = admin.post(f"{API}/military-cards", json={"soldier_id": s["id"], "card_no": "C-0", "status": "issued",
                                                    "issue_date": "2020-01-01", "expiry_date": d(-5)}).json()
    assert soon["days_left"] == 20 and old["status"] == "expired" and old["status_name"] == "ផុតកំណត់"
    assert ids("military-cards", expiring_within=30) == {soon["id"]} and ids("military-cards", expiring_within=10) == set()
    assert ids("military-cards", status="expired") == {old["id"]} and ids("military-cards", status="issued") == {soon["id"]}

    # retirement by death: soldier becomes ស្លាប់ (out of the strength), case status filter
    r = admin.post(f"{API}/retirements", json={"soldier_id": s["id"], "type": "death", "effective_date": today.isoformat(),
                                               "case_status": "processing"}).json()
    assert r["type_name"] == "ស្លាប់" and r["case_status_name"] == "កំពុងដំណើរការ"
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["status_code"] == "deceased"
    assert ids("retirements", case_status="processing", year=today.year) == {r["id"]}


def test_training_filters(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-T1")
    abroad_country = next(c["id"] for c in lk["countries"] if c["name_en"] not in ("Cambodia", None))
    course = admin.post(f"{API}/training/courses", json={
        "name": "វគ្គ TEST", "course_type": "long", "sector": "civil", "country_id": abroad_country, "institution": "សាកលវិទ្យាល័យ X",
        "start_date": "2020-01-01", "end_date": "2020-06-01",
        "participants": [{"soldier_id": s["id"], "status": "dropped", "result": "ល្អ"}]}).json()
    assert course["status"] == "finished" and course["participants"][0]["status"] == "dropped"
    found = lambda **p: {x["id"] for x in admin.get(f"{API}/training/courses", params={"q": "វគ្គ TEST", **p}).json()["items"]}  # noqa: E731
    assert found(abroad="yes", sector="civil", status="finished", participant_status="dropped") == {course["id"]}
    assert found(abroad="no") == set() and found(status="ongoing") == set() and found(institution="X") == {course["id"]}


def test_decision_filters_and_staffing_fill(admin):
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    pos = lk["positions"][0]["id"]
    s = _soldier(admin, lk, unit["id"], mid="TEST-D1")
    old_rank, new_rank = lk["ranks"][-3]["id"], lk["ranks"][-4]["id"]
    d = admin.post(f"{API}/decisions", json={
        "kind": "transfer", "decision_no": "F-1", "decision_date": "2025-06-01", "effective_date": "2025-07-01",
        "items": [{"soldier_id": s["id"], "new_rank_id": new_rank, "new_unit_id": other["id"]}]}).json()
    me = admin.get(f"{API}/auth/me").json()

    def found(**p):
        r = admin.get(f"{API}/decisions", params={"kind": "transfer", "q": "F-1", **p})
        assert r.status_code == 200, r.text
        return {x["id"] for x in r.json()["items"]}

    assert found(old_rank_id=old_rank, new_rank_id=new_rank, new_unit_id=other["id"]) == {d["id"]}
    assert found(old_rank_id=new_rank) == set()
    assert found(old_unit_id=unit["id"], created_by=me["id"], effective_from="2025-07-01", effective_to="2025-07-31") == {d["id"]}
    assert found(effective_from="2025-08-01") == set() and found(overdue="true") == set()  # a draft is never overdue
    row = admin.get(f"{API}/decisions", params={"kind": "transfer", "q": "F-1"}).json()["items"][0]
    assert row["created_by_name"] == me["full_name"]

    # staffing table rows by fill: vacant / full / over
    up = admin.post(f"{API}/unit-positions", json={"unit_id": unit["id"], "position_id": pos, "quota": 2}).json()
    fills = lambda f: {x["id"] for x in admin.get(f"{API}/unit-positions", params={"unit_id": unit["id"], "fill": f}).json()["items"]}  # noqa: E731
    assert up["id"] in fills("vacant") and up["id"] not in fills("full") | fills("over")


def test_conscript_service_filters(admin):
    _, unit, other = _units(admin)
    c = admin.post(f"{API}/conscripts", json={"conscript_no": "TEST-CF1", "name_kh": "កាតព្វកិច្ច TEST", "gender": "M",
                                               "phone": "097111222"}).json()
    sv = admin.post(f"{API}/conscript-services", json={
        "conscript_id": c["id"], "service_type": "reserve", "status": "finished", "start_date": "2022-01-01",
        "end_date": "2024-01-01", "unit_id": unit["id"], "reserve_unit_id": other["id"], "post_service_status": "ពលបម្រុង"})
    assert sv.status_code == 201, sv.text
    assert sv.json()["reserve_unit_name"] == other["name_kh"] and sv.json()["status_name"] == "បញ្ចប់"

    def found(**p):
        r = admin.get(f"{API}/conscripts", params={"q": "TEST-CF1", **p})
        assert r.status_code == 200, r.text
        return [x["id"] for x in r.json()["items"]]

    assert found(service_type="reserve", service_status="finished", reserve_unit_id=other["id"], unit_id=unit["id"],
                 service_end_from="2023-12-01", service_end_to="2024-02-01", phone="111") == [c["id"]]
    assert found(service_type="duty") == [] and found(service_status="serving") == []
    row = admin.get(f"{API}/conscripts", params={"q": "TEST-CF1"}).json()["items"][0]
    assert (row["service_type_name"], row["service_end"], row["post_service_status"]) == ("បម្រុង", "2024-01-01", "ពលបម្រុង")


def test_policy_fields_and_filters(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    soon = date.fromordinal(date.today().toordinal() + 30).isoformat()
    a = _soldier(admin, lk, unit["id"], mid="TEST-P1", national_id_expiry=soon, ethnicity="ចាម", housing_status="rent",
                 dependents_count=3, base_village_id=1020101, voting_village_id=1020101, voting_place="សាលាបឋមសិក្សា")
    b = _soldier(admin, lk, unit["id"], mid="TEST-P2", national_id="NID-P2", national_id_expiry="2020-01-01")
    scope = {"unit_id": unit["id"]}
    assert _ids(admin, **scope, id_expiry="soon") == {a["id"]}
    assert _ids(admin, **scope, id_expiry="expired") == {b["id"]}
    assert _ids(admin, **scope, ethnicity="ចាម", housing_status="rent", dependents_min=2) == {a["id"]}
    assert _ids(admin, **scope, nationality="ខ្មែរ") == {a["id"], b["id"]}
    assert _ids(admin, **scope, base_province_id=1, voting_district_id=102) == {a["id"]}
    prof = admin.get(f"{API}/soldiers/{a['id']}/profile").json()
    assert prof["housing_status_name"] == "ជួល" and prof["voting_village_text"] and prof["base_village_text"]
