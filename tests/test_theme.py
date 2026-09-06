from ui.theme import COLORS, verdict_for


def test_palette_has_required_tokens():
    for key in ("bg", "surface", "elevated", "border", "text", "text_dim",
                "text_muted", "accent", "accent2", "pos", "neg", "warn"):
        assert key in COLORS
        assert COLORS[key].startswith("#")


def test_verdict_undervalued_above_15pct():
    label, color_key = verdict_for(30.0)
    assert label == "НЕДООЦЕНЕНА"
    assert color_key == "pos"


def test_verdict_fair_within_band():
    assert verdict_for(0.0)[0] == "СПРАВЕДЛИВО"
    assert verdict_for(14.9)[0] == "СПРАВЕДЛИВО"
    assert verdict_for(-14.9)[0] == "СПРАВЕДЛИВО"


def test_verdict_overvalued_below_minus15pct():
    label, color_key = verdict_for(-68.5)
    assert label == "ПЕРЕОЦЕНЕНА"
    assert color_key == "neg"


def test_verdict_boundaries_are_inclusive_outside_band():
    assert verdict_for(15.0)[0] == "НЕДООЦЕНЕНА"
    assert verdict_for(-15.0)[0] == "ПЕРЕОЦЕНЕНА"


def test_verdict_none_when_upside_unknown():
    assert verdict_for(None) is None
