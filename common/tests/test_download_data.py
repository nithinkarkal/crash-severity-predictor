"""
Tests for download_data
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from common.data.download_data import download_raw_data


@pytest.fixture
def api_response() -> dict:
    return {
        "resources": [
            {"title": "usagers-2021.csv", "url": "https://ex.com/u.csv"},
            {"title": "vehicules-2021.csv", "url": "https://ex.com/v.csv"},
            {"title": "lieux-2021.csv", "url": "https://ex.com/l.csv"},
            {"title": "caracteristiques-2021.csv", "url": "https://ex.com/c.csv"},
            {"title": "usagers-2022.csv", "url": "https://ex.com/u2.csv"},  # wrong year
            {"title": "baac-2021.csv", "url": "https://ex.com/b.csv"},  # baac skip
            {"title": "readme.pdf", "url": "https://ex.com/r.pdf"},  # not csv
        ]
    }


@patch("common.data.download_data.requests.get")
def test_downloads_2021_csvs(mock_get: MagicMock, api_response: dict, tmp_path: Path) -> None:
    api_mock = MagicMock()
    api_mock.status_code = 200
    api_mock.json.return_value = api_response

    file_mock = MagicMock()
    file_mock.iter_content.return_value = [b"data"]
    file_mock.raise_for_status = MagicMock()

    mock_get.side_effect = [api_mock, file_mock, file_mock, file_mock, file_mock]

    out = tmp_path / "raw"
    out.mkdir()

    with patch("common.data.download_data.file_exists", return_value=False):
        result = download_raw_data(year=2021, output_dir=out)

    assert len(result) == 4
    assert all(isinstance(p, Path) for p in result)


@patch("common.data.download_data.requests.get")
def test_skips_existing(mock_get: MagicMock, api_response: dict, tmp_path: Path) -> None:
    api_mock = MagicMock()
    api_mock.status_code = 200
    api_mock.json.return_value = api_response
    mock_get.return_value = api_mock

    out = tmp_path / "raw"
    out.mkdir()
    (out / "usagers-2021.csv").write_text("x")

    with patch("common.data.download_data.file_exists", return_value=True):
        result = download_raw_data(year=2021, output_dir=out, overwrite=False)

    assert len(result) == 4


@patch("common.data.download_data.requests.get")
def test_api_failure(mock_get: MagicMock, tmp_path: Path) -> None:
    resp = MagicMock()
    resp.status_code = 404
    mock_get.return_value = resp

    with pytest.raises(Exception, match="Download dataset failed"):
        download_raw_data(year=2021, output_dir=tmp_path / "raw")


@patch("common.data.download_data.requests.get")
def test_skips_non_csv(mock_get: MagicMock, api_response: dict, tmp_path: Path) -> None:
    api_mock = MagicMock()
    api_mock.status_code = 200
    api_mock.json.return_value = api_response

    file_mock = MagicMock()
    file_mock.iter_content.return_value = [b"data"]
    file_mock.raise_for_status = MagicMock()

    mock_get.side_effect = [api_mock, file_mock, file_mock, file_mock, file_mock]

    out = tmp_path / "raw"
    out.mkdir()

    with patch("common.data.download_data.file_exists", return_value=False):
        result = download_raw_data(year=2021, output_dir=out)

    assert not any("readme" in str(p) for p in result)
    assert not any("baac" in str(p) for p in result)
