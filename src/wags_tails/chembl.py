"""Provide source fetching for ChEMBL."""
import fnmatch
import re
import tarfile
from pathlib import Path

import requests

from .base_source import DataSource, RemoteDataError
from .utils.downloads import download_http


class ChemblData(DataSource):
    """Provide access to ChEMBL database."""

    _src_name = "chembl"
    _filetype = "db"

    @staticmethod
    def _get_latest_version() -> str:
        """Retrieve latest version value

        :return: latest release value
        :raise RemoteDataError: if unable to parse version number from README
        """
        latest_readme_url = (
            "https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/README"
        )
        response = requests.get(latest_readme_url)
        response.raise_for_status()
        data = response.text
        pattern = re.compile(r"\*\s*Release:\s*chembl_(\d*).*")
        for line in data.splitlines():
            m = re.match(pattern, line)
            if m and m.group():
                version = m.group(1)
                return version
        else:
            raise RemoteDataError(
                "Unable to parse latest ChEMBL version number from latest release README"
            )

    def _tarball_handler(self, dl_path: Path, outfile_path: Path) -> None:
        """Get ChEMBL file from tarball. Callback to pass to download methods.

        :param dl_path: path to temp data file
        :param outfile_path: path to save file within
        """
        with tarfile.open(dl_path, "r:gz") as tar:
            for file in tar.getmembers():
                if fnmatch.fnmatch(file.name, self._glob):
                    file.name = outfile_path.name
                    tar.extract(file, path=outfile_path.parent)

    def _download_data(self, version: str, outfile: Path) -> None:
        """Download data file to specified location.

        :param version: version to acquire
        :param outfile: location and filename for final data file
        """
        download_http(
            f"https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/chembl_{version}_sqlite.tar.gz",
            outfile,
            handler=self._tarball_handler,
            tqdm_params=self._tqdm_params,
        )
