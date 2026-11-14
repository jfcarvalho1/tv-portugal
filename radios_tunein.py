#!/usr/bin/env python3
"""Recolhe TODAS as rádios portuguesas do directório público do TuneIn (opml.radiotime.com)
e guarda-as em listas/radios-tunein.json para o actualizar.py juntar às outras.

Como o TuneIn só mostra as rádios mais ouvidas quando se navega por regiões, procura também
concelho a concelho (os 308 de Portugal, tirados da Wikidata) e confirma com a ficha de cada
rádio que ela é mesmo de Portugal, e de que distrito. Corre no GitHub; não precisa de conta.
"""
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "."
SAIDA = os.path.join(BASE, "listas", "radios-tunein.json")
DEBUG = os.path.join(BASE, "listas", "radios-tunein-relatorio.txt")
OPML = "https://opml.radiotime.com"
PORTUGAL = "r101286"
UA = "Mozilla/5.0 (TV-Radios-Portugal)"
DISTRITOS = ["Aveiro", "Beja", "Braga", "Bragança", "Castelo Branco", "Coimbra", "Évora", "Faro", "Guarda",
             "Leiria", "Lisboa", "Portalegre", "Porto", "Santarém", "Setúbal", "Viana do Castelo", "Vila Real",
             "Viseu", "Açores", "Madeira"]
INGLES = {"lisbon": "Lisboa", "azores": "Açores", "oporto": "Porto"}
SPARQL = """SELECT ?mLabel ?dLabel WHERE {
  ?m wdt:P31 wd:Q13217644 .
  OPTIONAL { ?m wdt:P131+ ?d . ?d rdfs:label ?dl . FILTER(LANG(?dl) = "pt")
             FILTER(STRSTARTS(?dl, "Distrito d") || STRSTARTS(?dl, "Região Autónoma")) }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pt". }
}"""
relatorio = []


def simples(t):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()).strip()


def obter(url, ua=UA, json_=True):
    erro = None
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "pt-PT,pt"})
            with urllib.request.urlopen(req, timeout=40) as r:
                txt = r.read().decode("utf-8", "replace")
                return json.loads(txt) if json_ else txt
        except Exception as e:
            erro = e
            time.sleep(2 * (tentativa + 1))
    relatorio.append(f"falhou {url[:120]}: {erro}")
    return {} if json_ else ""


def opml(caminho, **params):
    params["render"] = "json"
    return obter(f"{OPML}/{caminho}?{urllib.parse.urlencode(params)}")


def elementos(corpo):
    for e in corpo or []:
        yield e
        yield from elementos(e.get("children"))


def distrito_de(texto):
    s = simples(texto)
    s = re.sub(r"^(distrito d[eo]s?|regiao autonoma d[aeo]s?)\s+", "", s)
    s = INGLES.get(s, s)
    for d in DISTRITOS:
        if simples(d) == simples(s):
            return d
    return ""


def concelhos():
    """Os 308 concelhos e o distrito de cada um (Wikidata)."""
    url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(SPARQL)
    dados = obter(url, ua="TVRadiosPortugal/1.0 (github.com/jfcarvalho1/tv-portugal)")
    out = {}
    for b in dados.get("results", {}).get("bindings", []):
        c = b.get("mLabel", {}).get("value", "")
        d = distrito_de(b.get("dLabel", {}).get("value", ""))
        if c and not re.match(r"^Q\d+$", c):
            out[c] = out.get(c) or d
    relatorio.append(f"Wikidata: {len(out)} concelhos, {sum(1 for d in out.values() if d)} com distrito")
    return out


def navegar(achadas):
    """Navega o Portugal do TuneIn (regiões e páginas seguintes)."""
    fila, vistas = [(f"{OPML}/Browse.ashx?id={PORTUGAL}", 0)], set()
    while fila:
        url, prof = fila.pop(0)
        if url in vistas or prof > 3:
            continue
        vistas.add(url)
        url_json = url.replace("http://", "https://") + ("&" if "?" in url else "?") + "render=json"
        for e in elementos(obter(url_json).get("body")):
            gid = e.get("guide_id") or ""
            if e.get("type") == "audio" and gid.startswith("s"):
                achadas.setdefault(gid, {"id": gid, "nome": (e.get("text") or "").strip(), "logo": e.get("image") or ""})
            elif e.get("type") == "link" and e.get("URL"):
                if e.get("key") == "nextStations":
                    fila.append((e["URL"], prof))
                elif gid.startswith("r") and prof < 2 and simples(e.get("text")) not in ("europe", "europa", "portugal"):
                    fila.append((e["URL"], prof + 1))
    relatorio.append(f"Navegação: {len(achadas)} rádios")


def procurar(termo):
    dados = opml("Search.ashx", query=termo, types="station")
    return [{"id": e["guide_id"], "nome": (e.get("text") or "").strip(), "logo": e.get("image") or ""}
            for e in elementos(dados.get("body"))
            if e.get("type") == "audio" and (e.get("guide_id") or "").startswith("s")]


def ficha(est):
    """Confirma que a rádio é portuguesa e descobre o distrito pela localização."""
    d = opml("Describe.ashx", id=est["id"])
    info = next((e for e in d.get("body") or [] if e.get("element") == "station"), {})
    est["local"] = info.get("location") or ""
    est["pais_ok"] = str(info.get("country_region_id") or "") == PORTUGAL[1:] or "portugal" in simples(est["local"])
    if info.get("frequency") and info.get("band"):
        est["freq"] = f"{info['frequency']} {info['band']}"
    return est


def resolver(est):
    """Troca o endereço do TuneIn pelo da própria rádio; se não der, fica o do TuneIn."""
    dados = opml("Tune.ashx", id=est["id"], formats="mp3,aac,ogg,hls")
    for e in dados.get("body") or []:
        u = (e.get("url") or "").strip()
        if u.startswith("http") and not re.search(r"notcompatible|unavailable|nostream", u, re.I):
            est["url"] = u
            return est
    est["url"] = f"http://opml.radiotime.com/Tune.ashx?id={est['id']}"
    return est


def main():
    achadas = {}
    navegar(achadas)
    conc = concelhos()
    termos = sorted(set(conc) | set(DISTRITOS) | {"rádio portugal", "rádio local", "rádio clube", "rádio voz"})
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for termo, res in zip(termos, ex.map(procurar, termos)):
            for e in res:
                e["termo"] = termo
                achadas.setdefault(e["id"], e)
    relatorio.append(f"Depois de procurar {len(termos)} termos: {len(achadas)} rádios (antes de confirmar o país)")

    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        todas = list(ex.map(ficha, achadas.values()))
    pt = [e for e in todas if e.get("pais_ok")]
    relatorio.append(f"Confirmadas em Portugal: {len(pt)}")
    if len(pt) < 50:
        open(DEBUG, "w", encoding="utf-8").write("\n".join(relatorio) + "\n")
        sys.exit("Muito poucas rádios (TuneIn mudou?); mantenho a lista anterior.")

    por_concelho = {simples(c): d for c, d in conc.items()}
    for e in pt:
        cidade = simples(e["local"].split(",")[0])
        e["regiao"] = (distrito_de(e["local"].split(",")[0]) or por_concelho.get(cidade)
                       or next((d for c, d in por_concelho.items() if d and len(c) > 4 and c in simples(e["nome"])), ""))
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        pt = list(ex.map(resolver, pt))
    pt.sort(key=lambda e: (DISTRITOS.index(e["regiao"]) if e["regiao"] in DISTRITOS else 99, simples(e["nome"])))
    for e in pt:
        e.pop("pais_ok", None)
        e.pop("termo", None)
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(pt, f, ensure_ascii=False, indent=1)
    sem = [e for e in pt if not e["regiao"]]
    relatorio.append(f"Guardadas: {len(pt)} | sem distrito: {len(sem)}")
    relatorio += ["", "Sem distrito (localização do TuneIn):"] + [f"  {e['nome']} — {e['local']}" for e in sem]
    open(DEBUG, "w", encoding="utf-8").write("\n".join(relatorio) + "\n")
    print("\n".join(relatorio[:8]))


if __name__ == "__main__":
    main()
