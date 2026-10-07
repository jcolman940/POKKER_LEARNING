def test_empty_report_has_warning(client):
    body = client.get("/api/leaks").json()
    assert body["leaks"] == [] and body["total_hands"] == 0
    assert any("Importá historiales" in w for w in body["warnings"])


def test_detail_not_found(client):
    assert client.get("/api/leaks/detail", params={"key": "x"}).status_code == 404


def test_report_and_detail_with_data(client):
    from app.db.session import _session_factory
    from tests.test_leaks import add_chart, tight_hero

    with _session_factory()() as session:
        add_chart(session)
        tight_hero(session, 60)
    body = client.get("/api/leaks").json()
    assert body["total_hands"] == 60 and len(body["leaks"]) == 1
    key = body["leaks"][0]["key"]
    detail = client.get("/api/leaks/detail", params={"key": key})
    assert detail.status_code == 200
    out = detail.json()
    assert out["group"]["key"] == key and len(out["grid"]) == 169 and out["action"] == "raise"
