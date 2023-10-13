"""Define base data source class."""
import abc
import os
import tempfile
from pathlib import Path
from typing import Callable, Dict, Generator, Optional

import requests
from tqdm import tqdm


class RemoteDataError(Exception):
    """Raise when unable to parse, navigate, or extract information from a remote
    resource, like a data API
    """


class DataSource(abc.ABC):
    """Access tool for a given data source."""

    # required attributes
    _src_name: str

    def __init__(self, data_dir: Optional[Path] = None, silent: bool = True) -> None:
        """Set common class parameters.

        :param data_dir: direct location to store data files in. If not provided, tries
            to find a source-specific subdirectory within the path at environment
            variable $WAGSTAILS_DIR, or within a "wagstails" subdirectory under
            environment variables $XDG_DATA_HOME or $XDG_DATA_DIRS, or finally, at
            ``~/.local/share/``
        :param silent: if True, don't print any info/updates to console
        """
        if not data_dir:
            data_dir = self._get_data_base() / self._src_name
        data_dir.mkdir(exist_ok=True)
        self._data_dir = data_dir
        self._tqdm_params = {
            "unit": "B",
            "ncols": 80,
            "disable": silent,
            "unit_divisor": 1024,
            "unit_scale": True,
        }

    @abc.abstractmethod
    def get_latest(self, from_local: bool = False, force_refresh: bool = False) -> Path:
        """Get path to latest version of data.

        :param from_local: if True, use latest available local file
        :param force_refresh: if True, fetch and return data from remote regardless of
            whether a local copy is present
        :return: Path to location of data
        :raise ValueError: if both ``force_refresh`` and ``from_local`` are True
        """
        raise NotImplementedError

    ### shared utilities

    @staticmethod
    def _get_data_base() -> Path:
        """Get base data storage location.

        By default, conform to `XDG Base Directory Specification <https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html>`_,
        unless a directory is specified otherwise:

        1) check env var ``"WAGSTAILS_DIR"``
        2) check env var ``"XDG_DATA_HOME"``
        3) check env var ``"XDG_DATA_DIRS"`` for a colon-separated list, skipping any
            that can't be used (i.e. they're already a file)
        4) otherwise, use ``~/.local/share/``

        :return: path to base data directory
        """
        spec_wagstails_dir = os.environ.get("WAGSTAILS_DIR")
        if spec_wagstails_dir:
            data_base_dir = Path(spec_wagstails_dir)
        else:
            xdg_data_home = os.environ.get("XDG_DATA_HOME")
            if xdg_data_home:
                data_base_dir = Path(xdg_data_home) / "wagstails"
            else:
                xdg_data_dirs = os.environ.get("XDG_DATA_DIRS")
                if xdg_data_dirs:
                    dirs = os.environ["XDG_DATA_DIRS"].split(":")
                    for dir in dirs:
                        dir_path = Path(dir) / "wagstails"
                        if not dir_path.is_file():
                            data_base_dir = dir_path
                            break
                    else:
                        data_base_dir = Path.home() / ".local" / "share" / "wagstails"
                else:
                    data_base_dir = Path.home() / ".local" / "share" / "wagstails"

        data_base_dir.mkdir(exist_ok=True, parents=True)
        return data_base_dir

    def _http_download(
        self,
        url: str,
        outfile_path: Path,
        headers: Optional[Dict] = None,
        handler: Optional[Callable[[Path, Path], None]] = None,
    ) -> None:
        """Perform HTTP download of remote data file.

        :param url: URL to retrieve file from
        :param outfile_path: path to where file should be saved. Must be an actual
            Path instance rather than merely a pathlike string.
        :param headers: Any needed HTTP headers to include in request
        :param handler: provide if downloaded file requires additional action, e.g.
            it's a zip file.
        """
        if handler:
            dl_path = Path(tempfile.gettempdir()) / "wagstails_tmp"
        else:
            dl_path = outfile_path
        # use stream to avoid saving download completely to memory
        with requests.get(url, stream=True, headers=headers) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            with open(dl_path, "wb") as h:
                if not self._tqdm_params["disable"]:
                    print(f"Downloading {os.path.basename(url)}")
                with tqdm(
                    total=total_size,
                    **self._tqdm_params,
                ) as progress_bar:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            h.write(chunk)
                            progress_bar.update(len(chunk))
        if handler:
            handler(dl_path, outfile_path)

    def _get_latest_local_file(self, glob: str) -> Path:
        """Get most recent locally-available file.

        :param glob: file pattern to match against
        :return: Path to most recent file
        :raise FileNotFoundError: if no local data is available
        """
        files = list(sorted(self._data_dir.glob(glob)))
        if len(files) < 1:
            raise FileNotFoundError(f"No source data found for {self._src_name}")
        return files[-1]


class SpecificVersionDataSource(DataSource):
    """Class for data source which supports retrieval of specific versions, not just
    latest version.

    Useful for sources where the most recent data source sometimes gives us trouble.
    Enables a workflow where we could try the newest version of data, and if it parses
    incorrectly, try the next-most-recent until something works.
    """

    @abc.abstractmethod
    def iterate_versions(self) -> Generator:
        """Lazily get versions (i.e. not the files themselves, just their version
        strings), starting with the most recent value and moving backwards.

        I don't know if every source can feasibly implement this, so I haven't marked
        it as an abstractmethod, but I think it could be useful (e.g. retry with a
        prior version if something fails in the latest version.)

        :return: Generator yielding version strings
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_specific(
        self, version: str, from_local: bool = False, force_refresh: bool = False
    ) -> Path:
        """Get specified version of data.

        Like ``iterate_version()``, probably not necessary to implement for every class.


        :param from_local: if True, use matching local file, don't try to fetch from remote
        :param force_refresh: if True, fetch and return data from remote regardless of
            whether a local copy is present
        :return: Path to location of data
        :raise ValueError: if both ``force_refresh`` and ``from_local`` are True
        """
        raise NotImplementedError


class GitHubDataSource(SpecificVersionDataSource):
    """Class for data sources provided via GitHub releases, where versioning is defined
    by release tag names.

    Defined as a child class of SpecificDataSource because it's fairly straightforward
    to fulfill the required stuff for version iteration and fetching in the context
    of the GitHub release API.
    """

    _repo: str

    def iterate_versions(self) -> Generator:
        """Lazily get versions (i.e. not the files themselves, just their version
        strings), starting with the most recent value and moving backwards.

        :return: Generator yielding version strings
        """
        url = f"https://api.github.com/repos/{self._repo}/releases"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        for release in data:
            yield release["tag_name"]
