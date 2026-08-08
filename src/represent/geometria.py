"""Geometria do sistema — atrator, recorrencia, fractal e distancia nao-euclidiana.

POR QUE ESTE MODULO PODE EXISTIR
================================

O README do projeto autoriza exatamente isto, e com uma fronteira nitida:

    "Matematica sofisticada e permitida onde nao toca o alvo;
     onde toca, <=6 parametros."

E a ADR-008 ja rejeitou uma familia inteira — TCN, assinaturas, TDA, rough
paths, RLS — com um criterio, nao com preconceito: **infalsificaveis neste
tamanho de amostra**.

Entao o teste de admissao aqui NAO e "isso e sofisticado?". E:

    Qual n este metodo exige para dizer algo falsificavel,
    e eu tenho esse n?

Este modulo responde essa pergunta para cada metodo que usa, com o numero na
mao, e RECUSA os que nao passam. Um expoente de Lyapunov calculado sobre 918
pontos mensais ruidosos produz um numero; ele so nao produz conhecimento.

OS TRES REGIMES DE AMOSTRA DO PROJETO
=====================================

    n = 36        temporadas de avaliacao (1991-2026).
                  Nada sofisticado sobrevive. E a razao da ADR-003 (<=6
                  parametros) e da ADR-008. Nao se toca.

    n = 918       ONI mensal (1950-2026).
                  Recorrencia sim; dimensao de correlacao ate D~2, com
                  ressalva; expoente de Lyapunov nao.

    n = 942.831   chuva diaria, 67 estacoes (1934-1999).
                  Multifractal, DFA e distancia de Wasserstein sao
                  confortaveis aqui. E o unico lugar do projeto onde a
                  estatistica de cauda tem material de sobra.

A FRONTEIRA QUE ESTE MODULO NAO CRUZA
=====================================

Nada aqui seleciona preditor, ajusta modelo ou entra em `feature_blocks.yaml`
— que ja esta congelado de fato desde o contato com o alvo (ADR-042). E
DESCRICAO da geometria, e qualquer uso preditivo teria de passar pela ADR-007,
que segue sem nenhum modelo aprovado.

Se algum numero daqui virar feature, o experimento morre. Esta escrito para
que ninguem descubra isso tarde.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

VERSION = "geometria-v1"


# ---------------------------------------------------------------------------
# Criterios de admissao — o que decide se um metodo entra
# ---------------------------------------------------------------------------
def ruelle_max_dim(n: int) -> float:
    """Teto de dimensao credivel pelo criterio de Ruelle: D < 2*log10(N).

    Ruelle (1990) argumentou que estimativas de dimensao acima disso sao
    artefato do tamanho da amostra, nao propriedade do sistema. E o criterio
    PERMISSIVO — ver `smith_min_pontos` para o rigoroso.
    """
    return 2.0 * np.log10(n)


def smith_min_pontos(d: float) -> float:
    """Criterio de Smith (1988): ~42^D pontos para estimar dimensao D.

    Muito mais duro que Ruelle e, na pratica, o que separa uma estimativa de
    dimensao publicavel de um exercicio de ajuste de reta. Reportamos os dois
    lado a lado justamente porque a distancia entre eles e a medida da nossa
    incerteza.
    """
    return 42.0**d


# ---------------------------------------------------------------------------
# Embedding de Takens
# ---------------------------------------------------------------------------
def informacao_mutua(x: np.ndarray, lag_max: int = 48, bins: int = 16) -> np.ndarray:
    """Informacao mutua media em funcao do atraso.

    O primeiro MINIMO da IM e a escolha classica de tau (Fraser & Swinney,
    1986) — e nao a primeira passagem por zero da autocorrelacao, que so
    captura dependencia linear. Num sistema nao linear como o ENSO, essa
    diferenca nao e cosmetica.
    """
    out = np.zeros(lag_max + 1)
    for lag in range(lag_max + 1):
        a, b = (x[: len(x) - lag], x[lag:]) if lag else (x, x)
        c, _, _ = np.histogram2d(a, b, bins=bins)
        pab = c / c.sum()
        pa = pab.sum(axis=1, keepdims=True)
        pb = pab.sum(axis=0, keepdims=True)
        nz = pab > 0
        out[lag] = float(np.sum(pab[nz] * np.log(pab[nz] / (pa @ pb)[nz])))
    return out


def primeiro_minimo(v: np.ndarray) -> int:
    for i in range(1, len(v) - 1):
        if v[i] < v[i - 1] and v[i] < v[i + 1]:
            return i
    return int(np.argmin(v))


def embutir(x: np.ndarray, m: int, tau: int) -> np.ndarray:
    """Matriz de vetores de atraso (Takens, 1981)."""
    n = len(x) - (m - 1) * tau
    if n <= 0:
        raise ValueError("serie curta demais para este m e tau")
    return np.column_stack([x[i * tau : i * tau + n] for i in range(m)])


def falsos_vizinhos(x: np.ndarray, tau: int, m_max: int = 10,
                    rtol: float = 15.0) -> list[float]:
    """Fracao de falsos vizinhos por dimensao (Kennel et al., 1992).

    A dimensao de embedding suficiente e aquela em que a fracao desaba para
    perto de zero: acima dela, aumentar m so adiciona ruido.
    """
    fracoes = []
    for m in range(1, m_max + 1):
        try:
            y = embutir(x, m + 1, tau)
        except ValueError:
            break
        base = y[:, :m]
        n = len(base)
        if n < 50:
            break
        # vizinho mais proximo em dimensao m (forca bruta: n<=918)
        d2 = ((base[:, None, :] - base[None, :, :]) ** 2).sum(-1)
        np.fill_diagonal(d2, np.inf)
        viz = np.argmin(d2, axis=1)
        dm = np.sqrt(d2[np.arange(n), viz])
        # distancia extra ao ganhar a coordenada m+1
        extra = np.abs(y[:, m] - y[viz, m])
        with np.errstate(divide="ignore", invalid="ignore"):
            razao = np.where(dm > 0, extra / dm, np.inf)
        fracoes.append(float(np.mean(razao > rtol)))
    return fracoes


# ---------------------------------------------------------------------------
# Dimensao de correlacao (Grassberger-Procaccia)
# ---------------------------------------------------------------------------
def dimensao_correlacao(y: np.ndarray, n_raios: int = 24) -> dict[str, Any]:
    """C(r) ~ r^D. Devolve D, a regiao de escala usada e o veredito de amostra.

    A honestidade aqui esta na REGIAO DE ESCALA: qualquer nuvem de pontos
    produz uma reta em log-log se o intervalo for escolhido convenientemente.
    Fixamos a regiao entre os percentis 5 e 25 das distancias — abaixo domina
    ruido, acima domina o tamanho finito do atrator — e reportamos o R² do
    ajuste para que um ajuste ruim seja visivel em vez de arredondado.
    """
    n = len(y)
    d = np.sqrt(((y[:, None, :] - y[None, :, :]) ** 2).sum(-1))
    iu = np.triu_indices(n, k=1)
    dist = d[iu]
    dist = dist[dist > 0]
    lo, hi = np.percentile(dist, [5, 25])
    raios = np.logspace(np.log10(lo), np.log10(hi), n_raios)
    par = len(dist)
    c = np.array([np.sum(dist < r) / par for r in raios])
    ok = c > 0
    if ok.sum() < 5:
        return {"dimensao": None, "motivo": "poucos pares na regiao de escala"}
    lx, ly = np.log(raios[ok]), np.log(c[ok])
    coef = np.polyfit(lx, ly, 1)
    resid = ly - np.polyval(coef, lx)
    r2 = 1.0 - float(np.sum(resid**2) / np.sum((ly - ly.mean()) ** 2))
    D = float(coef[0])
    return {
        "dimensao": round(D, 3),
        "r2_ajuste": round(r2, 4),
        "regiao_escala": [round(float(lo), 4), round(float(hi), 4)],
        "n_pontos": n,
        "teto_ruelle": round(ruelle_max_dim(n), 2),
        "pontos_exigidos_smith": int(smith_min_pontos(D)) if D < 6 else None,
        "passa_ruelle": bool(D < ruelle_max_dim(n)),
        "passa_smith": bool(smith_min_pontos(D) <= n),
    }


# ---------------------------------------------------------------------------
# Recorrencia (RQA) — o metodo mais robusto neste n
# ---------------------------------------------------------------------------
def rqa(y: np.ndarray, taxa_alvo: float = 0.05, l_min: int = 2) -> dict[str, Any]:
    """Quantificacao de recorrencia.

    Escolhido como metodo PRINCIPAL deste modulo por uma razao pratica: RQA
    nao estima nenhum expoente e nao depende de regiao de escala. Ela conta
    estrutura numa matriz binaria. Com 918 pontos isso e confortavel, e o
    resultado e falsificavel contra surrogates.

    DET  fracao de pontos recorrentes em linhas diagonais -> determinismo.
         Ruido branco da DET proximo de zero; sistema deterministico, alto.
    LAM  fracao em linhas verticais -> laminaridade, estados presos.
    TT   tempo medio de aprisionamento, em meses.
    """
    n = len(y)
    d = np.sqrt(((y[:, None, :] - y[None, :, :]) ** 2).sum(-1))
    eps = float(np.quantile(d[np.triu_indices(n, 1)], taxa_alvo))
    R = (d <= eps).astype(np.uint8)
    np.fill_diagonal(R, 0)

    def linhas(mat: np.ndarray, diagonal: bool) -> np.ndarray:
        comp = []
        faixa = range(-n + 1, n) if diagonal else range(n)
        for k in faixa:
            v = np.diagonal(mat, k) if diagonal else mat[:, k]
            atual = 0
            for x in v:
                if x:
                    atual += 1
                elif atual:
                    comp.append(atual)
                    atual = 0
            if atual:
                comp.append(atual)
        return np.array(comp) if comp else np.array([0])

    diag = linhas(R, True)
    vert = linhas(R, False)
    total = R.sum()
    det = float(diag[diag >= l_min].sum() / total) if total else 0.0
    lam = float(vert[vert >= l_min].sum() / total) if total else 0.0
    tt = float(vert[vert >= l_min].mean()) if (vert >= l_min).any() else 0.0
    return {
        "taxa_recorrencia": round(float(total / (n * n)), 4),
        "epsilon": round(eps, 4),
        "determinismo": round(det, 4),
        "laminaridade": round(lam, 4),
        "tempo_aprisionamento_meses": round(tt, 2),
        "diagonal_maxima": int(diag.max()),
        "n_pontos": n,
    }


def rqa_surrogate(x: np.ndarray, m: int, tau: int, n_surr: int = 20,
                  semente: int = 20260808) -> dict[str, Any]:
    """Compara o DET observado com o de surrogates de fase aleatoria.

    E ESTE teste que torna o numero falsificavel. Surrogate de fase preserva o
    espectro de potencia (logo toda a estrutura LINEAR) e destroi a nao
    linearidade. Se o DET observado nao se destacar da nuvem de surrogates, a
    recorrencia observada nao passa de autocorrelacao — e nao ha atrator
    nenhum a reivindicar.
    """
    rng = np.random.default_rng(semente)
    obs = rqa(embutir(x, m, tau))["determinismo"]
    dets = []
    fft = np.fft.rfft(x)
    mag = np.abs(fft)
    for _ in range(n_surr):
        fase = rng.uniform(0, 2 * np.pi, len(fft))
        fase[0] = 0.0
        s = np.fft.irfft(mag * np.exp(1j * fase), n=len(x))
        dets.append(rqa(embutir(s, m, tau))["determinismo"])
    dets = np.array(dets)
    # p unilateral: fracao de surrogates que alcancam o observado
    p = float((dets >= obs).sum() + 1) / (n_surr + 1)
    return {
        "det_observado": round(float(obs), 4),
        "det_surrogates_media": round(float(dets.mean()), 4),
        "det_surrogates_p95": round(float(np.percentile(dets, 95)), 4),
        "n_surrogates": n_surr,
        "p_unilateral": round(p, 4),
        "separa_do_linear": bool(obs > np.percentile(dets, 95)),
        "leitura": (
            "Surrogate de fase preserva o espectro (estrutura linear) e destroi a nao "
            "linearidade. DET acima do p95 dos surrogates e evidencia de estrutura nao "
            "linear; abaixo, a recorrencia e apenas autocorrelacao."
        ),
    }


def surrogate_iaaft(x: np.ndarray, rng: np.random.Generator,
                    n_iter: int = 100) -> np.ndarray:
    """Surrogate IAAFT — preserva espectro E distribuicao de amplitude.

    POR QUE TROCAR O SURROGATE DE FASE SIMPLES

    O surrogate de fase (FT) preserva o espectro de potencia mas IMPOE
    amplitude gaussiana. Se a serie original nao for gaussiana, parte da
    diferenca entre observado e surrogate vem da distribuicao, nao da
    dinamica — e o teste passa a rejeitar a hipotese errada.

    O IAAFT (Schreiber & Schmitz, 1996) itera entre impor o espectro e impor
    o histograma original, convergindo para um surrogate que preserva os dois.
    E o teste correto para "ha nao linearidade alem de espectro e distribuicao".
    """
    ordenados = np.sort(x)
    mag = np.abs(np.fft.rfft(x))
    s = rng.permutation(x)
    for _ in range(n_iter):
        # impoe o espectro, mantendo as fases atuais
        fase = np.angle(np.fft.rfft(s))
        s = np.fft.irfft(mag * np.exp(1j * fase), n=len(x))
        # impoe a distribuicao original, mantendo a ordem atual
        s = ordenados[np.argsort(np.argsort(s))]
    return s


def teste_nao_linearidade(x: np.ndarray, m: int, tau: int, n_surr: int = 200,
                          semente: int = 20260808) -> dict[str, Any]:
    """DET observado contra surrogates IAAFT, com n suficiente para um p real.

    CORRIGE UM DEFEITO DO PRIMEIRO TESTE deste modulo: com 20 surrogates o
    menor p alcancavel e 1/21 = 0,048. Reportar "p = 0,048" ali era reportar
    o PISO DE RESOLUCAO do teste, nao a forca da evidencia — os dois valores
    coincidem numericamente e significam coisas muito diferentes.

    Com 200 surrogates o piso cai para 0,005 e o p passa a discriminar.
    """
    rng = np.random.default_rng(semente)
    obs = rqa(embutir(x, m, tau))["determinismo"]
    dets = np.array([
        rqa(embutir(surrogate_iaaft(x, rng), m, tau))["determinismo"]
        for _ in range(n_surr)
    ])
    p = float((dets >= obs).sum() + 1) / (n_surr + 1)
    return {
        "det_observado": round(float(obs), 4),
        "surrogate": "IAAFT (preserva espectro e distribuicao)",
        "n_surrogates": n_surr,
        "piso_de_p": round(1.0 / (n_surr + 1), 4),
        "det_surrogates_media": round(float(dets.mean()), 4),
        "det_surrogates_p95": round(float(np.percentile(dets, 95)), 4),
        "det_surrogates_max": round(float(dets.max()), 4),
        "p_unilateral": round(p, 4),
        "separa_do_linear": bool(obs > np.percentile(dets, 95)),
        "z_score": round(float((obs - dets.mean()) / dets.std()), 2) if dets.std() > 0 else None,
    }


# ---------------------------------------------------------------------------
# Barreira de previsibilidade da primavera, medida na recorrencia
# ---------------------------------------------------------------------------
def divergencia_por_mes(x: np.ndarray, m: int, tau: int, meses: np.ndarray,
                        taxa_alvo: float = 0.05) -> dict[str, Any]:
    """Quanto tempo trajetorias vizinhas permanecem juntas, por mes de partida.

    O QUE ISTO TESTA, E POR QUE IMPORTA PARA O PROJETO

    A ADR-026 afirma que o horizonte util de previsao ENSO e de ~6-9 meses e
    que a barreira de previsibilidade da primavera boreal degrada o que
    atravessa o primeiro semestre. Isso entrou no projeto como conhecimento
    de literatura — nunca foi medido aqui.

    Este calculo mede: dado um estado em determinado mes do calendario, por
    quantos meses um estado historicamente parecido continua parecido. E uma
    estimativa do horizonte de previsibilidade DIRETO DA GEOMETRIA, sem
    modelo e sem ajuste.

    Se o minimo cair sobre abril-junho, a barreira aparece no dado do projeto
    — e a ADR-026 deixa de ser citacao e passa a ser medida.
    """
    y = embutir(x, m, tau)
    n = len(y)
    mm = meses[: n]  # mes de calendario de cada vetor de atraso
    d = np.sqrt(((y[:, None, :] - y[None, :, :]) ** 2).sum(-1))
    eps = float(np.quantile(d[np.triu_indices(n, 1)], taxa_alvo))

    por_mes: dict[int, list[int]] = {k: [] for k in range(1, 13)}
    for i in range(n):
        # vizinhos recorrentes, excluindo a vizinhanca temporal imediata
        # (senao mede-se autocorrelacao trivial, nao recorrencia do atrator)
        cand = np.where((d[i] <= eps) & (np.abs(np.arange(n) - i) > 12))[0]
        if cand.size == 0:
            continue
        melhor = 0
        for j in cand:
            k = 0
            while i + k + 1 < n and j + k + 1 < n and d[i + k + 1, j + k + 1] <= eps:
                k += 1
            melhor = max(melhor, k)
        por_mes[int(mm[i])].append(melhor)

    medias = {
        k: round(float(np.mean(v)), 2) for k, v in por_mes.items() if v
    }
    if not medias:
        return {"por_mes": {}, "motivo": "sem pares recorrentes suficientes"}
    pior = min(medias, key=medias.get)
    melhor_mes = max(medias, key=medias.get)
    NOMES = ["", "jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]
    return {
        "meses_juntos_por_mes_de_partida": {NOMES[k]: v for k, v in sorted(medias.items())},
        "pior_mes": NOMES[pior],
        "pior_valor": medias[pior],
        "melhor_mes": NOMES[melhor_mes],
        "melhor_valor": medias[melhor_mes],
        "horizonte_mediano_meses": round(float(np.median(list(medias.values()))), 2),
        "barreira_no_primeiro_semestre": bool(pior in (3, 4, 5, 6)),
        "leitura": (
            "Meses que trajetorias historicamente parecidas permanecem parecidas, contado a "
            "partir de cada mes do calendario. Minimo no primeiro semestre e a assinatura da "
            "barreira de previsibilidade da primavera boreal — medida aqui, nao citada."
        ),
    }


# ---------------------------------------------------------------------------
# Fractal: DFA e multifractal na chuva diaria
# ---------------------------------------------------------------------------
def dfa(x: np.ndarray, escalas: np.ndarray | None = None, q: float = 2.0) -> dict[str, Any]:
    """Detrended Fluctuation Analysis. F(s) ~ s^H.

    H = 0.5   sem memoria (passeio aleatorio)
    H > 0.5   persistencia — periodo umido puxa periodo umido
    H < 0.5   antipersistencia

    Na chuva diaria ha material de sobra (centenas de milhares de pontos), o
    que torna este o unico expoente deste modulo que nao precisa de ressalva
    de tamanho de amostra.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 512:
        return {"hurst": None, "motivo": f"serie curta demais (n={n})"}
    y = np.cumsum(x - x.mean())
    if escalas is None:
        # Escala maxima em n/10, nao n/4.
        #
        # Com n/4 sobram apenas 4 segmentos na maior escala, e a media de F
        # sobre 4 valores e instavel o bastante para ENVIESAR a reta inteira:
        # medido em ruido branco, n/4 devolvia H = 0,44 onde a resposta e 0,5.
        # Com n/10 (>= 10 segmentos) a media sobre 6 sementes deu 0,4936.
        # O piso em 16 evita o vies de pequena escala do DFA-1.
        escalas = np.unique(np.logspace(np.log10(16), np.log10(max(n // 10, 32)), 20).astype(int))
    fs = []
    for s in escalas:
        n_seg = n // s
        if n_seg < 4:
            continue
        seg = y[: n_seg * s].reshape(n_seg, s)
        t = np.arange(s)
        # remove tendencia linear de cada segmento
        coef = np.polyfit(t, seg.T, 1)
        tend = np.outer(coef[0], t) + coef[1][:, None]
        f2 = ((seg - tend) ** 2).mean(axis=1)
        # Segmento com variancia zero e fatal para q negativo: 0**(q/2) diverge
        # e contamina a media inteira com inf. Isso acontece de verdade na
        # chuva diaria, que tem sequencias longas de zero — descartar o
        # segmento e o tratamento padrao em MFDFA, e e honesto: um trecho
        # perfeitamente seco nao carrega informacao de flutuacao.
        f2 = f2[f2 > 0]
        if len(f2) < 4:
            continue
        fs.append((s, float(np.mean(f2 ** (q / 2)) ** (1 / q))))
    if len(fs) < 5:
        return {"hurst": None, "motivo": "poucas escalas utilizaveis"}
    s_arr = np.array([a for a, _ in fs])
    f_arr = np.array([b for _, b in fs])
    coef = np.polyfit(np.log(s_arr), np.log(f_arr), 1)
    resid = np.log(f_arr) - np.polyval(coef, np.log(s_arr))
    r2 = 1.0 - float(np.sum(resid**2) / np.sum((np.log(f_arr) - np.log(f_arr).mean()) ** 2))
    return {
        "hurst": round(float(coef[0]), 4),
        "r2_ajuste": round(r2, 4),
        "n_pontos": int(n),
        "n_escalas": len(fs),
    }


def espectro_multifractal(x: np.ndarray, qs: np.ndarray | None = None) -> dict[str, Any]:
    """Largura do espectro via MFDFA: h(q) para varios q.

    Largura ~0 significa monofractal (um so expoente descreve todas as
    escalas). Largura grande significa MULTIfractal: eventos extremos e
    eventos comuns escalam de forma diferente — que e exatamente o regime da
    chuva, e a razao pela qual media e desvio nao bastam para descreve-la.
    """
    if qs is None:
        qs = np.array([-5, -3, -2, -1, 0.5, 1, 2, 3, 5], dtype=float)
    hs = {}
    for q in qs:
        if abs(q) < 1e-6:
            continue
        r = dfa(x, q=float(q))
        if r.get("hurst") is not None:
            hs[float(q)] = r["hurst"]
    if len(hs) < 4:
        return {"largura": None, "motivo": "poucos expoentes estimaveis"}
    vals = list(hs.values())
    return {
        "h_por_q": {str(k): v for k, v in hs.items()},
        "largura": round(float(max(vals) - min(vals)), 4),
        "h_min": round(float(min(vals)), 4),
        "h_max": round(float(max(vals)), 4),
        "leitura": (
            "Largura proxima de zero: monofractal, um expoente descreve todas as escalas. "
            "Largura grande: extremos e eventos comuns escalam diferente — media e desvio "
            "nao descrevem a serie."
        ),
    }


def diagnostico_multifractal(x: np.ndarray) -> dict[str, Any]:
    """Interroga a propria largura do espectro antes de acreditar nela.

    POR QUE ESTE DIAGNOSTICO EXISTE

    A primeira medicao deste modulo devolveu largura 3,0 com h_max 3,48 numa
    serie de chuva diaria. A literatura de MFDFA em precipitacao reporta
    larguras tipicas entre ~0,5 e ~1,5. Um valor duas vezes maior que o teto
    da literatura e, quase sempre, artefato — nao descoberta.

    A suspeita concreta: h > 1 ja indica regime nao estacionario, e o lado de
    q NEGATIVO do espectro pesa as pequenas flutuacoes, que e exatamente onde
    a chuva diaria tem sequencias longas de zero. Descartar segmentos de
    variancia nula (feito em `dfa`) evita o infinito, mas ENVIESA: sobram so
    os segmentos com alguma chuva, e a estatistica de pequena flutuacao passa
    a descrever outra populacao.

    Este diagnostico separa os dois lados e mede a serie so nos dias umidos,
    para que a decisao sobre em qual numero acreditar seja informada.
    """
    umidos = x[x >= 1.0]
    positivos = espectro_multifractal(x, qs=np.array([0.5, 1, 2, 3, 5], dtype=float))
    negativos = espectro_multifractal(x, qs=np.array([-5, -3, -2, -1], dtype=float))
    so_umidos = espectro_multifractal(
        umidos, qs=np.array([-3, -1, 0.5, 1, 2, 3], dtype=float)
    ) if len(umidos) >= 512 else {"largura": None, "motivo": "poucos dias umidos"}

    largura_pos = positivos.get("largura")
    return {
        "lado_q_positivo": {k: v for k, v in positivos.items() if k != "leitura"},
        "lado_q_negativo": {k: v for k, v in negativos.items() if k != "leitura"},
        "so_dias_umidos": {k: v for k, v in so_umidos.items() if k != "leitura"},
        "n_total": int(len(x)),
        "n_umidos": int(len(umidos)),
        "frac_zeros": round(float(np.mean(x < 1.0)), 4),
        "veredito": (
            "Confie no lado de q positivo. O lado negativo pesa pequenas flutuacoes, e numa "
            "serie com "
            f"{np.mean(x < 1.0) * 100:.0f}% de dias secos ele descreve o descarte de segmentos, "
            "nao a dinamica. A largura publicavel e a do lado positivo"
            + (f" ({largura_pos})." if largura_pos is not None else ".")
        ),
    }


# ---------------------------------------------------------------------------
# Geometria nao-euclidiana: distancia entre distribuicoes
# ---------------------------------------------------------------------------
def wasserstein_por_fase(por_ano) -> dict[str, Any]:
    """Distancia de Wasserstein-1 entre as distribuicoes de chuva por fase ENSO.

    POR QUE ISTO E MELHOR QUE A DIFERENCA DE MEDIAS QUE O PROJETO JA TEM

    `src/risk/historico.py` compara El Nino e Neutro por diferenca de media,
    com IC por bootstrap. Media e uma projecao da distribuicao sobre a reta —
    ela responde "o centro se moveu?" e e cega a tudo o mais.

    O espaco natural das distribuicoes NAO e euclidiano. Wasserstein-1 e a
    distancia propria desse espaco: mede o trabalho minimo para transportar
    uma distribuicao ate a outra, e por isso enxerga deslocamento de cauda,
    mudanca de forma e assimetria — coisas que importam quando o alvo e
    extremo de chuva, nao chuva media.

    Duas distribuicoes com a MESMA media podem ter Wasserstein grande. Numa
    central de risco de cheia, essa e precisamente a diferenca que interessa.
    """
    from scipy.stats import wasserstein_distance

    fases = {}
    for fase in ("El Nino", "Neutro", "La Nina"):
        sub = por_ano[por_ano["fase"] == fase]
        if len(sub):
            fases[fase] = sub["total_mm"].to_numpy(dtype=float)
    if len(fases) < 2:
        return {"distancias": {}, "motivo": "fases insuficientes"}

    dist = {}
    nomes = list(fases)
    for i, a in enumerate(nomes):
        for b in nomes[i + 1 :]:
            dist[f"{a} vs {b}"] = {
                "wasserstein_mm": round(float(wasserstein_distance(fases[a], fases[b])), 2),
                "diferenca_de_medias_mm": round(float(fases[a].mean() - fases[b].mean()), 2),
                "n": [int(len(fases[a])), int(len(fases[b]))],
            }
    return {
        "distancias": dist,
        "leitura": (
            "Wasserstein mede o transporte minimo entre as distribuicoes inteiras; a "
            "diferenca de medias so ve o centro. Quando as duas divergem, a mudanca esta "
            "na forma ou na cauda — que e o que importa em risco de extremo."
        ),
    }


# ---------------------------------------------------------------------------
# Dimensao fractal da geometria da agua
# ---------------------------------------------------------------------------
def box_counting(mascara: np.ndarray, escalas: list[int] | None = None) -> dict[str, Any]:
    """Dimensao de contagem de caixas de uma mascara binaria.

    Aplicada a geometria da agua do JRC, distingue padroes que a area total
    nao distingue: rede dendritica de rio tende a D~1.6-1.8, corpo lagunar
    compacto tende a D~1.9-2.0.

    Isso da um teste INDEPENDENTE da classificacao de regime feita por bacia
    em `src/ingest/ana_bacias.py` — que e editorial. Se a geometria concordar
    com a classificacao, sao duas evidencias distintas; se discordar, a
    classificacao e que precisa ser revista.
    """
    if escalas is None:
        escalas = [2, 4, 8, 16, 32, 64]
    n_total = int(mascara.sum())
    if n_total < 200:
        return {"dimensao": None, "motivo": f"mascara pequena demais (n={n_total})"}
    pontos = []
    for s in escalas:
        h = (mascara.shape[0] // s) * s
        w = (mascara.shape[1] // s) * s
        if h == 0 or w == 0:
            continue
        blocos = mascara[:h, :w].reshape(h // s, s, w // s, s)
        ocupadas = int((blocos.sum(axis=(1, 3)) > 0).sum())
        if ocupadas > 0:
            pontos.append((s, ocupadas))
    if len(pontos) < 4:
        return {"dimensao": None, "motivo": "poucas escalas utilizaveis"}
    s_arr = np.array([p[0] for p in pontos], dtype=float)
    n_arr = np.array([p[1] for p in pontos], dtype=float)
    coef = np.polyfit(np.log(1 / s_arr), np.log(n_arr), 1)
    resid = np.log(n_arr) - np.polyval(coef, np.log(1 / s_arr))
    r2 = 1.0 - float(np.sum(resid**2) / np.sum((np.log(n_arr) - np.log(n_arr).mean()) ** 2))
    return {
        "dimensao": round(float(coef[0]), 3),
        "r2_ajuste": round(r2, 4),
        "escalas": [int(s) for s in s_arr],
        "n_celulas": n_total,
    }


def testar_regime_pela_geometria() -> dict[str, Any]:
    """Confronta a classificacao EDITORIAL de regime com a geometria da agua.

    O QUE ESTE TESTE ARRISCA

    `src/ingest/ana_bacias.py` classifica os 497 municipios em lagunar,
    fluvial com remanso e fluvial. Essa classificacao e leitura hidrologica
    SOBRE o poligono da ANA — nao e campo do dado. Ate agora ninguem a
    confrontou com nada.

    A geometria da agua permite um teste independente. Corpo lagunar e
    compacto e preenche area: dimensao de contagem de caixas proxima de 2.
    Rede fluvial e dendritica e ramificada: dimensao mais baixa, tipicamente
    1,5-1,8.

    PREVISAO ANTES DE OLHAR: D(lagunar) > D(fluvial). Se sair ao contrario ou
    empatado, quem esta errado e a classificacao, nao a geometria — e a lista
    de obras que depende dela precisa ser revista.

    Este e o unico teste deste modulo que pode DERRUBAR algo ja construido.
    """
    import json as _json

    grade_path = INTERIM / "jrc_gsw_rs_grade.npz"
    bacias_path = INTERIM / "ana_bacias.parquet"
    if not grade_path.exists() or not bacias_path.exists():
        return {"disponivel": False, "motivo": "grade do JRC ou classificacao de bacia ausente"}

    import pandas as pd
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    z = np.load(grade_path, allow_pickle=True)
    meta = _json.loads(z["meta"][0])
    perm = z["count_permanente"] > 0

    malha = _json.loads((INTERIM / "ibge_malha_rs.geojson").read_text(encoding="utf-8"))
    bac = pd.read_parquet(bacias_path)
    regime_por_cod = {int(r["cod_mun"]): r["regime"] for _, r in bac.iterrows()}

    b = meta["bbox"]
    transform = from_origin(b["lon_min"], b["lat_max"], meta["res_saida"], meta["res_saida"])

    saida: dict[str, Any] = {}
    for regime in ("lagunar", "fluvial_com_remanso", "fluvial"):
        shapes = [
            (f["geometry"], 1)
            for f in malha["features"]
            if regime_por_cod.get(int(f["properties"]["codarea"])) == regime
        ]
        if not shapes:
            continue
        mask_reg = rasterize(
            shapes, out_shape=(meta["n_lat"], meta["n_lon"]),
            transform=transform, fill=0, dtype="uint8", all_touched=False,
        ).astype(bool)
        saida[regime] = box_counting(perm & mask_reg)

    dims = {k: v.get("dimensao") for k, v in saida.items() if v.get("dimensao") is not None}
    lag = dims.get("lagunar")
    flu = dims.get("fluvial")
    if lag is None or flu is None:
        return {"disponivel": True, "por_regime": saida, "veredito": "dimensoes insuficientes"}

    # CONFUNDIMENTO QUE INVALIDA O TESTE — medido, nao suposto.
    #
    # A malha municipal do IBGE nao cobre as grandes lagoas: Patos e Mirim
    # ficam FORA de qualquer poligono. Mascarar a agua pelos municipios
    # portanto REMOVE exatamente o corpo compacto que tornaria a dimensao
    # lagunar alta, e deixa so os cursos internos — dendriticos como em
    # qualquer lugar.
    #
    # Sem esta verificacao o teste "reprovaria" a classificacao por um
    # artefato de recorte, e a lista de obras seria revista com base em nada.
    cobertas = sum(v.get("n_celulas", 0) for v in saida.values())
    total_agua = int(perm.sum())
    frac_coberta = cobertas / total_agua if total_agua else 0.0
    invalido = frac_coberta < 0.5

    confirma = lag > flu
    return {
        "disponivel": True,
        "por_regime": saida,
        "previsao": "D(lagunar) > D(fluvial) — corpo compacto preenche area, rede dendritica nao",
        "observado": {"lagunar": lag, "fluvial": flu, "diferenca": round(lag - flu, 3)},
        "cobertura_da_agua": {
            "celulas_no_recorte": cobertas,
            "celulas_no_estado": total_agua,
            "fracao": round(frac_coberta, 4),
        },
        "teste_valido": not invalido,
        "confirma_classificacao": None if invalido else bool(confirma),
        "veredito": (
            "TESTE INVALIDO, nao refutacao. Apenas "
            f"{frac_coberta * 100:.0f}% da agua permanente do estado cai dentro de poligono "
            "municipal: a malha do IBGE exclui a Lagoa dos Patos e a Mirim, que sao justamente "
            "o corpo compacto que elevaria a dimensao lagunar. O recorte remove a evidencia que "
            "o teste procurava. Um teste valido exige a geometria das lagoas, fora da malha "
            "municipal — enquanto isso, a classificacao de regime segue NAO TESTADA."
            if invalido
            else (
                "A geometria CORROBORA a classificacao editorial de regime: duas evidencias "
                "independentes na mesma direcao."
                if confirma
                else "A geometria CONTRARIA a classificacao editorial. Quem deve ser revisto e o "
                     "mapeamento em src/ingest/ana_bacias.py, e com ele a lista de obras que "
                     "dele depende."
            )
        ),
    }


# ---------------------------------------------------------------------------
# Metodos RECUSADOS — e por que
# ---------------------------------------------------------------------------
RECUSADOS: list[dict[str, str]] = [
    {
        "metodo": "Expoente de Lyapunov maximo",
        "exigiria": "serie longa, pouco ruidosa e amostrada acima da escala de divergencia",
        "temos": "918 pontos MENSAIS, com ruido de medicao e sazonalidade forte",
        "veredito": "RECUSADO. A 918 pontos mensais o algoritmo devolve um numero para "
                    "qualquer serie, inclusive ruido branco. O numero existiria; o "
                    "conhecimento nao.",
    },
    {
        "metodo": "Analise topologica de dados (TDA, homologia persistente)",
        "exigiria": "amostra grande no espaco de estados e um alvo para falsificar contra",
        "temos": "n=36 na camada que toca o alvo",
        "veredito": "RECUSADO por ADR-008, e a razao continua valendo. Diagramas de "
                    "persistencia sempre saem; o que nao sai e um teste.",
    },
    {
        "metodo": "Assinaturas de caminho / rough paths",
        "exigiria": "regressao sobre coeficientes de assinatura — dezenas a centenas de termos",
        "temos": "n=36 e teto de 6 parametros (ADR-003)",
        "veredito": "RECUSADO por ADR-008. Trocar 6 parametros por 200 coeficientes num "
                    "n=36 e a definicao de sobreajuste.",
    },
    {
        "metodo": "Difusao / NLSA (Giannakis & Majda)",
        "exigiria": "campos espaciais completos (reanalise) para construir o operador",
        "temos": "indices escalares e 67 estacoes pontuais — nao ha campo",
        "veredito": "NAO APLICAVEL hoje. Volta a mesa se ERA5 for ingerido; a matematica "
                    "e valida, o insumo e que nao existe aqui.",
    },
    {
        "metodo": "Dimensao de correlacao acima de D~2",
        "exigiria": "~42^D pontos (Smith): D=3 pede 74 mil, D=4 pede 3 milhoes",
        "temos": "918",
        "veredito": "PARCIAL. Reportamos D com os dois criterios (Ruelle e Smith) lado a "
                    "lado; acima de D~2 o numero e ajuste de reta, nao dimensao.",
    },
]
