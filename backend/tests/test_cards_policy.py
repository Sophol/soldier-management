"""Version 1.1.0: military ID card reason / out-of-date cards, the policy list (ការងារគោលនយោបាយ), the near-retirement
list and the new reports."""

from datetime import date, timedelta

from tests.test_flow import API, _lookups, _soldier, _units


def _day(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _ids(c, path, key="id", **params):
    r = c.get(f"{API}/{path}", params={"size": 500, **params})
    assert r.status_code == 200, r.text
    return {x[key] for x in r.json()["items"]}


def test_military_card_reason_and_outdated(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    promoted = _soldier(admin, lk, unit["id"], mid="TEST-C1", rank_date=_day(-10))
    same = _soldier(admin, lk, unit["id"], mid="TEST-C2", national_id="NID-C2", rank_date="2015-01-01")
    nocard = _soldier(admin, lk, unit["id"], mid="TEST-C3", national_id="NID-C3")
    card = lambda s, no, issued: admin.post(f"{API}/military-cards", json={  # noqa: E731
        "soldier_id": s["id"], "card_no": no, "status": "issued", "reason": "first",
        "issue_date": issued, "expiry_date": _day(400)})
    a = card(promoted, "TC-1", _day(-100)).json()  # issued before the promotion
    b = card(same, "TC-2", "2020-01-01").json()
    assert a["reason_name"] == "ធ្វើលើកដំបូង" and a["outdated"] == ["rank"] and b["outdated"] == []
    assert admin.post(f"{API}/military-cards", json={"soldier_id": nocard["id"], "reason": "bogus"}).status_code == 422

    assert _ids(admin, "military-cards", soldier_id=promoted["id"], outdated="yes") == {a["id"]}
    assert _ids(admin, "military-cards", soldier_id=promoted["id"], outdated="position") == set()
    assert _ids(admin, "military-cards", soldier_id=same["id"], outdated="yes") == set()
    assert a["id"] in _ids(admin, "military-cards", reason="first")

    scope = {"unit_id": unit["id"]}
    assert _ids(admin, "soldiers", **scope, card="none") == {nocard["id"]}
    assert _ids(admin, "soldiers", **scope, card="outdated") == {promoted["id"]}
    assert admin.get(f"{API}/soldiers", params={"card": "other"}).status_code == 422
    # a card replaced by a new one no longer counts
    admin.put(f"{API}/military-cards/{a['id']}", json={**{k: a[k] for k in ("soldier_id", "card_no", "reason", "issue_date",
                                                                          "expiry_date")}, "status": "replaced"})
    assert _ids(admin, "soldiers", **scope, card="none") == {nocard["id"], promoted["id"]}


def test_policy_list(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    soon = _soldier(admin, lk, unit["id"], mid="TEST-P1", national_id_expiry=_day(20), housing_status="rent",
                    dependents_count=3, base_village_id=1020101)
    expired = _soldier(admin, lk, unit["id"], mid="TEST-P2", national_id="NID-P2", national_id_expiry=_day(-5))
    missing = _soldier(admin, lk, unit["id"], mid="TEST-P3", national_id="NID-P3")
    r = admin.get(f"{API}/soldiers/policy", params={"unit_id": unit["id"], "size": 100})
    assert r.status_code == 200, r.text
    rows = {x["id"]: x for x in r.json()["items"]}
    assert rows[soon["id"]]["id_expiry_state"] == "soon" and rows[soon["id"]]["id_days_left"] == 20
    assert rows[soon["id"]]["housing_status_name"] == "ជួល" and rows[soon["id"]]["dependents_count"] == 3
    assert rows[soon["id"]]["base_text"].startswith("ភូមិ")
    assert rows[expired["id"]]["id_expiry_state"] == "expired" and rows[missing["id"]]["id_expiry_state"] == "missing"
    assert _ids(admin, "soldiers/policy", unit_id=unit["id"], id_expiry="expired") == {expired["id"]}

    rep = admin.get(f"{API}/reports/policy", params={"unit_id": unit["id"]}).json()
    assert {x["military_id"] for x in rep["rows"]} == {"TEST-P1", "TEST-P2"}
    rep = admin.get(f"{API}/reports/policy", params={"unit_id": unit["id"], "kind": "expired"}).json()
    assert [x["military_id"] for x in rep["rows"]] == ["TEST-P2"]


def test_retirement_due(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    ages = {"M": int(admin.get(f"{API}/settings").json()["retirement_age_male"]["value"])}
    # the rank's own retirement age wins over the per-gender setting
    rank = lk["ranks"][-3]
    retire_age = rank.get("retirement_age") or ages["M"]
    born = date.today().replace(year=date.today().year - retire_age) + timedelta(days=30)
    due = _soldier(admin, lk, unit["id"], mid="TEST-R1", date_of_birth=born.isoformat())
    _soldier(admin, lk, unit["id"], mid="TEST-R2", national_id="NID-R2", date_of_birth="1995-01-01")
    r = admin.get(f"{API}/retirement-due", params={"unit_id": unit["id"], "months": 12})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert [x["id"] for x in items] == [due["id"]] and 25 <= items[0]["days_left"] <= 31
    assert admin.get(f"{API}/retirement-due", params={"unit_id": unit["id"], "months": 0}).json()["total"] == 0


def test_new_reports(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    _soldier(admin, lk, unit["id"], mid="TEST-G1", gender="F", date_of_birth="1990-05-01")
    _soldier(admin, lk, unit["id"], mid="TEST-G2", national_id="NID-G2", date_of_birth=None)
    run = lambda key, **p: admin.get(f"{API}/reports/{key}", params={"unit_id": unit["id"], **p})  # noqa: E731

    age = run("strength_by_age").json()
    assert age["totals"]["total"] == 2 and age["totals"]["female"] == 1
    assert any(x["age_group"] == "មិនស្គាល់ថ្ងៃកំណើត" and x["total"] == 1 for x in age["rows"])
    missing = run("missing_data").json()
    assert missing["totals"]["total"] == 2 and missing["totals"]["dob"] == 1
    assert run("staffing").status_code == 200 and run("staffing", kind="over").status_code == 200
    decisions = run("decision_status").json()
    assert len(decisions["rows"]) == 3
    assert run("id_cards", kind="outdated").status_code == 200
    for key in ("strength_by_age", "staffing", "missing_data", "decision_status", "id_cards", "policy"):
        r = run(key, format="xlsx")
        assert r.status_code == 200, (key, r.text)
