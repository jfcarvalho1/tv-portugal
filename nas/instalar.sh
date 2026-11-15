#!/usr/bin/env bash
# =====================================================================
#  TV e RÁDIOS no Jellyfin do NAS  —  instalador (Debian)
#  Uso (no NAS):
#    curl -fsSL https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/nas/instalar.sh | sudo bash
#  - TV em directo: o Jellyfin lê a lista directamente do GitHub (actualizada 2x por dia)
#  - Rádios: biblioteca própria "Rádios", sincronizada todos os dias
#  - Pode correr-se outra vez sem problema: não duplica nada.
# =====================================================================
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Corre com sudo."; exit 1; fi
BASE=/opt/tv-radios-nas
REPO=https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main
mkdir -p "$BASE/radios"
command -v python3 >/dev/null || { apt-get update && apt-get install -y python3; }

echo "== 1/4  Programas"
curl -fsSL "$REPO/nas/radios_strm.py" -o "$BASE/radios_strm.py"
curl -fsSL "$REPO/nas/jellyfin_nas.py" -o "$BASE/jellyfin_nas.py"
chmod 755 "$BASE"/*.py

echo "== 2/4  Rádios (a descarregar a lista)"
python3 "$BASE/radios_strm.py" "$BASE/radios"
chmod -R a+rX "$BASE"

echo "== 3/4  Actualização diária automática (07:40)"
cat > /etc/systemd/system/tv-radios-nas.service <<'UNIT'
[Unit]
Description=Sincronizar rádios e actualizar guia de TV no Jellyfin
Wants=network-online.target
After=network-online.target jellyfin.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/tv-radios-nas/radios_strm.py /opt/tv-radios-nas/radios
ExecStartPost=-/usr/bin/python3 /opt/tv-radios-nas/jellyfin_nas.py --refrescar
UNIT
cat > /etc/systemd/system/tv-radios-nas.timer <<'UNIT'
[Unit]
Description=Rádios e TV no Jellyfin todos os dias
[Timer]
OnCalendar=*-*-* 07:40
OnBootSec=10min
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now tv-radios-nas.timer >/dev/null
# versão antiga (gerava tudo no NAS, 20 min): desligar se existir
if systemctl list-unit-files 2>/dev/null | grep -q '^tv-radios-actualizar.timer'; then
  systemctl disable --now tv-radios-actualizar.timer >/dev/null 2>&1 || true
  echo "   (versão antiga desligada)"
fi

echo "== 4/4  Ligar ao Jellyfin"
if [ ! -s "$BASE/.chave" ]; then
  echo "   No Jellyfin: Painel de controlo > Chaves de API > +  (nome: tv-radios) e copia a chave."
  read -rp "   Cola aqui a chave: " KEY < /dev/tty
  [ -n "${KEY:-}" ] || { echo "Sem chave, não consigo ligar ao Jellyfin. Corre o instalador outra vez."; exit 1; }
  printf '%s' "$KEY" > "$BASE/.chave"; chmod 600 "$BASE/.chave"
fi
python3 "$BASE/jellyfin_nas.py"
echo
echo "FEITO. No Jellyfin (TV/telemóvel): 'TV em directo' = televisão | biblioteca 'Rádios' = rádios."
echo "O guia e os canais podem demorar uns minutos a aparecer na primeira vez."
