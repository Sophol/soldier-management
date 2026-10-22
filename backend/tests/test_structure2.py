"""Structure from New.txt §1–2: position hierarchy, specialty sections, incoming documents by unit,
documents by type, conscript filters."""

from tests.test_flow import API, _lookups, _soldier, _units


def test_position_hierarchy(admin):
    head = admin.post(f"{API}/positions", json={"name_kh": "ប្រធាន TEST"}).json()
    deputy = admin.post(f"{API}/positions", json={"name_kh": "អនុប្រធាន TEST", "parent_id": head["id"]}).json()
    attached = admin.post(f"{API}/positions", json={"name_kh": "ចំណុះ TEST", "parent_id": deputy["id"]}).json()
    assert (head["level"], deputy["level"], attached["level"]) == (1, 2, 3) and attached["parent_name"] == "អនុប្រធាន TEST"
    assert admin.post(f"{API}/positions", json={"name_kh": "x", "parent_id": attached["id"]}).status_code == 400  # level 4
    cycle = admin.put(f"{API}/positions/{head['id']}", json={"name_kh": "ប្រធាន TEST", "parent_id": attached["id"]})
    assert cycle.status_code == 400
    tree = admin.get(f"{API}/positions/tree").json()
    node = next(n for n in tree if n["id"] == head["id"])
    assert node["children"][0]["children"][0]["id"] == attached["id"]
    assert admin.delete(f"{API}/positions/{head['id']}").status_code == 409  # has sub-positions


def test_specialty_section_filters_soldiers(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    section = admin.post(f"{API}/lookups", json={"category": "specialty_section", "name_kh": "ផ្នែក TEST"}).json()
    sp = admin.post(f"{API}/specialties", json={"name_kh": "ជំនាញ TEST", "section_id": section["id"]}).json()
    assert sp["section_name"] == "ផ្នែក TEST"
    not_a_section = lk["blood_type"][0]["id"]
    assert admin.post(f"{API}/specialties", json={"name_kh": "x", "section_id": not_a_section}).status_code == 400
    s = _soldier(admin, lk, unit["id"], specialty_id=sp["id"])
    found = admin.get(f"{API}/soldiers", params={"section_id": section["id"]}).json()
    assert [x["id"] for x in found["items"]] == [s["id"]]


def test_incoming_from_unit_and_documents_by_type(admin):
    root, unit, _ = _units(admin)
    types = admin.get(f"{API}/document-types", params={"size": 50}).json()["items"]
    doc = admin.post(f"{API}/documents/incoming", json={"incoming_no": "IN-S1", "subject": "សំណើ", "doc_date": "2026-01-02",
                                                         "from_unit_id": unit["id"], "document_type_id": types[0]["id"]}).json()
    assert doc["from_unit_name"] == unit["name_kh"] and doc["from_unit"] == unit["name_kh"]
    found = admin.get(f"{API}/documents/incoming", params={"from_unit_id": unit["id"]}).json()
    assert [d["id"] for d in found["items"]] == [doc["id"]]
    by_type = {r["id"]: r for r in admin.get(f"{API}/documents/by-type", params={"year": 2026}).json()}
    assert by_type[types[0]["id"]]["incoming"] >= 1
    assert root


def test_conscript_new_fields_and_filters(admin):
    lk = _lookups(admin)
    _, unit, _ = _units(admin)
    blood = lk["blood_type"][0]["id"]
    c = admin.post(f"{API}/conscripts", json={"conscript_no": "TEST-CF1", "name_kh": "x", "gender": "M",
                                              "date_of_birth": "2006-01-01", "blood_type_id": blood}).json()
    rank = lk["ranks"][-1]["id"]
    admin.post(f"{API}/conscript-services", json={"conscript_id": c["id"], "start_date": "2025-06-01", "unit_id": unit["id"],
                                                  "rank_id": rank, "role": "ពលទាហាន"})
    row = admin.get(f"{API}/conscripts/{c['id']}").json()
    assert (row["blood_type_name"], row["rank_name"], row["unit_name"], row["service_start"]) == \
        (lk["blood_type"][0]["name_kh"], lk["ranks"][-1]["name_kh"], unit["name_kh"], "2025-06-01")
    for params in ({"blood_type_id": blood}, {"unit_id": unit["id"]}, {"rank_id": rank}, {"age_min": 18, "age_max": 25}):
        ids = [x["id"] for x in admin.get(f"{API}/conscripts", params={**params, "size": 500}).json()["items"]]
        assert c["id"] in ids, params
