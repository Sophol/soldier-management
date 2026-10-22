"""Decision approval workflow (answer.txt) and conscription."""

from tests.test_flow import API, _lookups, _soldier, _units


def _login_as(admin, client, username, role):
    roles = {r["name"]: r["id"] for r in admin.get(f"{API}/roles").json()["items"]}
    admin.post(f"{API}/users", json={"username": username, "full_name": username, "role_id": roles[role],
                                     "password": "Level@123"})
    tok = client.post(f"{API}/auth/login", json={"username": username, "password": "Level@123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _draft(admin, lk, soldier_id, no=""):
    return admin.post(f"{API}/decisions", json={
        "kind": "promote", "decision_no": no, "decision_date": "2025-06-01", "effective_date": "2025-07-01",
        "items": [{"soldier_id": soldier_id, "new_rank_id": lk["ranks"][-4]["id"]}]}).json()


def test_each_level_acts_only_at_its_own_step(admin, client):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    chief = _login_as(admin, client, "wf.chief", "Chief of Office")
    admin_h = dict(client.headers)
    assert admin.post(f"{API}/decisions/{d['id']}/submit").json()["status"] == "deputy_office"
    # the chief of office cannot act while the file is with the deputy chief of office
    assert client.post(f"{API}/decisions/{d['id']}/approve", headers=chief).status_code == 403
    client.headers.update(admin_h)
    admin.post(f"{API}/decisions/{d['id']}/approve", json={"comment": "បានទទួលទិស"})
    r = client.post(f"{API}/decisions/{d['id']}/approve", headers=chief, json={"comment": "ត្រឹមត្រូវ"})
    assert r.status_code == 200 and r.json()["status"] == "deputy_director"
    assert client.post(f"{API}/decisions/{d['id']}/approve", headers=chief).status_code == 403
    client.headers.update(admin_h)
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == s["current_rank_id"]  # unchanged yet
    full = admin.get(f"{API}/decisions/{d['id']}").json()
    assert [st["action"] for st in full["steps"]] == ["submit", "approve", "approve"]
    assert full["steps"][1]["comment"] == "បានទទួលទិស"


def test_return_and_reject_need_a_reason(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    admin.post(f"{API}/decisions/{d['id']}/submit")
    admin.post(f"{API}/decisions/{d['id']}/approve")  # -> chief_office
    assert admin.post(f"{API}/decisions/{d['id']}/return", json={}).status_code == 400
    r = admin.post(f"{API}/decisions/{d['id']}/return", json={"comment": "ខ្វះឯកសារ"}).json()
    assert r["status"] == "deputy_office"
    r = admin.post(f"{API}/decisions/{d['id']}/return", json={"comment": "កែលេខ"}).json()
    assert r["status"] == "draft" and "edit" in r["actions"]
    admin.post(f"{API}/decisions/{d['id']}/submit")
    assert admin.post(f"{API}/decisions/{d['id']}/reject", json={"comment": "មិនគ្រប់លក្ខខណ្ឌ"}).json()["status"] == "rejected"
    assert admin.post(f"{API}/decisions/{d['id']}/approve").status_code == 400  # closed
    assert admin.delete(f"{API}/decisions/{d['id']}").status_code == 200


def test_director_approval_registers_letter_and_applies(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    admin.post(f"{API}/decisions/{d['id']}/submit")
    for _ in range(3):
        r = admin.post(f"{API}/decisions/{d['id']}/approve").json()
    assert r["status"] == "submitted" and r["status_name"].startswith("កំពុងដាក់សំណើ")
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == s["current_rank_id"]
    r = admin.post(f"{API}/decisions/{d['id']}/approve", json={"decision_no": "77 ស.ស.រ"}).json()
    assert r["status"] == "approved" and r["outgoing_no"] and r["decision_no"] == "77 ស.ស.រ"
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == lk["ranks"][-4]["id"]
    assert admin.post(f"{API}/decisions/{d['id']}/cancel").json()["status"] == "cancelled"
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == s["current_rank_id"]


def test_waiting_filter_and_dashboard(admin, client):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    admin.post(f"{API}/decisions/{d['id']}/submit")
    h = _login_as(admin, client, "wf.deputy", "Deputy Chief of Office")
    inbox = client.get(f"{API}/decisions", params={"kind": "promote", "waiting": True, "size": 200}, headers=h).json()
    assert d["id"] in {x["id"] for x in inbox["items"]}
    assert client.get(f"{API}/dashboard/summary", headers=h).json()["workflow"]["waiting_for_me"] >= 1


def test_only_the_level_role_or_super_admin_acts(admin, client):
    """After submitting, only the deputy chief of office (and Super Admin) acts at that step — not Admin or others."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    admin.post(f"{API}/decisions/{d['id']}/submit")
    admin_h = dict(client.headers)
    others = [_login_as(admin, client, f"wf.{r.lower().replace(' ', '')}", r)
              for r in ("Admin", "Assistant", "Chief of Office", "Director")]
    deputy = _login_as(admin, client, "wf.dep", "Deputy Chief of Office")
    for h in others:
        assert client.post(f"{API}/decisions/{d['id']}/approve", headers=h).status_code == 403
        assert client.get(f"{API}/decisions/{d['id']}", headers=h).json()["actions"] == []
    assert client.get(f"{API}/decisions/{d['id']}", headers=deputy).json()["actions"] == ["approve", "return", "reject"]
    r = client.post(f"{API}/decisions/{d['id']}/approve", headers=deputy)
    assert r.status_code == 200 and r.json()["status"] == "chief_office"
    client.headers.update(admin_h)


def test_assistant_enters_and_submits(admin, client):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    admin_h = dict(client.headers)
    h = _login_as(admin, client, "wf.assist", "Assistant")
    d = client.post(f"{API}/decisions", headers=h, json={
        "kind": "promote", "decision_date": "2025-06-01", "effective_date": "2025-07-01",
        "items": [{"soldier_id": s["id"], "new_rank_id": lk["ranks"][-4]["id"]}]}).json()
    assert d["actions"] == ["edit", "submit"]
    assert client.post(f"{API}/decisions/{d['id']}/submit", headers=h).json()["status"] == "deputy_office"
    client.headers.update(admin_h)


def test_conscription(admin):
    c = admin.post(f"{API}/conscripts", json={"conscript_no": "TEST-C1", "name_kh": "សុខ វិសាល", "gender": "M",
                                              "date_of_birth": "2006-03-01", "national_id": "TEST-NID-1"})
    assert c.status_code == 201, c.text
    cid = c.json()["id"]
    dup = admin.post(f"{API}/conscripts", json={"conscript_no": "TEST-C1", "name_kh": "x", "gender": "M"})
    assert dup.status_code == 409
    reg = {"conscript_id": cid, "registration_year": 2025, "province_id": 12, "status": "deferred"}
    assert admin.post(f"{API}/conscript-registrations", json=reg).status_code == 400  # deferral needs a reason
    r = admin.post(f"{API}/conscript-registrations", json={**reg, "reason": "study"})
    assert r.status_code == 201 and r.json()["reason_name"] == "សិក្សា"
    m = admin.post(f"{API}/conscript-medicals", json={"conscript_id": cid, "exam_date": "2025-02-01",
                                                      "height_cm": 170, "weight_kg": 60, "result": "pass"}).json()
    assert m["bmi"] == 20.8
    found = admin.get(f"{API}/conscripts", params={"status": "deferred", "registration_year": 2025}).json()
    assert any(x["id"] == cid and x["status_name"] == "ពន្យារ" for x in found["items"])
    rep = admin.get(f"{API}/reports/conscripts", params={"date_from": "2025-01-01", "date_to": "2025-12-31"}).json()
    assert rep["totals"]["deferred"] >= 1


def test_medical_data_needs_its_own_permission(admin, client):
    h = _login_as(admin, client, "wf.viewer", "Viewer")
    assert client.get(f"{API}/conscripts", headers=h).status_code == 200
    assert client.get(f"{API}/conscript-medicals", headers=h).status_code == 403


def test_dashboard_new_counts_and_activity(admin):
    d = admin.get(f"{API}/dashboard/summary").json()
    assert {"category1", "category2"} <= d["categories"].keys()
    assert {"missing_dob", "missing_enlistment", "missing_rank_date"} <= d["alerts"].keys()
    assert {"incoming", "outgoing"} == d["requests"].keys() and {"in_country", "abroad"} == d["studying"].keys()
    feed = admin.get(f"{API}/dashboard/activity", params={"limit": 5}).json()
    assert feed and feed[0]["user"] and feed[0]["action"]


def test_activity_feed_needs_audit_permission(admin, client):
    h = _login_as(admin, client, "wf.view", "Viewer")
    assert client.get(f"{API}/dashboard/activity", headers=h).status_code == 403


def test_military_id_list_filter(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    a = _soldier(admin, lk, unit["id"], mid="TEST-L1")
    _soldier(admin, lk, unit["id"], mid="TEST-L2", national_id=None)
    c = _soldier(admin, lk, unit["id"], mid="TEST-L3", national_id="TEST-NID-L3")
    found = admin.get(f"{API}/soldiers", params={"military_ids": "TEST-L1\nTEST-L3, NOPE"}).json()
    assert {x["id"] for x in found["items"]} == {a["id"], c["id"]}
    assert admin.get(f"{API}/soldiers/export", params={"military_ids": "TEST-L1"}).status_code == 200


def test_voluntary_retirement_and_service_track(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], service_track="combat")
    assert s["service_track"] == "combat"
    r = admin.post(f"{API}/retirements", json={"soldier_id": s["id"], "type": "voluntary", "effective_date": "2025-01-01"})
    assert r.status_code == 201 and r.json()["type_name"] == "ស្ម័គ្រចិត្តចូលនិវត្តន៍"
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["status_code"] == "retired"


def test_logo_upload_is_public_and_protected(admin, client):
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da6364f8cf"
                        "000000020001e221bc330000000049454e44ae426082")
    assert admin.post(f"{API}/settings/logo", files={"file": ("logo.png", png, "image/png")}).status_code == 200
    headers = client.headers.pop("Authorization")
    assert client.get(f"{API}/settings/logo").status_code == 200  # shown on the login page
    client.headers["Authorization"] = headers
    # the general settings save cannot point the public logo at another stored file
    admin.put(f"{API}/settings", json={"values": {"logo_path": "photos/x.jpg"}})
    assert admin.get(f"{API}/settings/logo").status_code == 200
    admin.delete(f"{API}/settings/logo")
