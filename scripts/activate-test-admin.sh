#!/usr/bin/env bash
# Run only in an authorized root session. Changes TEST Admin and its snippet.
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo 'root session required'; exit 1; }
[[ $# == 3 ]] || { echo 'usage: activate-test-admin.sh ARCHIVE SHA256 RELEASE_ID'; exit 1; }
archive=$1 checksum=$2 release_id=$3
[[ $checksum =~ ^[a-f0-9]{64}$ && $release_id =~ ^[a-z0-9-]+$ ]] || exit 1
base=/srv/gravitation-admin
snippet=/etc/nginx/snippets/gravitation-admin-test.conf
production_config=/etc/nginx/sites-available/club-gravitation.ru
[[ $(readlink -f "$base") == "$base" && -L $base/current && -f $snippet ]] || exit 1
previous=$(readlink -f "$base/current")
[[ $previous == "$base/releases/"* ]] || exit 1
release="$base/releases/$release_id"
[[ ! -e $release ]] || { echo 'release already exists'; exit 1; }
prod_before=$(sha256sum "$production_config" | cut -d' ' -f1)
mkdir "$release"
backup="$base/backups/$release_id"
install -d -m 700 "$backup"
install -m 600 "$archive" "$backup/package.tar.gz"
printf '%s  %s\n' "$checksum" "$backup/package.tar.gz" | sha256sum --check --status
tar -tzf "$backup/package.tar.gz" | while IFS= read -r entry; do
  case "$entry" in ./|./index.html|./assets/|./assets/css/|./assets/js/|./assets/css/site.css|./assets/css/admin.css|./assets/js/admin-auth.js|./assets/js/admin.js|./assets/js/admin-config.js) ;; *) echo 'unexpected archive path'; exit 1;; esac
done
tar -tvzf "$backup/package.tar.gz" | awk 'substr($0,1,1)!="-" && substr($0,1,1)!="d" {exit 1}'
cp "$snippet" "$backup/previous-test-nginx.conf"
printf '%s\n' "$previous" > "$backup/previous-release"
rollback() {
  cp "$backup/previous-test-nginx.conf" "$snippet"
  ln -s "$previous" "$base/.rollback-current"
  mv -Tf "$base/.rollback-current" "$base/current"
  nginx -t && systemctl reload nginx
}
trap rollback ERR
tar --extract --gzip --file "$backup/package.tar.gz" --directory "$release" --no-same-owner --no-same-permissions
python3 - <<'PY'
from pathlib import Path
p=Path('/etc/nginx/snippets/gravitation-admin-test.conf')
s=p.read_text()
assert 'location ^~ /admin-test/' in s and 'alias /srv/gravitation-admin/current/' in s
old="img-src 'self' data:;"
new="img-src 'self' data: https://storage.yandexcloud.net/gravitation-v5-test-photos-b1g4bdjb/;"
assert s.count(old)==1 or s.count(new)==1
p.write_text(s.replace(old,new))
PY
nginx -t
ln -s "$release" "$base/.new-current"
mv -Tf "$base/.new-current" "$base/current"
systemctl reload nginx
[[ $(sha256sum "$production_config" | cut -d' ' -f1) == "$prod_before" ]]
trap - ERR
printf 'TEST_ADMIN_ACTIVE=%s\n' "$release_id"
