"""Regression tests for Veyr Forge's archive extraction boundaries.

Run from the repository root:
    python3 -m unittest discover -s tests -p 'test_forge_security.py' -v

These tests use small synthetic tar archives and never download or build Linux.
"""

from __future__ import annotations

import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

# Import Forge directly without installing any Python package or dependencies.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "forge"))

from forge import Forge, ForgeError, ROOT  # noqa: E402


class ArchiveMemberValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        # These methods don't need the Forge constructor or host build tools.
        self.forge = object.__new__(Forge)
        self.archive = Path("synthetic.tar")

    def assert_member_rejected(self, member: tarfile.TarInfo) -> None:
        with self.assertRaises(ForgeError):
            self.forge._validate_archive_member(self.archive, member)

    def test_archive_paths_cannot_escape_or_be_absolute(self) -> None:
        self.assertIsNone(Forge._normalise_archive_path("../escape"))
        self.assertIsNone(Forge._normalise_archive_path("/etc/passwd"))
        self.assertIsNone(Forge._normalise_archive_path("name\x00bad"))
        self.assertEqual(
            ("safe", "file.txt"),
            Forge._normalise_archive_path("safe/./file.txt"),
        )

    def test_member_path_traversal_is_rejected(self) -> None:
        self.assert_member_rejected(tarfile.TarInfo("../../escape.txt"))

    def test_absolute_member_path_is_rejected(self) -> None:
        self.assert_member_rejected(tarfile.TarInfo("/etc/passwd"))

    def test_escaping_symlink_is_rejected(self) -> None:
        member = tarfile.TarInfo("safe/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../escape"
        self.assert_member_rejected(member)

    def test_escaping_hardlink_is_rejected(self) -> None:
        member = tarfile.TarInfo("safe/link")
        member.type = tarfile.LNKTYPE
        member.linkname = "../escape"
        self.assert_member_rejected(member)

    def test_special_device_is_rejected(self) -> None:
        member = tarfile.TarInfo("device")
        member.type = tarfile.CHRTYPE
        self.assert_member_rejected(member)


class ArchiveExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.forge = object.__new__(Forge)
        (ROOT / "build").mkdir(exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(
            prefix="veyr-security-test-", dir=ROOT / "build"
        )
        self.addCleanup(self.temp_dir.cleanup)
        self.workspace = Path(self.temp_dir.name)

    @staticmethod
    def write_single_file_archive(archive: Path, name: str, data: bytes) -> None:
        with tarfile.open(archive, mode="w") as tar:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))

    def test_valid_synthetic_archive_extracts(self) -> None:
        archive = self.workspace / "valid.tar"
        dest = self.workspace / "extracted"
        self.write_single_file_archive(archive, "safe.txt", b"veyr")
        result = self.forge._safe_extract(archive, dest)
        self.assertEqual((result / "safe.txt").read_bytes(), b"veyr")

    def test_path_traversal_archive_is_refused(self) -> None:
        archive = self.workspace / "traversal.tar"
        dest = self.workspace / "extracted"
        self.write_single_file_archive(archive, "../escape.txt", b"unsafe")
        with self.assertRaises(ForgeError):
            self.forge._safe_extract(archive, dest)
        self.assertFalse((self.workspace / "escape.txt").exists())


if __name__ == "__main__":
    unittest.main()
