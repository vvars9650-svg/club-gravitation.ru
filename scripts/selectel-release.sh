#!/usr/bin/env bash
set -Eeuo pipefail

BASE=/srv/gravitation
RELEASES="$BASE/releases"
SHARED="$BASE/shared"
CURRENT="$BASE/current"
PREVIOUS_FILE="$SHARED/previous-release"
LOCK_DIR="$SHARED/deploy.lock"

operation="${1:-}"
release_id="${2:-}"
checksum="${3:-}"
archive=''
staging=''
temporary_link=''

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

validate_release_id() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$ ]] || fail 'invalid release ID'
}

cleanup() {
  local exit_status=$?
  trap - EXIT INT TERM
  set +e
  if [[ -n "$temporary_link" ]]; then
    rm -f -- "$temporary_link"
  fi
  if [[ -n "$staging" ]]; then
    rm -rf -- "$staging"
  fi
  if [[ -n "$archive" ]]; then
    rm -f -- "$archive"
  fi
  rmdir -- "$LOCK_DIR" 2>/dev/null || true
  exit "$exit_status"
}

acquire_lock() {
  mkdir -- "$LOCK_DIR" 2>/dev/null || fail 'another release operation is in progress'
  trap cleanup EXIT INT TERM
}

verify_release_directory() {
  local directory="$1"
  [[ -d "$directory" ]] || fail "release directory does not exist: $directory"
  [[ -f "$directory/index.html" ]] || fail 'release is missing index.html'

  if find "$directory" -type l -print -quit | grep -q .; then
    fail 'release must not contain symlinks'
  fi
  if find "$directory" -type f \( \
    -name '*.py' -o -name '*.pyc' -o -name '*.yaml' -o -name '*.yml' -o \
    -name '*.json' -o -name '*.md' -o -name '*.sh' \
  \) -print -quit | grep -q .; then
    fail 'release contains a forbidden backend, config, or source file'
  fi

  if [[ "$directory" == "$RELEASES/bootstrap-blocked" ]]; then
    grep -Fq 'Сайт временно недоступен' "$directory/index.html" \
      || fail 'bootstrap-blocked placeholder text is missing'
    if grep -Eiq '<script(?:[[:space:]>])' "$directory/index.html"; then
      fail 'bootstrap-blocked placeholder must not execute scripts'
    fi
    return
  fi

  [[ -f "$directory/apply/index.html" ]] || fail 'release is missing apply/index.html'
  [[ -f "$directory/admin/index.html" ]] || fail 'release is missing safe admin placeholder'
  [[ -f "$directory/assets/js/apply.js" ]] || fail 'release is missing assets/js/apply.js'
  grep -Fq "PUBLIC_BLOCKED" "$directory/assets/js/apply.js" || fail 'PUBLIC_BLOCKED guard is missing'
}

record_current_as_previous() {
  local resolved previous_id temporary_previous
  resolved="$(readlink -f -- "$CURRENT")" || fail 'current symlink cannot be resolved'
  [[ "$resolved" == "$RELEASES/"* ]] || fail 'current points outside the releases directory'
  previous_id="${resolved#"$RELEASES/"}"
  validate_release_id "$previous_id"
  [[ "$resolved" == "$RELEASES/$previous_id" ]] || fail 'current must point to a direct release child'
  [[ -d "$resolved" ]] || fail 'current release directory does not exist'

  temporary_previous="$SHARED/.previous-release.$$"
  printf '%s\n' "$previous_id" > "$temporary_previous"
  chmod 600 "$temporary_previous"
  mv -f -- "$temporary_previous" "$PREVIOUS_FILE"
}

switch_current() {
  local target="$1"
  temporary_link="$BASE/.current-${release_id}.$$"
  ln -s -- "$target" "$temporary_link"
  mv -T -- "$temporary_link" "$CURRENT"
  temporary_link=''
}

deploy_release() {
  validate_release_id "$release_id"
  [[ "$checksum" =~ ^[a-f0-9]{64}$ ]] || fail 'invalid SHA-256 checksum'

  archive="$SHARED/incoming/${release_id}.tar.gz"
  staging="$RELEASES/.incoming-${release_id}.$$"
  local final="$RELEASES/$release_id"

  [[ -f "$archive" ]] || fail 'uploaded archive not found'
  [[ ! -e "$final" ]] || fail 'release directory already exists'
  printf '%s  %s\n' "$checksum" "$archive" | sha256sum --check --status - \
    || fail 'uploaded archive checksum mismatch'

  while IFS= read -r member; do
    [[ -n "$member" ]] || fail 'archive contains an empty member name'
    [[ "$member" != /* ]] || fail 'archive contains an absolute path'
    [[ "$member" != '..' && "$member" != ../* && "$member" != */../* && "$member" != */.. ]] \
      || fail 'archive contains path traversal'
  done < <(tar -tzf "$archive")
  tar -tvzf "$archive" | awk 'substr($1, 1, 1) != "-" && substr($1, 1, 1) != "d" {exit 1}' \
    || fail 'archive contains a non-regular entry'

  mkdir -- "$staging"
  tar --extract --gzip --file "$archive" --directory "$staging" \
    --no-same-owner --no-same-permissions
  find "$staging" -type d -exec chmod 755 {} +
  find "$staging" -type f -exec chmod 644 {} +
  verify_release_directory "$staging"

  mv -- "$staging" "$final"
  staging=''
  record_current_as_previous
  switch_current "$final"
}

rollback_release() {
  if [[ -z "$release_id" ]]; then
    [[ -f "$PREVIOUS_FILE" ]] || fail 'previous release is not recorded'
    IFS= read -r release_id < "$PREVIOUS_FILE"
  fi
  validate_release_id "$release_id"

  local target="$RELEASES/$release_id"
  local current_resolved
  verify_release_directory "$target"
  current_resolved="$(readlink -f -- "$CURRENT")" || fail 'current symlink cannot be resolved'
  [[ "$current_resolved" != "$target" ]] || fail 'requested release is already current'

  record_current_as_previous
  switch_current "$target"
}

[[ "$operation" == 'deploy' || "$operation" == 'rollback' ]] || fail 'operation must be deploy or rollback'
acquire_lock

if [[ "$operation" == 'deploy' ]]; then
  deploy_release
else
  rollback_release
fi
