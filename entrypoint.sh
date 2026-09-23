#!/bin/bash
set -e

# Base command
CMD="rsmetacheck"

# Handle required input
if [ -n "$INPUT_INPUT" ]; then
  # Note: Do not quote $INPUT_INPUT here in case multiple URLs are passed as spaces
  CMD="$CMD --input $INPUT_INPUT"
else
  echo "Error: The 'input' argument is required and $GITHUB_REPOSITORY environment variable is not set. Please provide an input or run this action within a GitHub repository context."
  exit 1
fi

# Handle boolean flags
if [ "$INPUT_SKIP_SOMEF" = "true" ]; then
  CMD="$CMD --skip-somef"
fi

if [ "$INPUT_GENERATE_CODEMETA" = "true" ]; then
  CMD="$CMD --generate-codemeta"
fi

if [ "$INPUT_VERBOSE" = "true" ]; then
  CMD="$CMD --verbose"
fi

# Handle parameters with values
if [ -n "$INPUT_PITFALLS_OUTPUT" ]; then
  CMD="$CMD --pitfalls-output \"$INPUT_PITFALLS_OUTPUT\""
fi

if [ -n "$INPUT_SOMEF_OUTPUT" ]; then
  CMD="$CMD --somef-output \"$INPUT_SOMEF_OUTPUT\""
fi

if [ -n "$INPUT_ANALYSIS_OUTPUT" ]; then
  CMD="$CMD --analysis-output \"$INPUT_ANALYSIS_OUTPUT\""
fi

if [ -n "$INPUT_THRESHOLD" ]; then
  CMD="$CMD --threshold \"$INPUT_THRESHOLD\""
fi

if [ -n "$INPUT_BRANCH" ]; then
  CMD="$CMD --branch \"$INPUT_BRANCH\""
fi

if [ -n "$INPUT_CONFIG" ]; then
  CMD="$CMD --config \"$INPUT_CONFIG\""
fi

if [ -n "$INPUT_CONFIG_PROFILE" ]; then
  CMD="$CMD --config-profile \"$INPUT_CONFIG_PROFILE\""
fi

# Optionally configure SoMEF with a GitHub token to raise API rate limits
if [ -n "$INPUT_GITHUB_TOKEN" ]; then
  echo "GitHub token provided: configuring SoMEF with higher API rate limits..."
  somef configure -a
  python3 - "$INPUT_GITHUB_TOKEN" <<'PY'
import json
import os
import sys
from pathlib import Path

token = sys.argv[1]
cfg = Path.home() / ".somef" / "config.json"

with cfg.open() as fh:
    data = json.load(fh)

data["GitHubAuthorization"] = "token " + token

os.makedirs(str(cfg.parent), exist_ok=True)
with cfg.open("w") as fh:
    os.chmod(str(cfg.parent), 0o700)
    cfg.chmod(0o600)
    json.dump(data, fh)
PY
fi

echo "Executing RsMetaCheck command:"
echo "$CMD"

RSMETA_EXIT=0
eval "$CMD" || RSMETA_EXIT=$?

# Run post-processing for GitHub Actions output
if [ -n "$GITHUB_STEP_SUMMARY" ] || [ -n "$GITHUB_OUTPUT" ]; then
  echo "Generating GitHub Actions output..."
  POST_EXIT=0
  python3 /postprocess.py || POST_EXIT=$?
else
  POST_EXIT=0
fi

# Use post-process exit code (1 = pitfalls found) if it applies,
# otherwise fall back to the rsmetacheck exit code
if [ "$POST_EXIT" -ne 0 ]; then
  exit "$POST_EXIT"
fi
exit "$RSMETA_EXIT"
