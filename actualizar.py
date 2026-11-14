#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TV & Rádios Portugal para o Jellyfin — gera as listas (v2).
Fontes só públicas e legais:
  - M3UPT        (canais portugueses oficiais + guia de programação; rádios portuguesas)
  - iptv-org     (links públicos de canais do mundo inteiro, por país)
  - Radio Browser (rádios portuguesas)
Saídas:
  listas/tv.m3u              -> só canais de TV em directo (Jellyfin: TV em directo)
  biblioteca-radios/...strm  -> rádios, numa biblioteca separada "Rádios"
  listas/radios.m3u          -> as mesmas rádios, para usar no VLC se quiseres
  listas/relatorio.txt       -> lista final, canal a canal, e o que ficou de fora
Só usa a biblioteca padrão do Python (nada para instalar).
"""
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "/opt/tv-radios"
LISTAS = os.path.join(BASE, "listas")
BIB_RADIOS = os.path.join(BASE, "biblioteca-radios")
CONFIG = os.path.join(BASE, "config.txt")

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
UA_API = "TVRadiosPortugal-Jellyfin/2.0"
M3UPT = "https://m3upt.com/iptv"
IPTVORG = "https://iptv-org.github.io/iptv/index.country.m3u"
RADIO_BROWSER = ["https://de1.api.radio-browser.info", "https://nl1.api.radio-browser.info",
                 "https://at1.api.radio-browser.info", "https://de2.api.radio-browser.info",
                 "https://fi1.api.radio-browser.info"]
EPG = "https://m3upt.com/epg"

# ---------------------------------------------------------------- países
# (nome no iptv-org, nome a mostrar, primeiro número de canal)
PAISES = [
    ("Portugal", "Portugal", 1),
    ("Spain", "Espanha", 1001),
    ("France", "França", 2001),
    ("Italy", "Itália", 3001),
    ("Netherlands", "Holanda", 4001),
    ("Belgium", "Bélgica", 5001),
    ("Germany", "Alemanha", 6001),
    ("Brazil", "Brasil", 7001),
    ("United States", "Estados Unidos", 8001),
    ("International", "Internacional", 9001),
]
RESTO_INICIO = 10001  # restantes países, por ordem alfabética, seguidos
TRADUZ = {
    "United Kingdom": "Reino Unido", "Ireland": "Irlanda", "Switzerland": "Suíça", "Austria": "Áustria",
    "Luxembourg": "Luxemburgo", "Andorra": "Andorra", "Angola": "Angola", "Mozambique": "Moçambique",
    "Cape Verde": "Cabo Verde", "Guinea-Bissau": "Guiné-Bissau", "Sao Tome and Principe": "São Tomé e Príncipe",
    "Timor-Leste": "Timor-Leste", "Macao": "Macau", "Argentina": "Argentina", "Mexico": "México",
    "Canada": "Canadá", "Chile": "Chile", "Colombia": "Colômbia", "Peru": "Peru", "Uruguay": "Uruguai",
    "Venezuela": "Venezuela", "Greece": "Grécia", "Poland": "Polónia", "Sweden": "Suécia", "Norway": "Noruega",
    "Denmark": "Dinamarca", "Finland": "Finlândia", "Iceland": "Islândia", "Czech Republic": "Chéquia",
    "Croatia": "Croácia", "Romania": "Roménia", "Hungary": "Hungria", "Turkey": "Turquia", "Morocco": "Marrocos",
    "Japan": "Japão", "China": "China", "South Korea": "Coreia do Sul", "India": "Índia", "Australia": "Austrália",
    "Russia": "Rússia", "Ukraine": "Ucrânia", "Undefined": "Sem país definido",
}

# Ordem de importância dentro de cada país (regex sobre o nome simplificado: sem acentos/espaços)
IMPORTANCIA = {
    "Portugal": [r"^rtp1$", r"^rtp2$", r"^sic$", r"^tvi$", r"^(rtp3|rtpnoticias)$", r"^sicnoticias", r"^cnnportugal",
                 r"^rtpmemoria", r"^(artv|canalparlamento)", r"^canal11", r"^cmtv", r"^portocanal",
                 r"^rtpacores", r"^rtpmadeira", r"^rtpafrica", r"^rtpinternacional", r"^tviinternacional",
                 r"^sicinternacional", r"^vtvi", r"^euronews.*(pt|portug)"],
    "Spain": [r"^(tve)?la1$", r"^(tve)?la2$", r"^(canal)?24h|^tve24", r"^antena3$", r"^cuatro$", r"^telecinco$",
              r"^lasexta$", r"^clan", r"^teledeporte", r"^tveinternacional", r"^(tv3|3cat)", r"^telemadrid",
              r"^canalsur", r"^tvg|^galicia", r"^etb|^eitb", r"^apunt"],
    "France": [r"^tf1$", r"^france2$", r"^france3$", r"^france5$", r"^arte", r"^m6$", r"^france24",
               r"^franceinfo", r"^bfmtv$", r"^cnews$", r"^lci$", r"^tv5monde", r"^(lcp|publicsenat)",
               r"^france4$", r"^tmc$", r"^w9$"],
    "Italy": [r"^rai1$", r"^rai2$", r"^rai3$", r"^rainews", r"^rete4$", r"^canale5$", r"^italia1$", r"^la7$",
              r"^tv8$", r"^nove$", r"^raistoria", r"^raiscuola", r"^raiitalia", r"^tgcom24", r"^skytg24"],
    "Netherlands": [r"^npo1$", r"^npo2$", r"^npo3$", r"^nos", r"^rtl4$", r"^rtl5$", r"^sbs6$", r"^veronica",
                    r"^npopolitiek"],
    "Belgium": [r"^(vrt)?(1|een)$", r"^(vrt)?canvas", r"^ketnet", r"^laune$", r"^(tipik|ladeux)", r"^latrois",
                r"^vtm$", r"^rtltvi", r"^bx1", r"^kanaalz", r"^ln24"],
    "Germany": [r"^(daserste|ard)$", r"^zdf$", r"^tagesschau24", r"^phoenix", r"^3sat", r"^arte", r"^zdfneo",
                r"^zdfinfo", r"^one$", r"^kika", r"^br", r"^wdr", r"^ndr", r"^mdr", r"^swr", r"^hr", r"^rbb",
                r"^(dw|deutschewelle)"],
    "Brazil": [r"^(tv|rede)?globo$", r"^sbt", r"^record", r"^band", r"^tvcultura", r"^tvbrasil", r"^redetv",
               r"^cnnbrasil", r"^globonews", r"^jovempan", r"^tvcamara", r"^tvsenado", r"^canalgov"],
    "United States": [r"^abcnews", r"^cbsnews", r"^nbcnews", r"^pbs", r"^fox", r"^bloomberg", r"^cspan",
                      r"^nasa", r"^newsmax", r"^weather"],
    "International": [r"^euronews", r"^(dw|deutschewelle)", r"^france24", r"^bbc", r"^aljazeera", r"^cnn",
                      r"^reuters", r"^nhk", r"^tv5monde", r"^cgtn", r"^rt"],
}

RADIOS_NACIONAIS = [r"^(rdp)?antena1$", r"^antena2$", r"^antena3$", r"^(radio)?renascenca$", r"^rfm$",
                    r"^radiocomercial$", r"^m80(radio)?$", r"^cidadefm$", r"^smoothfm$", r"^megahits",
                    r"^tsf(radionoticias)?$", r"^(radio)?observador$", r"^antena1acores", r"^antena1madeira",
                    r"^rdpinternacional", r"^rdpafrica", r"^antena1fado", r"^antena1vida", r"^antena2opera",
                    r"^(radio)?sbsr"]
ADULTOS = ["xxx", "adult", "erotic", "porn", "+18", "18+", "playboy", "hustler", "private", "brazzers"]
IPTVORG_ADULTOS = "https://iptv-org.github.io/iptv/index.nsfw.m3u"
GRUPO_ADULTOS = "Adultos (+18)"
ADULTOS_INICIO = 90001
# ANTI-PIRATARIA 1: canais pagos nunca são livres -> qualquer link para eles é ilegal
PAGOS = ["sport tv", "sporttv", "dazn", "eurosport", "axn", "star channel", "star movies", "star crime",
         "star life", "star comedy", "disney", "hbo", "sky sport", "sky cinema", "sky atlantic", "canal+",
         "canal plus", "bein", "espn", "fox sports", "movistar", "discovery", "national geographic", "nat geo",
         "cartoon network", "cartoonito", "hollywood", "tnt", "warner", "cinemax", "showtime", "starz",
         "sic mulher", "sic radical", "sic caras", "sic k", "mcm", "premiere", "sportv", "telecine",
         "globonews", "benfica tv", "btv", "sporting tv", "canal panda", "biggs", "odisseia", "historia",
         "history", "a&e", "syfy", "amc", "cinemundo", "tvcine", "eleven", "arena sport", "nova sport",
         "dazn", "max ", "paramount+", "fx ", "e! ", "mtv"]
# ANTI-PIRATARIA 2: links em servidores caseiros (endereço IP ou DNS dinâmico) não são emissões oficiais
HOST_SUSPEITO = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$|dyndns|ddns|no-ip|noip|duckdns|myftp|hopto|zapto|"
                           r"serveftp|sytes|redirectme|ddnsfree|freeddns|dynu|servebeer|servehttp")

# Categorias do iptv-org que ficam de fora: religião e televendas
CATEGORIAS_FORA = {
    "religião": "https://iptv-org.github.io/iptv/categories/religious.m3u",
    "televendas": "https://iptv-org.github.io/iptv/categories/shop.m3u",
}
# Rede de segurança: nomes religiosos que escapem à categoria
RELIGIAO = ["igreja", "church", "gospel", "christ", "cristo", "jesus", "god ", "deus", "bible", "biblia",
            "catholic", "catolic", "evangel", "islam", "quran", "coran", "kuran", "allah", "hindu", "sikh",
            "ewtn", "3abn", "daystar", "tbn", "hope channel", "cancao nova", "rede vida", "aparecida",
            "kuriakos", "tv seculo 21", "novo tempo", "padre", "faith", "pray", "ministr", "mision", "missao",
            "torah", "buddh", "shalom", "graca", "vaticano", "vatican", "maria tv", "telepace"]


def ler_config():
    cfg = {"INCLUIR_RESTO_DO_MUNDO": "1", "TESTAR_LINKS": "1", "EXCLUIR": "", "MIN_RESOLUCAO": "720", "NAO_TESTAR_PAISES": "", "INCLUIR_ADULTOS": "1"}
    if os.path.exists(CONFIG):
        for linha in open(CONFIG, encoding="utf-8"):
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                cfg[k.strip().upper()] = v.strip()
    cfg["EXCLUIR_LISTA"] = [sem_acentos(x.strip()) for x in cfg["EXCLUIR"].split(",") if x.strip()]
    return cfg


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def baixar(url, ua=UA, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def sem_acentos(t):
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


def pirata(c):
    host = re.sub(r"^https?://", "", c["url"]).split("/")[0].split(":")[0].lower()
    if HOST_SUSPEITO.search(host):
        return "link não oficial (servidor caseiro)"
    n = " " + sem_acentos(c["nome"]) + " "
    if any(" " + p.strip() + " " in n or n.strip().startswith(p.strip()) for p in PAGOS):
        return "canal pago (só existe pirata)"
    return None


def chave(nome):
    n = re.sub(r"\(.*?\)|\[.*?\]", "", nome or "")
    n = re.sub(r"[^a-z0-9]", "", sem_acentos(n))
    return re.sub(r"(fhd|uhd|hd|sd|4k)$", "", n)


def parse_m3u(texto, fonte):
    canais, atual = [], None
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        if linha.startswith("#EXTINF"):
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', linha))
            ult = linha.rfind('"')
            virg = linha.find(",", ult if ult > 0 else 0)
            bruto = linha[virg + 1:].strip() if virg >= 0 else attrs.get("tvg-name", "")
            nome = re.sub(r"\s*(\(\d+p\)|\[[^\]]*\])", "", bruto).strip()
            atual = {"nome": nome, "bruto": bruto, "attrs": attrs, "fonte": fonte}
        elif linha.startswith("#"):
            continue
        elif atual is not None:
            url = linha.split("|", 1)[0].strip()
            if url.startswith("http"):
                atual["url"] = url
                canais.append(atual)
            atual = None
    return canais


def e_radio(c):
    a = c["attrs"]
    return a.get("radio", "").lower() == "true" or "radio" in sem_acentos(a.get("group-title", ""))


def testar(url):
    """Devolve (funciona, altura_em_linhas). A altura vem da playlist HLS (RESOLUTION=1280x720), se houver."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Icy-MetaData": "0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            dados = r.read(65536)
            if r.status >= 400 or not dados:
                return (False, 0)
            alturas = [int(h) for h in re.findall(rb"RESOLUTION=\d+x(\d+)", dados)]
            return (True, max(alturas) if alturas else 0)
    except Exception:
        return (False, 0)


def altura_no_nome(c):
    m = re.search(r"\((\d{3,4})p\)", c.get("bruto", ""))
    return int(m.group(1)) if m else 0


def radio_browser():
    for m in RADIO_BROWSER:
        try:
            url = m + "/json/stations/bycountrycodeexact/PT?hidebroken=true&order=votes&reverse=true&limit=3000"
            dados = json.loads(baixar(url, ua=UA_API))
            log(f"Radio Browser: {len(dados)} rádios portuguesas")
            out = []
            for s in sorted(dados, key=lambda s: -int(s.get("votes") or 0)):
                u = (s.get("url_resolved") or s.get("url") or "").strip()
                if u.startswith("http") and str(s.get("lastcheckok", 1)) == "1":
                    out.append({"nome": (s.get("name") or "").strip(), "url": u, "fonte": "radio-browser",
                                "attrs": {"tvg-logo": s.get("favicon") or ""}})
            return out
        except Exception as e:
            log(f"Radio Browser ({m}) falhou: {e}")
    return []


def posicao(pais, nome):
    k = chave(nome)
    for i, rx in enumerate(IMPORTANCIA.get(pais, [])):
        if re.search(rx, k):
            return i
    return 999


def linha_extinf(c, numero, grupo, radio=False):
    a = c["attrs"]
    nome = c["nome"].replace(",", " ").strip()
    p = ["#EXTINF:-1"]
    if a.get("tvg-id"):
        p.append(f'tvg-id="{a["tvg-id"]}"')
    p.append(f'tvg-name="{nome}"')
    if a.get("tvg-logo"):
        p.append(f'tvg-logo="{a["tvg-logo"]}"')
    p.append(f'tvg-chno="{numero}"')
    if radio:
        p.append('radio="true"')
    p.append(f'group-title="{grupo}"')
    return " ".join(p) + "," + nome


def escrever(caminho, texto):
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, caminho)


def nome_ficheiro(t):
    return re.sub(r'[\\/:*?"<>|]', "-", t).strip(" .")[:120] or "sem nome"


def sincronizar_strm(radios):
    desejado = {}
    for n, nacional, c in radios:
        pasta = "1 - Nacionais" if nacional else "2 - Regionais e Locais"
        desejado[os.path.join(pasta, f"{n} - {nome_ficheiro(c['nome'])}.strm")] = c["url"] + "\n"
    os.makedirs(BIB_RADIOS, exist_ok=True)
    for raiz, _, fichs in os.walk(BIB_RADIOS):
        for f in fichs:
            rel = os.path.relpath(os.path.join(raiz, f), BIB_RADIOS)
            if f.endswith(".strm") and rel not in desejado:
                os.remove(os.path.join(raiz, f))
    for rel, conteudo in desejado.items():
        p = os.path.join(BIB_RADIOS, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p) or open(p, encoding="utf-8").read() != conteudo:
            with open(p, "w", encoding="utf-8") as f:
                f.write(conteudo)


def main():
    cfg = ler_config()
    os.makedirs(LISTAS, exist_ok=True)
    prioridade = {p[0]: i for i, p in enumerate(PAISES)}
    fora = []  # (motivo, nome, país)

    def bloqueado(nome):
        s = sem_acentos(nome)
        return any(x and x in s for x in cfg["EXCLUIR_LISTA"])

    # ---------- descarregar
    log("A descarregar listas…")
    tv_bruto, radios_bruto, epg = [], [], EPG
    try:
        t = baixar(M3UPT)
        m = re.search(r'(?:url-tvg|x-tvg-url)="([^"]+)"', t[:2000])
        if m:
            epg = m.group(1).split(",")[0].strip()
        lst = parse_m3u(t, "M3UPT")
        log(f"M3UPT: {len(lst)} entradas")
        for c in lst:
            if e_radio(c):
                if "venice" not in sem_acentos(c["nome"]):
                    radios_bruto.append(c)
            elif "beachcam" in sem_acentos(c["attrs"].get("group-title", "") + c["nome"]):
                continue  # câmaras de praia: não são canais de TV
            else:
                tid = c["attrs"].get("tvg-id", "").lower()
                espanhol = posicao("Spain", c["nome"]) < 999 or "tve" in sem_acentos(c["nome"])
                if (".pt" in tid or posicao("Portugal", c["nome"]) < 999) and not espanhol:
                    c["pais"] = "Portugal"
                    tv_bruto.append(c)
                # os estrangeiros do M3UPT vêm também do iptv-org, já com o país certo
    except Exception as e:
        log(f"M3UPT falhou: {e}")
    try:
        lst = parse_m3u(baixar(IPTVORG, timeout=120), "iptv-org")
        log(f"iptv-org: {len(lst)} entradas")
        for c in lst:
            if "not 24/7" in c["bruto"].lower():
                fora.append(("não é 24h em directo", c["nome"], c["attrs"].get("group-title", "")))
                continue
            c["pais"] = c["attrs"].get("group-title", "Undefined").split(";")[0].strip() or "Undefined"
            if posicao("Portugal", c["nome"]) < 999 and re.search(r"euronews", chave(c["nome"])):
                c["pais"] = "Portugal"  # Euronews em português
            tv_bruto.append(c)
    except Exception as e:
        log(f"iptv-org falhou: {e}")
    if cfg["INCLUIR_ADULTOS"] == "1":
        try:
            lst = parse_m3u(baixar(IPTVORG_ADULTOS, timeout=120), "iptv-org")
            log(f"iptv-org (+18): {len(lst)} entradas")
            for c in lst:
                c["pais"] = GRUPO_ADULTOS
            tv_bruto += lst
        except Exception as e:
            log(f"Lista +18 não disponível ({e})")
    for c in tv_bruto:  # tudo o que for adulto vai para um grupo próprio, no fim
        if any(a in sem_acentos(c["nome"] + " " + c["attrs"].get("group-title", "")) for a in ADULTOS):
            c["pais"] = GRUPO_ADULTOS
    if cfg["INCLUIR_ADULTOS"] != "1":
        tv_bruto = [c for c in tv_bruto if c["pais"] != GRUPO_ADULTOS]
    radios_bruto += radio_browser()
    excl_url, excl_id = {}, {}
    for motivo, url in CATEGORIAS_FORA.items():
        try:
            for c in parse_m3u(baixar(url, timeout=120), motivo):
                excl_url[c["url"]] = motivo
                tid = c["attrs"].get("tvg-id", "").split("@")[0].lower()
                if tid:
                    excl_id[tid] = motivo
        except Exception as e:
            log(f"Lista de {motivo} falhou ({e}); fica só o filtro por nome.")

    # ---------- TV: ordenar por país e importância; tirar duplicados (ficam como reserva)
    if cfg["INCLUIR_RESTO_DO_MUNDO"] != "1":
        tv_bruto = [c for c in tv_bruto if c["pais"] in prioridade]
    tv_bruto.sort(key=lambda c: (prioridade.get(c["pais"], 999 if c["pais"] == GRUPO_ADULTOS else 99), c["pais"], c["fonte"] != "M3UPT",
                                 posicao(c["pais"], c["nome"]), sem_acentos(c["nome"])))
    tv, por_id, por_nome = [], {}, {}
    for c in tv_bruto:
        tid = c["attrs"].get("tvg-id", "").split("@")[0].lower()
        motivo = excl_url.get(c["url"]) or (excl_id.get(tid) if tid else None)
        if not motivo and any(r in " " + sem_acentos(c["nome"]) + " " for r in RELIGIAO):
            motivo = "religião"
        motivo = motivo or pirata(c)
        if motivo or bloqueado(c["nome"]):
            fora.append((motivo or "excluído", c["nome"], c["pais"]))
            continue
        kn = (c["pais"], chave(c["nome"]))
        dono = (por_id.get(tid) if tid else None) or por_nome.get(kn)
        if dono is not None:
            dono.setdefault("reservas", []).append(c["url"])
            continue
        tv.append(c)
        if tid:
            por_id[tid] = c
        por_nome[kn] = c

    # ---------- rádios: sem duplicados
    radios, vistos = [], set()
    for c in radios_bruto:
        k = chave(c["nome"])
        if k and k not in vistos and not bloqueado(c["nome"]):
            vistos.add(k)
            radios.append(c)

    # ---------- testar
    if cfg["TESTAR_LINKS"] == "1":
        todos = {c["url"] for c in tv + radios}
        for c in tv:
            todos.update(c.get("reservas", []))
        log(f"A testar {len(todos)} links (pode demorar uns minutos)…")
        with cf.ThreadPoolExecutor(max_workers=48) as ex:
            ok = dict(zip(todos, ex.map(testar, todos)))
        minimo = int(cfg["MIN_RESOLUCAO"] or 0)
        tv_ok = []
        for c in tv:
            boa = next((u for u in [c["url"]] + c.get("reservas", []) if ok[u][0]), None)
            if not boa and c["pais"] in cfg["NAO_TESTAR_PAISES"].split(","):
                boa = c["url"]  # testado fora de Portugal: canais PT com bloqueio geográfico ficam
            if not boa:
                fora.append(("link não respondeu", c["nome"], c["pais"]))
                continue
            c["url"] = boa
            c["altura"] = max(ok[boa][1], altura_no_nome(c))
            if c["altura"] and c["altura"] < minimo and c["pais"] != "Portugal":
                fora.append((f"qualidade baixa ({c['altura']}p)", c["nome"], c["pais"]))
            elif not c["altura"] and c["pais"] != "Portugal" and minimo:
                fora.append(("qualidade desconhecida", c["nome"], c["pais"]))
            else:
                tv_ok.append(c)
        r_ok = [c for c in radios if ok[c["url"]][0]]
        fora += [("link não respondeu", c["nome"], "Rádio") for c in radios if not ok[c["url"]][0]]
        tv, radios = tv_ok, r_ok

    if not tv and not radios:
        log("ERRO: não obtive nenhum canal (sem internet?). Mantenho as listas antigas.")
        sys.exit(1)

    # ---------- numerar TV
    nomes_pais = {p[0]: p[1] for p in PAISES}
    inicio = {p[0]: p[2] for p in PAISES}
    linhas, rel_tv, cont, prox_resto, pais_atual = [f'#EXTM3U url-tvg="{epg}"'], [], {}, RESTO_INICIO, None
    for c in tv:
        p = c["pais"]
        nome_pais = nomes_pais.get(p) or TRADUZ.get(p, p)
        if p == GRUPO_ADULTOS:
            n = ADULTOS_INICIO + cont.get(p, 0)
            cont[p] = cont.get(p, 0) + 1
        elif p in inicio:
            n = inicio[p] + cont.get(p, 0)
            cont[p] = cont.get(p, 0) + 1
        else:
            n = prox_resto
            prox_resto += 1
        if p != pais_atual:
            rel_tv.append(f"\n--- {nome_pais} ---")
            pais_atual = p
        linhas += [linha_extinf(c, n, nome_pais), c["url"]]
        q = f"{c['altura']}p" if c.get("altura") else "?"
        rel_tv.append(f"{n:>6}  {c['nome']}  [{q}]")

    # ---------- numerar rádios
    def r_pos(c):
        k = chave(c["nome"])
        return next((i for i, rx in enumerate(RADIOS_NACIONAIS) if re.search(rx, k)), 999)
    radios.sort(key=lambda c: (r_pos(c), sem_acentos(c["nome"])))
    linhas_r, rel_r, numerados, nn, nl = [f'#EXTM3U url-tvg="{epg}"'], [], [], 1, 101
    for c in radios:
        nac = r_pos(c) < 999
        n = nn if nac else nl
        nn, nl = (nn + 1, nl) if nac else (nn, nl + 1)
        g = "Rádios Nacionais" if nac else "Rádios Regionais e Locais"
        linhas_r += [linha_extinf(c, n, g, radio=True), c["url"]]
        rel_r.append(f"{n:>6}  [{g}]  {c['nome']}")
        numerados.append((n, nac, c))

    escrever(os.path.join(LISTAS, "tv.m3u"), "\n".join(linhas) + "\n")
    escrever(os.path.join(LISTAS, "radios.m3u"), "\n".join(linhas_r) + "\n")
    sincronizar_strm(numerados)
    resumo = [f"Actualizado: {time.strftime('%Y-%m-%d %H:%M')}",
              f"TV: {len(tv)} canais em directo | Rádios: {len(radios)}", "", "======== TV EM DIRECTO ========"]
    resumo += rel_tv + ["", "======== RÁDIOS (biblioteca 'Rádios') ========"] + rel_r
    resumo += ["", f"======== FICARAM DE FORA: {len(fora)} ========"] + [f"[{m}] {n} ({p})" for m, n, p in fora]
    escrever(os.path.join(LISTAS, "relatorio.txt"), "\n".join(resumo) + "\n")
    log(f"Pronto: {len(tv)} canais de TV, {len(radios)} rádios, {len(fora)} de fora.")


if __name__ == "__main__":
    main()
