#!/bin/bash
# Instala a "Ponte TV e Rádios" no NAS (Debian). Correr no NAS com:
#   curl -fsSL https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/ponte/instalar-ponte.sh | sudo bash
# Não mexe em discos nem em dados. Só cria /opt/ponte-tv e um serviço "ponte-tv".
set -u
PORTA=8787          # só dentro do NAS
PORTA_TS=8443       # porta https na rede Tailscale (não mexe na 443, que pode estar a ser usada)
RAW=https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/ponte

ok()   { echo -e "\e[32m✔\e[0m $*"; }
erro() { echo -e "\e[31m✘ $*\e[0m"; exit 1; }

[ "$(id -u)" = 0 ] || erro "Corre com sudo (ver a primeira linha deste ficheiro)."
command -v python3 >/dev/null || erro "Falta o python3 no NAS (sudo apt install python3)."
command -v tailscale >/dev/null || erro "Falta o Tailscale no NAS."

mkdir -p /opt/ponte-tv
curl -fsSL "$RAW/ponte.py" -o /opt/ponte-tv/ponte.py || erro "Não consegui descarregar a ponte (há internet no NAS?)."
ok "Ponte descarregada para /opt/ponte-tv"

cat > /etc/systemd/system/ponte-tv.service <<EOF
[Unit]
Description=Ponte TV e Radios (app jfcarvalho1.github.io/tv-portugal)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/ponte-tv/ponte.py $PORTA
DynamicUser=yes
Restart=always
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now ponte-tv >/dev/null 2>&1
sleep 2
curl -fs "http://127.0.0.1:$PORTA/ok" >/dev/null || erro "O serviço não arrancou. Vê com: sudo journalctl -u ponte-tv -n 30"
ok "Serviço ponte-tv a correr (arranca sozinho quando o NAS liga)"

# publicar só na rede Tailscale, com https
if ! tailscale serve --bg --https=$PORTA_TS http://127.0.0.1:$PORTA >/tmp/ponte-ts.txt 2>&1; then
  cat /tmp/ponte-ts.txt
  echo
  echo "O Tailscale não deixou ligar o https. Normalmente é só ligar uma opção, uma vez:"
  echo "  1) No computador, abre https://login.tailscale.com/admin/dns"
  echo "  2) Liga 'MagicDNS' (se estiver desligado) e carrega em 'Enable HTTPS'"
  echo "  3) Volta a correr este instalador."
  exit 1
fi
NOME=$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
ENDERECO="https://$NOME:$PORTA_TS"
sleep 3
if curl -fs --max-time 20 "$ENDERECO/ok" >/dev/null; then
  ok "Ponte acessível pela rede Tailscale"
else
  echo "(o certificado https pode demorar um minuto a ser criado da primeira vez)"
fi
echo
echo "=============================================================="
echo " PRONTO. Endereço da ponte (manda-o ao Claude):"
echo
echo "   $ENDERECO"
echo "=============================================================="
