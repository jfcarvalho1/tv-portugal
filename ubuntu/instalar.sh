#!/bin/bash
# Instala a app "TV e Rádios" no Ubuntu: ícone no menu de aplicações e no ambiente de trabalho,
# abre numa janela própria (sem barras do navegador). Não precisa de sudo, excepto se faltar o Chromium.
# Correr no Terminal:
#   curl -fsSL https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/ubuntu/instalar.sh | bash
set -u
URL="https://jfcarvalho1.github.io/tv-portugal/"
ICONE_URL="https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/docs/icone-512.png"
PASTA="$HOME/.local/share/tv-radios"
LANCADOR="$HOME/.local/share/applications/tv-radios.desktop"

# 1) um navegador que saiba abrir apps em janela própria (Chromium é gratuito e open source)
NAV=""
for n in chromium chromium-browser google-chrome google-chrome-stable brave-browser microsoft-edge; do
  if command -v "$n" >/dev/null 2>&1; then NAV="$n"; break; fi
done
if [ -z "$NAV" ]; then
  echo "A instalar o Chromium (gratuito e open source). Pode pedir a tua palavra-passe…"
  sudo snap install chromium && NAV="chromium"
fi
[ -n "$NAV" ] || { echo "Não consegui instalar o Chromium."; exit 1; }

# 2) ícone
mkdir -p "$PASTA" "$(dirname "$LANCADOR")"
curl -fsSL "$ICONE_URL" -o "$PASTA/icone.png" || echo "(sem ícone, continua na mesma)"

# 3) lançador no menu de aplicações
cat > "$LANCADOR" <<FIM
[Desktop Entry]
Type=Application
Name=TV e Rádios
Comment=TV em directo e rádios portuguesas
Exec=$NAV --app=$URL --class=TVRadios
Icon=$PASTA/icone.png
Terminal=false
Categories=AudioVideo;TV;Audio;Video;
StartupWMClass=TVRadios
FIM
chmod +x "$LANCADOR"
update-desktop-database "$(dirname "$LANCADOR")" >/dev/null 2>&1 || true

# 4) atalho também no ambiente de trabalho
DESK=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
if [ -d "$DESK" ]; then
  cp "$LANCADOR" "$DESK/TV e Rádios.desktop"
  chmod +x "$DESK/TV e Rádios.desktop"
  gio set "$DESK/TV e Rádios.desktop" metadata::trusted true 2>/dev/null || true
fi

echo
echo "✔ Pronto! Procura \"TV e Rádios\" no menu de aplicações (ou usa o ícone no ambiente de trabalho)."
echo "  Para a fixar na barra lateral: abre-a, clica com o botão direito no ícone → Fixar no painel."
nohup $NAV --app=$URL --class=TVRadios >/dev/null 2>&1 &
