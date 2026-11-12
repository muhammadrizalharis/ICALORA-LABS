from app.services.authorship import _fw_similarity, analyze_authorship

_SAME_A = (
    "I honestly don't know what to make of it. We went to the beach and got sunburned, "
    "and then we came home really tired. It was fun though, I think. Maybe we'll go again "
    "next week if the weather holds up. My brother wanted to stay longer but I was done "
    "with the sand getting into everything. Still, you can't beat a day out when the sun "
    "is shining and nobody has to work. I'd do it again in a heartbeat, honestly. We "
    "grabbed ice cream on the way back home and the kids were happy about that."
)
_SAME_B = (
    "So I grabbed my coffee and sat down by the window. The morning was quiet, kind of "
    "peaceful actually. I love these little moments when nothing is going on and I can just "
    "breathe and think about stuff. My cat jumped up on the table and knocked over a pen, "
    "but I didn't even mind. Sometimes you just need to slow down, you know? I've been so "
    "busy lately that I forgot what it feels like to do nothing at all. It was nice. I "
    "think I'll try to do this more often from now on, just for myself."
)
_FORMAL = (
    "This study examines the thermal dynamics of urban environments through remote sensing. "
    "The analysis employs multi-temporal satellite imagery to quantify surface temperature "
    "variation across the metropolitan region. Results demonstrate a significant correlation "
    "between impervious surfaces and elevated heat retention. The findings suggest that "
    "targeted green infrastructure can mitigate the urban heat island effect. These results "
    "have important implications for sustainable urban planning and climate adaptation policy."
)


def test_fw_similarity_bounds():
    assert 0.0 <= _fw_similarity(_SAME_A, _FORMAL) <= 1.0
    assert _fw_similarity(_SAME_A, _SAME_A) == 1.0


def test_fw_similarity_discriminates_register():
    # Burrows's Delta: casual-vs-casual harus lebih mirip daripada casual-vs-formal.
    assert _fw_similarity(_SAME_A, _SAME_B) > _fw_similarity(_SAME_A, _FORMAL)


def test_analyze_authorship_comparison_shape():
    res = analyze_authorship(_SAME_A, _FORMAL)
    comp = res["comparison"]
    for key in ("style_similarity", "function_word_similarity", "structural_similarity",
                "confidence", "verdict"):
        assert key in comp
    assert 0.0 <= comp["style_similarity"] <= 100.0
