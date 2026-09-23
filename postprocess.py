#!/usr/bin/env python3
"""Post-process RsMetaCheck outputs for GitHub Actions."""

import json
import os
import sys
from pathlib import Path


def get_env_path(env_var: str, default: str) -> Path:
    path_str = os.environ.get(env_var) or default
    return Path(path_str)


def main() -> int:
    analysis_path = get_env_path("INPUT_ANALYSIS_OUTPUT", "./analysis_results.json")
    pitfalls_dir = get_env_path("INPUT_PITFALLS_OUTPUT", "./pitfalls_outputs")
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    github_output_path = os.environ.get("GITHUB_OUTPUT")

    if not analysis_path.exists():
        print(f"::warning::Analysis results not found at {analysis_path}")
        return 0
    if not pitfalls_dir.is_dir():
        print(f"::warning::Pitfalls output directory not found at {pitfalls_dir}")
        return 0

    with open(analysis_path) as f:
        data = json.load(f)

    summary = data.get("summary", {})
    total_pitfalls = summary.get("total_pitfalls_detected", 0)
    total_warnings = summary.get("total_warnings_detected", 0)
    repo_map = summary.get("evaluated_repositories", {})
    pitfall_entries = data.get("pitfalls & warnings", [])

    pitfalls_found = []
    warnings_found = []
    for entry in pitfall_entries:
        code = entry.get("pitfall_code") or entry.get("warning_code", "")
        desc = entry.get("pitfall_desc") or entry.get("warning_desc", "")
        entry["pitfall_code"] = code
        entry["pitfall_desc"] = desc
        count = entry.get("count", 0)
        if count == 0:
            continue
        if code.startswith("P"):
            pitfalls_found.append(entry)
        elif code.startswith("W"):
            warnings_found.append(entry)

    per_repo_checks = {}
    for jsonld_file in sorted(pitfalls_dir.glob("*_pitfalls.jsonld")):
        with open(jsonld_file) as f:
            doc = json.load(f)
        software = doc.get("assessedSoftware", {})
        repo_name = software.get("name", jsonld_file.stem)
        checks = doc.get("checks", [])
        detected = []
        for check in checks:
            if check.get("output") == "true":
                indicator = check.get("assessesIndicator", {})
                code_url = indicator.get("@id", "")
                code = code_url.rstrip("/").rsplit("#", 1)[-1] if "#" in code_url else ""
                detected.append({
                    "code": code,
                    "evidence": check.get("evidence", ""),
                    "suggestion": check.get("suggestion", ""),
                })
        if detected:
            per_repo_checks[repo_name] = {
                "url": software.get("url", ""),
                "commit": software.get("commit_id", ""),
                "detected": detected,
            }

    suggestion_map = {}
    evidence_map = {}
    for info in per_repo_checks.values():
        for d in info.get("detected", []):
            code = d.get("code", "")
            suggestion = d.get("suggestion", "")
            evidence = d.get("evidence", "")
            if code and suggestion and code not in suggestion_map:
                suggestion_map[code] = suggestion
            if code and evidence and code not in evidence_map:
                evidence_map[code] = evidence

    if step_summary_path:
        _write_step_summary(
            step_summary_path, total_pitfalls, total_warnings,
            repo_map, pitfalls_found, warnings_found, per_repo_checks, suggestion_map, evidence_map,
        )

    if github_output_path:
        _set_github_output(github_output_path, total_pitfalls, total_warnings, pitfalls_found, warnings_found)

    for p in pitfalls_found:
        url = p.get("pitfall", f"https://w3id.org/rsmetacheck/catalog/#{p.get('pitfall_code','')}")
        print(f"::error title=RsMetaCheck {p.get('pitfall_code','')}::{p.get('pitfall_desc','')} | More info: {url}")
    for w in warnings_found:
        url = w.get("pitfall", f"https://w3id.org/rsmetacheck/catalog/#{w.get('pitfall_code','')}")
        print(f"::warning title=RsMetaCheck {w.get('pitfall_code','')}::{w.get('pitfall_desc','')} | More info: {url}")

    return 1 if pitfalls_found else 0


def _write_step_summary(path, total_pitfalls, total_warnings,
                         repo_map, pitfalls_found, warnings_found, per_repo_checks, suggestion_map, evidence_map):
    with open(path, "a") as f:
        f.write("## RsMetaCheck Results\n\n")

        if total_pitfalls > 0:
            status_icon = "❌"
            status_text = "Pitfalls Detected"
        elif total_warnings > 0:
            status_icon = "⚠️"
            status_text = "Warnings Detected"
        else:
            status_icon = "✅"
            status_text = "Passed"

        f.write(f"| Status | Pitfalls | Warnings |\n")
        f.write(f"|--------|----------|----------|\n")
        f.write(f"| {status_icon} **{status_text}** | {total_pitfalls} | {total_warnings} |\n\n")

        if repo_map:
            f.write("### Repositories Analyzed\n\n")
            f.write("| Repository | URL |\n")
            f.write("|------------|-----|\n")
            for name, info in repo_map.items():
                url = info.get("url", "")
                f.write(f"| {name} | [{url}]({url}) |\n")
            f.write("\n")

        if pitfalls_found:
            f.write("### Detected Pitfalls\n\n")
            f.write("| Code | Description | Evidence | Suggestion |\n")
            f.write("|------|-------------|----------|------------|\n")
            for p in pitfalls_found:
                code = p.get("pitfall_code", "")
                desc = p.get("pitfall_desc", "")
                evidence = evidence_map.get(code, "").replace("\n", " ").replace("|", "\\|")
                suggestion = suggestion_map.get(code, "")
                suggestion = suggestion.replace("\n", " ").replace("|", "\\|")
                f.write(f"| {code} | {desc} | {evidence} | {suggestion} |\n")
            f.write("\n")

        if warnings_found:
            f.write("### Detected Warnings\n\n")
            f.write("| Code | Description | Evidence | Suggestion |\n")
            f.write("|------|-------------|----------|------------|\n")
            for w in warnings_found:
                code = w.get("pitfall_code", "")
                desc = w.get("pitfall_desc", "")
                evidence = evidence_map.get(code, "").replace("\n", " ").replace("|", "\\|")
                suggestion = suggestion_map.get(code, "")
                suggestion = suggestion.replace("\n", " ").replace("|", "\\|")
                f.write(f"| {code} | {desc} | {evidence} | {suggestion} |\n")
            f.write("\n")

        if per_repo_checks:
            f.write("### Per-Repository Details\n\n")
            for repo_name, info in per_repo_checks.items():
                repo_url = info.get("url", "")
                commit = info.get("commit", "")
                display_name = f"[{repo_name}]({repo_url})" if repo_url else repo_name
                f.write(f"<details>\n")
                f.write(f"<summary>{display_name} — {len(info['detected'])} issue(s)</summary>\n\n")
                f.write("| Code | Evidence | Suggestion |\n")
                f.write("|------|----------|------------|\n")
                for d in info["detected"]:
                    evidence = d.get("evidence", "").replace("\n", " ").replace("|", "\\|")
                    suggestion = d.get("suggestion", "").replace("\n", " ").replace("|", "\\|")
                    f.write(f"| {d['code']} | {evidence} | {suggestion} |\n")
                f.write(f"\n</details>\n\n")

        if not pitfalls_found and not warnings_found:
            f.write("No pitfalls or warnings detected. ✅\n\n")


def _set_github_output(path, total_pitfalls, total_warnings, pitfalls_found, warnings_found):
    with open(path, "a") as f:
        f.write(f"has_pitfalls={'true' if (total_pitfalls > 0 or total_warnings > 0) else 'false'}\n")
        f.write(f"total_pitfalls={total_pitfalls}\n")
        f.write(f"total_warnings={total_warnings}\n")
        f.write(f"pitfalls_found={json.dumps([p.get('pitfall_code','') for p in pitfalls_found])}\n")
        f.write(f"warnings_found={json.dumps([w.get('pitfall_code','') for w in warnings_found])}\n")


if __name__ == "__main__":
    sys.exit(main())
