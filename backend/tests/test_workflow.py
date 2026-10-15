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
    assert admin.post(f"{API}/decisions/{d['id']}/submit").json()["status"] == "review"
    # the chief of office cannot act while the file is at the specialist or the deputy chief
    assert client.post(f"{API}/decisions/{d['id']}/approve", headers=chief).status_code == 403
    client.headers.update(admin_h)
    admin.post(f"{API}/decisions/{d['id']}/approve", json={"comment": "លក្ខខណ្ឌគ្រប់គ្រាន់"})
    admin.post(f"{API}/decisions/{d['id']}/approve")
    r = client.post(f"{API}/decisions/{d['id']}/approve", headers=chief, json={"comment": "ត្រឹមត្រូវ"})
    assert r.status_code == 200 and r.json()["status"] == "deputy_department"
    assert client.post(f"{API}/decisions/{d['id']}/approve", headers=chief).status_code == 403
    # nothing changed on the soldier yet
    client.headers.update(admin_h)
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == s["current_rank_id"]
    full = admin.get(f"{API}/decisions/{d['id']}").json()
    assert [st["action"] for st in full["steps"]] == ["submit", "approve", "approve", "approve"]
    assert full["steps"][1]["comment"] == "លក្ខខណ្ឌគ្រប់គ្រាន់"


def test_return_and_reject_need_a_reason(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    admin.post(f"{API}/decisions/{d['id']}/submit")
    admin.post(f"{API}/decisions/{d['id']}/approve")  # -> deputy_office
    assert admin.post(f"{API}/decisions/{d['id']}/return", json={}).status_code == 400
    r = admin.post(f"{API}/decisions/{d['id']}/return", json={"comment": "ខ្វះឯកសារ"}).json()
    assert r["status"] == "review"
    r = admin.post(f"{API}/decisions/{d['id']}/return", json={"comment": "កែលេខ"}).json()
    assert r["status"] == "draft" and "edit" in r["actions"]
    admin.post(f"{API}/decisions/{d['id']}/submit")
    assert admin.post(f"{API}/decisions/{d['id']}/reject", json={"comment": "មិនគ្រប់លក្ខខណ្ឌ"}).json()["status"] == "rejected"
    assert admin.post(f"{API}/decisions/{d['id']}/approve").status_code == 400  # closed
    assert admin.delete(f"{API}/decisions/{d['id']}").status_code == 200


def test_publish_registers_outgoing_letter_and_applies(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    assert admin.post(f"{API}/decisions/{d['id']}/publish").status_code == 400  # not approved yet
    admin.post(f"{API}/decisions/{d['id']}/submit")
    for _ in range(6):
        admin.post(f"{API}/decisions/{d['id']}/approve")
    r = admin.post(f"{API}/decisions/{d['id']}/publish").json()
    assert r["status"] == "published" and r["outgoing_no"] and r["decision_no"] == r["outgoing_no"]
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == lk["ranks"][-4]["id"]


def test_waiting_filter_and_dashboard(admin, client):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    admin.post(f"{API}/decisions/{d['id']}/submit")
    h = _login_as(admin, client, "wf.specialist", "Specialist")
    inbox = client.get(f"{API}/decisions", params={"kind": "promote", "waiting": True, "size": 200}, headers=h).json()
    assert d["id"] in {x["id"] for x in inbox["items"]}
    assert client.get(f"{API}/dashboard/summary", headers=h).json()["workflow"]["waiting_for_me"] >= 1


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


def test_only_specialist_or_super_admin_approves_review(admin, client):
    """After submitting, only the Specialist role (and Super Admin) may act at the review step — not Admin."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _draft(admin, lk, s["id"])
    admin.post(f"{API}/decisions/{d['id']}/submit")
    admin_h = dict(client.headers)
    others = [_login_as(admin, client, f"wf.{r.lower().replace(' ', '')}", r) for r in ("Admin", "Officer", "Chief of Office")]
    specialist = _login_as(admin, client, "wf.spec", "Specialist")
    for h in others:
        assert client.post(f"{API}/decisions/{d['id']}/approve", headers=h).status_code == 403
        item = client.get(f"{API}/decisions/{d['id']}", headers=h).json()
        assert item["actions"] == []
    assert client.get(f"{API}/decisions/{d['id']}", headers=specialist).json()["actions"] == ["approve", "return", "reject"]
    r = client.post(f"{API}/decisions/{d['id']}/approve", headers=specialist)
    assert r.status_code == 200 and r.json()["status"] == "deputy_office"
    client.headers.update(admin_h)
