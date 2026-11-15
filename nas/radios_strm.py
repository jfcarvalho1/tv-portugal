#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descarrega a lista de rádios do GitHub e cria a biblioteca "Rádios" do Jellyfin:
uma pasta por grupo (Nacionais, Regionais, Locais - distrito) e um ficheiro .strm por rádio.
Só mexe no que mudou. Se a internet falhar, deixa tudo como estava."""
import os
import re
import sys
import urllib.request

DESTINO = sys.argv[1] if len(sys.argv) > 1 else "/opt/tv-radios-nas/radios"
URL = "https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/listas/radios.m3u"


def limpo(t):
    return re.sub(r'[\\/:*?"<>|]', "-", t).strip(" .")[:110] or "sem nome"


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "tv-radios-nas"})
    texto = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    desejado, atual = {}, None
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha.startswith("#EXTINF"):
            nome = linha.rsplit(",", 1)[-1].strip()
            grupo = (re.search(r'group-title="([^"]*)"', linha) or [None, "Rádios"])[1]
            num = (re.search(r'tvg-chno="(\d+)"', linha) or [None, ""])[1]
            atual = (grupo, f"{int(num):04d} - {nome}" if num else nome)
        elif linha.startswith("http") and atual:
            grupo, nome = atual
            desejado[os.path.join(limpo(grupo), limpo(nome) + ".strm")] = linha + "\n"
            atual = None
    if len(desejado) < 50:
        sys.exit(f"Lista de rádios estranha ({len(desejado)} rádios). Não mexo em nada.")
    os.makedirs(DESTINO, exist_ok=True)
    apagadas = 0
    for raiz, _, fichs in os.walk(DESTINO):
        for f in fichs:
            rel = os.path.relpath(os.path.join(raiz, f), DESTINO)
            if f.endswith(".strm") and rel not in desejado:
                os.remove(os.path.join(raiz, f))
                apagadas += 1
    novas = 0
    for rel, conteudo in desejado.items():
        p = os.path.join(DESTINO, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p) or open(p, encoding="utf-8").read() != conteudo:
            open(p, "w", encoding="utf-8").write(conteudo)
            novas += 1
    for raiz, dirs, fichs in os.walk(DESTINO, topdown=False):
        if raiz != DESTINO and not os.listdir(raiz):
            os.rmdir(raiz)
    print(f"Rádios: {len(desejado)} ({novas} novas/alteradas, {apagadas} retiradas)")


if __name__ == "__main__":
    main()
