#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# Pre-deploy env checker for Cloud Run.
# Validates that every cloudrun-env/*.yaml has the keys each service
# actually reads from its Settings class, and that no value is blank.
#
# Usage:  bash infra/check-env.sh          (run from repo root)
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

ENV_DIR="infra/cloudrun-env"
SERVICES_DIR="services"
ERRORS=0
WARNINGS=0

red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

# ── Map: yaml filename → service directory name ──────────────────
declare -A YAML_TO_DIR=(
  ["cache-service"]="cache_service"
  ["code-service"]="code_service"
  ["db-service"]="db-service"
  ["user-profile-service"]="user_profile_service"
  ["revenue-service"]="revenue_service"
  ["ai-service"]="ai_service"
  ["notification-service"]="notification_service"
)

# ── Extract env var names from a settings/config.py ──────────────
# Looks for pydantic field definitions and os.getenv() calls.
extract_expected_keys() {
  local config_file="$1"
  {
    # Match lines like:  SOME_VAR: type = ...  or  SOME_VAR = Field(...)
    grep -oP '^\s+([A-Z][A-Z0-9_]+)\s*[:=]' "$config_file" \
      | sed 's/[[:space:]]*//g; s/[:=]$//' || true
    # Also match os.getenv("SOME_VAR", ...)
    grep -oP 'os\.getenv\(\s*["\x27]\K[A-Z][A-Z0-9_]+' "$config_file" || true
  } | sort -u
}

# ── Extract keys present in a YAML env file ──────────────────────
extract_yaml_keys() {
  local yaml_file="$1"
  grep -oP '^[A-Z][A-Z0-9_]+(?=:)' "$yaml_file" | sort -u
}

# ── Keys to skip during checks ───────────────────────────────────
# Computed/assembled internally — not real env vars:
INTERNAL_KEYS="DB_CONFIG REDIS_URL JWT_ALGORITHM SPATIAL_ANOMALY_PAYLOAD_DEBUG GOOGLE_APPLICATION_CREDENTIALS SERVICE_NAME"
# Pydantic metadata — not env vars:
INTERNAL_KEYS+=" APP_NAME APP_VERSION APP_DESCRIPTION"

is_internal() {
  local key="$1"
  for ik in $INTERNAL_KEYS; do
    [[ "$key" == "$ik" ]] && return 0
  done
  return 1
}

# Repo-wide keys we intentionally set in every YAML even if some
# services don't reference them in config.py. Not worth warning about.
REPO_WIDE_KEYS="SECRET_KEY INTERNAL_API_KEY FRONTEND_BASE_URL SERVICE_NAME ENV"

is_repo_wide() {
  local key="$1"
  for rk in $REPO_WIDE_KEYS; do
    [[ "$key" == "$rk" ]] && return 0
  done
  return 1
}

# ══════════════════════════════════════════════════════════════════
bold "╔══════════════════════════════════════════════════╗"
bold "║       Cloud Run Env Var Pre-Deploy Checker       ║"
bold "╚══════════════════════════════════════════════════╝"
echo

# ── Check each service ───────────────────────────────────────────
for yaml_stem in "${!YAML_TO_DIR[@]}"; do
  yaml_file="${ENV_DIR}/${yaml_stem}.yaml"
  svc_dir="${YAML_TO_DIR[$yaml_stem]}"
  config_file="${SERVICES_DIR}/${svc_dir}/app/core/config.py"

  bold "── ${yaml_stem} ──"

  # 1. YAML file exists?
  if [[ ! -f "$yaml_file" ]]; then
    red "  ✗ MISSING env file: ${yaml_file}"
    ERRORS=$((ERRORS + 1))
    echo
    continue
  fi

  # 2. Config file exists?
  if [[ ! -f "$config_file" ]]; then
    red "  ✗ MISSING config file: ${config_file}"
    ERRORS=$((ERRORS + 1))
    echo
    continue
  fi

  # 3. Extract keys
  mapfile -t expected < <(extract_expected_keys "$config_file")
  mapfile -t provided < <(extract_yaml_keys "$yaml_file")

  # Convert provided to associative array for O(1) lookup
  declare -A provided_set=()
  for k in "${provided[@]}"; do
    provided_set["$k"]=1
  done

  # Convert expected to associative array
  declare -A expected_set=()
  for k in "${expected[@]}"; do
    expected_set["$k"]=1
  done

  svc_ok=true

  # 4. Check for missing keys (expected by code but not in YAML)
  for key in "${expected[@]}"; do
    is_internal "$key" && continue
    if [[ -z "${provided_set[$key]+x}" ]]; then
      yellow "  ⚠ MISSING in YAML: ${key}"
      WARNINGS=$((WARNINGS + 1))
      svc_ok=false
    fi
  done

  # 5. Check for extra keys (in YAML but not expected by code)
  for key in "${provided[@]}"; do
    if [[ -z "${expected_set[$key]+x}" ]]; then
      is_repo_wide "$key" && continue
      yellow "  ⚠ EXTRA in YAML (not in config.py): ${key}"
      WARNINGS=$((WARNINGS + 1))
      svc_ok=false
    fi
  done

  # 6. Check for empty values
  while IFS= read -r line; do
    # Skip comments and blank lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    key="${line%%:*}"
    val="${line#*: }"
    # Strip quotes
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    if [[ -z "$val" ]]; then
      red "  ✗ EMPTY value: ${key}"
      ERRORS=$((ERRORS + 1))
      svc_ok=false
    fi
  done < "$yaml_file"

  if $svc_ok; then
    green "  ✓ All checks passed"
  fi

  # Cleanup associative arrays for next iteration
  unset provided_set
  unset expected_set
  echo
done

# ── Cross-service consistency checks ─────────────────────────────
bold "── Cross-service checks ──"

# Check that INTERNAL_API_KEY is the same across all services that have it
api_keys=()
api_key_files=()
for yaml_stem in "${!YAML_TO_DIR[@]}"; do
  yaml_file="${ENV_DIR}/${yaml_stem}.yaml"
  [[ ! -f "$yaml_file" ]] && continue
  val=$(grep -oP '^INTERNAL_API_KEY:\s*"\K[^"]+' "$yaml_file" 2>/dev/null || true)
  if [[ -n "$val" ]]; then
    api_keys+=("$val")
    api_key_files+=("$yaml_stem")
  fi
done
if [[ ${#api_keys[@]} -gt 1 ]]; then
  first="${api_keys[0]}"
  all_same=true
  for k in "${api_keys[@]}"; do
    [[ "$k" != "$first" ]] && all_same=false
  done
  if ! $all_same; then
    red "  ✗ INTERNAL_API_KEY mismatch across: ${api_key_files[*]}"
    ERRORS=$((ERRORS + 1))
  else
    green "  ✓ INTERNAL_API_KEY consistent across ${#api_keys[@]} services"
  fi
fi

# Check that SECRET_KEY is the same across all services that have it
secret_keys=()
secret_key_files=()
for yaml_stem in "${!YAML_TO_DIR[@]}"; do
  yaml_file="${ENV_DIR}/${yaml_stem}.yaml"
  [[ ! -f "$yaml_file" ]] && continue
  val=$(grep -oP '^SECRET_KEY:\s*"\K[^"]+' "$yaml_file" 2>/dev/null || true)
  if [[ -n "$val" ]]; then
    secret_keys+=("$val")
    secret_key_files+=("$yaml_stem")
  fi
done
if [[ ${#secret_keys[@]} -gt 1 ]]; then
  first="${secret_keys[0]}"
  all_same=true
  for k in "${secret_keys[@]}"; do
    [[ "$k" != "$first" ]] && all_same=false
  done
  if ! $all_same; then
    red "  ✗ SECRET_KEY mismatch across: ${secret_key_files[*]}"
    ERRORS=$((ERRORS + 1))
  else
    green "  ✓ SECRET_KEY consistent across ${#secret_keys[@]} services"
  fi
fi

# Check that inter-service URLs use the correct Cloud Run domain
for yaml_stem in "${!YAML_TO_DIR[@]}"; do
  yaml_file="${ENV_DIR}/${yaml_stem}.yaml"
  [[ ! -f "$yaml_file" ]] && continue
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    key="${line%%:*}"
    if [[ "$key" =~ _URL$ ]] && [[ "$key" != "FRONTEND_BASE_URL" ]] && [[ "$key" != "PAYSTACK_BASE_URL" ]] && [[ "$key" != "PAYSTACK_CALLBACK_URL" ]] && [[ "$key" != "OPENAI_BASE_URL" ]] && [[ "$key" != "REDIS_URL" ]]; then
      val="${line#*: }"
      val="${val%\"}"
      val="${val#\"}"
      if [[ -n "$val" ]] && [[ ! "$val" =~ \.run\.app ]]; then
        yellow "  ⚠ ${yaml_stem}: ${key} doesn't point to *.run.app — got: ${val}"
        WARNINGS=$((WARNINGS + 1))
      fi
    fi
  done < "$yaml_file"
done
green "  ✓ Inter-service URL check complete"

echo
bold "══════════════════════════════════════════════════"
if [[ $ERRORS -gt 0 ]]; then
  red "  ${ERRORS} error(s), ${WARNINGS} warning(s) — FIX BEFORE DEPLOYING"
  exit 1
elif [[ $WARNINGS -gt 0 ]]; then
  yellow "  0 errors, ${WARNINGS} warning(s) — review before deploying"
  exit 0
else
  green "  All checks passed ✓"
  exit 0
fi
