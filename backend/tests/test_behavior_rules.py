from behavior_rules import classify_behavior_candidate


def test_classifies_sustained_upward_growth_as_possible_climbing():
    history = [
        (0.0, [100, 200, 140, 280], False),
        (2.0, [105, 140, 155, 250], True),
    ]

    assert classify_behavior_candidate(history) == "possible_climbing"


def test_classifies_slow_motion_near_fence_as_loitering():
    history = [
        (0.0, [100, 200, 140, 280], True),
        (4.0, [104, 202, 144, 282], True),
    ]

    assert classify_behavior_candidate(history) == "loitering_near_fence"
