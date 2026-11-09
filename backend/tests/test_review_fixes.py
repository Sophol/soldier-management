"""Fixes from the review of speed and duplicate data (2026-11-09)."""

import time
from io import BytesIO

from tests.test_flow import API, _lookups, _soldier, _units


def _net(c, soldier_id):
    """Movements in minus out, per unit."""
    out = {}
    for m in c.get(f"{API}/strength-movements", params={"soldier_id": soldier_id, "size": 100}).json()["items"]:
        out[m["unit_id"]] = out.get(m["unit_id"], 0) + (1 if m["direction"] == "in" else -1)
    return {k: v for k, v in out.items() if v}


def test_deleting_a_retirement_undoes_its_move(admin):
    lk = _lookups(admin)
    _, child, other = _units(admin)
    s = _soldier(admin, lk, child["id"], mid="791001", unit_transfer_date="2020-03-01")
    r = admin.post(f"{API}/retirements/bulk", json={"soldier_ids": [s["id"]], "type": "pension",
                                                    "effective_date": "2026-01-15", "unit_id": other["id"]})
    assert r.status_code == 201, r.text
    after = admin.get(f"{API}/soldiers/{s['id']}").json()
    assert after["current_unit_id"] == other["id"] and after["status_code"] == "retired"
    assert _net(admin, s["id"]) == {}  # out of the strength

    assert admin.delete(f"{API}/retirements/{r.json()['items'][0]['id']}").status_code in (200, 204)
    back = admin.get(f"{API}/soldiers/{s['id']}").json()
    assert (back["current_unit_id"], back["unit_transfer_date"], back["status_code"]) == (child["id"], "2020-03-01", "active")
    assert _net(admin, s["id"]) == {child["id"]: 1}  # in the strength of the unit he is in, nothing elsewhere
    assert not any(h["note"] == "ផ្លាស់អង្គភាព ពេលចូលនិវត្តន៍" for h in admin.get(f"{API}/soldiers/{s['id']}/history").json())


def test_long_reports_come_one_page_at_a_time(admin):
    lk = _lookups(admin)
    _, child, _ = _units(admin)
    for i in range(3):
        _soldier(admin, lk, child["id"], mid=f"79200{i}", national_id=f"TEST-NID-RF{i}")
    rep = admin.get(f"{API}/reports/movements", params={"page": 1, "size": 2, "unit_id": child["id"],
                                                        "date_from": "1900-01-01"}).json()
    assert rep["paging"]["total"] == 3 and len(rep["rows"]) == 2 and rep["totals"]["direction"] == "កើន 3 / ថយ 0"
    assert [r["no"] for r in admin.get(f"{API}/reports/movements", params={
        "page": 2, "size": 2, "unit_id": child["id"], "date_from": "1900-01-01"}).json()["rows"]] == [3]
    for key in ("promotion_due", "retirement_due"):
        rep = admin.get(f"{API}/reports/{key}", params={"page": 1, "size": 1}).json()
        assert rep["paging"]["page"] == 1 and len(rep["rows"]) <= 1
    # the Excel file has every row
    assert admin.get(f"{API}/reports/movements", params={"format": "xlsx", "unit_id": child["id"]}).status_code == 200


def test_audit_log_lists_the_user(admin):
    admin.post(f"{API}/units", json={"name_kh": "អង្គភាព AUDIT TEST", "level": 1})
    items = admin.get(f"{API}/audit-logs", params={"size": 5}).json()["items"]
    assert items and items[0]["username"] == "admin"
    assert admin.get(f"{API}/dashboard/activity").json()[0]["user"]


def test_statuses_have_their_codes(admin):
    codes = {x["code"] for x in _lookups(admin)["soldier_status"]}
    assert {"active", "retired", "category2", "separated", "deceased"} <= codes


def test_possible_duplicate_soldiers(admin):
    from tests.test_import_compare import _post, _xlsx

    lk = _lookups(admin)
    _, child, _ = _units(admin)
    a = _soldier(admin, lk, child["id"], mid="795001", name_kh="ហេង សុវណ្ណ", date_of_birth="1985-02-03")
    # same name (spaces / zero-width space ignored) and birth date: a possible duplicate, not when editing itself
    for name in ("ហេង សុវណ្ណ", "ហេងសុវណ្ណ", "ហេង​សុវណ្ណ "):
        found = admin.get(f"{API}/soldiers/duplicates", params={"name_kh": name, "date_of_birth": "1985-02-03"}).json()
        assert [d["military_id"] for d in found] == ["795001"] and found[0]["id"] == a["id"]
    assert admin.get(f"{API}/soldiers/duplicates", params={"name_kh": "ហេង សុវណ្ណ", "date_of_birth": "1985-02-04"}).json() == []
    assert admin.get(f"{API}/soldiers/duplicates", params={
        "name_kh": "ហេង សុវណ្ណ", "date_of_birth": "1985-02-03", "exclude_id": a["id"]}).json() == []
    # only a warning: the second soldier can still be saved
    _soldier(admin, lk, child["id"], mid="795002", name_kh="ហេងសុវណ្ណ", date_of_birth="1985-02-03")

    # Excel import: warned against the system and against another row of the file, still imported
    header = ["អត្តលេខ *", "គោត្តនាមនិងនាម *", "ភេទ *", "ថ្ងៃខែឆ្នាំកំណើត"]
    content = _xlsx(header, ["795003", "ហេង សុវណ្ណ", "ប្រុស", "03/02/1985"], ["795004", "គង់ មករា", "ប្រុស", "01/01/1990"],
                    ["795005", "គង់មករា", "ប្រុស", "01/01/1990"], ["795006", "គង់ មករា", "ប្រុស", "02/01/1990"])
    plan = _post(admin, "import", content).json()
    rows = {r["military_id"]: r for r in plan["rows"]}
    assert plan["create"] == 4 and plan["warning"] == 3
    assert any("795001" in w for w in rows["795003"]["warnings"]) and any("795002" in w for w in rows["795003"]["warnings"])
    assert rows["795004"]["warnings"] == ["ឈ្មោះ និងថ្ងៃកំណើតដូចជួរ 4 ក្នុងឯកសារ"]
    assert rows["795005"]["warnings"] == ["ឈ្មោះ និងថ្ងៃកំណើតដូចជួរ 3 ក្នុងឯកសារ"]
    assert rows["795006"]["warnings"] == []
    assert _post(admin, "import", content, dry_run=False).json()["create"] == 4


def test_dashboard_figures_are_kept_until_counted_again(admin):
    lk = _lookups(admin)
    _, child, _ = _units(admin)
    first = admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()
    assert first["computed_at"] and "pending_decisions" in first and "workflow" in first
    s = _soldier(admin, lk, child["id"], mid="796001")
    kept = admin.get(f"{API}/dashboard/summary").json()  # within dashboard_refresh_minutes: the stored figures
    assert (kept["total_active"], kept["computed_at"]) == (first["total_active"], first["computed_at"])
    after = admin.get(f"{API}/dashboard/summary", params={"refresh": True}).json()
    assert after["total_active"] == first["total_active"] + 1
    assert after["by_gender"]["ប្រុស"] == first["by_gender"].get("ប្រុស", 0) + 1
    assert after["alerts"]["missing_photo"] == first["alerts"]["missing_photo"] + 1
    assert sum(after["by_rank_class"].values()) == sum(after["by_status"].values()) == after["total_active"]
    assert sum(after["by_institution"].values()) == after["total_active"]
    admin.delete(f"{API}/soldiers/{s['id']}")
    # once older than the setting, they are shown while counted again in the background
    admin.put(f"{API}/settings", json={"values": {"dashboard_refresh_minutes": "0"}})
    try:
        admin.get(f"{API}/dashboard/summary")
        for _ in range(50):
            if admin.get(f"{API}/dashboard/summary").json()["total_active"] == first["total_active"]:
                break
            time.sleep(0.2)
        else:
            raise AssertionError("the dashboard was not counted again")
    finally:
        admin.put(f"{API}/settings", json={"values": {"dashboard_refresh_minutes": "5"}})


def _wait_job(c, job):
    for _ in range(100):
        state = c.get(f"{API}/export-jobs/{job['id']}").json()
        if state["status"] in ("done", "failed"):
            return state
        time.sleep(0.2)
    raise AssertionError(f"export job {job['id']} did not finish")


def test_excel_files_are_made_in_the_background(admin, client):
    from openpyxl import load_workbook

    from tests.test_workflow import _login_as

    lk = _lookups(admin)
    _, child, _ = _units(admin)
    _soldier(admin, lk, child["id"], mid="797001")
    r = admin.post(f"{API}/soldiers/export-jobs", params={"q": "797001"})
    assert r.status_code == 202 and r.json()["status"] in ("queued", "running", "done"), r.text
    state = _wait_job(admin, r.json())
    assert state["status"] == "done" and state["size"] > 0, state
    f = admin.get(f"{API}/export-jobs/{state['id']}/file")
    assert f.status_code == 200
    ws = load_workbook(BytesIO(f.content)).worksheets[0]
    assert [row[0].value for row in ws.iter_rows(min_row=2)] == ["797001"]  # the same file as /soldiers/export
    assert any(j["id"] == state["id"] for j in admin.get(f"{API}/export-jobs").json())

    rep = admin.post(f"{API}/reports/strength_by_unit/export-jobs").json()
    assert _wait_job(admin, rep)["status"] == "done"
    assert admin.post(f"{API}/reports/nope/export-jobs").status_code == 404
    # only its owner gets the file; the export permission is needed
    viewer = _login_as(admin, client, "exp.viewer", "Viewer")
    assert client.get(f"{API}/export-jobs/{state['id']}/file", headers=viewer).status_code == 404
    assert client.post(f"{API}/soldiers/export-jobs", headers=viewer).status_code == 403


def test_activity_log_retention(admin, db_session):
    from datetime import datetime, timedelta

    from app.models import AuditLog, ExportJob
    from app.services import maintenance

    old = AuditLog(action="update", table_name="soldiers", record_id="1", created_at=datetime.now() - timedelta(days=4 * 366))
    recent = AuditLog(action="update", table_name="soldiers", record_id="1", created_at=datetime.now() - timedelta(days=700))
    job = ExportJob(kind="soldiers", title="x", filename="x.xlsx", status="done",
                    created_at=datetime.now() - timedelta(days=2))
    db_session.add_all([old, recent, job])
    db_session.commit()
    ids = (old.id, recent.id, job.id)
    maintenance.run_once(db_session)  # audit_retention_years = 3 (seed)
    db_session.expire_all()
    assert db_session.get(AuditLog, ids[0]) is None and db_session.get(AuditLog, ids[1]) is not None
    assert db_session.get(ExportJob, ids[2]) is None
    admin.put(f"{API}/settings", json={"values": {"audit_retention_years": "0"}})  # 0 = keep everything
    try:
        db_session.add(AuditLog(action="update", table_name="soldiers", record_id="1",
                        created_at=datetime.now() - timedelta(days=20 * 366)))
        db_session.commit()
        assert maintenance.prune_audit_log(db_session) == 0
    finally:
        admin.put(f"{API}/settings", json={"values": {"audit_retention_years": "3"}})
