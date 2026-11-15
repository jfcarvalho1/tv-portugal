#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Liga a TV e as rádios ao Jellyfin pela API (sem cliques).
  jellyfin_nas.py             -> configuração (sintonizador TV do GitHub, guia, biblioteca Rádios)
  jellyfin_nas.py --refrescar -> só pede ao Jellyfin para reler canais, guia e biblioteca"""
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "/opt/tv-radios-nas"
JF = os.environ.get("JELLYFIN_URL", "http://localhost:8096").rstrip("/")
CHAVE = open(os.path.join(BASE, ".chave"), encoding="utf-8").read().strip()
TV = "https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/listas/tv.m3u"
EPG = "https://m3upt.com/epg"
RADIOS = os.path.join(BASE, "radios")
NOME_BIB = "Rádios"
UA = "VLC/3.0.21 LibVLC/3.0.21"


def api(metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(JF + caminho, data=dados, method=metodo, headers={
        "Authorization": f'MediaBrowser Token="{CHAVE}"', "X-Emby-Token": CHAVE,
        "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read().decode() or "null"
        try:
            return json.loads(t)
        except ValueError:
            return None


def passo(nome, fn):
    try:
        r = fn()
        print(f"   ✔ {nome}" + (f" — {r}" if isinstance(r, str) else ""))
        return True
    except Exception as e:
        print(f"   ✖ {nome} — {e}")
        return False


def tarefa(chave):
    for t in api("GET", "/ScheduledTasks") or []:
        if t.get("Key") == chave:
            api("POST", f"/ScheduledTasks/Running/{t['Id']}")
            return "pedido"
    return "tarefa não encontrada"


def refrescar():
    passo("Reler canais e guia", lambda: tarefa("RefreshGuide"))
    passo("Reler biblioteca Rádios", lambda: api("POST", "/Library/Refresh") or "pedido")


def configurar():
    if not passo("Ligação ao Jellyfin", lambda: "versão " + api("GET", "/System/Info")["Version"]):
        print("   → Confirma a chave e se o Jellyfin está a correr. Para trocar a chave: sudo rm /opt/tv-radios-nas/.chave")
        sys.exit(2)
    cfg = api("GET", "/System/Configuration/livetv") or {}

    def limpar_antigos():
        tirados = 0
        for t in cfg.get("TunerHosts", []):
            u = t.get("Url") or ""
            if t.get("Id") and ("/opt/tv-radios/listas/" in u):  # instalação antiga (listas geradas no NAS)
                api("DELETE", f"/LiveTv/TunerHosts?id={t['Id']}")
                tirados += 1
        return f"{tirados} retirados" if tirados else "nada a limpar"
    passo("Sintonizadores antigos", limpar_antigos)

    def tuner():
        if any(t.get("Url") == TV for t in cfg.get("TunerHosts", [])):
            return "já existia"
        api("POST", "/LiveTv/TunerHosts", {
            "Type": "m3u", "Url": TV, "FriendlyName": "TV (GitHub)", "ImportFavoritesOnly": False,
            "AllowHWTranscoding": True, "AllowStreamSharing": True, "EnableStreamLooping": False,
            "IgnoreDts": True, "TunerCount": 0, "UserAgent": UA, "Source": "",
            "FallbackMaxStreamingBitrate": 30000000})
        return "adicionado"
    passo("TV em directo (lista do GitHub)", tuner)

    def guia():
        if any(p.get("Path") == EPG for p in cfg.get("ListingProviders", [])):
            return "já existia"
        api("POST", "/LiveTv/ListingProviders?validateListings=false&validateLogin=false",
            {"Type": "xmltv", "Path": EPG, "EnableAllTuners": True, "EnabledTuners": []})
        return "adicionado"
    passo("Guia de programação", guia)

    def biblioteca():
        for b in api("GET", "/Library/VirtualFolders") or []:
            if b.get("Name") == NOME_BIB or RADIOS in (b.get("Locations") or []):
                return "já existia"
        q = urllib.parse.urlencode({"name": NOME_BIB, "collectionType": "homevideos", "refreshLibrary": "true"})
        api("POST", f"/Library/VirtualFolders?{q}",
            {"LibraryOptions": {"PathInfos": [{"Path": RADIOS}], "EnableRealtimeMonitor": True}})
        return "criada"
    passo("Biblioteca 'Rádios'", biblioteca)
    refrescar()


if __name__ == "__main__":
    refrescar() if "--refrescar" in sys.argv else configurar()
