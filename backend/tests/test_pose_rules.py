from pose_rules import classify_pose_candidate


def test_classifies_tilted_torso_with_rising_ankles_as_possible_climbing():
    history = [
        {5: [40, 30, 0.9], 6: [60, 30, 0.9], 11: [42, 80, 0.9], 12: [62, 80, 0.9], 15: [40, 120, 0.9], 16: [60, 120, 0.9]},
        {5: [55, 25, 0.9], 6: [75, 25, 0.9], 11: [40, 70, 0.9], 12: [60, 70, 0.9], 15: [40, 105, 0.9], 16: [60, 105, 0.9]},
    ]

    assert classify_pose_candidate(history) == "possible_climbing_pose"
