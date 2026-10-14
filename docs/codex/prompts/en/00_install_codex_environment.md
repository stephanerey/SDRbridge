# Install SR Method 4.1 in a fresh project

Do not code. Install released version `4.1.0`, verify it, then stop before application work. Read the nearest `AGENTS.md`, select `SR_PACK_SOURCE` explicitly, and record `release_status`, `source_commit`, and Git state. Reject a source that does not match the expected release. If any SR marker exists, use `05_upgrade_codex_environment.md`.

Preview, report creations and preservation, wait for exact authority, then use `--write`:

```bash
python3 "$SR_PACK_SOURCE/scripts/install_codex_pack.py" --source "$SR_PACK_SOURCE" --target "$SR_TARGET" --json
python3 "$SR_TARGET/scripts/codex/sr_post_install_check.py" --root "$SR_TARGET" --json
```

The target must include `SR_LOTS.yaml`, `SR_PASSES.yaml` with `passes: []`, a core-mode `MCP_POLICY.yaml`, and `task_state.yaml`. Invent no lot, pass, requirement, or MCP capability. Change no application code, secret, migration, dependency, or deployment. Flow: `00 -> 06` or `05 -> 06 -> 07`.
