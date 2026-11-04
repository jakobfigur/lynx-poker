# Security

Lynx is research software, not a hardened service. The current `main` branch is the maintenance target; there is no promised support window for earlier snapshots.

## Reporting a vulnerability

Please use the repository's **Security → Report a vulnerability** feature for confidential reports. Do not post credentials, private recordings or exploit details in a public issue. If private reporting is unavailable, contact the maintainer through [the GitHub profile](https://github.com/jakobfigur) to arrange a private channel before sharing details.

Include the affected commit, platform, impact and a minimal reproduction with synthetic data. There is no guaranteed response time or bug bounty.

## Models and external services

Treat model files as executable inputs: do not load untrusted PyTorch checkpoints. Use the supplied files or verify the provenance and hashes of separately downloaded models. Research scripts can contact external APIs or create cloud resources when explicitly invoked; review their arguments and provider charges first. Never commit API keys, SSH keys, tokens or local `.env` files.
