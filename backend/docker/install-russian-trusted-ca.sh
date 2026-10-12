#!/bin/sh
# Bootstrap образа backend: зеркало apt (Reg.ru и др. RU VPS — deb.debian.org/Fastly часто таймаут),
# Russian Trusted CA для MAX API (*.max.ru), ffmpeg.
set -eu

use_yandex_debian_mirror() {
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then
    sed -i \
      -e 's|http://deb\.debian\.org/debian-security|http://mirror.yandex.ru/debian-security|g' \
      -e 's|http://deb\.debian\.org/debian|http://mirror.yandex.ru/debian|g' \
      /etc/apt/sources.list.d/debian.sources
  fi
  if [ -f /etc/apt/sources.list ]; then
    sed -i \
      -e 's|deb\.debian\.org/debian-security|mirror.yandex.ru/debian-security|g' \
      -e 's|deb\.debian\.org/debian|mirror.yandex.ru/debian|g' \
      /etc/apt/sources.list
  fi
}

use_yandex_debian_mirror

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl ffmpeg

curl -fsSL https://gu-st.ru/content/lrv/russian_trusted_root_ca_pem.crt \
  -o /usr/local/share/ca-certificates/russian_trusted_root_ca.crt
curl -fsSL https://gu-st.ru/content/lrv/russian_trusted_sub_ca_pem.crt \
  -o /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt
update-ca-certificates

rm -rf /var/lib/apt/lists/*
