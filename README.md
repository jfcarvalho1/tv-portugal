# TV Portugal (e do mundo) — listas M3U livres e legais

Só fontes públicas e oficiais: **M3UPT** (canais portugueses + guia), **iptv-org** (links públicos de todo o mundo) e **Radio Browser** (rádios).
Sem pirataria, sem religião, sem televendas. Sem canais para adultos. Estrangeiros só a partir de **720p**. Links mortos saem sozinhos.

## Listas (actualizadas todos os dias)
- `listas/tv/*.m3u` — a mesma TV dividida por país (listas pequenas para o VLC do iPhone)
- `listas/tv.m3u` — TV em directo, por países: Portugal (1+), Espanha (1001+), França (2001+), Itália (3001+), Holanda (4001+), Bélgica (5001+), Alemanha (6001+), Brasil (7001+), EUA (8001+), Internacional (9001+), resto do mundo (10001+)
- `listas/radios.m3u` — rádios portuguesas (nacionais 1+, regionais e locais 101+)
- `listas/relatorio.txt` — lista canal a canal e o que ficou de fora (e porquê)

## Ver no VLC (Linux)
`vlc https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/listas/tv.m3u`
ou no VLC: Media > Abrir fluxo de rede > colar o endereço.

## Jellyfin
TV em directo > Sintonizador M3U > o mesmo endereço. Guia: `https://m3upt.com/epg`.

## Mudar opções
Editar `config.txt` (ex.: `EXCLUIR=fashion, rt news`). A actualização seguinte já respeita.

## No NAS (Jellyfin) — um só comando
No terminal do NAS (Debian):
```
curl -fsSL https://raw.githubusercontent.com/jfcarvalho1/tv-portugal/main/nas/instalar.sh | sudo bash
```
Pede a chave API do Jellyfin (Painel de controlo > Chaves de API > +). Depois fica:
- **TV em directo** — lista do GitHub + **SIC** (canal 3) através de um intermediário no NAS, que pede a emissão oficial como se fosse o site sic.pt. Só para uso em casa (fora de casa: Tailscale).
- **Biblioteca "Rádios"** — uma pasta por grupo/distrito, actualizada às 07:40 e 18:10
