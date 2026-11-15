#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Retira do Jellyfin só o que o instalador TV/Rádios pôs: sintonizadores destas listas,
guia m3upt e a biblioteca "Rádios" (só a biblioteca; não toca em filmes, séries ou música)."""
import json
import os
import urllib.parse
import urllib.request

JF = "http://localhost:8096"
CH = "/opt/tv-radios-nas/.chave"
EPG = "https://m3upt.com/epg"
MEUS = ("/opt/tv-radios-nas/", "/opt/tv-radios/listas/", "jfcarvalho1/tv-portugal")


def api(m, c):
    k = open(CH).read().strip()
    req = urllib.request.Request(JF + c, method=m, headers={"Authorization": f'MediaBrowser Token="{k}"', "X-Emby-Token": k})
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read().decode() or "null"
        try:
            return json.loads(t)
        except ValueError:
            return None


def passo(nome, fn):
    try:
        print(f"   ✔ {nome} — {fn()}")
    except Exception as e:
        print(f"   ✖ {nome} — {e}")


def main():
    if not os.path.exists(CH):
        print("   (sem chave guardada: retira à mão no Jellyfin > Painel > TV em directo e Bibliotecas)")
        return
    cfg = api("GET", "/System/Configuration/livetv") or {}

    def tuners():
        n = 0
        for t in cfg.get("TunerHosts", []):
            if t.get("Id") and any(x in (t.get("Url") or "") for x in MEUS):
                api("DELETE", f"/LiveTv/TunerHosts?id={t['Id']}")
                n += 1
        return f"{n} retirado(s)"
    passo("TV em directo (sintonizadores)", tuners)

    def guia():
        n = 0
        for p in cfg.get("ListingProviders", []):
            if p.get("Id") and p.get("Path") == EPG:
                api("DELETE", f"/LiveTv/ListingProviders?id={p['Id']}")
                n += 1
        return f"{n} retirado(s)"
    passo("Guia de programação", guia)

    def biblioteca():
        n = 0
        for b in api("GET", "/Library/VirtualFolders") or []:
            if any("/opt/tv-radios" in l for l in (b.get("Locations") or [])):
                q = urllib.parse.urlencode({"name": b["Name"], "refreshLibrary": "true"})
                api("DELETE", f"/Library/VirtualFolders?{q}")
                n += 1
        return f"{n} retirada(s)"
    passo("Biblioteca 'Rádios'", biblioteca)


if __name__ == "__main__":
    main()
