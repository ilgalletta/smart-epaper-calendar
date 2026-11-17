#!/usr/bin/env bash
# ==============================================================================
# Smart E-Paper Calendar - Idempotent Raspberry Pi OS Lite Setup Script
# ==============================================================================
# Enables SPI & I2C, installs system dependencies and Python virtualenv,
# installs Waveshare 7.5" (B) V2 driver support, and configures systemd services:
#   - smart-calendar-web.service   (LAN FastAPI Web UI on port 8080)
#   - smart-calendar-sync.service  (One-shot wake-sync-render-display cycle)
#
# Usage:
#   sudo bash scripts/setup_pi.sh [--enable-timer]
# ==============================================================================

set -euo pipefail

ENABLE_TIMER=false
for arg in "$@"; do
  case "$arg" in
    --enable-timer)
      ENABLE_TIMER=true
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Usage: sudo bash $0 [--enable-timer]" >&2
      exit 1
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run this script with sudo: sudo bash $0" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_USER="${SUDO_USER:-$(stat -c '%U' "${PROJECT_DIR}")}"
APP_GROUP="$(id -gn "${APP_USER}")"
VENV_DIR="${PROJECT_DIR}/.venv"
WAVESHARE_DIR="/opt/waveshare-epaper"

echo "==> Setting up Smart E-Paper Calendar"
echo "    Project directory : ${PROJECT_DIR}"
echo "    Service user      : ${APP_USER}:${APP_GROUP}"

# ------------------------------------------------------------------------------
# 1. Enable SPI and I2C (idempotent)
# ------------------------------------------------------------------------------
echo "==> Enabling SPI and I2C interfaces..."
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_spi 0 || true
  raspi-config nonint do_i2c 0 || true
fi

BOOT_CFG=""
if [[ -f /boot/firmware/config.txt ]]; then
  BOOT_CFG="/boot/firmware/config.txt"
elif [[ -f /boot/config.txt ]]; then
  BOOT_CFG="/boot/config.txt"
fi

if [[ -n "${BOOT_CFG}" ]]; then
  if ! grep -Eq '^\s*dtparam=spi=on' "${BOOT_CFG}"; then
    echo "dtparam=spi=on" >> "${BOOT_CFG}"
  fi
  if ! grep -Eq '^\s*dtparam=i2c_arm=on' "${BOOT_CFG}"; then
    echo "dtparam=i2c_arm=on" >> "${BOOT_CFG}"
  fi
fi

# Ensure service user has SPI, I2C, and GPIO group access
for grp in spi i2c gpio; do
  if getent group "${grp}" >/dev/null 2>&1; then
    usermod -aG "${grp}" "${APP_USER}" || true
  fi
done

# ------------------------------------------------------------------------------
# 2. Install system packages (idempotent)
# ------------------------------------------------------------------------------
echo "==> Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

BASE_PKGS=(
  python3
  python3-venv
  python3-pip
  python3-dev
  python3-spidev
  i2c-tools
  git
  libjpeg-dev
  zlib1g-dev
  libfreetype6-dev
  libopenjp2-7
  fonts-dejavu-core
  fonts-liberation
)

apt-get install -y --no-install-recommends "${BASE_PKGS[@]}"

# Install GPIO & TIFF packages depending on Debian/Pi OS release (Bookworm vs Bullseye)
for opt_pkg in python3-lgpio python3-rpi.gpio libtiff6 libtiff5; do
  if apt-cache show "${opt_pkg}" >/dev/null 2>&1; then
    apt-get install -y --no-install-recommends "${opt_pkg}" || true
  fi
done

# ------------------------------------------------------------------------------
# 3. Create Python virtual environment & install dependencies (idempotent)
# ------------------------------------------------------------------------------
echo "==> Configuring Python virtual environment at ${VENV_DIR}..."
if [[ ! -d "${VENV_DIR}" ]]; then
  sudo -u "${APP_USER}" python3 -m venv --system-site-packages "${VENV_DIR}"
fi

sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel setuptools -q
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${PROJECT_DIR}/requirements.txt" -q

# Install hardware SPI/GPIO Python packages cleanly inside venv if needed
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install spidev gpiozero -q || true

# Install Waveshare e-Paper Python library if not already importable
if ! "${VENV_DIR}/bin/python" -c "from waveshare_epd import epd7in5b_V2" >/dev/null 2>&1; then
  echo "==> Installing Waveshare e-Paper Python library..."
  if [[ ! -d "${WAVESHARE_DIR}/.git" ]]; then
    git clone --depth 1 https://github.com/waveshareteam/e-Paper.git "${WAVESHARE_DIR}"
  else
    git -C "${WAVESHARE_DIR}" pull --ff-only || true
  fi
  if [[ -d "${WAVESHARE_DIR}/RaspberryPi_JetsonNano/python" ]]; then
    "${VENV_DIR}/bin/pip" install "${WAVESHARE_DIR}/RaspberryPi_JetsonNano/python" -q
  fi
fi

# ------------------------------------------------------------------------------
# 4. Initialize directories & default config (idempotent)
# ------------------------------------------------------------------------------
echo "==> Ensuring data/logs directories and config.yaml..."
mkdir -p "${PROJECT_DIR}/data" "${PROJECT_DIR}/logs"
if [[ ! -f "${PROJECT_DIR}/config.yaml" && -f "${PROJECT_DIR}/config.example.yaml" ]]; then
  cp "${PROJECT_DIR}/config.example.yaml" "${PROJECT_DIR}/config.yaml"
  echo "    Created ${PROJECT_DIR}/config.yaml from config.example.yaml"
fi
chown -R "${APP_USER}:${APP_GROUP}" "${PROJECT_DIR}/data" "${PROJECT_DIR}/logs" "${VENV_DIR}"
if [[ -f "${PROJECT_DIR}/config.yaml" ]]; then
  chown "${APP_USER}:${APP_GROUP}" "${PROJECT_DIR}/config.yaml"
fi

# ------------------------------------------------------------------------------
# 5. Install systemd service units (idempotent)
# ------------------------------------------------------------------------------
echo "==> Installing systemd units..."

cat > /etc/systemd/system/smart-calendar-web.service <<EOF
[Unit]
Description=Smart E-Paper Calendar LAN Web UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${PROJECT_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=EPAPER_PROJECT_ROOT=${PROJECT_DIR}
ExecStart=${VENV_DIR}/bin/python -m src.main --web
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/smart-calendar-sync.service <<EOF
[Unit]
Description=Smart E-Paper Calendar One-Shot Sync & Display Refresh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${PROJECT_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=EPAPER_PROJECT_ROOT=${PROJECT_DIR}
ExecStart=${VENV_DIR}/bin/python -m src.main --sync-once

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/smart-calendar-sync.timer <<EOF
[Unit]
Description=Periodic Smart E-Paper Calendar Refresh Timer

[Timer]
OnBootSec=1min
OnUnitActiveSec=60min
Unit=smart-calendar-sync.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable smart-calendar-web.service
systemctl enable smart-calendar-sync.service

if [[ "${ENABLE_TIMER}" == "true" ]]; then
  systemctl enable --now smart-calendar-sync.timer
  echo "==> Enabled smart-calendar-sync.timer (hourly refresh)."
fi

echo "==> Setup complete!"
echo "    - Edit ${PROJECT_DIR}/config.yaml with your calendar, weather, and Telegram settings."
echo "    - Test a one-shot sync: ${VENV_DIR}/bin/python -m src.main --sync-once"
echo "    - Start Web UI now:     sudo systemctl start smart-calendar-web.service"
echo "    - Reboot recommended if SPI/I2C was newly enabled: sudo reboot"
