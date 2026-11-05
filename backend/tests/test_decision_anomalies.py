"""ព័ត៌មានខុសប្រក្រតី per soldier (shown next to the new unit) and the proposal (សំណើ) as an Excel file."""

from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from tests.test_flow import API, _lookups, _soldier, _units

SAME_UNIT = "អង្គភាពថ្មី ដូចអង្គភាពបច្ចុប្បន្ន"
SAME_POSITION = "មុខតំណែងថ្មី ដូចមុខតំណែងបច្ចុប្បន្ន"


def test_anomalies_per_soldier_and_excel(admin):
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    a = _soldier(admin, lk, unit["id"], mid="TEST-DA1")
    b = _soldier(admin, lk, unit["id"], mid="TEST-DA2", national_id="NID-DA2")
    today = date.today().isoformat()
    doc = admin.post(f"{API}/documents/incoming", json={"incoming_no": "IN-DA1", "subject": "សំណើ", "doc_date": today}).json()
    body = {"kind": "transfer", "decision_date": today, "effective_date": today, "incoming_document_id": doc["id"],
            "items": [{"soldier_id": a["id"], "new_unit_id": unit["id"]},  # "moves" to the unit it is already in
                      {"soldier_id": b["id"], "new_unit_id": other["id"]}]}

    # while typing: one list per soldier line, plus the decision-level ones
    chk = admin.post(f"{API}/decisions/check", json=body).json()
    per = {i["soldier_id"]: i["warnings"] for i in chk["items"]}
    assert SAME_UNIT in per[a["id"]] and per[b["id"]] == [] and chk["general"] == []
    assert any(w.endswith(SAME_UNIT) and "TEST-DA1" in w for w in chk["warnings"])  # labelled list still there

    # saved draft: each item carries its own anomalies
    r = admin.post(f"{API}/decisions", json=body)
    assert r.status_code == 201, r.text
    d = r.json()
    items = {i["soldier_id"]: i for i in d["items"]}
    assert SAME_UNIT in items[a["id"]]["anomalies"] and items[b["id"]]["anomalies"] == []
    assert d["general_anomalies"] == [] and len(d["anomalies"]) == len(items[a["id"]]["anomalies"])
    got = admin.get(f"{API}/decisions/{d['id']}").json()
    assert {i["soldier_id"]: i["anomalies"] for i in got["items"]} == {k: v["anomalies"] for k, v in items.items()}

    # the proposal as Excel: one row per soldier, unchanged values repeated, anomalies next to the new unit
    r = admin.get(f"{API}/decisions/{d['id']}/export")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    ws = load_workbook(BytesIO(r.content)).active
    rows = [[c.value for c in row] for row in ws.iter_rows()]
    header = next(row for row in rows if row and row[0] == "ល.រ")
    col = {name: i for i, name in enumerate(header)}
    assert header.index("ព័ត៌មានខុសប្រក្រតី") == header.index("អង្គភាពថ្មី") + 1
    data = {row[col["អត្តលេខ"]]: row for row in rows[rows.index(header) + 1:] if row and isinstance(row[0], int)}
    ra, rb = data[a["military_id"]], data[b["military_id"]]
    assert SAME_UNIT in ra[col["ព័ត៌មានខុសប្រក្រតី"]] and not rb[col["ព័ត៌មានខុសប្រក្រតី"]]
    assert ra[col["ឋានន្តរស័ក្តិថ្មី"]] == ra[col["ឋានន្តរស័ក្តិចាស់"]] == a["rank_name"]  # no promotion: same rank
    assert rb[col["អង្គភាពចាស់"]] == unit["name_kh"] and rb[col["អង្គភាពថ្មី"]] == other["name_kh"]


def test_decision_export_needs_permission(client, admin):
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-DA3")
    today = date.today().isoformat()
    d = admin.post(f"{API}/decisions", json={"kind": "transfer", "decision_date": today, "effective_date": today,
                                             "items": [{"soldier_id": s["id"], "new_unit_id": other["id"]}]}).json()
    client.headers.pop("Authorization")
    assert client.get(f"{API}/decisions/{d['id']}/export").status_code == 401


def test_same_unit_is_normal_with_a_new_position(admin):
    """An appointment within the soldier's unit (new position, same unit chosen) or a transfer keeping the same
    position title is not flagged; choosing the current unit or position with nothing else changing is."""
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-DA4", current_position_id=lk["positions"][0]["id"])
    today = date.today().isoformat()

    def per(kind, **item):
        body = {"kind": kind, "decision_date": today, "effective_date": today, "items": [{"soldier_id": s["id"], **item}]}
        r = admin.post(f"{API}/decisions/check", json=body)
        assert r.status_code == 200, r.text
        return r.json()["items"][0]["warnings"]

    assert SAME_UNIT not in per("appoint", new_position_id=lk["positions"][1]["id"], new_unit_id=unit["id"])
    assert SAME_POSITION not in per("transfer", new_position_id=lk["positions"][0]["id"], new_unit_id=other["id"])
    assert SAME_UNIT in per("transfer", new_unit_id=unit["id"])
    assert SAME_POSITION in per("appoint", new_position_id=lk["positions"][0]["id"])


def test_check_reports_errors_and_decision_level_anomalies(admin):
    """While typing, each soldier line also shows what saving would refuse; the decision itself is flagged when it
    has no incoming request linked or reuses a decision number of the same year."""
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-DA5")
    today = date.today().isoformat()
    lower = lk["ranks"][-1]["id"]  # lowest rank: not a promotion
    admin.post(f"{API}/decisions", json={"kind": "promote", "decision_no": "DUP-1", "decision_date": today, "effective_date": today,
                                         "items": [{"soldier_id": s["id"], "new_rank_id": lk["ranks"][-4]["id"]}]})
    body = {"kind": "promote", "decision_no": "DUP-1", "decision_date": today, "effective_date": today,
            "items": [{"soldier_id": s["id"], "new_rank_id": lower}, {"soldier_id": s["id"], "new_rank_id": lower}]}
    chk = admin.post(f"{API}/decisions/check", json=body).json()
    assert "មិនទាន់ភ្ជាប់ឯកសារចូល (សំណើ)" in chk["general"]
    assert any("DUP-1" in g for g in chk["general"])
    errors = chk["items"][0]["errors"]
    assert any("ខ្ពស់ជាង" in e for e in errors) and "យោធិនម្នាក់នេះត្រូវបានបញ្ចូលច្រើនដង" in errors
    # the form as Excel, saved or not, with the errors next to the soldier
    r = admin.post(f"{API}/decisions/export-preview", json=body)
    assert r.status_code == 200, r.text
    ws = load_workbook(BytesIO(r.content)).active
    texts = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
    assert any(t.startswith("មិនអាចរក្សាទុក:") for t in texts)


def test_export_filename_with_khmer_decision_number(admin):
    lk = _lookups(admin)
    _, unit, other = _units(admin)
    s = _soldier(admin, lk, unit["id"], mid="TEST-DA6")
    today = date.today().isoformat()
    d = admin.post(f"{API}/decisions", json={"kind": "transfer", "decision_no": "០១២/២៦", "decision_date": today,
                                             "effective_date": today, "items": [{"soldier_id": s["id"], "new_unit_id": other["id"]}]}).json()
    r = admin.get(f"{API}/decisions/{d['id']}/export")
    assert r.status_code == 200, r.text
    cd = r.headers["content-disposition"]
    assert "filename=decision-transfer" in cd and "filename*=UTF-8''" in cd
