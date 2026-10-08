<p align="center">
  <img src="assets/banner/veyr-banner.png" alt="Veyr Linux" width="100%" />
</p>

<h1 align="center">Veyr Linux</h1>

<p align="center">
  Independent Linux distribution built from upstream components.
</p>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0--alpha.4-111111?style=flat-square">
  <img alt="Stage" src="https://img.shields.io/badge/stage-Native%20Chroot%20Tooling-111111?style=flat-square">
  <img alt="Architecture" src="https://img.shields.io/badge/arch-x86__64-111111?style=flat-square&logo=linux&logoColor=white">
  <img alt="Build host" src="https://img.shields.io/badge/build%20host-Fedora-111111?style=flat-square&logo=fedora&logoColor=white">
</p>

---

## 🧱 About

**Veyr** is an independent Linux distribution project built from upstream
components rather than using Fedora, Ubuntu, Arch, or another distribution as
its runtime base.

Fedora is currently used only as the supported build host.

The project is built around a shared **Veyr Base**, with future
**Desktop** and **Developer** editions on top of it.

## ⚙️ Current stage

**Veyr Base 0.1.0-alpha.4 — Native Chroot Tooling**

- Veyr Forge format 3
- x86_64 cross-toolchain
- temporary GNU userspace
- ext4 disk-backed root filesystem
- small BusyBox initramfs
- `switch_root` into Veyr
- native package builds inside the Veyr chroot
- build provenance and runtime verification
- project consistency checks via `./veyr check`

Target:

```text
x86_64-veyr-linux-gnu
```

A successful alpha.4 boot ends with:

```text
Native chroot tool verification: PASS
Alpha.4 runtime verification: PASS
```

## 🚀 Build

Supported build host:

```text
Fedora Linux · x86_64
```

Install build dependencies and verify the environment:

```bash
make deps
./veyr check
./veyr doctor
```

Build the current image:

```bash
make alpha4
```

Or run the individual Forge stages:

```bash
./veyr graph base-alpha4
./veyr fetch --profile base-alpha4
./veyr image base-alpha4
```

## ▶️ Run

Recommended serial/debug mode:

```bash
make run-alpha4-serial
```

Graphical QEMU mode:

```bash
./veyr run base-alpha4
```

Generated artifacts:

```text
out/images/base-alpha4/initramfs.img
out/images/base-alpha4/veyr-rootfs.ext4
out/images/base-alpha4/Veyr-0.1.0-alpha.4-base-alpha4-x86_64.iso
```

## 🧩 Project

```text
config/        Forge and toolchain configuration
packages/      Package manifests and build scripts
profiles/      Build and image profiles
scripts/       Build, chroot and image helpers
initramfs/     Early userspace
rootfs/        Veyr root filesystem files
tests/         Build and runtime verification
tools/forge/   Veyr Forge
docs/          Project documentation
```

Older alpha profiles remain available for regression testing:

```bash
make alpha1
make alpha2
make alpha3
make alpha4
```

## 🗺️ Roadmap

Development plans and upcoming milestones are tracked in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

---

<p align="center">
  <strong>Veyr Linux</strong><br>
  Built from the ground up.
</p>
