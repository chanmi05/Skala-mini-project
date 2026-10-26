#!/bin/sh
set -eu

# Reuse workplace/.env without a second copy of the database password.
: "${DB_PASSWORD:?Set DB_PASSWORD in workplace/.env}"
export MARIADB_PASSWORD="$DB_PASSWORD"
exec docker-entrypoint.sh "$@"
