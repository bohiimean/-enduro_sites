#!/usr/bin/env bash
set -euo pipefail
umask 077

cd /opt/enduro-site
key=/root/enduro-site-backup.key
destination=/var/backups/enduro-site
mkdir -p "$destination"
test -s "$key"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
compose=(docker compose -f docker-compose.production.yml)

encrypt() {
  openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -pass "file:$key" -out "$1.part"
  mv "$1.part" "$1"
}

"${compose[@]}" exec -T postgres pg_dump -U enduro -d enduro -Fc |
  encrypt "$destination/$stamp-db.dump.enc"
"${compose[@]}" exec -T backend tar -C /app/media -czf - . |
  encrypt "$destination/$stamp-media.tar.gz.enc"
tar -czf - .env docker-compose.production.yml nginx/default.conf |
  encrypt "$destination/$stamp-config.tar.gz.enc"

echo "Backup completed: $stamp"
