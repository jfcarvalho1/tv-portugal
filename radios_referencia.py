#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Procura uma a uma as rádios locais da lista de referência (radios-referencia.txt — lista oficial
de rádios locais da CNE e outras que se acrescentem) que ainda faltam nas nossas listas.
Procura no TuneIn, no Radio Garden e no Radio Browser. Escreve:
  listas/radios-referencia.json            -> as que encontrou (entram nas listas)
  listas/radios-referencia-relatorio.txt   -> as que ainda faltam (para procurar à mão)
"""
import concurrent.futures as cf
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from concelhos import mapa  # noqa: E402
import radios_tunein as ti  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else AQUI
LISTAS = os.path.join(BASE, "listas")
UA = "Mozilla/5.0 (TV-Radios-Portugal)"
RB = ["https://de1.api.radio-browser.info", "https://nl1.api.radio-browser.info", "https://at1.api.radio-browser.info"]
PALAVRAS_VAZIAS = {"radio", "radios", "fm", "am", "de", "da", "do", "das", "dos", "e", "clube", "voz", "a", "o"}


def simples(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]", " ", t)).strip()


def chave(t):
    t = re.sub(r"\(.*?\)|\[.*?\]|\b\d{2,3}[.,]\d\b", " ", t or "")
    return re.sub(r"\b(radio|fm|am|online|portugal)\b|\s", "", simples(t))


def distintivas(t):
    return [p for p in simples(t).split() if p not in PALAVRAS_VAZIAS and len(p) > 2]


def parecido(ref, achado):
    """O nome encontrado é mesmo a rádio procurada? Todas as palavras distintivas têm de lá estar."""
    a, b = chave(ref), chave(achado)
    if a and b and a == b:
        return True
    if a and b and min(len(a), len(b)) >= 5 and (a in b or b in a):
        return True
    pal = distintivas(ref)
    s = " " + simples(achado) + " "
    return bool(pal) and all(" " + p + " " in s for p in pal)


def obter(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def no_tunein(nome, concelho):
    try:
        for termo in (nome, f"{nome} {concelho}"):
            for est in ti.procurar(termo)[:8]:
                if parecido(nome, est["nome"]):
                    ti.ficha(est)
                    if est.get("pais_ok"):
                        ti.resolver(est)
                        return {"nome": nome, "url": est["url"], "logo": est.get("logo", ""), "fonte": "tunein"}
    except Exception:
        pass
    return None


def no_radio_garden(nome):
    try:
        dados = obter("https://radio.garden/api/search?q=" + urllib.parse.quote(nome))
        for h in dados.get("hits", {}).get("hits", []):
            s = h.get("_source", {})
            if s.get("type") != "channel" or "portugal" not in simples(s.get("subtitle", "")):
                continue
            if parecido(nome, s.get("title", "")):
                cid = (s.get("url") or "").rstrip("/").split("/")[-1]
                est = ti.seguir({"url": f"https://radio.garden/api/ara/content/listen/{cid}/channel.mp3"})
                return {"nome": nome, "url": est["url"], "logo": "", "fonte": "radiogarden"}
    except Exception:
        pass
    return None


def no_radio_browser(nome):
    for m in RB:
        try:
            q = urllib.parse.urlencode({"name": nome, "countrycode": "PT", "hidebroken": "true", "limit": 20})
            for s in obter(f"{m}/json/stations/search?{q}"):
                if parecido(nome, s.get("name", "")):
                    u = (s.get("url_resolved") or s.get("url") or "").strip()
                    if u.startswith("http"):
                        return {"nome": nome, "url": u, "logo": s.get("favicon") or "", "fonte": "radio-browser"}
            return None
        except Exception:
            continue
    return None


def ja_temos():
    nomes = set()
    for f in ("radios.m3u",):
        p = os.path.join(LISTAS, f)
        if os.path.exists(p):
            for l in open(p, encoding="utf-8"):
                if l.startswith("#EXTINF"):
                    nomes.add(l.rsplit(",", 1)[-1].strip())
    p = os.path.join(LISTAS, "radios-tunein.json")
    if os.path.exists(p):
        nomes.update(d.get("nome", "") for d in json.load(open(p, encoding="utf-8")))
    return nomes


def main():
    ref = []
    for l in open(os.path.join(AQUI, "radios-referencia.txt"), encoding="utf-8"):
        l = l.strip()
        if l and not l.startswith("#"):
            nome, _, conc = (x.strip() for x in l.partition("|"))
            ref.append((nome, conc))
    temos = ja_temos()
    distritos = {simples(k): v for k, v in mapa().items()}
    em_falta = [(n, c) for n, c in ref if not any(parecido(n, t) for t in temos)]
    print(f"Referência: {len(ref)} rádios | já temos: {len(ref) - len(em_falta)} | a procurar: {len(em_falta)}")

    def procurar(item):
        nome, conc = item
        achado = no_tunein(nome, conc) or no_radio_garden(nome) or no_radio_browser(nome)
        if achado:
            c = simples(re.split(r"\s+-\s+", conc)[0])
            achado["regiao"] = ("Açores" if "acores" in simples(conc) else "Madeira" if "madeira" in simples(conc)
                                else distritos.get(c, ""))
        return item, achado

    achadas, faltam = [], []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for (nome, conc), achado in ex.map(procurar, em_falta):
            (achadas.append(achado) if achado else faltam.append(f"{nome} — {conc}"))
    json.dump(achadas, open(os.path.join(LISTAS, "radios-referencia.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    rel = [f"Lista de referência: {len(ref)} rádios locais",
           f"Já estavam nas listas: {len(ref) - len(em_falta)}",
           f"Encontradas agora (TuneIn / Radio Garden / Radio Browser): {len(achadas)}",
           f"Ainda em falta (sem emissão online conhecida, ou fecharam desde 2007): {len(faltam)}", ""]
    rel += [f"  + {a['nome']}  ({a['fonte']})" for a in achadas] + [""] + [f"  - {f}" for f in faltam]
    open(os.path.join(LISTAS, "radios-referencia-relatorio.txt"), "w", encoding="utf-8").write("\n".join(rel) + "\n")
    print("\n".join(rel[:5]))


if __name__ == "__main__":
    main()
