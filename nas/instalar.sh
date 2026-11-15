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

echo "== 4/5  Actualização automática (listas 07:40 e 18:10; programas de hora a hora)"
cat > "$BASE/auto-actualizar.sh" <<'SH'
#!/bin/sh
# Vai buscar ao GitHub as versões novas dos programas do NAS e reinicia o intermediário se mudou.
REPO=https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/nas
B=/opt/tv-radios-nas
mudou_proxy=0
for f in proxy_canais.py lista_casa.py radios_strm.py jellyfin_nas.py; do
  curl -fsSL -m 60 "$REPO/$f" -o "$B/$f.novo" || { rm -f "$B/$f.novo"; continue; }
  python3 -m py_compile "$B/$f.novo" 2>/dev/null || { rm -f "$B/$f.novo"; continue; }
  if ! cmp -s "$B/$f.novo" "$B/$f"; then
    mv "$B/$f.novo" "$B/$f"; chmod 755 "$B/$f"; echo "actualizado: $f"
    [ "$f" = proxy_canais.py ] && mudou_proxy=1
  else
    rm -f "$B/$f.novo"
  fi
done
rm -rf "$B/__pycache__"
[ "$mudou_proxy" = 1 ] && systemctl restart tv-radios-proxy.service
exit 0
SH
chmod 755 "$BASE/auto-actualizar.sh"
cat > /etc/systemd/system/tv-radios-programas.service <<'UNIT'
[Unit]
Description=Actualizar programas TV/Radios do NAS a partir do GitHub
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
ExecStart=/opt/tv-radios-nas/auto-actualizar.sh
UNIT
cat > /etc/systemd/system/tv-radios-programas.timer <<'UNIT'
[Unit]
Description=Programas TV/Radios do NAS de hora a hora
[Timer]
OnCalendar=hourly
OnBootSec=3min
Persistent=true
[Install]
WantedBy=timers.target
UNIT
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
systemctl enable --now tv-radios-programas.timer >/dev/null
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
