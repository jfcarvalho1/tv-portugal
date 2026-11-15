#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intermediário caseiro para canais oficiais e gratuitos que só tocam "vindos do próprio site"
(ex.: SIC). Corre no NAS, só para uso em casa. Não é um proxy aberto: só fala com os servidores
oficiais listados em CANAIS.
  http://NAS:8098/c/sic/   -> emissão da SIC (escolhe a melhor qualidade que responder)
"""
import http.server
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request

PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else 8098
CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
CANAIS = {
    "sic": {
        "inicio": ["https://sic.live.impresa.pt/sic1080p.m3u8", "https://sic.live.impresa.pt/sic720p.m3u8",
                   "https://sic.live.impresa.pt/sic540p.m3u8"],
        "hosts": ["sic.live.impresa.pt", "impresa.pt"],
        "headers": {"Referer": "https://sic.pt/", "Origin": "https://sic.pt", "User-Agent": CHROME},
    },
}


def permitido(canal, url):
    h = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(h == x or h.endswith("." + x) for x in CANAIS[canal]["hosts"])


def pedir(canal, url):
    req = urllib.request.Request(url, headers=CANAIS[canal]["headers"])
    return urllib.request.urlopen(req, timeout=20)


def reescrever(canal, base, texto, prefixo):
    """Cada endereço da playlist passa a apontar para este intermediário."""
    def via(u):
        return f"{prefixo}/c/{canal}/x?u=" + urllib.parse.quote(urllib.parse.urljoin(base, u), safe="")
    out = []
    for l in texto.splitlines():
        s = l.strip()
        if s and not s.startswith("#"):
            out.append(via(s))
        elif 'URI="' in l:
            ini = l.index('URI="') + 5
            fim = l.index('"', ini)
            out.append(l[:ini] + via(l[ini:fim]) + l[fim:])
        else:
            out.append(l)
    return "\n".join(out) + "\n"


class Pedido(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def erro(self, codigo, msg):
        corpo = msg.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        partes = urllib.parse.urlsplit(self.path)
        bocados = [p for p in partes.path.split("/") if p]
        if len(bocados) < 2 or bocados[0] != "c" or bocados[1] not in CANAIS:
            return self.erro(404, "Canal desconhecido. Canais: " + ", ".join(CANAIS))
        canal = bocados[1]
        alvo = urllib.parse.parse_qs(partes.query).get("u", [None])[0]
        candidatos = [alvo] if alvo else CANAIS[canal]["inicio"]
        host = self.headers.get("Host") or f"127.0.0.1:{PORTA}"
        prefixo = f"http://{host}"
        ultimo = "sem resposta"
        for url in candidatos:
            if not permitido(canal, url):
                return self.erro(403, "Endereço não permitido")
            try:
                r = pedir(canal, url)
            except urllib.error.HTTPError as e:
                ultimo = f"{e.code} em {url}"
                continue
            except Exception as e:
                ultimo = f"{e} em {url}"
                continue
            with r:
                final = r.geturl()
                tipo = r.headers.get("Content-Type", "")
                if ".m3u8" in urllib.parse.urlsplit(final).path or "mpegurl" in tipo.lower():
                    corpo = reescrever(canal, final, r.read().decode("utf-8", "replace"), prefixo).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Content-Length", str(len(corpo)))
                    self.end_headers()
                    self.wfile.write(corpo)
                    return
                self.send_response(200)
                self.send_header("Content-Type", tipo or "video/mp2t")
                tam = r.headers.get("Content-Length")
                if tam:
                    self.send_header("Content-Length", tam)
                else:
                    self.send_header("Connection", "close")
                self.end_headers()
                try:
                    while True:
                        bloco = r.read(65536)
                        if not bloco:
                            break
                        self.wfile.write(bloco)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
        self.erro(502, "A emissão não respondeu: " + ultimo)


class Servidor(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"Intermediário de canais a ouvir na porta {PORTA}", flush=True)
    Servidor(("0.0.0.0", PORTA), Pedido).serve_forever()
