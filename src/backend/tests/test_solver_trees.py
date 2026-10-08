import json

import pytest

from app.solver.trees import STREETS, get_preset, load_presets


def test_bundled_presets():
    presets = load_presets()
    assert set(presets) == {"simple", "chico", "amplio"}
    simple = presets["simple"]
    assert simple.streets["flop"].bet == (33.0, 75.0)
    assert simple.streets["river"].raise_ == (60.0,)
    assert all(s in simple.streets for s in STREETS)


def test_canonical_is_json_stable():
    a = get_preset("simple").canonical()
    assert json.dumps(a, sort_keys=True) == json.dumps(
        get_preset("simple").canonical(), sort_keys=True
    )
    assert a["flop"]["bet"] == [33.0, 75.0]


def test_unknown_preset():
    with pytest.raises(ValueError, match="Preset de árbol desconocido: x"):
        get_preset("x")


@pytest.mark.parametrize(
    "street_cfg",
    [{"bet": [0], "raise": [60]}, {"bet": [400], "raise": [60]}, {"bet": [], "raise": [60]}],
)
def test_invalid_sizes(tmp_path, street_cfg):
    bad = {"p": {"label": "P", "flop": street_cfg, "turn": street_cfg, "river": street_cfg}}
    path = tmp_path / "trees.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_presets(path)
