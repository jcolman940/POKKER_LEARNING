from app.solver.flops import representative_flops


def suits(flop):
    return {flop[1], flop[3], flop[5]}


def ranks(flop):
    return [flop[0], flop[2], flop[4]]


def test_25_unique_and_deterministic():
    a = representative_flops()
    assert len(a) == 25 and len(set(a)) == 25
    assert a == representative_flops()


def test_covers_textures():
    flops = representative_flops()
    assert any(len(suits(f)) == 1 for f in flops)  # monotone
    assert any(len(suits(f)) == 2 for f in flops)  # two-tone
    assert any(len(suits(f)) == 3 for f in flops)  # rainbow
    assert any(len(set(ranks(f))) == 2 for f in flops)  # paired
    assert any(ranks(f)[0] == "A" for f in flops)
    assert any(ranks(f)[0] in "98765432" for f in flops)  # low boards


def test_high_cards_cover_every_height():
    highs = {ranks(f)[0] for f in representative_flops()}
    assert {"A", "K", "Q", "J", "T"} <= highs
    assert any(h in "98765432" for h in highs)


def test_boards_are_not_clustered_on_low_cards():
    flops = representative_flops()
    pairs: dict[tuple[str, str], int] = {}
    for f in flops:
        key = (ranks(f)[1], ranks(f)[2])
        pairs[key] = pairs.get(key, 0) + 1
    assert max(pairs.values()) <= 3
    assert len({ranks(f)[1] for f in flops}) >= 8
