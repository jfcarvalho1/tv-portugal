#!/usr/bin/env python3
"""Guia de programação (EPG) para a app: o que está a dar agora e a seguir.

Lê os canais de listas/tv/*.m3u, vai buscar guias XMLTV gratuitos (M3UPT para Portugal e epgshare01 para
os outros países), fica só com as próximas ~14 horas dos nossos canais e grava listas/epg/<país>.json,
pequeno, para a app carregar depressa. Corre no GitHub de 6 em 6 horas.
"""
import glob
import gzip
import io
import json
import lzma
import os
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

BASE = sys.argv[1] if len(sys.argv) > 1 else "."
LISTAS = os.path.join(BASE, "listas")
SAIDA = os.path.join(LISTAS, "epg")
UA = "Mozilla/5.0 (TV-Radios-Portugal EPG)"
ES = "https://epgshare01.online/epgshare01/epg_ripper_{}.xml.gz"
FONTES = ["https://raw.githubusercontent.com/LITUATUI/M3UPT/main/EPG/epg-m3upt.xml.xz"] + [
    ES.format(p) for p in ("PT1", "ES1", "FR1", "IT1", "NL1", "BE2", "DE1", "BR1", "UK1", "US2",
                           "RAKUTEN_ES1", "RAKUTEN_FR1", "RAKUTEN_IT1", "RAKUTEN_DE1", "SAMSUNG1",
                           "ALJAZEERA1")]
ANTES, DEPOIS = 1 * 3600, 14 * 3600


def sem_acentos(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def chave(nome):  # igual à da app (docs/index.html) e à do actualizar.py
    n = re.sub(r"\(.*?\)|\[.*?\]", "", nome or "")
    n = re.sub(r"[^a-z0-9]", "", sem_acentos(n))
    return re.sub(r"(fhd|uhd|hd|sd|4k)$", "", n)


def os_nossos():
    """{país: {chave_da_app: (tvg-id, chave do nome)}}"""
    paises = {}
    for f in glob.glob(os.path.join(LISTAS, "tv", "*.m3u")):
        pais = os.path.basename(f)[:-4]
        canais = {}
        for l in open(f, encoding="utf-8"):
            if l.startswith("#EXTINF"):
                tid = (re.search(r'tvg-id="([^"]*)"', l) or [None, ""])[1].strip().lower()
                nome = l.rsplit(",", 1)[-1].strip()
                k = tid or "n:" + chave(nome)
                canais[k] = (tid, chave(nome))
        paises[pais] = canais
    return paises


def hora(t):
    try:
        return int(datetime.strptime(t.strip()[:20], "%Y%m%d%H%M%S %z").timestamp())
    except Exception:
        try:
            return int(datetime.strptime(t.strip()[:14], "%Y%m%d%H%M%S").timestamp())
        except Exception:
            return 0


def abrir(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    dados = urllib.request.urlopen(req, timeout=180).read()
    if url.endswith(".xz") or dados[:6] == b"\xfd7zXZ\x00":
        dados = lzma.decompress(dados)
    elif url.endswith(".gz") or dados[:2] == b"\x1f\x8b":
        dados = gzip.decompress(dados)
    return io.BytesIO(dados)


def ler_guia(url, ids_procurados, nomes_procurados, agora, guia):
    """Junta ao 'guia' os programas dos canais que nos interessam. guia: {id_ou_nome: [[ini, fim, titulo]]}"""
    mapa = {}  # id do canal na fonte -> chaves nossas
    n = 0
    for _, el in ET.iterparse(abrir(url), events=("end",)):
        if el.tag == "channel":
            cid = (el.get("id") or "").strip()
            ks = set()
            if cid.lower() in ids_procurados:
                ks.add(cid.lower())
            for dn in el.findall("display-name"):
                k = "n:" + chave(dn.text or "")
                if k[2:] and k[2:] in nomes_procurados:
                    ks.add(k)
            if ks:
                mapa[cid] = ks
            el.clear()
        elif el.tag == "programme":
            ks = mapa.get(el.get("channel") or "")
            if ks:
                ini, fim = hora(el.get("start", "")), hora(el.get("stop", ""))
                if fim > agora - ANTES and ini < agora + DEPOIS:
                    titulo = (el.findtext("title") or "").strip()
                    for k in ks:
                        guia.setdefault(k, []).append([ini // 60, fim // 60, titulo])
                    n += 1
            el.clear()
    return len(mapa), n


def main():
    agora = int(time.time())
    nossos = os_nossos()
    ids = {tid for p in nossos.values() for tid, _ in p.values() if tid}
    nomes = {nk for p in nossos.values() for _, nk in p.values() if nk}
    guia = {}
    for url in FONTES:
        try:
            canais, progs = ler_guia(url, ids, nomes, agora, guia)
            print(f"{url.rsplit('/', 1)[-1]}: {canais} canais nossos, {progs} programas")
        except Exception as e:
            print(f"{url.rsplit('/', 1)[-1]}: falhou ({e})")
    for k in guia:  # ordenar e tirar repetidos (a mesma emissão vinda de duas fontes)
        vistos, limpo = set(), []
        for p in sorted(guia[k]):
            if p[0] not in vistos:
                vistos.add(p[0])
                limpo.append(p)
        guia[k] = limpo
    os.makedirs(SAIDA, exist_ok=True)
    total = 0
    for pais, canais in nossos.items():
        saida = {}
        for k, (tid, nk) in canais.items():
            progs = (guia.get(tid) if tid else None) or guia.get("n:" + nk)
            if progs:
                saida[k] = progs
        total += len(saida)
        with open(os.path.join(SAIDA, pais + ".json"), "w", encoding="utf-8") as f:
            json.dump({"gerado": agora, "c": saida}, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{pais}: guia para {len(saida)} de {len(canais)} canais")
    if total == 0:
        sys.exit("Nenhum guia encontrado.")


if __name__ == "__main__":
    main()
