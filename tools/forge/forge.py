#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Veyr Forge requires Python 3.11 or newer (tomllib is missing)."
    ) from exc


ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "config" / "forge.toml"
VERSION_FILE = ROOT / "VERSION"
BUILD_FINGERPRINT_SCHEMA = "veyr-forge-build-v2"
CHROOT_PROTOCOL = "veyr-chroot-v1"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ForgeError(RuntimeError):
    pass


def blue(text: str) -> str:
    return f"\033[1;34m{text}\033[0m"


def green(text: str) -> str:
    return f"\033[1;32m{text}\033[0m"


def yellow(text: str) -> str:
    return f"\033[1;33m{text}\033[0m"


def red(text: str) -> str:
    return f"\033[1;31m{text}\033[0m"


def log(message: str) -> None:
    print(f"\n{blue('[FORGE]')} {message}")


def ok(message: str) -> None:
    print(f"{green('[OK]')} {message}")


def warn(message: str) -> None:
    print(f"{yellow('[WARN]')} {message}")


def fail(message: str) -> None:
    raise ForgeError(message)


def load_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"TOML file not found: {path.relative_to(ROOT)}")

    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        fail(f"Invalid TOML in {path.relative_to(ROOT)}: {exc}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def hash_bytes(*parts: bytes) -> str:
    digest = hashlib.sha256()

    for part in parts:
        digest.update(part)

    return digest.hexdigest()


def ensure_within_root(path: Path) -> Path:
    resolved = path.resolve()

    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        fail(f"Refusing to operate outside the Veyr repository: {resolved}")

    return resolved


def ensure_output_within_root(path: Path) -> Path:
    """Validate an output path without collapsing its final symlink.

    Package outputs may legitimately be symlinks (for example /usr/bin/sh -> bash).
    Using Path.resolve() for the stored output path would make distinct declared
    outputs compare equal and would also stop Forge from verifying the symlink
    itself.  Normalize the path lexically, validate its real parent, and keep the
    final path component intact.
    """
    root = ROOT.resolve()
    normalized = Path(os.path.abspath(os.fspath(path)))

    try:
        normalized.relative_to(root)
    except ValueError:
        fail(f"Refusing output outside the Veyr repository: {normalized}")

    parent_resolved = normalized.parent.resolve()
    try:
        parent_resolved.relative_to(root)
    except ValueError:
        fail(
            "Refusing output through a parent symlink outside the Veyr "
            f"repository: {normalized}"
        )

    if normalized.is_symlink():
        target_resolved = normalized.resolve(strict=False)
        try:
            target_resolved.relative_to(root)
        except ValueError:
            fail(
                "Refusing output symlink that points outside the Veyr "
                f"repository: {normalized} -> {target_resolved}"
            )

    return normalized


def remove_tree_contents(path: Path) -> None:
    path = ensure_within_root(path)

    if path.exists():
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    category: str
    description: str

    dependencies: tuple[str, ...]
    required_commands: tuple[str, ...]
    outputs: tuple[Path, ...]

    source_urls: tuple[str, ...]
    source_archive: str
    source_sha256: str

    build_script: Path
    build_environment: str
    manifest: Path


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    status: str
    description: str

    parent: str
    packages: tuple[str, ...]

    prepare_steps: tuple[Path, ...]
    chroot_root: Path | None

    image_steps: tuple[Path, ...]
    run_script: Path | None

    manifest: Path


class Forge:
    def __init__(self) -> None:
        self.config = load_toml(CONFIG_FILE)
        self.version = VERSION_FILE.read_text(encoding="utf-8").strip()

        project = self.config.get("project", {})
        paths = self.config.get("paths", {})

        self.arch = str(project.get("architecture", "x86_64"))
        self.min_python = str(project.get("min_python", "3.11"))

        self.packages_dir = ensure_within_root(
            ROOT / str(paths.get("packages", "packages"))
        )
        self.profiles_dir = ensure_within_root(
            ROOT / str(paths.get("profiles", "profiles"))
        )
        self.sources_dir = ensure_within_root(
            ROOT / str(paths.get("sources", "sources/distfiles"))
        )
        self.build_dir = ensure_within_root(
            ROOT / str(paths.get("build", "build"))
        )
        self.out_dir = ensure_within_root(
            ROOT / str(paths.get("out", "out"))
        )
        self.state_dir = self.build_dir / "state" / "packages"

        for directory in (
            self.packages_dir,
            self.profiles_dir,
            self.sources_dir,
            self.build_dir,
            self.out_dir,
            self.state_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.packages = self._load_packages()
        self.profiles = self._load_profiles()
        self._validate_references()

    def _load_packages(self) -> dict[str, Package]:
        packages: dict[str, Package] = {}

        for manifest in sorted(self.packages_dir.rglob("package.toml")):
            data = load_toml(manifest)
            package_data = data.get("package", {})
            source_data = data.get("source", {})
            build_data = data.get("build", {})

            name = str(package_data.get("name", "")).strip()
            if not name:
                fail(f"Package name is missing in {manifest.relative_to(ROOT)}")
            if name in packages:
                fail(f"Duplicate package name: {name}")

            script_name = str(build_data.get("script", "build.sh"))
            build_script = ensure_within_root(manifest.parent / script_name)
            if not build_script.is_file():
                fail(
                    f"Build script not found for package {name}: "
                    f"{build_script.relative_to(ROOT)}"
                )

            build_environment = str(
                build_data.get("environment", "host")
            ).strip().lower()

            if build_environment not in {"host", "chroot"}:
                fail(
                    f"Package {name} has unsupported build environment: "
                    f"{build_environment}"
                )

            outputs = tuple(
                ensure_output_within_root(ROOT / str(item))
                for item in package_data.get("outputs", [])
            )

            packages[name] = Package(
                name=name,
                version=str(package_data.get("version", "")),
                category=str(package_data.get("category", "core")),
                description=str(package_data.get("description", "")),
                dependencies=tuple(
                    str(item) for item in package_data.get("dependencies", [])
                ),
                required_commands=tuple(
                    str(item)
                    for item in package_data.get("required_commands", [])
                ),
                outputs=outputs,
                source_urls=tuple(
                    str(item)
                    for item in (
                        source_data.get("urls")
                        or [source_data.get("url", "")]
                    )
                    if str(item).strip()
                ),
                source_archive=str(source_data.get("archive", "")),
                source_sha256=str(source_data.get("sha256", "")),
                build_script=build_script,
                build_environment=build_environment,
                manifest=manifest,
            )

        return packages

    def _load_profiles(self) -> dict[str, Profile]:
        profiles: dict[str, Profile] = {}

        for manifest in sorted(self.profiles_dir.rglob("profile.toml")):
            data = load_toml(manifest)
            profile_data = data.get("profile", {})
            prepare_data = data.get("prepare", {})
            chroot_data = data.get("chroot", {})
            image_data = data.get("image", {})

            profile_id = str(profile_data.get("id", "")).strip()
            if not profile_id:
                fail(f"Profile id is missing in {manifest.relative_to(ROOT)}")
            if profile_id in profiles:
                fail(f"Duplicate profile id: {profile_id}")

            run_value = str(image_data.get("run", "")).strip()
            run_script = (
                ensure_within_root(ROOT / run_value) if run_value else None
            )

            chroot_value = str(chroot_data.get("root", "")).strip()
            chroot_root = (
                ensure_within_root(ROOT / chroot_value) if chroot_value else None
            )

            profiles[profile_id] = Profile(
                id=profile_id,
                name=str(profile_data.get("name", profile_id)),
                status=str(profile_data.get("status", "planned")),
                description=str(profile_data.get("description", "")),
                parent=str(profile_data.get("parent", "")).strip(),
                packages=tuple(
                    str(item) for item in profile_data.get("packages", [])
                ),
                prepare_steps=tuple(
                    ensure_within_root(ROOT / str(item))
                    for item in prepare_data.get("steps", [])
                ),
                chroot_root=chroot_root,
                image_steps=tuple(
                    ensure_within_root(ROOT / str(item))
                    for item in image_data.get("steps", [])
                ),
                run_script=run_script,
                manifest=manifest,
            )

        return profiles

    def _validate_references(self) -> None:
        if not self.version:
            fail("VERSION is empty")

        archive_hashes: dict[str, str] = {}

        for package in self.packages.values():
            if not package.source_urls:
                fail(f"Package {package.name} has no source URL")

            archive_name = PurePosixPath(package.source_archive)
            if (
                not package.source_archive
                or archive_name.is_absolute()
                or len(archive_name.parts) != 1
                or archive_name.name in {"", ".", ".."}
            ):
                fail(
                    f"Package {package.name} has unsafe source archive name: "
                    f"{package.source_archive!r}"
                )

            if not SHA256_PATTERN.fullmatch(package.source_sha256):
                fail(
                    f"Package {package.name} has invalid source SHA256; "
                    "expected 64 lowercase hexadecimal characters"
                )

            previous_hash = archive_hashes.get(package.source_archive)
            if previous_hash and previous_hash != package.source_sha256:
                fail(
                    f"Source archive name collision with different SHA256: "
                    f"{package.source_archive}"
                )
            archive_hashes[package.source_archive] = package.source_sha256

            if not package.outputs:
                fail(f"Package {package.name} declares no outputs")

            if len(set(package.outputs)) != len(package.outputs):
                fail(f"Package {package.name} declares duplicate outputs")

            if not os.access(package.build_script, os.X_OK):
                fail(
                    f"Build script is not executable for package {package.name}: "
                    f"{package.build_script.relative_to(ROOT)}"
                )

            for dependency in package.dependencies:
                if dependency not in self.packages:
                    fail(
                        f"Package {package.name} depends on unknown package "
                        f"{dependency}"
                    )

        for profile in self.profiles.values():
            if profile.status not in {"active", "planned"}:
                fail(
                    f"Profile {profile.id} has unsupported status: "
                    f"{profile.status}"
                )

            if profile.parent and profile.parent not in self.profiles:
                fail(
                    f"Profile {profile.id} has unknown parent {profile.parent}"
                )

            if len(set(profile.packages)) != len(profile.packages):
                fail(f"Profile {profile.id} declares duplicate packages")

            for package_name in profile.packages:
                if package_name not in self.packages:
                    fail(
                        f"Profile {profile.id} references unknown package "
                        f"{package_name}"
                    )

            for step in (*profile.prepare_steps, *profile.image_steps):
                if not step.is_file():
                    fail(
                        f"Profile step not found for {profile.id}: "
                        f"{step.relative_to(ROOT)}"
                    )
                if not os.access(step, os.X_OK):
                    fail(
                        f"Profile step is not executable for {profile.id}: "
                        f"{step.relative_to(ROOT)}"
                    )

            if profile.run_script:
                if not profile.run_script.is_file():
                    fail(
                        f"Run script not found for profile {profile.id}: "
                        f"{profile.run_script.relative_to(ROOT)}"
                    )
                if not os.access(profile.run_script, os.X_OK):
                    fail(
                        f"Run script is not executable for profile {profile.id}: "
                        f"{profile.run_script.relative_to(ROOT)}"
                    )

    def package(self, name: str) -> Package:
        try:
            return self.packages[name]
        except KeyError:
            fail(f"Unknown package: {name}")

    def profile(self, profile_id: str) -> Profile:
        try:
            return self.profiles[profile_id]
        except KeyError:
            fail(f"Unknown profile: {profile_id}")

    def profile_chain(self, profile_id: str) -> list[Profile]:
        result: list[Profile] = []
        visiting: set[str] = set()

        def visit(current_id: str) -> None:
            if current_id in visiting:
                fail(f"Profile inheritance cycle detected at: {current_id}")

            visiting.add(current_id)
            profile = self.profile(current_id)

            if profile.parent:
                visit(profile.parent)

            result.append(profile)
            visiting.remove(current_id)

        visit(profile_id)
        return result

    def profile_packages(self, profile_id: str) -> list[str]:
        result: list[str] = []

        for profile in self.profile_chain(profile_id):
            for package_name in profile.packages:
                if package_name not in result:
                    result.append(package_name)

        return result

    def profile_prepare_steps(self, profile_id: str) -> list[Path]:
        result: list[Path] = []

        for profile in self.profile_chain(profile_id):
            for step in profile.prepare_steps:
                if step not in result:
                    result.append(step)

        return result

    def profile_chroot_root(self, profile_id: str) -> Path | None:
        resolved: Path | None = None

        for profile in self.profile_chain(profile_id):
            if profile.chroot_root is not None:
                resolved = profile.chroot_root

        return resolved

    def build_order(self, package_names: Iterable[str]) -> list[str]:
        order: list[str] = []
        temporary: set[str] = set()
        permanent: set[str] = set()

        def visit(name: str) -> None:
            if name in permanent:
                return
            if name in temporary:
                fail(f"Package dependency cycle detected at: {name}")

            package = self.package(name)
            temporary.add(name)

            for dependency in package.dependencies:
                visit(dependency)

            temporary.remove(name)
            permanent.add(name)
            order.append(name)

        for package_name in package_names:
            visit(package_name)

        return order

    def _validate_profile_build_stage(self, profile_id: str) -> None:
        order = self.build_order(self.profile_packages(profile_id))
        entered_chroot_stage = False
        has_chroot_packages = False

        for package_name in order:
            package = self.package(package_name)
            if package.build_environment == "chroot":
                entered_chroot_stage = True
                has_chroot_packages = True
            elif entered_chroot_stage:
                fail(
                    f"Invalid build graph for {profile_id}: host package "
                    f"{package.name} appears after the chroot stage began"
                )

        if has_chroot_packages:
            if not self.profile_prepare_steps(profile_id):
                fail(
                    f"Profile {profile_id} contains chroot packages but has "
                    "no prepare steps"
                )
            if self.profile_chroot_root(profile_id) is None:
                fail(
                    f"Profile {profile_id} contains chroot packages but has "
                    "no configured chroot root"
                )

    def _shell_check_files(self) -> list[Path]:
        candidates: set[Path] = {ROOT / "veyr"}
        candidates.update(self.packages[name].build_script for name in self.packages)

        for directory in (ROOT / "scripts", ROOT / "tests"):
            if directory.is_dir():
                candidates.update(directory.rglob("*.sh"))

        initramfs_dir = ROOT / "initramfs"
        if initramfs_dir.is_dir():
            for path in initramfs_dir.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    first_line = path.open(
                        "r", encoding="utf-8", errors="ignore"
                    ).readline()
                except OSError:
                    continue
                if first_line.startswith("#!") and (
                    "sh" in first_line or "bash" in first_line
                ):
                    candidates.add(path)

        return sorted(path for path in candidates if path.is_file())

    def check(self) -> int:
        print(f"Veyr Forge consistency check for Veyr {self.version}")
        print(f"Repository: {ROOT}")

        failures: list[str] = []

        def run_check(label: str, callback: Any) -> None:
            try:
                detail = callback()
            except Exception as exc:  # keep checking independent sections
                failures.append(f"{label}: {exc}")
                print(f"{red('[FAIL]')} {label}: {exc}")
                return

            suffix = f": {detail}" if detail else ""
            print(f"{green('[OK]')} {label}{suffix}")

        def check_project_metadata() -> str:
            project = self.config.get("project", {})
            format_value = project.get("format")
            if not isinstance(format_value, int) or format_value < 1:
                fail("config/forge.toml project.format must be a positive integer")
            if not self.arch.strip():
                fail("project architecture is empty")
            return f"format={format_value}, arch={self.arch}"

        def check_toml_manifests() -> str:
            manifests = [
                CONFIG_FILE,
                *(package.manifest for package in self.packages.values()),
                *(profile.manifest for profile in self.profiles.values()),
            ]
            for manifest in manifests:
                load_toml(manifest)
            return f"{len(manifests)} files"

        def check_references() -> str:
            self._validate_references()
            return (
                f"{len(self.packages)} packages, "
                f"{len(self.profiles)} profiles"
            )

        def check_package_graph() -> str:
            order = self.build_order(self.packages.keys())
            return f"{len(order)} packages, no dependency cycles"

        def check_profile_graphs() -> str:
            for profile_id in self.profiles:
                self.profile_chain(profile_id)
                self._validate_profile_build_stage(profile_id)
            return f"{len(self.profiles)} profiles"

        def check_shell_syntax() -> str:
            shell_files = self._shell_check_files()
            for path in shell_files:
                result = subprocess.run(
                    ["bash", "-n", str(path)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    error = result.stderr.strip() or "bash -n failed"
                    fail(f"{path.relative_to(ROOT)}: {error}")
            return f"{len(shell_files)} scripts"

        def check_python_syntax() -> str:
            python_files = sorted((ROOT / "tools").rglob("*.py"))
            for path in python_files:
                source = path.read_text(encoding="utf-8")
                compile(source, str(path.relative_to(ROOT)), "exec")
            return f"{len(python_files)} files"

        def check_secure_tar_support() -> str:
            if not hasattr(tarfile, "data_filter"):
                fail(
                    "host Python lacks tarfile.data_filter; secure source "
                    "extraction is unavailable"
                )
            return "tarfile data filter available"

        run_check("Project metadata", check_project_metadata)
        run_check("TOML manifests", check_toml_manifests)
        run_check("Manifest references and paths", check_references)
        run_check("Package dependency graph", check_package_graph)
        run_check("Profile inheritance/build graphs", check_profile_graphs)
        run_check("Shell syntax", check_shell_syntax)
        run_check("Python syntax", check_python_syntax)
        run_check("Secure tar extraction support", check_secure_tar_support)

        if failures:
            print()
            print(red(f"Forge consistency check failed ({len(failures)} section(s))"))
            return 1

        print()
        ok("Forge consistency check passed")
        return 0

    def doctor(self) -> int:
        print(f"Veyr Forge for Veyr {self.version}")
        print(f"Repository: {ROOT}")
        print(f"Architecture: {self.arch}")
        print(f"Python: {sys.version.split()[0]}")

        expected = tuple(
            int(part) for part in self.min_python.split(".")[:2]
        )

        if sys.version_info[:2] < expected:
            print(red(f"[FAIL] Python {self.min_python}+ is required"))
            return 1

        ok(f"Python {self.min_python}+ available")

        commands = list(
            self.config.get("host", {}).get("required_commands", [])
        )

        for package in self.packages.values():
            if package.build_environment == "host":
                commands.extend(package.required_commands)

        missing: list[str] = []

        for command in sorted(set(str(item) for item in commands)):
            if shutil.which(command):
                print(f"  {green('✓')} {command}")
            else:
                print(f"  {red('✗')} {command}")
                missing.append(command)

        if missing:
            warn("Missing host commands: " + ", ".join(missing))
            print("Run: make deps")
            return 1

        ok("Host build environment looks ready")
        return 0

    def list_packages(self) -> None:
        print(f"Packages ({len(self.packages)}):")

        for package in sorted(
            self.packages.values(),
            key=lambda item: (item.category, item.name),
        ):
            print(
                f"  {package.name:<20} {package.version:<12} "
                f"[{package.category}/{package.build_environment}]  "
                f"{package.description}"
            )

    def list_profiles(self) -> None:
        print(f"Profiles ({len(self.profiles)}):")

        for profile in sorted(self.profiles.values(), key=lambda item: item.id):
            parent = f", parent={profile.parent}" if profile.parent else ""
            print(
                f"  {profile.id:<18} [{profile.status}] "
                f"{profile.name}{parent}"
            )
            if profile.description:
                print(f"                     {profile.description}")

    def info_package(self, name: str) -> None:
        package = self.package(name)

        print(f"Package:      {package.name}")
        print(f"Version:      {package.version}")
        print(f"Category:     {package.category}")
        print(f"Environment:  {package.build_environment}")
        print(f"Description:  {package.description}")
        print(f"Manifest:     {package.manifest.relative_to(ROOT)}")
        print("Sources:")
        for source_url in package.source_urls:
            print(f"  - {source_url}")
        print(f"Archive:      {package.source_archive}")
        print(f"SHA256:       {package.source_sha256}")
        print(
            "Dependencies: "
            + (", ".join(package.dependencies) if package.dependencies else "(none)")
        )
        print("Outputs:")
        for output in package.outputs:
            print(f"  - {output.relative_to(ROOT)}")

    def info_profile(self, profile_id: str) -> None:
        profile = self.profile(profile_id)
        print(f"Profile:      {profile.id}")
        print(f"Name:         {profile.name}")
        print(f"Status:       {profile.status}")
        print(f"Parent:       {profile.parent or '(none)'}")
        print(f"Description:  {profile.description}")
        print(f"Manifest:     {profile.manifest.relative_to(ROOT)}")

        packages = self.profile_packages(profile_id)
        print("Packages:     " + (", ".join(packages) if packages else "(none)"))

        prepare_steps = self.profile_prepare_steps(profile_id)
        if prepare_steps:
            print("Prepare steps:")
            for step in prepare_steps:
                print(f"  - {step.relative_to(ROOT)}")

        chroot_root = self.profile_chroot_root(profile_id)
        if chroot_root is not None:
            print(f"Chroot root:  {chroot_root.relative_to(ROOT)}")

        if profile.image_steps:
            print("Image steps:")
            for step in profile.image_steps:
                print(f"  - {step.relative_to(ROOT)}")

    def graph(self, profile_id: str) -> None:
        package_names = self.profile_packages(profile_id)
        order = self.build_order(package_names)

        print(f"Build graph for profile '{profile_id}':")
        if not order:
            print("  (no packages yet)")
            return

        for index, name in enumerate(order, start=1):
            package = self.package(name)
            deps = ", ".join(package.dependencies) if package.dependencies else "none"
            print(
                f"  {index:>2}. {name} {package.version}  "
                f"env: {package.build_environment}  deps: {deps}"
            )

    def _source_path(self, package: Package) -> Path:
        return self.sources_dir / package.source_archive

    def fetch_package(self, name: str) -> Path:
        package = self.package(name)
        destination = self._source_path(package)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.is_file():
            actual = sha256_file(destination)
            if actual == package.source_sha256:
                ok(f"{package.name} source already verified")
                return destination

            warn(
                f"Checksum mismatch for cached {destination.name}; "
                "downloading again"
            )
            destination.unlink()

        log(f"Downloading {package.name} {package.version}")
        temporary = destination.with_suffix(destination.suffix + ".part")
        errors: list[str] = []

        for index, source_url in enumerate(package.source_urls, start=1):
            temporary.unlink(missing_ok=True)

            if len(package.source_urls) > 1:
                print(
                    f"  mirror {index}/{len(package.source_urls)}: {source_url}"
                )

            request = urllib.request.Request(
                source_url,
                headers={"User-Agent": f"Veyr-Forge/{self.version}"},
            )

            try:
                with (
                    urllib.request.urlopen(request, timeout=60) as response,
                    temporary.open("wb") as output,
                ):
                    shutil.copyfileobj(response, output)
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                errors.append(f"{source_url}: {exc}")
                warn(f"Download failed from {source_url}: {exc}")
                continue

            actual = sha256_file(temporary)
            if actual != package.source_sha256:
                errors.append(
                    f"{source_url}: SHA256 mismatch (got {actual})"
                )
                warn(f"SHA256 mismatch from {source_url}")
                temporary.unlink(missing_ok=True)
                continue

            temporary.replace(destination)
            ok(f"Downloaded and verified {package.source_archive}")
            return destination

        rendered = "\n".join(f"  - {item}" for item in errors)
        fail(
            f"Unable to obtain a verified source for {package.name}.\n"
            f"Expected SHA256: {package.source_sha256}\n"
            f"Attempts:\n{rendered}"
        )

    def fetch_packages(self, package_names: Iterable[str]) -> None:
        for package_name in self.build_order(package_names):
            self.fetch_package(package_name)

    @staticmethod
    def _normalise_archive_path(
        value: str,
        base: tuple[str, ...] = (),
    ) -> tuple[str, ...] | None:
        if "\x00" in value:
            return None

        path = PurePosixPath(value)
        if path.is_absolute():
            return None

        parts = list(base)
        for part in path.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    return None
                parts.pop()
                continue
            parts.append(part)

        return tuple(parts)

    def _validate_archive_member(
        self,
        archive: Path,
        member: tarfile.TarInfo,
    ) -> None:
        member_parts = self._normalise_archive_path(member.name)
        if member_parts is None:
            fail(
                f"Unsafe path in archive {archive.name}: {member.name!r}"
            )

        if member.ischr() or member.isblk() or member.isfifo():
            fail(
                f"Refusing special file in archive {archive.name}: "
                f"{member.name!r}"
            )

        if member.issym():
            target_parts = self._normalise_archive_path(
                member.linkname,
                member_parts[:-1],
            )
            if target_parts is None:
                fail(
                    f"Unsafe symlink in archive {archive.name}: "
                    f"{member.name!r} -> {member.linkname!r}"
                )

        if member.islnk():
            target_parts = self._normalise_archive_path(member.linkname)
            if target_parts is None:
                fail(
                    f"Unsafe hardlink in archive {archive.name}: "
                    f"{member.name!r} -> {member.linkname!r}"
                )

    def _safe_extract(self, archive: Path, destination: Path) -> Path:
        remove_tree_contents(destination)

        if not hasattr(tarfile, "data_filter"):
            fail(
                "Python tarfile secure extraction filters are unavailable. "
                "Update the host Python 3.11+ installation before building Veyr."
            )

        try:
            with tarfile.open(archive, mode="r:*") as tar:
                members = tar.getmembers()
                for member in members:
                    self._validate_archive_member(archive, member)

                tar.extractall(destination, members=members, filter="data")
        except ForgeError:
            raise
        except (tarfile.TarError, OSError, ValueError) as exc:
            remove_tree_contents(destination)
            fail(f"Unable to safely extract {archive.name}: {exc}")

        entries = list(destination.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]

        return destination

    def _dependency_fingerprints(self, package: Package) -> bytes:
        data: list[str] = []

        for dependency_name in package.dependencies:
            dependency = self.package(dependency_name)
            state_file = self._state_file(dependency)
            fingerprint = "missing"

            if state_file.is_file():
                try:
                    state = json.loads(state_file.read_text(encoding="utf-8"))
                    fingerprint = str(state.get("fingerprint", "missing"))
                except (json.JSONDecodeError, OSError):
                    fingerprint = "invalid"

            data.append(f"{dependency_name}:{fingerprint}")

        return "\n".join(data).encode("utf-8")

    @staticmethod
    def _named_files_fingerprint(paths: Iterable[Path]) -> bytes:
        digest = hashlib.sha256()

        for path in sorted(set(paths), key=lambda item: str(item)):
            if not path.is_file():
                continue
            digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")

        return digest.hexdigest().encode("ascii")

    def _support_files_fingerprint(self) -> bytes:
        support_dir = ROOT / "scripts" / "lib"
        paths: list[Path] = []

        if support_dir.is_dir():
            paths.extend(support_dir.rglob("*.sh"))

        paths.extend(
            path
            for path in (
                CONFIG_FILE,
                ROOT / "config" / "toolchain.env",
            )
            if path.is_file()
        )
        return self._named_files_fingerprint(paths)

    def _chroot_environment_fingerprint(self, profile_id: str | None) -> bytes:
        if profile_id is None:
            return b"missing-profile"

        chroot_root = self.profile_chroot_root(profile_id)
        prepare_steps = self.profile_prepare_steps(profile_id)
        support_paths = [
            ROOT / "scripts" / "run-chroot-package.sh",
            ROOT / "scripts" / "chroot-mounts.sh",
            *prepare_steps,
        ]

        return hash_bytes(
            CHROOT_PROTOCOL.encode("utf-8"),
            profile_id.encode("utf-8"),
            (
                str(chroot_root.relative_to(ROOT)).encode("utf-8")
                if chroot_root is not None
                else b"missing-chroot-root"
            ),
            self._named_files_fingerprint(support_paths),
        ).encode("ascii")

    def _package_fingerprint(
        self,
        package: Package,
        source: Path,
        profile_id: str | None = None,
    ) -> str:
        environment_support = b""

        if package.build_environment == "chroot":
            environment_support = self._chroot_environment_fingerprint(profile_id)

        return hash_bytes(
            BUILD_FINGERPRINT_SCHEMA.encode("utf-8"),
            self.version.encode("utf-8"),
            str(self.config.get("project", {}).get("format", 1)).encode("utf-8"),
            package.manifest.read_bytes(),
            package.build_script.read_bytes(),
            sha256_file(source).encode("ascii"),
            self.arch.encode("utf-8"),
            package.build_environment.encode("utf-8"),
            self._dependency_fingerprints(package),
            self._support_files_fingerprint(),
            environment_support,
        )

    def _state_file(self, package: Package) -> Path:
        return self.state_dir / f"{package.name}.json"

    def _is_cached(self, package: Package, fingerprint: str) -> bool:
        state_file = self._state_file(package)

        if not state_file.is_file():
            return False

        if not package.outputs or not all(path.exists() for path in package.outputs):
            return False

        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False

        if state.get("fingerprint_schema") != BUILD_FINGERPRINT_SCHEMA:
            return False

        return state.get("fingerprint") == fingerprint

    def _write_state(self, package: Package, fingerprint: str) -> None:
        state_file = self._state_file(package)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(
                {
                    "package": package.name,
                    "version": package.version,
                    "architecture": self.arch,
                    "environment": package.build_environment,
                    "fingerprint_schema": BUILD_FINGERPRINT_SCHEMA,
                    "fingerprint": fingerprint,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _host_build_environment(
        self,
        package: Package,
        source_archive: Path,
        source_dir: Path,
        package_build_dir: Path,
        package_out: Path,
        jobs: int,
    ) -> dict[str, str]:
        env = os.environ.copy()
        env.update(
            {
                "VEYR_ROOT": str(ROOT),
                "VEYR_VERSION": self.version,
                "VEYR_ARCH": self.arch,
                "VEYR_PACKAGE_NAME": package.name,
                "VEYR_PACKAGE_VERSION": package.version,
                "VEYR_SOURCE_ARCHIVE": str(source_archive),
                "VEYR_SOURCE_DIR": str(source_dir),
                "VEYR_BUILD_DIR": str(package_build_dir),
                "VEYR_PACKAGE_OUT": str(package_out),
                "VEYR_JOBS": str(jobs),
                "VEYR_BUILD_ENVIRONMENT": "host",
            }
        )
        return env

    def _build_host_package(
        self,
        package: Package,
        source_archive: Path,
        jobs: int,
    ) -> None:
        package_build_dir = self.build_dir / "packages" / package.name
        source_root = package_build_dir / "src"
        source_dir = self._safe_extract(source_archive, source_root)
        package_out = self.out_dir / "packages" / package.name
        package_out.mkdir(parents=True, exist_ok=True)

        env = self._host_build_environment(
            package,
            source_archive,
            source_dir,
            package_build_dir,
            package_out,
            jobs,
        )

        result = subprocess.run(
            [str(package.build_script)],
            cwd=source_dir,
            env=env,
            check=False,
        )

        if result.returncode != 0:
            fail(
                f"Build failed for package {package.name} "
                f"(exit code {result.returncode})"
            )

    def _build_chroot_package(
        self,
        package: Package,
        source_archive: Path,
        jobs: int,
        profile_id: str | None,
    ) -> None:
        if profile_id is None:
            fail(
                f"Package {package.name} must be built inside a profile chroot. "
                "Use: ./veyr build --profile temporary-alpha4"
            )

        chroot_root = self.profile_chroot_root(profile_id)
        if chroot_root is None:
            fail(f"Profile {profile_id} has no configured chroot root")

        chroot_root = ensure_within_root(chroot_root)
        if not chroot_root.is_dir():
            fail(
                f"Chroot root is not prepared for {package.name}: "
                f"{chroot_root.relative_to(ROOT)}"
            )

        source_root = chroot_root / "sources" / package.name
        source_dir = self._safe_extract(source_archive, source_root)

        runner = ROOT / "scripts" / "run-chroot-package.sh"
        if not runner.is_file():
            fail("Chroot package runner is missing: scripts/run-chroot-package.sh")

        env = os.environ.copy()
        env.update(
            {
                "VEYR_VERSION": self.version,
                "VEYR_ARCH": self.arch,
            }
        )

        result = subprocess.run(
            [
                str(runner),
                str(chroot_root),
                str(source_dir),
                str(package.build_script),
                package.name,
                package.version,
                str(jobs),
                CHROOT_PROTOCOL,
            ],
            cwd=ROOT,
            env=env,
            check=False,
        )

        if result.returncode != 0:
            fail(
                f"Chroot build failed for package {package.name} "
                f"(exit code {result.returncode})"
            )

    def _verify_outputs(self, package: Package) -> None:
        missing_outputs = [path for path in package.outputs if not path.exists()]

        if not missing_outputs:
            return

        rendered = "\n".join(
            f"  - {path.relative_to(ROOT)}" for path in missing_outputs
        )
        fail(
            f"Package {package.name} did not create declared outputs:\n{rendered}"
        )

    def build_package(
        self,
        name: str,
        rebuild: bool = False,
        profile_id: str | None = None,
    ) -> None:
        package = self.package(name)
        source_archive = self.fetch_package(name)
        fingerprint = self._package_fingerprint(
            package,
            source_archive,
            profile_id=profile_id,
        )

        if not rebuild and self._is_cached(package, fingerprint):
            ok(f"{package.name} {package.version} is already built")
            return

        jobs = max(1, os.cpu_count() or 1)

        log(
            f"Building {package.name} {package.version} "
            f"[{package.build_environment}]"
        )

        if package.build_environment == "host":
            self._build_host_package(package, source_archive, jobs)
        else:
            self._build_chroot_package(
                package,
                source_archive,
                jobs,
                profile_id,
            )

        self._verify_outputs(package)
        self._write_state(package, fingerprint)
        ok(f"Built {package.name} {package.version}")

    def build_packages(
        self,
        package_names: Iterable[str],
        rebuild: bool = False,
        profile_id: str | None = None,
    ) -> None:
        for package_name in self.build_order(package_names):
            self.build_package(
                package_name,
                rebuild=rebuild,
                profile_id=profile_id,
            )

    def _run_steps(self, steps: Iterable[Path], label: str) -> None:
        for step in steps:
            log(f"{label}: {step.relative_to(ROOT)}")
            result = subprocess.run([str(step)], cwd=ROOT, check=False)

            if result.returncode != 0:
                fail(f"{label} failed: {step.relative_to(ROOT)}")

    def build_profile(self, profile_id: str, rebuild: bool = False) -> None:
        package_names = self.profile_packages(profile_id)
        order = self.build_order(package_names)
        prepare_steps = self.profile_prepare_steps(profile_id)

        prepared = False
        entered_chroot_stage = False

        for package_name in order:
            package = self.package(package_name)

            if package.build_environment == "chroot":
                if not prepared:
                    if not prepare_steps:
                        fail(
                            f"Profile {profile_id} contains chroot packages but "
                            "has no prepare steps"
                        )

                    self._run_steps(prepare_steps, "Prepare step")
                    prepared = True

                entered_chroot_stage = True
            elif entered_chroot_stage:
                fail(
                    f"Invalid build graph for {profile_id}: host package "
                    f"{package.name} appears after the chroot stage began"
                )

            self.build_package(
                package_name,
                rebuild=rebuild,
                profile_id=profile_id,
            )

        if not entered_chroot_stage and prepare_steps:
            log(
                f"Profile {profile_id} has prepare steps but no chroot packages; "
                "prepare stage was not needed"
            )

        ok(f"Build profile '{profile_id}' completed")

    def image(self, profile_id: str, rebuild: bool = False) -> None:
        profile = self.profile(profile_id)

        if profile.status != "active":
            fail(
                f"Profile '{profile_id}' is {profile.status}; "
                "only active profiles can produce images"
            )

        self.build_profile(profile_id, rebuild=rebuild)

        if not profile.image_steps:
            fail(f"Profile '{profile_id}' has no image steps")

        self._run_steps(profile.image_steps, "Image step")
        ok(f"Image profile '{profile_id}' completed")

    def run(self, profile_id: str) -> None:
        profile = self.profile(profile_id)

        if profile.run_script is None:
            fail(f"Profile '{profile_id}' has no run script")

        result = subprocess.run(
            [str(profile.run_script)],
            cwd=ROOT,
            check=False,
        )

        if result.returncode != 0:
            fail(f"Run command failed for profile '{profile_id}'")

    def clean(self, include_sources: bool = False) -> None:
        log("Cleaning build and output directories")
        remove_tree_contents(self.build_dir)
        remove_tree_contents(self.out_dir)
        (self.build_dir / ".gitkeep").touch()
        (self.out_dir / ".gitkeep").touch()

        if include_sources:
            log("Cleaning downloaded sources")
            source_root = ROOT / "sources"
            remove_tree_contents(source_root)
            (source_root / ".gitkeep").touch()

        ok("Clean complete")


def select_packages(
    forge: Forge,
    package_name: str | None,
    profile_id: str | None,
) -> list[str]:
    if package_name and profile_id:
        fail("Choose either a package or --profile, not both")

    if profile_id:
        return forge.profile_packages(profile_id)

    if package_name:
        forge.package(package_name)
        return [package_name]

    fail("Specify a package name or --profile PROFILE")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veyr",
        description="Veyr Forge - build orchestration for the Veyr Linux distribution",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="show Veyr/Forge version",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("doctor", help="check the host build environment")
    subparsers.add_parser(
        "check", help="validate Forge manifests, graphs, scripts and safety rules"
    )

    list_parser = subparsers.add_parser("list", help="list packages or profiles")
    list_parser.add_argument("kind", choices=("packages", "profiles"))

    info_parser = subparsers.add_parser(
        "info", help="show package or profile information"
    )
    info_parser.add_argument("kind", choices=("package", "profile"))
    info_parser.add_argument("name")

    graph_parser = subparsers.add_parser(
        "graph", help="show build order for a profile"
    )
    graph_parser.add_argument("profile")

    fetch_parser = subparsers.add_parser(
        "fetch", help="download and verify sources"
    )
    fetch_parser.add_argument("package", nargs="?")
    fetch_parser.add_argument("--profile")

    build_cmd = subparsers.add_parser(
        "build", help="build a package or profile"
    )
    build_cmd.add_argument("package", nargs="?")
    build_cmd.add_argument("--profile")
    build_cmd.add_argument("--rebuild", action="store_true")

    image_parser = subparsers.add_parser(
        "image", help="build an image profile"
    )
    image_parser.add_argument("profile")
    image_parser.add_argument("--rebuild", action="store_true")

    run_parser = subparsers.add_parser(
        "run", help="run a profile in its configured VM"
    )
    run_parser.add_argument("profile")

    clean_parser = subparsers.add_parser(
        "clean", help="remove generated build artifacts"
    )
    clean_parser.add_argument(
        "--sources",
        action="store_true",
        help="also delete downloaded sources",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        forge = Forge()

        if args.version:
            print(
                f"Veyr {forge.version} / Forge format "
                f"{forge.config.get('project', {}).get('format', 1)}"
            )
            return 0

        if args.command is None:
            parser.print_help()
            return 0

        if args.command == "doctor":
            return forge.doctor()

        if args.command == "check":
            return forge.check()

        if args.command == "list":
            if args.kind == "packages":
                forge.list_packages()
            else:
                forge.list_profiles()
            return 0

        if args.command == "info":
            if args.kind == "package":
                forge.info_package(args.name)
            else:
                forge.info_profile(args.name)
            return 0

        if args.command == "graph":
            forge.graph(args.profile)
            return 0

        if args.command == "fetch":
            packages = select_packages(
                forge,
                args.package,
                args.profile,
            )
            forge.fetch_packages(packages)
            return 0

        if args.command == "build":
            if args.profile:
                if args.package:
                    fail("Choose either a package or --profile, not both")
                forge.build_profile(args.profile, rebuild=args.rebuild)
            else:
                packages = select_packages(forge, args.package, None)
                forge.build_packages(packages, rebuild=args.rebuild)
            return 0

        if args.command == "image":
            forge.image(args.profile, rebuild=args.rebuild)
            return 0

        if args.command == "run":
            forge.run(args.profile)
            return 0

        if args.command == "clean":
            forge.clean(include_sources=args.sources)
            return 0

        fail(f"Unknown command: {args.command}")

    except ForgeError as exc:
        print(f"{red('[ERROR]')} {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())