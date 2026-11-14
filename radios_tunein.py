#!/usr/bin/env python3
"""Recolhe TODAS as rádios portuguesas do directório público do TuneIn (opml.radiotime.com),
região a região, e guarda-as em listas/radios-tunein.json para o actualizar.py juntar às outras.

O TuneIn tem as rádios locais com nome certo (ex.: Rádio Voz de Basto, Rádio Região de Basto),
que faltam no Radio Browser. Corre no GitHub (tem internet); não precisa de conta.
"""
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "."
SAIDA = os.path.join(BASE, "listas", "radios-tunein.json")
OPML = "https://opml.radiotime.com"
PORTUGAL = "r101286"
UA = "Mozilla/5.0 (TV-Radios-Portugal)"
REGIOES_PT = ["aveiro", "beja", "braga", "braganca", "castelo branco", "coimbra", "evora", "faro",
              "algarve", "guarda", "leiria", "lisboa", "lisbon", "portalegre", "porto", "oporto",
              "santarem", "setubal", "viana do castelo", "vila real", "viseu", "azores", "acores",
              "madeira", "norte", "centro", "alentejo"]
NAO_SEGUIR = ["europe", "europa", "portugal", "spain", "espanha", "world", "mundo", "africa",
              "america", "asia", "oceania", "brazil", "brasil"]
TRADUZ = {"lisbon": "Lisboa", "azores": "Açores", "oporto": "Porto", "braganca": "Bragança",
          "evora": "Évora", "santarem": "Santarém", "setubal": "Setúbal"}


def simples(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower().strip()


def obter(url):
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-PT,pt"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            erro = e
            time.sleep(2 * (tentativa + 1))
    print(f"falhou {url}: {erro}", file=sys.stderr)
    return {}


def json_url(url):
    url = url.replace("http://", "https://")
    return url + ("&" if "?" in url else "?") + "render=json"


def elementos(corpo):
    for e in corpo or []:
        yield e
        yield from elementos(e.get("children"))


def recolher():
    estacoes, visitadas = {}, set()
    fila = [(f"{OPML}/Browse.ashx?id={PORTUGAL}", "", 0)]
    while fila:
        url, regiao, prof = fila.pop(0)
        if url in visitadas or prof > 3:
            continue
        visitadas.add(url)
        dados = obter(json_url(url))
        for e in elementos(dados.get("body")):
            gid = e.get("guide_id") or ""
            if e.get("type") == "audio" and gid.startswith("s"):
                if gid not in estacoes:
                    estacoes[gid] = {"id": gid, "nome": (e.get("text") or "").strip(),
                                     "logo": e.get("image") or "", "regiao": regiao,
                                     "tune": e.get("URL") or f"{OPML}/Tune.ashx?id={gid}"}
                elif regiao and not estacoes[gid]["regiao"]:
                    estacoes[gid]["regiao"] = regiao
            elif e.get("type") == "link" and e.get("URL"):
                texto = simples(e.get("text"))
                if e.get("key") == "nextStations" or "offset=" in e["URL"]:
                    fila.append((e["URL"], regiao, prof))           # página seguinte da mesma região
                elif gid.startswith("r") and texto not in NAO_SEGUIR:
                    if prof == 0 and not any(r in texto for r in REGIOES_PT):
                        continue                                    # do topo só segue regiões portuguesas
                    nova = regiao or TRADUZ.get(texto, (e.get("text") or "").strip())
                    fila.append((e["URL"], nova, prof + 1))
    return list(estacoes.values())


def resolver(est):
    """Troca o endereço do TuneIn pelo da própria rádio; se não der, fica o do TuneIn."""
    dados = obter(json_url(f"{OPML}/Tune.ashx?id={est['id']}&formats=mp3,aac,ogg,hls"))
    for e in dados.get("body") or []:
        u = (e.get("url") or "").strip()
        if u.startswith("http") and not re.search(r"notcompatible|unavailable|nostream", u, re.I):
            est["url"] = u
            return est
    est["url"] = f"http://opml.radiotime.com/Tune.ashx?id={est['id']}"
    return est


def main():
    estacoes = recolher()
    print(f"TuneIn: {len(estacoes)} rádios encontradas")
    if len(estacoes) < 50:
        sys.exit("Muito poucas rádios (TuneIn mudou?); mantenho a lista anterior.")
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        estacoes = list(ex.map(resolver, estacoes))
    estacoes.sort(key=lambda e: (simples(e["regiao"]), simples(e["nome"])))
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(estacoes, f, ensure_ascii=False, indent=1)
    print(f"Guardado em {SAIDA}")


if __name__ == "__main__":
    main()
