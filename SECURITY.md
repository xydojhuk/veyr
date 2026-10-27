# Security Policy

Veyr is an experimental, source-built Linux distribution. The current alpha
builds are intended for development and virtual-machine testing, not for
production systems or installation on personal hardware.

## Supported versions

| Version | Security maintenance |
| --- | --- |
| Current `main` development branch | Best-effort fixes |
| Published alpha release tags | Historical snapshots; no guaranteed backports |

No response-time or patch-delivery SLA is offered.

## Reporting a vulnerability

Please do **not** publish exploitable details in a public GitHub issue or
pull request.

If the repository's **Security** tab offers **Report a vulnerability**, use
that private reporting form. Private vulnerability reporting must be enabled
in GitHub Settings for this option to be available.

If the private form is unavailable, open a public issue **only to request a
private contact channel**. Do not include a proof of concept, exploit,
credentials, vulnerable payloads, personal data or other sensitive details
in that issue.

When a private reporting channel is available, please provide:

- A brief description of the security issue and its likely impact.
- The affected Veyr version or commit and relevant host/guest environment.
- Reproduction steps using synthetic data, where possible.
- Whether the issue concerns Veyr Forge, package acquisition/extraction,
  build scripts, generated images or guest runtime behavior.

Maintainers will review reports on a best-effort basis.

## Security considerations

- Veyr builds and extracts upstream source archives. Do not disable manifest
  integrity checks, path validation or hardened extraction protections.
- Build scripts may execute third-party source build systems; review the
  dependencies and scripts before running them on a machine with valuable data.
- Use disposable or isolated build environments for untrusted changes.
- Do not commit API keys, credentials, local machine data, generated images or
  downloaded source archives to this repository.
- A passing consistency check is not a security certification for a built OS.

Security automation and private vulnerability reporting are separate GitHub
configuration steps; the presence of this file does not mean they are enabled.
