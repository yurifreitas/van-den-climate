# -*- coding: utf-8 -*-
"""Monta os slides do carrossel de divulgacao a partir de capturas da demo.

    CAPTURAS_DIR=<pasta com screenshot-*.jpg> python scripts/build_carrossel.py

Formato 1080x1350 (4:5) — o retrato que o feed do LinkedIn menos corta.
Paleta identica a do projeto (web/src/theme/palette.ts): fundo abissal, giz
para texto, bruma para nota, menta como unico acento de interface.

As CAPTURAS nao sao versionadas, so os slides e este gerador: elas dependem de
janela, tema e da data do snapshot, e o proprio slide ja declara a data.
"""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CAPTURAS = Path(os.environ.get("CAPTURAS_DIR", "capturas"))
SAIDA = Path(__file__).resolve().parents[1] / "docs" / "carrossel"
SAIDA.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1350
ABISSAL = (15, 21, 24)
CARTA = (21, 30, 35)
GIZ = (216, 222, 224)
BRUMA = (138, 151, 158)
BRUMA_FRACA = (94, 107, 114)
MENTA = (22, 160, 168)
LINHA = (36, 49, 57)

F = "C:/Windows/Fonts/"
def fonte(nome, tam):
    return ImageFont.truetype(F + nome, tam)

TIT = lambda t: fonte("CascadiaMono.ttf", t)
TXT = lambda t: fonte("calibri.ttf", t)
TXT_B = lambda t: fonte("calibrib.ttf", t)


def quebrar(draw, texto, fnt, largura):
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = (atual + " " + palavra).strip()
        if draw.textlength(teste, font=fnt) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def base(indice=None, total=None):
    img = Image.new("RGB", (W, H), ABISSAL)
    d = ImageDraw.Draw(img)
    # Barra de acento no topo — o mesmo gesto da interface.
    d.rectangle([0, 0, W, 6], fill=MENTA)
    d.text((64, 44), "CENTRAL DE RISCO CLIMATICO RS", font=TIT(22), fill=BRUMA)
    if indice is not None:
        d.text((W - 64, 44), f"{indice}/{total}", font=TIT(22), fill=BRUMA_FRACA, anchor="ra")
    return img, d


def rodape(d, texto="github.com/yurifreitas/van-den-climate"):
    d.line([(64, H - 108), (W - 64, H - 108)], fill=LINHA, width=1)
    d.text((64, H - 84), texto, font=TIT(21), fill=BRUMA_FRACA)


def encaixar(img_fundo, caminho, caixa, recorte=None):
    """Cola a captura dentro da caixa (x, y, w, h), INTEIRA.

    Cabe por dentro, nao cobre: cobrir corta as bordas, e num painel a borda e
    justamente onde ficam o rotulo da coluna e o primeiro numero. O primeiro
    corte comeu o "R" de RISCO e o "4" de 497 — perder o numero e pior que
    deixar uma faixa de fundo.
    """
    foto = Image.open(caminho).convert("RGB")
    if recorte:
        foto = foto.crop(recorte)
    x, y, w, h = caixa
    escala = min(w / foto.width, h / foto.height)
    novo = foto.resize((max(1, int(foto.width * escala)), max(1, int(foto.height * escala))),
                       Image.LANCZOS)
    ox = x + (w - novo.width) // 2
    oy = y + (h - novo.height) // 2
    img_fundo.paste(novo, (ox, oy))
    d = ImageDraw.Draw(img_fundo)
    d.rectangle([ox, oy, ox + novo.width, oy + novo.height], outline=LINHA, width=2)


def slide_texto(indice, total, titulo, corpo, destaque=None, arquivo="s.png"):
    img, d = base(indice, total)
    # Altura do bloco, para centralizar: texto colado no topo deixa metade do
    # slide vazia, e no feed isso le como slide inacabado.
    n_tit = len(quebrar(d, titulo, TIT(52), W - 128))
    n_corpo = len(quebrar(d, corpo, TXT(38), W - 128))
    altura = n_tit * 74 + 40 + (140 if destaque else 0) + n_corpo * 54
    y = max(200, (H - altura) // 2 - 40)
    for linha in quebrar(d, titulo, TIT(52), W - 128):
        d.text((64, y), linha, font=TIT(52), fill=GIZ)
        y += 74
    y += 40
    if destaque:
        d.text((64, y), destaque, font=TIT(96), fill=MENTA)
        y += 140
    for linha in quebrar(d, corpo, TXT(38), W - 128):
        d.text((64, y), linha, font=TXT(38), fill=BRUMA)
        y += 54
    rodape(d)
    img.save(SAIDA / arquivo)
    return SAIDA / arquivo


def slide_tela(indice, total, titulo, legenda, captura, arquivo, recorte=None):
    img, d = base(indice, total)
    y = 150
    for linha in quebrar(d, titulo, TIT(44), W - 128):
        d.text((64, y), linha, font=TIT(44), fill=GIZ)
        y += 62
    y += 16
    encaixar(img, captura, (64, y, W - 128, 640), recorte)
    y += 684
    for linha in quebrar(d, legenda, TXT(34), W - 128):
        d.text((64, y), linha, font=TXT(34), fill=BRUMA)
        y += 48
    rodape(d)
    img.save(SAIDA / arquivo)
    return SAIDA / arquivo


def main():
    caps = sorted(CAPTURAS.glob("screenshot-*.jpg"))
    por_indice = {p.name.rsplit("-", 1)[-1].split(".")[0]: p for p in caps}
    risco = por_indice.get("3")
    risco_mapa = por_indice.get("5")
    terreno = por_indice.get("7")
    recursos = por_indice.get("8")

    total = 7
    feitos = []

    feitos.append(slide_texto(
        1, total,
        "Todo numero diz de onde veio — e onde deixa de valer.",
        "Central de risco climatico do Rio Grande do Sul, com dados publicos. "
        "Cada valor carrega um selo: medido, modelado ou sintetico. Painel sem "
        "selo e tratado como bug, nao como escolha de design.",
        arquivo="01-capa.png",
    ))

    if risco:
        feitos.append(slide_tela(
            2, total, "Onde agir antes da proxima temporada",
            "497 municipios ordenados por prioridade preventiva. Nao e previsao de "
            "cheia: e a pergunta que tem dono e prazo — se ha orcamento para 30 "
            "municipios antes da primavera, quais 30.",
            risco, "02-risco.png", recorte=(300, 75, 1290, 700),
        ))

    if risco_mapa:
        feitos.append(slide_tela(
            3, total, "Da lacuna declarada a acao nomeada",
            "2.062 acoes identificadas, 1.285 que cabem antes da primavera. Cada "
            "uma sai de um dado declarado pela propria prefeitura ao IBGE — nao de "
            "recomendacao generica.",
            risco_mapa, "03-plano.png", recorte=(300, 85, 1290, 720),
        ))

    if terreno:
        feitos.append(slide_tela(
            4, total, "No que a chuva cai — e como o solo esta hoje",
            "139 municipios com solo encharcado agora, medido pela chuva dos cinco "
            "dias anteriores (NOAA, ate ontem). A mesma chuva escoa quase o dobro "
            "quando o perfil ja esta cheio.",
            terreno, "04-terreno.png", recorte=(300, 45, 1290, 700),
        ))

    feitos.append(slide_texto(
        5, total,
        "A infraestrutura critica esta 4x mais exposta que o comercio.",
        "13,8% das subestacoes, captacoes e reservatorios ficam sobre terreno que "
        "ja foi agua, contra 3,5% dos supermercados. Nao e acaso, e projeto: "
        "captacao precisa ficar junto do rio, e subestacao procura terreno plano e "
        "barato — que na planicie e a varzea.",
        destaque="13,8% x 3,5%",
        arquivo="05-exposicao.png",
    ))

    if recursos:
        feitos.append(slide_tela(
            6, total, "17 papeis, 5 familias, e o que alaga junto",
            "Hospital, quartel, abrigo, subestacao, captacao, combustivel. Papeis de "
            "familias diferentes nao se somam: um atende ferido, o outro decide se a "
            "cidade come na quinta-feira.",
            recursos, "06-recursos.png", recorte=(380, 50, 1520, 700),
        ))

    feitos.append(slide_texto(
        7, total,
        "O gargalo nunca foi modelo. E acesso.",
        "Isto e o mais basico que da para fazer com os dados ao meu alcance. Com "
        "telemetria — nivel de rio, estacao automatica, casa de bomba — a mesma "
        "arquitetura roda em tempo real, sem reescrever. O que me interessa nao e "
        "prever melhor: e decidir melhor, com o recurso que ja existe e visibilidade "
        "para quem assina a decisao.",
        arquivo="07-fecho.png",
    ))

    for p in feitos:
        print(p)


if __name__ == "__main__":
    main()
