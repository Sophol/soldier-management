"""Decisions after approval (future effective date, cancelling) and who sees a decision at which workflow level."""

from datetime import date, timedelta

from app.api.v1.decisions import apply_due
from tests.test_flow import API, _lookups, _soldier, _units, approve_all
from tests.test_workflow import _login_as


def _promote(c, soldier_id, rank_id, effective: date, no: str):
    r = c.post(f"{API}/decisions", json={
        "kind": "promote", "decision_no": no, "decision_date": date.today().isoformat(),
        "effective_date": effective.isoformat(), "items": [{"soldier_id": soldier_id, "new_rank_id": rank_id}]})
    assert r.status_code == 201, r.text
    return r.json()


def test_future_effective_date_waits_then_applies(admin, db_session):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    eff = date.today() + timedelta(days=30)
    d = approve_all(admin, _promote(admin, s["id"], lk["ranks"][-4]["id"], eff, "LC-1")["id"])
    # approved and the letter registered, but nothing changes on the soldier before the effective date
    assert d["status"] == "approved" and d["pending"] and d["outgoing_no"]
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == s["current_rank_id"]
    assert apply_due(db_session, today=eff - timedelta(days=1)) == 0
    assert apply_due(db_session, today=eff) == 1
    db_session.flush()
    after = admin.get(f"{API}/soldiers/{s['id']}").json()
    assert (after["current_rank_id"], after["rank_date"]) == (lk["ranks"][-4]["id"], eff.isoformat())
    d = admin.get(f"{API}/decisions/{d['id']}").json()
    assert not d["pending"] and d["steps"][-1]["action"] == "apply"
    assert apply_due(db_session, today=eff) == 0  # never twice


def test_pending_decision_that_no_longer_fits_stays_pending_with_the_reason(admin, db_session):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    eff = date.today() + timedelta(days=10)
    later = approve_all(admin, _promote(admin, s["id"], lk["ranks"][-4]["id"], eff, "LC-2")["id"])
    # meanwhile the soldier is promoted higher, effective today: the pending promotion would now be a demotion
    approve_all(admin, _promote(admin, s["id"], lk["ranks"][-5]["id"], date.today(), "LC-3")["id"])
    assert apply_due(db_session, today=eff) == 0
    assert apply_due(db_session, today=eff) == 0
    d = admin.get(f"{API}/decisions/{later['id']}").json()
    assert d["pending"] and "ខ្ពស់ជាង" in d["apply_error"]
    assert [st["action"] for st in d["steps"]].count("apply_failed") == 1  # logged once, not at every run
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == lk["ranks"][-5]["id"]
    # leadership cancels it: nothing to revert, the letter is marked cancelled
    r = admin.post(f"{API}/decisions/{later['id']}/cancel", json={"comment": "ហួសពេល"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    doc = admin.get(f"{API}/documents/outgoing/{later['outgoing_document_id']}").json()
    assert doc["status"] == "cancelled" and "ហួសពេល" in doc["remarks"]
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == lk["ranks"][-5]["id"]


def test_cancelling_an_applied_decision_marks_its_letter(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = approve_all(admin, _promote(admin, s["id"], lk["ranks"][-4]["id"], date.today(), "LC-4")["id"])
    assert not d["pending"]
    assert admin.post(f"{API}/decisions/{d['id']}/cancel").json()["status"] == "cancelled"
    assert admin.get(f"{API}/soldiers/{s['id']}").json()["current_rank_id"] == s["current_rank_id"]
    assert admin.get(f"{API}/documents/outgoing/{d['outgoing_document_id']}").json()["status"] == "cancelled"


def test_a_level_sees_a_decision_only_once_it_reaches_it(admin, client):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    s = _soldier(admin, lk, unit["id"])
    d = _promote(admin, s["id"], lk["ranks"][-4]["id"], date.today(), "LC-5")
    chief = _login_as(admin, client, "lc.chief", "Chief of Office")
    admin_h = dict(client.headers)

    def chief_sees():
        ids = [x["id"] for x in client.get(f"{API}/decisions", params={"kind": "promote"}, headers=chief).json()["items"]]
        one = client.get(f"{API}/decisions/{d['id']}", headers=chief).status_code
        assert (d["id"] in ids) == (one == 200), (ids, one)
        return one == 200

    assert not chief_sees()  # draft
    admin.post(f"{API}/decisions/{d['id']}/submit")
    client.headers.update(admin_h)
    assert not chief_sees()  # with the deputy chief of office
    assert client.get(f"{API}/decisions/inbox", headers=chief).json()["total"] == 0
    client.headers.update(admin_h)
    admin.post(f"{API}/decisions/{d['id']}/approve")
    assert chief_sees()  # reached the chief of office
    inbox = client.get(f"{API}/decisions/inbox", headers=chief).json()
    assert inbox["total"] == 1 and inbox["waiting"]["promote"] == 1
    client.headers.update(admin_h)
    admin.post(f"{API}/decisions/{d['id']}/return", json={"comment": "កែ"})
    assert not chief_sees()  # back with the lower level
    client.headers.update(admin_h)
    # the dashboard counts what the lists show
    assert client.get(f"{API}/dashboard/summary", headers=chief).json()["pending_decisions"]["promote"] == 0
    client.headers.update(admin_h)
    # rejected below the chief's level: stays hidden; the admin (who enters decisions) sees everything
    admin.post(f"{API}/decisions/{d['id']}/reject", json={"comment": "មិនគ្រប់លក្ខខណ្ឌ"})
    assert not chief_sees()
    client.headers.update(admin_h)
    assert admin.get(f"{API}/decisions/{d['id']}").status_code == 200
