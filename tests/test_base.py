"""Test base class functions."""
import os
import tempfile
from pathlib import Path

import pytest

from wagstails import MondoData


@pytest.fixture(scope="function")
def config_teardown():
    """Make sure environment variables are unset after running `test_config_directory`"""
    yield
    for varname in ("XDG_DATA_DIRS", "XDG_DATA_HOME", "WAGSTAILS_DIR"):
        if varname in os.environ:
            del os.environ[varname]


def test_config_directory(base_data_dir: Path, config_teardown):
    """Basic tests of directory configuration that shouldn't affect non-temporary files."""
    m = MondoData(base_data_dir)
    assert m._data_dir == base_data_dir
    assert m._data_dir.exists() and m._data_dir.is_dir()

    tempdir = Path(tempfile.gettempdir())

    data_dirs_dir = tempdir / "xdg_data_dirs"
    os.environ["XDG_DATA_DIRS"] = str(data_dirs_dir)
    m = MondoData()
    assert m._data_dir == data_dirs_dir / "wagstails" / "mondo"

    data_home_dir = tempdir / "xdg_data_home"
    os.environ["XDG_DATA_HOME"] = str(data_home_dir)
    m = MondoData()
    assert m._data_dir == data_home_dir / "wagstails" / "mondo"

    wags_dir = tempdir / "wagstails_dir"
    os.environ["WAGSTAILS_DIR"] = str(wags_dir)
    m = MondoData()
    assert m._data_dir == wags_dir / "mondo"


@pytest.mark.skipif(
    os.environ.get("WAGSTAILS_TEST_ENV", "").lower() != "true", reason="Not in CI"
)
def test_default_directory_configs():
    """Test default directory in ~/.local/share

    Since this could affects things outside of the immediate code repo, this test
    should mainly run in CI, where we can guarantee a clean user environment.
    """
    m = MondoData()
    assert m._data_dir == Path.home() / ".local" / "share" / "wagstails" / "mondo"
    assert m._data_dir.exists() and m._data_dir.is_dir()

    # test again to ensure it's safe if the directory already exists
    m = MondoData()
    assert m._data_dir == Path.home() / ".local" / "share" / "wagstails" / "mondo"
    assert m._data_dir.exists() and m._data_dir.is_dir()