<p align="center">
  <img src="assets/banner/veyr-banner.png" alt="Veyr Linux banner" width="100%">
</p>

<div align="center">

# Veyr Linux

**Built from the ground up.**

An independent Linux distribution assembled from upstream source code,
with its own build orchestration system, **Veyr Forge**.

[![Release](https://img.shields.io/github/v/release/xydojhuk/veyr?display_name=tag&include_prereleases&sort=semver&style=flat-square&label=release)](https://github.com/xydojhuk/veyr/releases)
[![CI](https://github.com/xydojhuk/veyr/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/xydojhuk/veyr/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/xydojhuk/veyr?style=flat-square&label=license)](LICENSE)
![Architecture](https://img.shields.io/badge/architecture-x86__64-555555?style=flat-square)
![Build host](https://img.shields.io/badge/build%20host-Fedora-555555?style=flat-square)

**[Highlights](#-highlights) · [Build](#-build-from-source) · [Run](#-run-in-qemu) · [Contribute](#-contributing)**

</div>

## 🧱 About

Veyr is an independent, source-built Linux distribution project. It uses
upstream Linux and GNU components, rather than using an existing distribution
as its runtime base.

**Fedora is the currently supported build host**, not the runtime system inside
Veyr. This repository contains an early development preview intended for
building and testing in a virtual machine. It is **not an installable desktop
OS** and is not intended for everyday or production use.

## ✨ Highlights

The current Alpha.4-based system includes:

- **Veyr Forge** — source and package manifests, profile-based build graphs,
  dependency ordering, source SHA-256 verification and a build cache.
- **Cross-toolchain** — tools targeting `x86_64-veyr-linux-gnu`.
- **Disk-backed root filesystem** — ext4 root and a small BusyBox initramfs,
  followed by `switch_root` into Veyr.
- **Native chroot builds** — packages built inside the Veyr environment,
  with build provenance checks.
- **QEMU development boot** — serial and graphical workflows.
- **Consistency checks** — manifest validation, dependency graphs,
  Shell/Python syntax, file paths and secure archive-extraction support via
  `./veyr check`.

These are development capabilities; they do not imply production readiness.

## 🚀 Build from source

**Supported environment:** Fedora Linux on `x86_64`, Python 3.11+,
Git, and the system build tools installed by the setup script.

```bash
git clone https://github.com/xydojhuk/veyr.git
cd veyr

# Review this script first: it installs Fedora packages using sudo/dnf.
make deps

# Check repository consistency and local build prerequisites.
./veyr check
./veyr doctor

# Build the current Alpha.4 image.
make alpha4
```

`./veyr check` is a fast repository validation. `./veyr doctor` additionally
checks the build-host environment and may report missing tools. `make alpha4`
builds the Linux image and its dependencies; expect substantial time and disk
usage. It is not part of the lightweight CI checks planned for this project.

To inspect the Alpha.4 dependency graph without building anything:

```bash
./veyr graph base-alpha4
```

## ▶️ Run in QEMU

After a successful build, start the serial/debug environment:

```bash
make run-alpha4-serial
```

Or use the graphical QEMU launcher:

```bash
./veyr run base-alpha4
```

The serial launcher uses a snapshot disk and prints the QEMU exit shortcut.
If `/dev/kvm` is not accessible, it falls back to software emulation.

Expected output paths include:

```text
out/images/base-alpha4/initramfs.img
out/images/base-alpha4/veyr-rootfs.ext4
out/images/base-alpha4/Veyr-<VERSION>-base-alpha4-x86_64.iso
```

`<VERSION>` is the value of the repository's [`VERSION`](VERSION) file.
To check the version of your local source tree:

```bash
./veyr --version
```

The **Release** badge above shows the most recently published GitHub Release,
including prereleases. It does not change the local `VERSION` file.

## 🖥️ Preview

Boot screenshots and serial-console captures are not included yet. They can be
added here when available; no images or boot results are simulated in this README.

A successful Alpha.4 verification has previously produced:

```text
Native chroot tool verification: PASS
Alpha.4 runtime verification: PASS
```

This example documents the published Alpha.4 verification, not a guarantee
that every future build will succeed.

## 🧩 Repository structure

```text
config/        Forge and toolchain configuration
packages/      Package manifests and build scripts
profiles/      Build and image profiles
scripts/       Build and runtime helper scripts
initramfs/     Early userspace
rootfs/        Root filesystem files
tests/         Build and runtime verification
tools/forge/   Veyr Forge implementation
assets/        Branding and repository assets
```

Generated files are kept in `build/`, `sources/` and `out/` and should not be
committed to Git.

## 🤝 Contributing

Bug reports, reproducible build issues and focused pull requests are welcome.
Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change. Please
include the host distribution, relevant commands, expected results and
sanitized logs. Never publish secrets, private data or untrusted artifacts.

## 🛡️ Security

Please follow [SECURITY.md](SECURITY.md) for responsible vulnerability
reporting. Do not publish working exploits or sensitive security details in
public issues.

## 📦 Releases

See [GitHub Releases](https://github.com/xydojhuk/veyr/releases) for published
build milestones and [CHANGELOG.md](CHANGELOG.md) for release history.

## 📄 License

Veyr is released under the [MIT License](LICENSE).

---

<p align="center">
  <strong>Veyr Linux</strong><br>
  Built from the ground up.
</p>
