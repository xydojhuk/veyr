# Changelog

Notable changes to Veyr are recorded here. Published versions are documented
in [GitHub Releases](https://github.com/xydojhuk/veyr/releases).

## Unreleased

### Documentation

- Standardized the project README and changed the release badge to update
  automatically from GitHub Releases, including prereleases.
- Added contributor guidelines and a vulnerability-reporting policy.
- Removed the speculative public roadmap; future development plans are not
  presented as commitments.

## [0.1.0-alpha.4.1] — 2026-10-09

**Alpha.4 stabilization.**

### Improved

- Hardened source archive extraction and symlink output validation.
- Improved Forge build fingerprints and resumed root filesystem refreshes.
- Added `./veyr check` for repository consistency validation.
- Corrected Alpha.4 Gettext runtime verification.

[Release notes](https://github.com/xydojhuk/veyr/releases/tag/v0.1.0-alpha.4.1)

## [0.1.0-alpha.4] — 2026-08-20

**Native chroot tooling.**

### Added

- Forge format 3 with host/chroot build environments.
- Native package builds and build provenance markers.
- Disk-backed ext4 root, small BusyBox initramfs and serial/graphical QEMU
  development workflows.
- Native tooling including Gettext, Bison, Perl, Zlib, Python, Texinfo
  and Util-linux.

[Release notes](https://github.com/xydojhuk/veyr/releases/tag/v0.1.0-alpha.4)

## [0.1.0-alpha.3] — 2026-08-08

**Disk root and chroot foundation.**

### Added

- Small early initramfs and ext4 root filesystem on a Virtio disk.
- `switch_root` to the disk-backed Veyr userspace.
- Controlled host-side chroot workflow and serial QEMU debugging.

[Release notes](https://github.com/xydojhuk/veyr/releases/tag/v0.1.0-alpha.3)

## [0.1.0-alpha.2] — 2026-08-06

**Temporary userspace.**

### Added

- Cross-built GNU/Linux userspace, including Bash, Coreutils, GCC/G++, and
  development utilities.
- Runtime verification for tools and C/C++ compilation in the guest.

[Release notes](https://github.com/xydojhuk/veyr/releases/tag/v0.1.0-alpha.2)

## [0.1.0-alpha.1] — 2026-08-06

**Cross-toolchain.**

### Added

- Veyr Forge build orchestration.
- Cross Binutils, GCC pass 1, Linux headers and bootstrap Glibc targeting
  `x86_64-veyr-linux-gnu`.
- QEMU/KVM development image and toolchain verification.

[Release notes](https://github.com/xydojhuk/veyr/releases/tag/v0.1.0-alpha.1)
