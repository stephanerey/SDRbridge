#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


LANGUAGES = ("en", "fr", "de", "es", "pt")
RELEASE_HISTORY = (
    "4.0.0",
    "3.7.0",
    "3.6.0",
    "3.5.2",
    "3.5.1",
    "3.5.0",
    "3.4.0",
    "3.3.0",
    "3.2.2",
    "3.2.1",
    "3.2.0",
    "3.0.4",
)
PUBLIC_PROMPTS = {
    "00_install_codex_environment.md": (
        "4.1.0",
        "SR_PACK_SOURCE",
        "release_status",
        "source_commit",
        "MCP_POLICY.yaml",
        "task_state.yaml",
    ),
    "01_start_sr_session.md": (
        "task_state.yaml",
        "selected",
        "ambiguous",
        "repair",
        "user_testing",
    ),
    "05_upgrade_codex_environment.md": (
        "4.1.0",
        "SR_PACK_SOURCE",
        "release_status",
        "source_commit",
        "locally_modified",
        "already_aligned",
        "MCP_POLICY.yaml",
        "task_state.yaml",
        "sr_post_install_check.py",
    ),
    "06_verify_sr_installation.md": (
        "read_only",
        "MCP_POLICY.yaml",
        "task_state.yaml",
        "validate_release_docs.py",
        "sr_post_install_check.py",
    ),
    "07_realign_sr_state_after_upgrade.md": (
        "SR_BOOTSTRAP.md",
        "find_next_session_prompt.py",
        "selected",
        "ambiguous",
        "--prompt",
        "je valide",
        "task_state.yaml",
        "repair",
        "user_testing",
    ),
    "08_define_sr_passes_from_lots.md": (
        "SR_PASSES.yaml",
        "repair",
        "reopened",
        "Scope",
        "Verification",
        "Activation",
        "task_state.yaml",
        "MCP_POLICY.yaml",
    ),
    "09_define_sr_lots_from_scope.md": (
        "SR_LOTS.yaml",
        "validated_requests",
        "existing_requirement_repair",
        "Scope",
        "Verification",
        "Activation",
        "task_state.yaml",
        "MCP_POLICY.yaml",
    ),
    "15_define_runtime_agents.md": (
        "Pydantic",
        "output schema",
        "invalid_output_policy",
        "Verification",
        "Activation",
        "deferred",
        "MCP_POLICY.yaml",
    ),
}
ROOT_ONLY_PROMPTS = {
    "10_define_domain_skills_from_cis.md": ("métier", "project-skills", "runtime", "MCP_POLICY.yaml"),
    "20_generate_domain_skills.md": ("SKILL.md", "project-skills", "references/", "validate_skills.py"),
    "30_review_generated_skills.md": ("trigger", "token", "MCP", "validate_skills.py"),
}
INSTALL_MARKERS = (
    "4.1.0",
    "SR_LOTS.yaml",
    "SR_PASSES.yaml",
    "MCP_POLICY.yaml",
    "task_state.yaml",
    "--upgrade",
)


def load_json(path: Path, errors: list[str]) -> dict:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: root must be an object")
        return {}
    return value


def require_markers(path: Path, markers: tuple[str, ...], errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    for marker in markers:
        if marker not in text:
            errors.append(f"{path}: missing marker {marker!r}")


def validate_prompt_policy(path: Path, version: str | None, errors: list[str]) -> None:
    """Catch known contradictory instructions, without claiming semantic proof."""
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if path.name.startswith(("00_", "05_")):
        for heading in re.findall(r"^#+ .+$", text, re.MULTILINE):
            for named_version in re.findall(r"\bSR[ -]+(\d+(?:\.\d+){1,2})\b", heading):
                if version and named_version != version:
                    errors.append(f"{path}: stale SR heading {heading!r}; target is {version}")
    if path.name.startswith("05_"):
        if re.search(r"\bupgrade_(?:minor_3x|standard_235_plus|legacy_unknown)\b", text):
            errors.append(f"{path}: version-based upgrade routing conflicts with content-based classification")
    if path.name.startswith("06_"):
        # A verification-only prompt routes repairs elsewhere; it must not embed
        # runnable mutation options, including the old automatic-fix path.
        for option in ("--write", "--upgrade", "--fix-safe", "--apply-plan", "--plan-out", "--restore"):
            if re.search(rf"(?<![\w-]){re.escape(option)}(?![\w-])", text):
                errors.append(f"{path}: mutative option in read-only prompt: {option}")
    if path.name.startswith(("08_", "09_")):
        for legacy_instruction in ("Lot Design Evidence Gate", "RepoMap/KG ->"):
            if legacy_instruction in text:
                errors.append(f"{path}: obsolete autonomous gate instruction: {legacy_instruction}")


def validate_links(root: Path, paths: list[Path], errors: list[str]) -> None:
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for raw_target in pattern.findall(text):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            candidate = (path.parent / target).resolve()
            if not candidate.exists():
                errors.append(f"{path}: broken local link {raw_target!r}")


def source_doc(root: Path, stem: str, language: str) -> Path:
    return root / (f"{stem}.md" if language == "en" else f"{stem}.{language}.md")


def audit(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    source_mode = (root / "MANIFEST.json").exists() and (root / "core/SR_PACK_VERSION.json").exists()
    version_path = root / ("core/SR_PACK_VERSION.json" if source_mode else "docs/codex/SR_PACK_VERSION.json")
    changelog_path = root / ("CHANGELOG.md" if source_mode else "docs/codex/CHANGELOG.md")
    version_data = load_json(version_path, errors)
    version = version_data.get("version")

    if source_mode:
        manifest = load_json(root / "MANIFEST.json", errors)
        manifest_version = manifest.get("version")
        if manifest_version != version:
            errors.append(f"MANIFEST version {manifest_version!r} != SR pack version {version!r}")
        files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
        if "CHANGELOG.md" not in files:
            errors.append("MANIFEST files must include CHANGELOG.md")

    if changelog_path.exists():
        changelog = changelog_path.read_text(encoding="utf-8", errors="ignore")
        if "## [Unreleased]" not in changelog:
            errors.append(f"{changelog_path}: missing [Unreleased] section")
        if version and f"Target version: `{version}`" not in changelog and f"## [{version}]" not in changelog:
            errors.append(f"{changelog_path}: current version {version!r} is not documented")
        for historical_version in RELEASE_HISTORY:
            if f"## [{historical_version}]" not in changelog:
                errors.append(f"{changelog_path}: missing historical version {historical_version}")
    else:
        errors.append(f"missing file: {changelog_path}")

    release_status = version_data.get("release_status")
    released_at = version_data.get("released_at")
    if release_status not in {"unreleased", "released"}:
        errors.append(f"{version_path}: release_status must be 'unreleased' or 'released'")
    elif release_status == "unreleased" and released_at is not None:
        errors.append(f"{version_path}: released_at must be null while release_status is unreleased")
    elif release_status == "released" and not isinstance(released_at, str):
        errors.append(f"{version_path}: released_at must be a date string for a released pack")

    prompt_root = root / ("prompts" if source_mode else "docs/codex/prompts")
    # Root prompts are public entry points too, and are also installed.
    for language in ("", *LANGUAGES):
        for prompt, markers in PUBLIC_PROMPTS.items():
            path = prompt_root / language / prompt
            require_markers(path, markers, errors)
            validate_prompt_policy(path, version, errors)
    for prompt, markers in ROOT_ONLY_PROMPTS.items():
        path = prompt_root / prompt
        require_markers(path, markers, errors)
        validate_prompt_policy(path, version, errors)

    if source_mode:
        docs_to_check = [changelog_path]
        for language in LANGUAGES:
            readme = source_doc(root, "README", language)
            installation = source_doc(root, "INSTALLATION", language)
            require_markers(
                readme,
                ("4.1.0", "CHANGELOG.md", f"prompts/{language}/07_realign_sr_state_after_upgrade.md"),
                errors,
            )
            require_markers(installation, INSTALL_MARKERS, errors)
            if readme.exists():
                readme_text = readme.read_text(encoding="utf-8", errors="ignore")
                for historical_version in RELEASE_HISTORY:
                    if re.search(rf"^##+ .*{re.escape(historical_version)}", readme_text, re.MULTILINE):
                        errors.append(
                            f"{readme}: historical release {historical_version} must live in CHANGELOG.md, not a README heading"
                        )
            docs_to_check.extend((readme, installation))
        validate_links(root, docs_to_check, errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SR release documentation and localized public prompts")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    errors = audit(root)
    result = {"root": str(root.resolve()), "errors": errors, "ok": not errors}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif errors:
        print("SR release documentation errors:")
        for error in errors:
            print(f"- {error}")
    else:
        print("OK: SR release documentation and localized public prompts are coherent")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
