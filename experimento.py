#!/usr/bin/env python3
"""
Experimentos para o relatório final (seção 3.5, itens 2 e 5, e avaliação da Bombe).

  E1 - Falha estrutural: conta coincidências claro==cifrado em muitas letras.
  E2 - Fração de alinhamentos sobreviventes vs. tamanho do crib, comparada
       com o valor teórico (25/26)^n, para texto aleatório e texto em português.
  E3 - Bombe: número de paradas, taxa de sucesso e tempo vs. tamanho do crib
       (ordem dos rotores conhecida, painel com 10 cabos).
  E4 - (opcional, --completo) Bombe com as 60 ordens de rotores.

Saída: resultados/*.csv, resultados/resumo.md e resultados/sobrevivencia.svg
Uso:   python3 experimento.py [--rapido] [--completo]
"""

import argparse
import csv
import os
import random
import statistics
import time

from ataque_crib import ataque_crib
from bombe import recuperar_chave
from enigma import ALFABETO, ROTORES, Enigma, limpar

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "resultados")

# Texto em português escrito pelos autores para servir de corpus de teste.
CORPUS = limpar("""
Relatorio diario do setor norte. Previsao do tempo para amanha: ceu parcialmente nublado com
possibilidade de chuva fraca no periodo da tarde. Vento de direcao sul com intensidade moderada.
Temperatura minima de quatorze graus e maxima de vinte e dois graus. Nada de especial a relatar
nas posicoes avancadas. As tropas permanecem nas mesmas coordenadas informadas ontem e aguardam
novas ordens do comando central. O abastecimento de combustivel e de mantimentos chegou conforme
o previsto e foi distribuido entre as companhias. A estrada que liga a cidade ao porto continua
interditada por causa da ponte danificada pela tempestade. Os engenheiros estimam que o reparo
sera concluido em tres dias. Solicitamos o envio de dois caminhoes e de uma equipe de manutencao
para o deposito do sul. A comunicacao por radio funcionou normalmente durante toda a noite e nao
houve interferencia. O proximo relatorio sera transmitido amanha as seis horas da manha com a
previsao do tempo atualizada e a situacao das estradas da regiao. Fim da mensagem.
""")


def chave_aleatoria(rng, cabos=10, aneis_aleatorios=True):
    rot = rng.sample(list(ROTORES), 3)
    letras = rng.sample(ALFABETO, 2 * cabos)
    painel = " ".join(letras[i] + letras[i + 1] for i in range(0, 2 * cabos, 2))
    aneis = "".join(rng.choices(ALFABETO, k=3)) if aneis_aleatorios else "AAA"
    return dict(rotores=" ".join(rot), refletor="B", aneis=aneis,
                posicoes="".join(rng.choices(ALFABETO, k=3)), painel=painel)


def maquina(ch):
    return Enigma(ch["rotores"], ch["refletor"], ch["aneis"], ch["posicoes"], ch["painel"])


def trecho_portugues(rng, n):
    i = rng.randint(0, len(CORPUS) - n)
    return CORPUS[i:i + n]


# ---------------------------------------------------------------------------
def e1_sem_ponto_fixo(rng, mensagens=2000, tamanho=500):
    coincid = 0
    for _ in range(mensagens):
        texto = "".join(rng.choices(ALFABETO, k=tamanho))
        c = maquina(chave_aleatoria(rng)).cifrar(texto)
        coincid += sum(a == b for a, b in zip(texto, c))
    total = mensagens * tamanho
    return dict(letras=total, coincidencias=coincid, esperado_cifra_ideal=round(total / 26))


def e2_sobrevivencia(rng, tamanhos, tentativas=300, tam_msg=250):
    linhas = []
    for fonte in ("aleatorio", "portugues"):
        for n in tamanhos:
            fracs, verdadeiro_ok = [], 0
            for _ in range(tentativas):
                texto = ("".join(rng.choices(ALFABETO, k=tam_msg)) if fonte == "aleatorio"
                         else trecho_portugues(rng, tam_msg))
                c = maquina(chave_aleatoria(rng)).cifrar(texto)
                i = rng.randint(0, tam_msg - n)
                crib = texto[i:i + n]
                cand, desc = ataque_crib(c, crib)
                # fração entre os alinhamentos ERRADOS (o correto sempre sobrevive)
                errados = len(cand) + len(desc) - 1
                fracs.append((len(cand) - 1) / errados)
                verdadeiro_ok += i in cand
            linhas.append(dict(fonte=fonte, n=n, sobrevivencia_media=round(statistics.mean(fracs), 4),
                               desvio=round(statistics.stdev(fracs), 4),
                               teorico=round((25 / 26) ** n, 4),
                               candidatos_esperados_msg250=round((25 / 26) ** n * (tam_msg - n), 1),
                               correto_sobreviveu=f"{verdadeiro_ok}/{tentativas}"))
            print(f"  E2 {fonte:<10} n={n:2d}  medido={linhas[-1]['sobrevivencia_media']:.3f}  "
                  f"teórico={linhas[-1]['teorico']:.3f}")
    return linhas


def e3_bombe(rng, tamanhos, tentativas=5, tam_msg=200):
    linhas = []
    for n in tamanhos:
        paradas, tempos, sucesso, fracos = [], [], 0, 0
        for _ in range(tentativas):
            ch = chave_aleatoria(rng, aneis_aleatorios=False)
            texto = trecho_portugues(rng, tam_msg)
            c = maquina(ch).cifrar(texto)
            i = rng.randint(0, tam_msg - n)
            crib = texto[i:i + n]
            est = {}
            sols = recuperar_chave(c, crib, [i], ordens=[ch["rotores"]], estatisticas=est)
            tempos.append(est["tempo_s"])
            paradas.append(est["paradas"])
            fracos += est["menus_fracos"]
            sucesso += bool(sols) and sols[0].texto == texto
        linhas.append(dict(n=n, paradas_media=round(statistics.mean(paradas), 1),
                           paradas_max=max(paradas), menu_fraco=f"{fracos}/{tentativas}",
                           sucesso=f"{sucesso}/{tentativas}",
                           tempo_medio_s=round(statistics.mean(tempos), 2)))
        print(f"  E3 n={n:2d}  paradas≈{linhas[-1]['paradas_media']:7.1f}  sucesso {sucesso}/{tentativas}  "
              f"tempo {linhas[-1]['tempo_medio_s']}s")
    return linhas


def e4_completo(rng, n=15, tam_msg=200):
    ch = chave_aleatoria(rng, aneis_aleatorios=False)
    texto = trecho_portugues(rng, tam_msg)
    c = maquina(ch).cifrar(texto)
    i = rng.randint(0, tam_msg - n)
    crib = texto[i:i + n]
    est = {}
    sols = recuperar_chave(c, crib, [i], estatisticas=est)
    s = sols[0]
    return dict(chave_real=ch, crib=crib, alinhamento=i, tempo_s=round(est["tempo_s"], 1),
                paradas_total=est["paradas"],
                rotores_achados=" ".join(s.ordem), inicio_achado=s.inicio[0], painel_achado=s.painel,
                texto_correto=s.texto == texto)


# ---------------------------------------------------------------------------
def salvar_csv(nome, linhas):
    with open(os.path.join(SAIDA, nome), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def tabela_md(linhas):
    cab = list(linhas[0])
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(str(l[c]) for c in cab) + " |" for l in linhas]
    return "\n".join(out)


def grafico_svg(linhas, caminho):
    """Gráfico simples (sem dependências) de sobrevivência medida vs. teórica."""
    W, H, ml, mr, mt, mb = 640, 380, 60, 150, 30, 50
    ns = sorted({l["n"] for l in linhas})
    xmax = max(ns)
    X = lambda n: ml + (W - ml - mr) * n / xmax
    Y = lambda v: mt + (H - mt - mb) * (1 - v)
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="Helvetica,Arial" font-size="12">',
          f'<rect width="{W}" height="{H}" fill="white"/>']
    for v in (0, .25, .5, .75, 1):
        el.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(v)}" y2="{Y(v)}" stroke="#e5e5e5"/>')
        el.append(f'<text x="{ml - 8}" y="{Y(v) + 4}" text-anchor="end" fill="#555">{v:.2f}</text>')
    for n in ns:
        el.append(f'<text x="{X(n)}" y="{H - mb + 18}" text-anchor="middle" fill="#555">{n}</text>')
    el.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(0)}" y2="{Y(0)}" stroke="#333"/>')
    el.append(f'<line x1="{ml}" x2="{ml}" y1="{Y(0)}" y2="{Y(1)}" stroke="#333"/>')
    el.append(f'<text x="{(W - mr + ml) / 2}" y="{H - 12}" text-anchor="middle">tamanho do crib (n)</text>')
    el.append(f'<text x="16" y="{(H - mb + mt) / 2}" text-anchor="middle" '
              f'transform="rotate(-90 16 {(H - mb + mt) / 2})">fração de alinhamentos errados que sobrevivem</text>')
    # curva teórica contínua
    pts = " ".join(f"{X(n / 4)},{Y((25 / 26) ** (n / 4))}" for n in range(0, 4 * xmax + 1))
    el.append(f'<polyline points="{pts}" fill="none" stroke="#888" stroke-dasharray="5 4" stroke-width="1.5"/>')
    cores = {"aleatorio": "#2a6fdb", "portugues": "#d9480f"}
    for fonte, cor in cores.items():
        ls = sorted((l for l in linhas if l["fonte"] == fonte), key=lambda l: l["n"])
        pts = " ".join(f"{X(l['n'])},{Y(l['sobrevivencia_media'])}" for l in ls)
        el.append(f'<polyline points="{pts}" fill="none" stroke="{cor}" stroke-width="2"/>')
        for l in ls:
            el.append(f'<circle cx="{X(l["n"])}" cy="{Y(l["sobrevivencia_media"])}" r="3.5" fill="{cor}"/>')
    lx = W - mr + 12
    el.append(f'<line x1="{lx}" x2="{lx + 22}" y1="{mt + 10}" y2="{mt + 10}" stroke="#888" stroke-dasharray="5 4" stroke-width="1.5"/>'
              f'<text x="{lx + 28}" y="{mt + 14}">(25/26)^n</text>')
    for k, (fonte, cor) in enumerate(cores.items()):
        y = mt + 32 + 20 * k
        el.append(f'<line x1="{lx}" x2="{lx + 22}" y1="{y}" y2="{y}" stroke="{cor}" stroke-width="2"/>'
                  f'<text x="{lx + 28}" y="{y + 4}">{"texto aleatório" if fonte == "aleatorio" else "português"}</text>')
    el.append("</svg>")
    with open(caminho, "w") as f:
        f.write("\n".join(el))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="menos repetições (teste)")
    ap.add_argument("--completo", action="store_true", help="inclui E4 (60 ordens de rotores)")
    ap.add_argument("--semente", type=int, default=2026)
    a = ap.parse_args()
    os.makedirs(SAIDA, exist_ok=True)
    rng = random.Random(a.semente)
    rep = 0.2 if a.rapido else 1.0

    print("E1: propriedade 'nenhuma letra vira ela mesma'")
    r1 = e1_sem_ponto_fixo(rng, mensagens=int(2000 * rep))
    print(f"  {r1}")
    print("E2: sobrevivência de alinhamentos")
    r2 = e2_sobrevivencia(rng, [2, 4, 6, 8, 10, 12, 15, 20, 25, 30, 40], tentativas=int(300 * rep))
    salvar_csv("e2_sobrevivencia.csv", r2)
    grafico_svg(r2, os.path.join(SAIDA, "sobrevivencia.svg"))
    print("E3: Bombe (ordem dos rotores conhecida)")
    r3 = e3_bombe(rng, [8, 10, 12, 15, 20, 25], tentativas=max(2, int(5 * rep)))
    salvar_csv("e3_bombe.csv", r3)
    r4 = None
    if a.completo:
        print("E4: Bombe com as 60 ordens de rotores")
        r4 = e4_completo(rng)
        print(f"  {r4}")

    with open(os.path.join(SAIDA, "resumo.md"), "w") as f:
        f.write(f"# Resultados dos experimentos (semente {a.semente})\n\n")
        f.write("## E1 – Nenhuma letra é cifrada nela mesma\n\n")
        br = lambda x: f"{x:,}".replace(",", ".")
        f.write(f"Letras cifradas: {br(r1['letras'])}. Coincidências claro=cifrado: **{r1['coincidencias']}** "
                f"(uma cifra ideal teria ≈ {br(r1['esperado_cifra_ideal'])}).\n\n")
        f.write("## E2 – Fração de alinhamentos errados que sobrevivem\n\n")
        f.write(tabela_md(r2) + "\n\n![](sobrevivencia.svg)\n\n")
        f.write("## E3 – Bombe com ordem dos rotores conhecida (10 cabos, mensagem de 200 letras, tempo de CPU)\n\n")
        f.write(tabela_md(r3) + "\n\n")
        if r4:
            f.write("## E4 – Bombe testando as 60 ordens de rotores\n\n")
            for k, v in r4.items():
                f.write(f"- **{k}**: {v}\n")
    print(f"\nResultados em {SAIDA}/")


if __name__ == "__main__":
    main()
