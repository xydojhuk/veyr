# Contributing to Veyr

Thank you for your interest in Veyr. The project is an early, source-built
Linux development environment with a custom build tool, Veyr Forge.

## Scope

Focused contributions are welcome for:

- Forge correctness, source integrity, validation and error handling.
- Package and profile manifest fixes.
- Build-script reliability and reproducible debugging steps.
- Documentation corrections and verification examples.
- Tests that do not require a full Linux image build for every change.

Please do not treat unpublished features or personal development ideas as
committed project plans.

## Before opening a pull request

1. Check for a related [issue](https://github.com/xydojhuk/veyr/issues).
2. Make a focused change on a separate branch.
3. On Python 3.11+ run the fast consistency check from the repository root:

   ```bash
   ./veyr check
   ```

4. If you are on a supported Fedora x86_64 build host with the required tools,
   you can also run:

   ```bash
   ./veyr doctor
   ```

5. For changes that affect images, boot, toolchains or chroot behavior, describe
   the exact build/run commands you actually executed and their results. Full
   image builds and QEMU verification are not required for documentation-only
   contributions.

## Pull request checklist

Include:

- The reason for the change and the files it affects.
- The relevant Veyr version (`cat VERSION`) and host environment, when useful.
- Successful checks you ran, or a clear explanation of what was not run.
- Any compatibility or security implications.

Keep generated files in ignored build locations. Do not commit downloaded
source archives, output images, secrets, private logs or personal data.

## Building locally

The documented build host is Fedora Linux on x86_64. The `make deps` target
runs a setup script that installs host packages with `sudo dnf`; review that
script before using it. See the [README](README.md) for build and QEMU
commands. Avoid running or testing untrusted build changes on a production
workstation.

## Security issues

Do not open public issues containing sensitive vulnerability details. Follow
[SECURITY.md](SECURITY.md) instead.

## License

By contributing, you agree to license your contribution under the project's
existing [MIT License](LICENSE).
