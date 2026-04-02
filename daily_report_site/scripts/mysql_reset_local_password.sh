#!/usr/bin/env bash
# Reset local MySQL root + app user for Oracle macOS DMG install (skip-grant-tables).
# Usage (in Terminal on your Mac):
#   cd /path/to/daily_report_site
#   chmod +x scripts/mysql_reset_local_password.sh
#   sudo ./scripts/mysql_reset_local_password.sh 'YourNewPassword'
#
# Optional: MYSQL_BASEDIR=/custom/path sudo ./scripts/mysql_reset_local_password.sh '...'
set -euo pipefail

BASEDIR="${MYSQL_BASEDIR:-/usr/local/mysql}"
BIN="${BASEDIR}/bin"
DATADIR="${BASEDIR}/data"
# Oracle macOS DMG uses LaunchDaemon + mysqld.local.pid; mysql.server looks for hostname.pid only.
ORACLE_LAUNCHD_PLIST="/Library/LaunchDaemons/com.oracle.oss.mysql.mysqld.plist"
NEW_PW="${1:?Usage: sudo $0 'NEW_PASSWORD'}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "This script must be run as root. Example:"
  echo "  sudo $0 '$NEW_PW'"
  exit 1
fi

stop_oracle_mysql() {
  echo "Stopping MySQL (Oracle installer uses LaunchDaemon + ${DATADIR}/mysqld.local.pid)..."
  if [[ -f "$ORACLE_LAUNCHD_PLIST" ]]; then
    # KeepAlive in plist would respawn mysqld if we only kill the process.
    launchctl bootout system "$ORACLE_LAUNCHD_PLIST" 2>/dev/null \
      || launchctl unload -w "$ORACLE_LAUNCHD_PLIST" 2>/dev/null \
      || true
  fi
  "${BASEDIR}/support-files/mysql.server" stop 2>/dev/null || true
  sleep 2
  for pidfile in "${DATADIR}/mysqld.local.pid" "${DATADIR}/$(hostname).pid" "${DATADIR}/$(hostname -s).pid"; do
    if [[ -f "$pidfile" ]]; then
      pid="$(cat "$pidfile" 2>/dev/null || true)"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "Sending SIGTERM to mysqld pid $pid ($pidfile)..."
        kill "$pid" 2>/dev/null || true
      fi
    fi
  done
  sleep 2
  if pgrep -f "${BASEDIR}/bin/mysqld" >/dev/null 2>&1; then
    echo "Forcing remaining mysqld to exit..."
    pkill -f "${BASEDIR}/bin/mysqld" 2>/dev/null || true
    sleep 2
  fi
  local n=0
  while lsof -nP -iTCP:3306 -sTCP:LISTEN >/dev/null 2>&1; do
    echo "Waiting for port 3306 to be free..."
    sleep 1
    n=$((n + 1))
    if [[ $n -gt 90 ]]; then
      echo "Port 3306 still busy. Close MySQL Workbench/other clients, then re-run this script." >&2
      exit 1
    fi
  done
}

start_oracle_mysql_normal() {
  if [[ -f "$ORACLE_LAUNCHD_PLIST" ]]; then
    echo "Starting MySQL via LaunchDaemon..."
    launchctl bootstrap system "$ORACLE_LAUNCHD_PLIST" 2>/dev/null \
      || launchctl load -w "$ORACLE_LAUNCHD_PLIST" 2>/dev/null \
      || true
    sleep 2
  fi
  if pgrep -f "${BASEDIR}/bin/mysqld" >/dev/null 2>&1; then
    return 0
  fi
  echo "Falling back to mysql.server start..."
  "${BASEDIR}/support-files/mysql.server" start
}

SQL_FILE="$(mktemp /tmp/mysql_reset_dr_XXXXXX.sql)"
cleanup() { rm -f "$SQL_FILE"; }
trap cleanup EXIT

# Escape single quotes for MySQL string literals
esc_sql() { printf '%s' "$1" | sed "s/'/''/g"; }
PW_ESC="$(esc_sql "$NEW_PW")"

cat >"$SQL_FILE" <<EOF
FLUSH PRIVILEGES;
ALTER USER 'root'@'localhost' IDENTIFIED BY '${PW_ESC}';
CREATE DATABASE IF NOT EXISTS \`daily_report\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'fangyi'@'localhost' IDENTIFIED BY '${PW_ESC}';
ALTER USER 'fangyi'@'localhost' IDENTIFIED BY '${PW_ESC}';
CREATE USER IF NOT EXISTS 'fangyi'@'127.0.0.1' IDENTIFIED BY '${PW_ESC}';
ALTER USER 'fangyi'@'127.0.0.1' IDENTIFIED BY '${PW_ESC}';
GRANT ALL PRIVILEGES ON \`daily_report\`.* TO 'fangyi'@'localhost';
GRANT ALL PRIVILEGES ON \`daily_report\`.* TO 'fangyi'@'127.0.0.1';
FLUSH PRIVILEGES;
EOF

stop_oracle_mysql

echo "Starting MySQL with --skip-networking --skip-grant-tables..."
"${BASEDIR}/support-files/mysql.server" start --skip-networking --skip-grant-tables

echo "Waiting for server..."
for _ in $(seq 1 45); do
  if "${BIN}/mysql" -u root -e "SELECT 1" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! "${BIN}/mysql" -u root -e "SELECT 1" >/dev/null 2>&1; then
  echo "MySQL did not become ready. Check ${DATADIR}/mysqld.local.err" >&2
  exit 1
fi

echo "Applying SQL..."
"${BIN}/mysql" -u root <"$SQL_FILE"

echo "Restarting MySQL normally..."
"${BASEDIR}/support-files/mysql.server" stop || true
sleep 3
stop_oracle_mysql
start_oracle_mysql_normal

for _ in $(seq 1 45); do
  if "${BIN}/mysql" -u fangyi -p"${NEW_PW}" -h 127.0.0.1 -e "SELECT 1" >/dev/null 2>&1; then
    echo "Verified login as fangyi@127.0.0.1."
    break
  fi
  sleep 1
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  echo "Updating ${PROJECT_ROOT}/.env MYSQL_PASSWORD..."
  python3 "${SCRIPT_DIR}/update_env_mysql_password.py" "${PROJECT_ROOT}/.env" "${NEW_PW}"
else
  echo "No ${PROJECT_ROOT}/.env found; set MYSQL_PASSWORD yourself to match the password you used."
fi

echo "Done. Next: cd ${PROJECT_ROOT} && source .venv/bin/activate && python manage.py migrate"
