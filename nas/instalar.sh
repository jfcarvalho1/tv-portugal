#!/usr/bin/env bash
# =====================================================================
#  TV e RÁDIOS no Jellyfin do NAS  —  instalador (Debian)
#  Uso (no NAS):
#    curl -fsSL https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/nas/instalar.sh | sudo bash
#  - TV em directo: lista do GitHub + SIC através de um intermediário no NAS (só em casa)
#  - Rádios: biblioteca própria "Rádios", sincronizada todos os dias
#  - Pode correr-se outra vez sem problema: não duplica nada.
# =====================================================================
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "Corre com sudo."; exit 1; fi
BASE=/opt/tv-radios-nas
REPO=https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main
mkdir -p "$BASE/radios"
command -v python3 >/dev/null || { apt-get update && apt-get install -y python3; }

echo "== 1/5  Programas"
curl -fsSL "$REPO/nas/radios_strm.py" -o "$BASE/radios_strm.py"
curl -fsSL "$REPO/nas/jellyfin_nas.py" -o "$BASE/jellyfin_nas.py"
curl -fsSL "$REPO/nas/proxy_canais.py" -o "$BASE/proxy_canais.py"
curl -fsSL "$REPO/nas/lista_casa.py" -o "$BASE/lista_casa.py"
chmod 755 "$BASE"/*.py

echo "== 2/5  Intermediário da SIC (porta 8098)"
cat > /etc/systemd/system/tv-radios-proxy.service <<'UNIT'
[Unit]
Description=Intermediario de canais oficiais (SIC) para o Jellyfin
After=network-online.target
Wants=network-online.target
[Service]
ExecStart=/usr/bin/python3 /opt/tv-radios-nas/proxy_canais.py 8098
Restart=always
RestartSec=5
DynamicUser=yes
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable tv-radios-proxy.service >/dev/null
systemctl restart tv-radios-proxy.service
sleep 2
if curl -fsS -m 25 http://127.0.0.1:8098/c/sic/sic.m3u8 | grep -q '#EXTM3U'; then
  echo "   ✔ SIC responde através do NAS"
else
  echo "   ✖ A SIC não respondeu através do NAS (o resto instala-se na mesma; manda-me esta mensagem)"
  curl -sS -m 25 http://127.0.0.1:8098/c/sic/sic.m3u8 | head -3 || true
fi
IP=$(hostname -I | awk '{print $1}')
echo "$IP" > "$BASE/ip"

echo "== 3/5  Listas (TV de casa e rádios)"
python3 "$BASE/lista_casa.py" "$BASE/tv-casa.m3u" "$IP"
python3 "$BASE/radios_strm.py" "$BASE/radios"
chmod -R a+rX "$BASE"

echo "== 4/5  Actualização automática (07:40 e 18:10)"
cat > /etc/systemd/system/tv-radios-nas.service <<'UNIT'
[Unit]
Description=Sincronizar rádios e actualizar guia de TV no Jellyfin
Wants=network-online.target
After=network-online.target jellyfin.service
[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/bin/python3 /opt/tv-radios-nas/lista_casa.py /opt/tv-radios-nas/tv-casa.m3u "$$(cat /opt/tv-radios-nas/ip)"; /usr/bin/python3 /opt/tv-radios-nas/radios_strm.py /opt/tv-radios-nas/radios'
ExecStartPost=-/usr/bin/python3 /opt/tv-radios-nas/jellyfin_nas.py --refrescar
UNIT
cat > /etc/systemd/system/tv-radios-nas.timer <<'UNIT'
[Unit]
Description=Rádios e TV no Jellyfin todos os dias
[Timer]
OnCalendar=*-*-* 07:40
OnCalendar=*-*-* 18:10
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

echo "== 5/5  Ligar ao Jellyfin"
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
