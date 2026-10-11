from datetime import date

API = "/api/v1"


def _lookups(c):
    r = c.get(f"{API}/lookups/all")
    assert r.status_code == 200
    return r.json()


def _units(c):
    root = c.post(f"{API}/units", json={"name_kh": "កងទ័ពជើងគោក TEST", "level": 1}).json()
    child = c.post(f"{API}/units", json={"name_kh": "កងពលធំ TEST", "parent_id": root["id"], "level": 1}).json()
    other = c.post(f"{API}/units", json={"name_kh": "កងពលតូច TEST", "parent_id": root["id"], "level": 1}).json()
    return root, child, other


def _soldier(c, lk, unit_id, mid="TEST-0001", **kw):
    ranks = lk["ranks"]  # ordered highest first
    body = {
        "military_id": mid, "name_kh": "សុខ សុភា", "name_latin": "SOK SOPHEA", "gender": "M",
        "date_of_birth": "1980-05-01", "enlistment_date": "2000-01-15",
        "current_rank_id": ranks[-3]["id"], "rank_date": "2015-01-01", "current_unit_id": unit_id,
        "status_id": next(x["id"] for x in lk["soldier_status"] if x["code"] == "active"),
        "birth_village_id": 1020101, "educations": [{"kind": "general", "institution": "វិទ្យាល័យ"}],
        "languages": [{"language_id": lk["language"][0]["id"], "level": "ល្អ"}], **kw,
    }
    r = c.post(f"{API}/soldiers", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_health_and_auth(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get(f"{API}/auth/me").status_code == 401
    assert client.post(f"{API}/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401


def test_geo(admin):
    provinces = admin.get(f"{API}/geo/provinces", params={"size": 100}).json()
    assert provinces["total"] == 25
    d = admin.get(f"{API}/geo/districts", params={"province_id": 12, "size": 100}).json()
    assert d["total"] > 0 and all(x["type"] == "ខណ្ឌ" for x in d["items"])
    path = admin.get(f"{API}/geo/village-path/1020101").json()
    assert path["province_id"] == 1 and path["commune_id"] == 10201


def test_unit_tree_levels(admin):
    root, child, _ = _units(admin)
    assert root["level"] == 1 and child["level"] == 2
    assert child["path"] == f"{root['path']}{child['id']}/"
    # cannot move a unit under its own child
    r = admin.put(f"{API}/units/{root['id']}", json={"name_kh": "x", "parent_id": child["id"], "level": 1})
    assert r.status_code == 400
    tree = admin.get(f"{API}/units/tree").json()
    node = next(n for n in tree if n["id"] == root["id"])
    assert len(node["children"]) == 2


def test_soldier_crud_and_search(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    assert s["age"] >= 40 and s["service_length"].endswith("ខែ")
    assert len(s["educations"]) == 1 and len(s["languages"]) == 1
    # duplicate military id
    r = admin.post(f"{API}/soldiers", json={"military_id": "TEST-0001", "name_kh": "x", "gender": "F"})
    assert r.status_code == 409
    found = admin.get(f"{API}/soldiers", params={"q": "SOPHEA"}).json()
    assert any(x["id"] == s["id"] for x in found["items"])
    found = admin.get(f"{API}/soldiers", params={"age_min": 40, "unit_id": unit["id"]}).json()
    assert found["total"] == 1
    prof = admin.get(f"{API}/soldiers/{s['id']}/profile").json()
    assert prof["birth_village_text"].startswith("ភូមិ")
    assert prof["history"][0]["kind"] == "initial"
    mv = admin.get(f"{API}/strength-movements", params={"soldier_id": s["id"]}).json()
    assert mv["total"] == 1 and mv["items"][0]["reason"] == "recruit"
    assert admin.get(f"{API}/soldiers/export").status_code == 200


def test_promotion_decision_approve_and_cancel(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    old_rank = s["current_rank_id"]
    higher = lk["ranks"][-4]["id"]
    lower = lk["ranks"][-1]["id"]
    body = {"kind": "promote", "decision_no": "001/26", "decision_date": "2026-01-10",
            "effective_date": "2026-01-15", "items": [{"soldier_id": s["id"], "new_rank_id": lower}]}
    assert admin.post(f"{API}/decisions", json=body).status_code == 400  # lower rank rejected
    body["items"][0]["new_rank_id"] = higher
    d = admin.post(f"{API}/decisions", json=body).json()
    assert d["status"] == "draft"
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == old_rank  # unchanged until approved
    d = admin.post(f"{API}/decisions/{d['id']}/approve").json()
    assert d["status"] == "approved"
    after = admin.get(f"{API}/soldiers/{s['id']}").json()
    assert after["current_rank_id"] == higher and after["rank_date"] == "2026-01-15"
    d = admin.post(f"{API}/decisions/{d['id']}/cancel").json()
    assert d["status"] == "cancelled"
    reverted = admin.get(f"{API}/soldiers/{s['id']}").json()
    assert reverted["current_rank_id"] == old_rank and reverted["rank_date"] == "2015-01-01"


def test_transfer_creates_movements(admin):
    lk = _lookups(admin)
    _, unit_a, unit_b = _units(admin)
    s = _soldier(admin, lk, unit_a["id"])
    body = {"kind": "transfer", "decision_no": "T-1", "decision_date": "2026-02-01", "effective_date": "2026-02-01",
            "items": [{"soldier_id": s["id"], "new_unit_id": unit_b["id"]}]}
    d = admin.post(f"{API}/decisions", json=body).json()
    admin.post(f"{API}/decisions/{d['id']}/approve")
    after = admin.get(f"{API}/soldiers/{s['id']}").json()
    assert after["current_unit_id"] == unit_b["id"] and after["from_unit_text"] == unit_a["name_kh"]
    mv = admin.get(f"{API}/strength-movements", params={"soldier_id": s["id"]}).json()["items"]
    assert {(m["direction"], m["reason"]) for m in mv} >= {("out", "transfer_out"), ("in", "transfer_in")}
    rep = admin.get(f"{API}/reports/movements", params={"date_from": "2026-01-01", "date_to": "2026-12-31"}).json()
    assert any(r["military_id"] == s["military_id"] for r in rep["rows"])


def test_retirement_sets_status_and_delete_restores(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    r = admin.post(f"{API}/retirements", json={"soldier_id": s["id"], "type": "pension",
                                               "effective_date": date.today().isoformat()}).json()
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["status_code"] == "retired"
    admin.delete(f"{API}/retirements/{r['id']}")
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["status_code"] == "active"


def test_outgoing_document_numbering(admin):
    a = admin.post(f"{API}/documents/outgoing", json={"subject": "ក", "doc_date": "2026-03-01"}).json()
    b = admin.post(f"{API}/documents/outgoing", json={"subject": "ខ", "doc_date": "2026-03-02"}).json()
    assert b["seq"] == a["seq"] + 1 and b["outgoing_no"].endswith("/26")
    i = admin.post(f"{API}/documents/incoming", json={"incoming_no": "IN-1", "subject": "x", "doc_date": "2026-03-01"})
    assert i.status_code == 201
    dup = admin.post(f"{API}/documents/incoming", json={"incoming_no": "IN-1", "subject": "y", "doc_date": "2026-05-01"})
    assert dup.status_code == 409


def test_dashboard_and_reports(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    _soldier(admin, lk, unit["id"])
    dash = admin.get(f"{API}/dashboard/summary").json()
    assert dash["total_active"] >= 1 and len(dash["movements"]["months"]) == 13
    for rep in admin.get(f"{API}/reports").json():
        r = admin.get(f"{API}/reports/{rep['key']}")
        assert r.status_code == 200, (rep["key"], r.text)
    x = admin.get(f"{API}/reports/strength_by_unit", params={"format": "xlsx"})
    assert x.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_viewer_permissions_and_unit_scope(admin):
    lk = _lookups(admin)
    _, unit_a, unit_b = _units(admin)
    _soldier(admin, lk, unit_a["id"], mid="TEST-A")
    _soldier(admin, lk, unit_b["id"], mid="TEST-B")
    viewer_role = next(r for r in admin.get(f"{API}/roles").json()["items"] if r["name"] == "Viewer")
    r = admin.post(f"{API}/users", json={"username": "viewer_test", "full_name": "V", "role_id": viewer_role["id"],
                                        "unit_scope_id": unit_a["id"], "password": "Viewer@123"})
    assert r.status_code == 201, r.text
    tok = admin.post(f"{API}/auth/login", json={"username": "viewer_test", "password": "Viewer@123"}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    items = admin.get(f"{API}/soldiers", headers=h).json()["items"]
    assert {i["military_id"] for i in items} == {"TEST-A"}
    assert admin.post(f"{API}/soldiers", headers=h, json={"military_id": "Z", "name_kh": "z", "gender": "M"}).status_code == 403
    assert admin.get(f"{API}/users", headers=h).status_code == 403


def test_document_attachments_upload_list_download(admin):
    doc = admin.post(f"{API}/documents/incoming", json={"incoming_no": "ATT-1", "subject": "x", "doc_date": "2026-03-01"}).json()
    pdf = b"%PDF-1.4\n%test\n"
    r = admin.post(f"{API}/files/doc_in/{doc['id']}", files={"file": ("letter.pdf", pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    bad = admin.post(f"{API}/files/doc_in/{doc['id']}", files={"file": ("virus.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 400
    files = admin.get(f"{API}/files/doc_in/{doc['id']}").json()
    assert [f["file_name"] for f in files] == ["letter.pdf"]
    dl = admin.get(f"{API}/files/download/{files[0]['id']}", params={"inline": 1})
    assert dl.status_code == 200 and dl.content == pdf
    assert dl.headers["content-disposition"].startswith("inline")
    listed = admin.get(f"{API}/documents/incoming", params={"q": "ATT-1"}).json()["items"][0]
    assert listed["file_count"] == 1
    assert admin.delete(f"{API}/files/{files[0]['id']}").status_code == 200
