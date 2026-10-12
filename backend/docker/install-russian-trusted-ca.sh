#!/bin/sh
# MAX API (и др. *.max.ru) — сертификаты Russian Trusted CA; без них requests/curl падают на verify.
set -eu
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl
curl -fsSL https://gu-st.ru/content/lrv/russian_trusted_root_ca_pem.crt \
  -o /usr/local/share/ca-certificates/russian_trusted_root_ca.crt
curl -fsSL https://gu-st.ru/content/lrv/russian_trusted_sub_ca_pem.crt \
  -o /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt
update-ca-certificates
rm -rf /var/lib/apt/lists/*
