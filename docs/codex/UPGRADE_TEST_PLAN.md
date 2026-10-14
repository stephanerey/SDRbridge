# Version-agnostic upgrade test plan

The declared source version is provenance only. Upgrade behavior is selected from observed files, managed fingerprints, markers, capabilities and local modifications.

## Required starting states

- no SR installation;
- recognized clean managed content;
- partial installation;
- locally modified managed block;
- unmanaged `AGENTS.md`;
- missing or unreadable version metadata;
- unknown or future declared version;
- obsolete managed skill files;
- already aligned target.

## Scenario

For each state: preview, verify preservation, apply transactionally, run post-install checks, apply again and require zero operations. Modified unknown files must be preserved or reported as conflicts; they must never be overwritten silently.

Post-install checks are read-only by default. Persist a report only with explicit `--write-report`.

Legacy task contracts remain readable. Their presence must not force V4.1 to generate new duplicate contracts.
