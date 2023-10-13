"""Test Mondo data source."""
import json
from io import TextIOWrapper
from pathlib import Path
from typing import Dict

import pytest
import requests_mock

from wagstails.mondo import MondoData


@pytest.fixture(scope="function")
def mondo_data_dir(base_data_dir: Path):
    """Provide Mondo data directory."""
    dir = base_data_dir / "mondo"
    dir.mkdir(exist_ok=True, parents=True)
    return dir


@pytest.fixture(scope="function")
def mondo(mondo_data_dir: Path):
    """Provide MondoData fixture"""
    return MondoData(mondo_data_dir, silent=True)


@pytest.fixture(scope="module")
def latest_release_response(fixture_dir):
    """Provide JSON response to latest release API endpoint"""
    with open(fixture_dir / "mondo_release_latest.json", "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def august_release_response(fixture_dir):
    """Provide JSON response for older release API endpoint."""
    with open(fixture_dir / "mondo_release_v2023-08-02.json", "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def versions_response(fixture_dir):
    """Provide JSON response to releases API endpoint"""
    with open(fixture_dir / "mondo_releases.json", "r") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def mondo_file(fixture_dir):
    """Provide mock mondo.owl file."""
    with open(fixture_dir / "mondo.owl", "r") as f:
        return f


def test_get_latest(
    mondo: MondoData,
    mondo_data_dir,
    latest_release_response: Dict,
    mondo_file: TextIOWrapper,
):
    """Test MondoData.get_latest()"""
    with pytest.raises(ValueError):
        mondo.get_latest(from_local=True, force_refresh=True)

    with pytest.raises(FileNotFoundError):
        mondo.get_latest(from_local=True)

    with requests_mock.Mocker() as m:
        m.get(
            "https://api.github.com/repos/monarch-initiative/mondo/releases/latest",
            json=latest_release_response,
        )
        m.get(
            "https://github.com/monarch-initiative/mondo/releases/download/v2023-09-12/mondo.owl",
            body=mondo_file,
        )
        response = mondo.get_latest()
        assert response == mondo_data_dir / "mondo_v2023-09-12.owl"
        assert response.exists()

        response = mondo.get_latest()
        assert response == mondo_data_dir / "mondo_v2023-09-12.owl"
        assert response.exists()
        assert m.call_count == 3

        response = mondo.get_latest(from_local=True)
        assert response == mondo_data_dir / "mondo_v2023-09-12.owl"
        assert response.exists()
        assert m.call_count == 3

        (mondo_data_dir / "mondo_v2023-08-02.owl").touch()
        response = mondo.get_latest(from_local=True)
        assert response == mondo_data_dir / "mondo_v2023-09-12.owl"
        assert response.exists()
        assert m.call_count == 3

        response = mondo.get_latest(force_refresh=True)
        assert response == mondo_data_dir / "mondo_v2023-09-12.owl"
        assert response.exists()
        assert m.call_count == 5


def test_iterate_versions(mondo: MondoData, versions_response: Dict):
    """Test MondoData.iterate_versions()"""
    with requests_mock.Mocker() as m:
        m.get(
            "https://api.github.com/repos/monarch-initiative/mondo/releases",
            json=versions_response,
        )
        versions = mondo.iterate_versions()
        assert list(versions) == [
            "v2023-09-12",
            "v2023-08-02",
            "v2022-11-01",
            "v2021-08-03",
        ]


def test_get_specific_version(
    mondo: MondoData,
    mondo_data_dir: Path,
    mondo_file: TextIOWrapper,
):
    """Test MondoData.get_specific()"""
    with pytest.raises(ValueError):
        mondo.get_specific("v2023-09-12", from_local=True, force_refresh=True)

    with pytest.raises(FileNotFoundError):
        mondo.get_specific("v2023-09-12", from_local=True)

    with requests_mock.Mocker() as m:
        m.get(
            "https://github.com/monarch-initiative/mondo/releases/download/v2023-08-02/mondo.owl",
            body=mondo_file,
        )
        response = mondo.get_specific("v2023-08-02")
        assert response == mondo_data_dir / "mondo_v2023-08-02.owl"
        assert response.exists()
        assert m.call_count == 1

        response = mondo.get_specific("v2023-08-02")
        assert response == mondo_data_dir / "mondo_v2023-08-02.owl"
        assert response.exists()
        assert m.call_count == 1

        response = mondo.get_specific("v2023-08-02", from_local=True)
        assert response == mondo_data_dir / "mondo_v2023-08-02.owl"
        assert response.exists()
        assert m.call_count == 1

        response = mondo.get_specific("v2023-08-02", force_refresh=True)
        assert response == mondo_data_dir / "mondo_v2023-08-02.owl"
        assert response.exists()
        assert m.call_count == 2

        with pytest.raises(FileNotFoundError):
            response = mondo.get_specific("v2023-09-12", from_local=True)

        m.get(
            "https://github.com/monarch-initiative/mondo/releases/download/v2023-09-12/mondo.owl",
            body=mondo_file,
        )
        response = mondo.get_specific("v2023-09-12")
        assert response == mondo_data_dir / "mondo_v2023-09-12.owl"
        assert response.exists()
        assert m.call_count == 3

        response = mondo.get_specific("v2023-08-02")
        assert response == mondo_data_dir / "mondo_v2023-08-02.owl"
        assert response.exists()
        assert m.call_count == 3