#!/usr/bin/env python3
"""Ponte TV & Rádios — corre no NAS e deixa a app tocar canais que o navegador não consegue abrir sozinho:
  * canais que exigem cabeçalhos (SIC, TVI…: Referer/Origin/User-Agent do site oficial);
  * rádios que só emitem em "http" (o iPhone recusa-as dentro de uma app segura).

Uso: GET /p?u=<endereço>&r=<referer>&o=<origin>&a=<user-agent>
As listas HLS (.m3u8) são reescritas para que cada pedaço também passe pela ponte com os mesmos cabeçalhos.
Só se chega cá dentro pela rede Tailscale (tailscale serve). Só Python, sem nada para instalar.
"""
import http.server
import ipaddress
import re
import socket
import socketserver
import sys
import urllib.error
import urllib.parse
import urllib.request

PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
UA_PADRAO = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
BLOCO = 64 * 1024


def endereco_publico(url):
    """Recusa endereços da rede de casa (a ponte não pode servir para espreitar o router, etc.)."""
    host = urllib.parse.urlsplit(url).hostname or ""
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        return True
    except Exception:
        return False


class Ponte(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        partes = urllib.parse.urlsplit(self.path)
        if partes.path in ("/", "/ok"):
            corpo = b"Ponte TV e Radios: a funcionar\n"
            self.send_response(200)
            self.cors()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return
        if partes.path != "/p":
            self.send_error(404)
            return
        q = urllib.parse.parse_qs(partes.query)
        url = (q.get("u") or [""])[0]
        if not re.match(r"^https?://", url) or not endereco_publico(url):
            self.send_error(400, "endereco invalido")
            return
        cab = {"User-Agent": (q.get("a") or [UA_PADRAO])[0], "Accept": "*/*", "Icy-MetaData": "0"}
        if q.get("r"):
            cab["Referer"] = q["r"][0]
        if q.get("o"):
            cab["Origin"] = q["o"][0]
        if self.headers.get("Range"):
            cab["Range"] = self.headers["Range"]
        extra = {k: q[k][0] for k in ("r", "o", "a") if q.get(k)}
        try:
            resp = urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=20)
        except urllib.error.HTTPError as e:
            self.send_error(e.code)
            return
        except Exception:
            self.send_error(502)
            return
        with resp:
            final = resp.geturl()
            tipo = resp.headers.get("Content-Type", "")
            e_lista = "mpegurl" in tipo.lower() or final.split("?")[0].lower().endswith(".m3u8")
            if e_lista:
                texto = resp.read(4 * 1024 * 1024).decode("utf-8", "replace")
                if texto.lstrip().startswith("#EXTM3U"):
                    corpo = self.reescrever(texto, final, extra).encode("utf-8")
                    self.send_response(200)
                    self.cors()
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Content-Length", str(len(corpo)))
                    self.end_headers()
                    self.wfile.write(corpo)
                    return
                corpo = texto.encode("utf-8")
                self.send_response(200)
                self.cors()
                self.send_header("Content-Type", tipo or "application/octet-stream")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
                return
            # vídeo, áudio ou rádio contínua: passa tal e qual, aos bocados
            self.send_response(resp.status)
            self.cors()
            for h in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                if resp.headers.get(h):
                    self.send_header(h, resp.headers[h])
            if not resp.headers.get("Content-Type") and resp.headers.get("icy-name"):
                self.send_header("Content-Type", "audio/mpeg")
            if not resp.headers.get("Content-Length"):
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            try:
                while True:
                    b = resp.read(BLOCO)
                    if not b:
                        break
                    self.wfile.write(b)
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                pass

    def reescrever(self, texto, base, extra):
        def via(u):
            absoluto = urllib.parse.urljoin(base, u.strip())
            return "/p?" + urllib.parse.urlencode({"u": absoluto, **extra})
        linhas = []
        for l in texto.splitlines():
            if l and not l.startswith("#"):
                linhas.append(via(l))
            elif 'URI="' in l:
                linhas.append(re.sub(r'URI="([^"]+)"', lambda m: f'URI="{via(m.group(1))}"', l))
            else:
                linhas.append(l)
        return "\n".join(linhas) + "\n"


class Servidor(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"Ponte TV e Rádios em http://127.0.0.1:{PORTA}")
    Servidor(("127.0.0.1", PORTA), Ponte).serve_forever()
