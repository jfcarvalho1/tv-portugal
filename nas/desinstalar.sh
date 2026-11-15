#!/usr/bin/env bash
# Retira do NAS e do Jellyfin tudo o que o instalador TV/Rádios pôs. Não mexe em mais nada.
# Uso: curl -fsSL https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/nas/desinstalar.sh | sudo bash
set -u
if [ "$(id -u)" -ne 0 ]; then echo "Corre com sudo."; exit 1; fi
echo "== 1/3  Retirar do Jellyfin"
curl -fsSL https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/nas/desinstalar.py -o /tmp/desinstalar-tv.py \
  && python3 /tmp/desinstalar-tv.py; rm -f /tmp/desinstalar-tv.py
echo "== 2/3  Parar e apagar os serviços"
for u in tv-radios-proxy.service tv-radios-nas.timer tv-radios-nas.service tv-radios-programas.timer \
         tv-radios-programas.service tv-radios-actualizar.timer tv-radios-actualizar.service; do
  systemctl disable --now "$u" >/dev/null 2>&1
  rm -f "/etc/systemd/system/$u"
done
systemctl daemon-reload
echo "   ✔ serviços retirados"
echo "== 3/3  Apagar ficheiros"
rm -rf /opt/tv-radios-nas /opt/tv-radios
echo "   ✔ /opt/tv-radios-nas e /opt/tv-radios apagados"
echo
echo "FEITO. O NAS e o Jellyfin ficaram como estavam antes (filmes, séries e música intactos)."
