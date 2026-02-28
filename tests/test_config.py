from kalshi_cricket_tracker.config import load_config


def test_load_config_handles_empty_yaml(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.trading.mode == "paper"
