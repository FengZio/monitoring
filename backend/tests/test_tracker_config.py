from pathlib import Path

import yaml


def test_botsort_reid_config_enables_appearance_matching():
    config_path = Path(__file__).resolve().parents[1] / "botsort_reid.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert config["tracker_type"] == "botsort"
    assert config["with_reid"] is True
    assert config["track_buffer"] == 90
