#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liga as listas ao Jellyfin através da API (sem cliques no painel).
  configurar_jellyfin.py <BASE>            -> configuração inicial (sintonizadores, guia, biblioteca Rádios)
  configurar_jellyfin.py <BASE> --refrescar -> só pede ao Jellyfin para reler guia e biblioteca
A chave API é lida de <BASE>/.jellyfin_api_key
"""
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "/opt/tv-radios"
SO_REFRESCAR = "--refrescar" in sys.argv
JF = os.environ.get("JELLYFIN_URL", "http://localhost:8096").rstrip("/")
CHAVE = open(os.path.join(BASE, ".jellyfin_api_key"), encoding="utf-8").read().strip()
UA = "VLC/3.0.21 LibVLC/3.0.21"
EPG = "https://m3upt.com/epg"
TV = os.path.join(BASE, "listas", "tv.m3u")
RADIOS = os.path.join(BASE, "listas", "radios.m3u")
BIB = os.path.join(BASE, "biblioteca-radios")
NOME_BIB = "Rádios"


def api(metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(JF + caminho, data=dados, method=metodo, headers={
        "Authorization": f'MediaBrowser Token="{CHAVE}"',
        "X-Emby-Token": CHAVE,
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read().decode() or "null"
        try:
            return json.loads(txt)
        except ValueError:
            return None


def passo(nome, fn):
    try:
        r = fn()
        print(f"  ✔ {nome}" + (f" — {r}" if isinstance(r, str) else ""))
        return True
    except Exception as e:
        print(f"  ✖ {nome} — {e}")
        return False


def tarefa(chave_tarefa):
    for t in api("GET", "/ScheduledTasks") or []:
        if t.get("Key") == chave_tarefa:
            api("POST", f"/ScheduledTasks/Running/{t['Id']}")
            return "pedido"
    return "tarefa não encontrada"


def refrescar():
    passo("Actualizar guia/canais", lambda: tarefa("RefreshGuide"))
    passo("Actualizar bibliotecas", lambda: api("POST", "/Library/Refresh") or "pedido")


def configurar():
    if not passo("Ligação ao Jellyfin", lambda: api("GET", "/System/Info")["Version"]):
        print("  → Confirma a chave API e se o Jellyfin está a correr (http://localhost:8096).")
        sys.exit(2)
    cfg = api("GET", "/System/Configuration/livetv") or {}
    urls = {t.get("Url") for t in cfg.get("TunerHosts", [])}
    epgs = {p.get("Path") for p in cfg.get("ListingProviders", [])}

    def tuner(nome, url):
        if url in urls:
            return "já existia"
        api("POST", "/LiveTv/TunerHosts", {
            "Type": "m3u", "Url": url, "FriendlyName": nome, "ImportFavoritesOnly": False,
            "AllowHWTranscoding": True, "AllowStreamSharing": True, "EnableStreamLooping": False,
            "IgnoreDts": True, "TunerCount": 0, "UserAgent": UA, "Source": "",
            "FallbackMaxStreamingBitrate": 30000000,
        })
        return "adicionado"

    passo("Sintonizador TV Portugal", lambda: tuner("TV Portugal", TV))

    def tirar_radios_da_tv():
        for t in cfg.get("TunerHosts", []):
            if t.get("Url") == RADIOS and t.get("Id"):
                api("DELETE", f"/LiveTv/TunerHosts?id={t['Id']}")
                return "removido"
        return "não estava lá"
    passo("Rádios fora da TV em directo", tirar_radios_da_tv)

    def guia():
        if EPG in epgs:
            return "já existia"
        api("POST", "/LiveTv/ListingProviders?validateListings=false&validateLogin=false",
            {"Type": "xmltv", "Path": EPG, "EnableAllTuners": True, "EnabledTuners": []})
        return "adicionado"
    passo("Guia de programação (EPG M3UPT)", guia)

    def biblioteca():
        for b in api("GET", "/Library/VirtualFolders") or []:
            if b.get("Name") == NOME_BIB or BIB in (b.get("Locations") or []):
                return "já existia"
        q = urllib.parse.urlencode({"name": NOME_BIB, "collectionType": "homevideos",
                                    "refreshLibrary": "true"})
        api("POST", f"/Library/VirtualFolders?{q}",
            {"LibraryOptions": {"PathInfos": [{"Path": BIB}], "EnableRealtimeMonitor": True}})
        return "adicionada"
    passo("Biblioteca 'Rádios'", biblioteca)
    refrescar()


if __name__ == "__main__":
    refrescar() if SO_REFRESCAR else configurar()
