# Veyr Roadmap

<p align="center">
  <strong>From bootstrap Linux to a complete Veyr desktop system.</strong>
</p>

<p align="center">
  ✅ Completed &nbsp;&nbsp; 🚧 Next &nbsp;&nbsp; ○ Planned
</p>

---

## 🧱 Foundation

### ✅ 0.0.1 — Bootstrap

- Bootable ISO
- Upstream Linux kernel
- Static BusyBox initramfs
- GRUB
- QEMU/KVM workflow

### ✅ 0.0.2 — Veyr Forge

- Forge CLI
- Package and profile manifests
- Dependency ordering
- Verified source downloads
- Build fingerprints and cache
- Image orchestration

---

## ⚙️ 0.1 — Veyr Base

### ✅ 0.1.0-alpha.1 — Cross Toolchain

- Binutils 2.47
- GCC 16.1.0 pass 1
- Linux 7.1.5 headers
- Glibc 2.44 bootstrap
- `x86_64-veyr-linux-gnu`

### ✅ 0.1.0-alpha.2 — Temporary Userspace

- Temporary GNU userspace
- Binutils/GCC pass 2
- C/C++ compilation inside the Veyr environment
- Static rescue environment

### ✅ 0.1.0-alpha.3 — Disk Root

- Small early initramfs
- Ext4 disk-backed root
- Virtio `/dev/vda`
- `switch_root`
- Controlled chroot environment

### ✅ 0.1.0-alpha.4 — Native Chroot Tooling

- Host/chroot build environments
- Native package builds inside Veyr
- Build provenance verification
- Runtime smoke tests
- Hardened Forge extraction
- Build fingerprint cache v2
- `./veyr check`

Verified:

```text
Native chroot tool verification: PASS
Alpha.4 runtime verification: PASS
```

### 🚧 0.1.0-alpha.5 — Final Toolchain

- Replace temporary toolchain components
- Final Glibc
- Final Binutils
- Final GCC
- Core libraries required by the final Veyr userspace

### ○ 0.1.0-alpha.6 — Final Userspace

- Remaining essential GNU/base packages
- E2fsprogs
- Procps-ng
- Kmod
- Core system utilities
- D-Bus/system integration groundwork

### ○ 0.1.0-alpha.7 — systemd Boot

```text
kernel
  ↓
systemd PID 1
  ↓
services
  ↓
login
  ↓
bash
```

### ○ 0.1.0 — Veyr Base

Release target:

- Final Glibc userspace
- Final compiler and base tools
- systemd as PID 1
- Reproducible disk-backed image
- QEMU boot without BusyBox as the primary userspace

---

## 📦 0.2 — Packages & Repository

- Binary package strategy
- Package metadata
- Repository generation
- Signing
- Update groundwork

## 💾 0.3 — Installation

- GPT / UEFI layout
- Target disk handling
- Bootloader installation
- Persistent installed system

## 🌐 0.4 — Hardware & Network

- Firmware
- NetworkManager
- Bluetooth
- PipeWire / WirePlumber
- Mesa / Wayland

## 🖥️ 0.5 — Veyr Desktop

- KDE Plasma
- Original Veyr visual style
- Familiar desktop interaction
- Graphical settings, software and updates
- Flatpak integration

---

## 🚀 1.0 — Stable

Goal:

> An installable and updateable Veyr desktop for everyday users, where normal
> system tasks do not require the terminal.
