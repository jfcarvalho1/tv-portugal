#!/usr/bin/env python3
"""Divide listas/tv.m3u em listas pequenas por país (listas/tv/*.m3u).

O VLC do iPhone engasga-se com a lista completa (milhares de canais);
com listas pequenas abre logo. Corre depois do actualizar.py.
"""
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "."
ORIGEM = os.path.join(BASE, "listas", "tv.m3u")
DESTINO = os.path.join(BASE, "listas", "tv")

FICHEIROS = {
    "Portugal": "portugal", "Espanha": "espanha", "França": "franca", "Itália": "italia",
    "Holanda": "holanda", "Bélgica": "belgica", "Alemanha": "alemanha", "Brasil": "brasil",
    "Estados Unidos": "eua", "Internacional": "internacional", "Adultos (+18)": "adultos",
}
RESTO = "resto-do-mundo"


def substituicoes():
    """tv-substituir.txt: tvg-id = endereço oficial que não exige cabeçalhos."""
    f = os.path.join(BASE, "tv-substituir.txt")
    out = {}
    if os.path.exists(f):
        for l in open(f, encoding="utf-8"):
            if "=" in l and not l.lstrip().startswith("#"):
                a, b = l.split("=", 1)
                out[a.strip().lower()] = b.strip()
    return out


def aplicar_substituicoes(linhas):
    subs = substituicoes()
    if not subs:
        return linhas
    out, tid = [], None
    for l in linhas:
        if l.startswith("#EXTINF"):
            tid = l.split('tvg-id="', 1)[1].split('"', 1)[0].lower() if 'tvg-id="' in l else None
            out.append(l)
        elif l.startswith("#EXTVLCOPT") and tid in subs:
            continue  # o endereço oficial não precisa de cabeçalhos
        elif l and not l.startswith("#") and tid in subs:
            out.append(subs[tid])
            tid = None
        else:
            out.append(l)
    return out


def main():
    with open(ORIGEM, encoding="utf-8") as f:
        linhas = aplicar_substituicoes(f.read().splitlines())
    with open(ORIGEM, "w", encoding="utf-8") as f:  # a lista completa (Jellyfin, VLC) também fica corrigida
        f.write("\n".join(linhas) + "\n")
    cabecalho = linhas[0] if linhas and linhas[0].startswith("#EXTM3U") else "#EXTM3U"
    grupos, bloco = {}, []
    for linha in linhas[1:]:
        if not linha.strip():
            continue
        bloco.append(linha)
        if not linha.startswith("#"):  # o endereço fecha o bloco do canal
            extinf = next((l for l in bloco if l.startswith("#EXTINF")), "")
            g = extinf.split('group-title="', 1)[1].split('"', 1)[0] if 'group-title="' in extinf else ""
            grupos.setdefault(FICHEIROS.get(g, RESTO), []).extend(bloco)
            bloco = []
    if not grupos:
        sys.exit("tv.m3u vazio; não mexo nas listas por país.")
    os.makedirs(DESTINO, exist_ok=True)
    for antigo in os.listdir(DESTINO):
        if antigo.endswith(".m3u"):
            os.remove(os.path.join(DESTINO, antigo))
    for nome, conteudo in grupos.items():
        with open(os.path.join(DESTINO, nome + ".m3u"), "w", encoding="utf-8") as f:
            f.write(cabecalho + "\n" + "\n".join(conteudo) + "\n")
        print(f"{nome}: {sum(1 for l in conteudo if l.startswith('#EXTINF'))} canais")


if __name__ == "__main__":
    main()
