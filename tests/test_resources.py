import os
from pathlib import Path

import pytest

from objecttwin import resources


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (resources.MODEL_ENV_VAR, "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        monkeypatch.setenv(var, "")  # records the original state so it is restored afterwards
        monkeypatch.delenv(var)


def test_env_var_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(resources.MODEL_ENV_VAR, "facebook/dinov2-small")
    assert resources.resolve_model_source() == "facebook/dinov2-small"


def test_bundled_folder_is_used_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "models" / resources.MODEL_DIR_NAME
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}")
    monkeypatch.setattr(resources, "bundle_root", lambda: tmp_path)

    assert resources.resolve_model_source() == str(model_dir)
    assert os.environ["HF_HUB_OFFLINE"] == "1"


def test_falls_back_to_hub_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(resources, "bundle_root", lambda: tmp_path)
    assert resources.resolve_model_source() == resources.MODEL_ID


def test_frozen_bundle_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)
    assert resources.is_frozen()
    assert resources.bundle_root() == tmp_path


def test_icon_assets_exist() -> None:
    assert resources.asset_path("objecttwin.png").is_file()
    assert resources.asset_path("objecttwin.ico").is_file()
