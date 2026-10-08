import pytest

from app.recommend.preflop_equity import class_index, range_vector


def grid(text: str) -> list[float]:
    return range_vector(text).tolist()


def chart(**overrides):
    body = {
        "name": "BTN RFI 100bb",
        "source": "pokalab",
        "game_format": "cash",
        "players": 6,
        "position": "BTN",
        "stack_bb": 100,
        "situation": "rfi",
        "open_size_bb": 2.5,
        "rake": "GG NL50",
        "actions": {"raise": grid("22+,A2s+,K9s+,QTs+,JTs,ATo+,KJo+,AJs:0.5")},
    }
    body.update(overrides)
    return body


def test_chart_crud(client):
    created = client.post("/api/charts", json=chart())
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert client.get("/api/charts").json()[0]["name"] == "BTN RFI 100bb"

    updated = client.put(f"/api/charts/{cid}", json=chart(name="BTN open"))
    assert updated.json()["name"] == "BTN open"
    assert client.get(f"/api/charts/{cid}").json()["rake"] == "GG NL50"

    assert client.delete(f"/api/charts/{cid}").status_code == 204
    assert client.get(f"/api/charts/{cid}").status_code == 404


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"position": "UTG"}, "no existe"),
        ({"vs_position": "BTN"}, "misma"),
        ({"actions": {"raise": grid("AA"), "call": grid("AA")}}, "más de 100%"),
        ({"actions": {"jam": grid("AA")}}, "desconocida"),
        ({"actions": {"raise": [1.0] * 10}}, "169"),
        ({"actions": {}}, "al menos una"),
    ],
)
def test_chart_validation(client, override, message):
    resp = client.post("/api/charts", json=chart(**override))
    assert resp.status_code == 422
    assert message in resp.text


def test_import_export_roundtrip_with_pio_text(client):
    exchange = {
        "format": "poker-study-ranges",
        "version": 1,
        "charts": [
            {
                **{k: v for k, v in chart().items() if k != "actions"},
                # PioViewer .txt content: weights, several lines.
                "actions": {"raise": "AA:1.0,AKs:0.5,\nKK:1.0\r\nQQ:0.75"},
            },
            {**{k: v for k, v in chart().items() if k != "actions"}, "actions": {"raise": "AKx"}},
        ],
    }
    result = client.post("/api/charts/import", json=exchange).json()
    assert result["created"] == 1
    assert "Rango inválido" in result["errors"][0]

    exported = client.get("/api/charts/export").json()
    assert exported["format"] == "poker-study-ranges"
    assert exported["charts"][0]["actions"]["raise"] == "AA,AKs:0.5,KK,QQ:0.75"

    only_custom = client.get("/api/charts/export", params={"source": "custom"}).json()
    assert only_custom["charts"] == []

    bad = client.post("/api/charts/import", json={**exchange, "format": "other"})
    assert bad.status_code == 422


def test_range_parse_accepts_multiline_pio_files(client):
    data = client.post("/api/ranges/parse", json={"text": "AA:1.0\nKK:0.5\n"}).json()
    assert data["valid"]
    assert data["grid"][class_index()["KK"]] == 0.5
