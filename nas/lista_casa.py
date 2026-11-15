#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cria a lista de TV "de casa" para o Jellyfin: a lista do GitHub + os canais que passam
pelo intermediário do NAS (SIC). Se a internet falhar, mantém a lista anterior."""
import os
import re
import sys
import urllib.request

DESTINO = sys.argv[1] if len(sys.argv) > 1 else "/opt/tv-radios-nas/tv-casa.m3u"
NAS = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
URL = "https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/listas/tv.m3u"
EXTRA = [  # (tvg-id, nome, número, caminho no intermediário)
    ("SIC.pt", "SIC", 3, "/c/sic/sic.m3u8"),
]
LOGO = "https://raw.githubusercontent.com/LITUATUI/M3UPT/main/logos/{}.png"


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "tv-radios-nas"})
    texto = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    linhas = texto.splitlines()
    if len([l for l in linhas if l.startswith("#EXTINF")]) < 100:
        sys.exit("Lista de TV estranha. Mantenho a anterior.")
    ids = {tid for tid, *_ in EXTRA}
    saida, saltar = [], False
    for l in linhas:  # tirar versões antigas destes canais, se a lista as tiver
        if l.startswith("#EXTINF"):
            m = re.search(r'tvg-id="([^"]*)"', l)
            saltar = bool(m and m.group(1) in ids)
        if not saltar:
            saida.append(l)
        elif l.strip() and not l.startswith("#"):
            saltar = False
    novos = []
    for tid, nome, num, caminho in EXTRA:
        novos += [f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{nome}" tvg-logo="{LOGO.format(tid)}" '
                  f'tvg-chno="{num}" group-title="Portugal",{nome}', f"http://{NAS}:8098{caminho}"]
    saida = saida[:1] + novos + saida[1:]
    tmp = DESTINO + ".tmp"
    open(tmp, "w", encoding="utf-8").write("\n".join(saida) + "\n")
    os.replace(tmp, DESTINO)
    print(f"Lista de casa: {len([l for l in saida if l.startswith('#EXTINF')])} canais (inclui SIC pelo NAS)")


if __name__ == "__main__":
    main()
