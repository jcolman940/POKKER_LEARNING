def test_empty_report_has_warning(client):
    body = client.get("/api/leaks").json()
    assert body["leaks"] == [] and body["total_hands"] == 0
    assert any("Importá historiales" in w for w in body["warnings"])


def test_detail_not_found(client):
    assert client.get("/api/leaks/detail", params={"key": "x"}).status_code == 404
