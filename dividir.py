#!/usr/bin/env python3
"""Divide listas/tv.m3u em listas pequenas por país (listas/tv/*.m3u).

O VLC do iPhone engasga-se com a lista completa (milhares de canais);
com listas pequenas abre logo. Corre depois do actualizar.py.
"""
import os
import re
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
                b = b.strip()
                if b.startswith("seguir:"):  # resolver o redireccionamento (o destino final aceita a nossa app)
                    b = seguir(b[7:].strip())
                out[a.strip().lower()] = b
    return out


def seguir(url):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            final = r.geturl()
            if final.startswith("https://") and r.read(7) == b"#EXTM3U":
                print(f"redireccionamento: {url[:60]}… → {final}")
                return final
    except Exception as e:
        print(f"não consegui seguir {url[:60]}…: {e}")
    return url


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


RADIO = re.compile(r"r[aá]dio|\bfm\b", re.I)
TV = re.compile(r"\btv\b|t[ée]l[ée]|televis", re.I)


RADIOS_DA_TV = []


def juntar_as_radios():
    """Passa as rádios com imagem para listas/radios.m3u (aba Rádios), sem repetir as que já lá estão."""
    f = os.path.join(BASE, "listas", "radios.m3u")
    if not RADIOS_DA_TV or not os.path.exists(f):
        return
    texto = open(f, encoding="utf-8").read()
    chave = lambda n: re.sub(r"[^a-z0-9]", "", re.sub(r"r[aá]dio|\bfm\b", "", n.lower()))
    existentes = {chave(l.rsplit(",", 1)[-1]) for l in texto.splitlines() if l.startswith("#EXTINF")}
    urls = set(l for l in texto.splitlines() if l and not l.startswith("#"))
    novas = []
    for bloco in RADIOS_DA_TV:
        inf = next(b for b in bloco if b.startswith("#EXTINF"))
        nome, url = inf.rsplit(",", 1)[-1], bloco[-1]
        if chave(nome) in existentes or url in urls:
            continue
        pais = inf.split('group-title="', 1)[1].split('"', 1)[0] if 'group-title="' in inf else ""
        grupo = "Rádios com Imagem" if pais == "Portugal" else "Rádios Estrangeiras"
        inf = re.sub(r'group-title="[^"]*"', f'group-title="{grupo}"', inf) if 'group-title="' in inf else inf.replace(",", f' group-title="{grupo}",', 1)
        novas.append([inf] + [b for b in bloco if b.startswith("#EXTVLCOPT")] + [url])
    novas.sort(key=lambda b: (b[0].count("Estrangeiras"), b[0].rsplit(",", 1)[-1].lower()))
    with open(f, "a", encoding="utf-8") as out:
        for b in novas:
            out.write("\n".join(b) + "\n")
    print(f"rádios com imagem passadas para a aba Rádios: {len(novas)}")


def sem_radios(linhas):
    """Tira da TV as rádios com imagem (On FM, Rádio Sines, Radio 538…): as rádios ficam na aba Rádios."""
    out, bloco, fora = [], [], 0
    for l in linhas:
        bloco.append(l)
        if l and not l.startswith("#"):
            inf = next((b for b in bloco if b.startswith("#EXTINF")), "")
            nome = inf.rsplit(",", 1)[-1]
            if inf and RADIO.search(nome) and not TV.search(nome):
                fora += 1
                RADIOS_DA_TV.append(list(bloco))
            else:
                out += bloco
            bloco = []
        elif l.startswith("#EXTM3U"):
            out += bloco
            bloco = []
    print(f"rádios tiradas da TV: {fora}")
    return out + bloco


def main():
    with open(ORIGEM, encoding="utf-8") as f:
        linhas = aplicar_substituicoes(f.read().splitlines())
    linhas = sem_radios(linhas)
    juntar_as_radios()
    sites = {u[5:] for u in substituicoes().values() if u.startswith("site:")}
    linhas = [l[5:] if l.startswith("site:") else l for l in linhas]
    # a lista completa (Jellyfin, VLC) fica corrigida e sem os canais que só abrem no site oficial
    completa, bloco = [], []
    for l in linhas:
        bloco.append(l)
        if l and not l.startswith("#"):
            if l not in sites:
                completa += bloco
            bloco = []
        elif l.startswith("#EXTM3U"):
            completa += bloco
            bloco = []
    with open(ORIGEM, "w", encoding="utf-8") as f:
        f.write("\n".join(completa + bloco) + "\n")
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
