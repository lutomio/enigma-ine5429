#!/usr/bin/env python3
"""
Simulador da Enigma I com animação no terminal (códigos ANSI).

Exemplos:
    python3 simulador.py AAAAA
    python3 simulador.py --rotores "II I III" --refletor A --aneis "24 13 22" \
        --pos ABL --painel "AM FI NV PS TU WZ" "GCDSE AHUGW TQGRK"
    python3 simulador.py --pos ADT --atraso 0.6 XXXXX     # mostra o duplo passo
    python3 simulador.py                                   # modo interativo
"""

import argparse
import sys
import time

from enigma import Enigma, em_grupos, limpar

R = "\033[0m"
NEG = "\033[1m"
DIM = "\033[2m"
AMA = "\033[33m"
VER = "\033[32m"
VERM = "\033[31m"
CIA = "\033[36m"
LIMPA_TELA = "\033[2J\033[H"

TECLADO = ["QWERTZUIO", "ASDFGHJK", "PYXCVBNML"]   # layout alemão da Enigma I


def desenhar_rotores(m: Enigma, girou=(False, False, False), duplo=False) -> str:
    linhas = ["      ESQ        MEIO       DIR"]
    caixas_t, caixas_m, caixas_b, nomes = [], [], [], []
    for r, g in zip((m.esq, m.meio, m.dir), girou):
        cor = AMA + NEG if g else ""
        ant = chr(65 + (r.pos - 1) % 26)
        prox = chr(65 + (r.pos + 1) % 26)
        caixas_t.append(f"  {DIM}  {ant}  {R}  ")
        caixas_m.append(f"  {cor}[ {chr(65 + r.pos)} ]{R}  ")
        caixas_b.append(f"  {DIM}  {prox}  {R}  ")
        nomes.append(f"  {r.nome:^5}  ")
    linhas += ["   " + "  ".join(caixas_t), "   " + "  ".join(caixas_m),
               "   " + "  ".join(caixas_b), "   " + "  ".join(nomes)]
    if duplo:
        linhas.append(f"   {AMA}{NEG}>> duplo passo: o rotor do meio girou junto com o da esquerda{R}")
    return "\n".join(linhas)


def desenhar_lampadas(acesa: str = "") -> str:
    out = []
    for i, fila in enumerate(TECLADO):
        pad = " " * (3 + i * 2)
        out.append(pad + " ".join(f"{AMA}{NEG}({c}){R}" if c == acesa else f"{DIM}({c}){R}" for c in fila))
    return "\n".join(out)


def desenhar_caminho(passo) -> str:
    partes = [f"{NEG}{passo.entrada}{R}"]
    for etapa, l in passo.caminho:
        cor = CIA if etapa == "Refletor" else ""
        partes.append(f"{DIM}{etapa}{R} {cor}{l}{R}")
    partes[-1] = f"{DIM}Painel{R} {VER}{NEG}{passo.saida}{R}"
    # quebra em duas linhas: ida e volta
    ida = "  →  ".join(partes[:5])
    volta = "  →  ".join(partes[5:])
    return f"   ida:   {ida}\n   volta: {volta}"


def animar(m: Enigma, texto: str, atraso: float, limpar_tela: bool = True) -> str:
    texto = limpar(texto)
    entrada, saida = "", ""
    for L in texto:
        meio_antes = m.meio.no_entalhe()
        passo = m.cifrar_letra(L, registrar=True)
        entrada += L
        saida += passo.saida
        duplo = passo.girou[0] and meio_antes
        tela = [
            f"{NEG}ENIGMA I{R}  rotores {m.config['rotores']} | refletor UKW-{m.config['refletor']} | "
            f"anéis {m.config['aneis']} | painel: {m.config['painel'] or '(vazio)'}",
            "",
            desenhar_rotores(m, passo.girou, duplo),
            "",
            desenhar_caminho(passo),
            "",
            desenhar_lampadas(passo.saida),
            "",
            f"   claro:   {em_grupos(entrada)}",
            f"   cifrado: {VER}{em_grupos(saida)}{R}",
        ]
        if limpar_tela:
            sys.stdout.write(LIMPA_TELA)
        print("\n".join(tela))
        if not limpar_tela:
            print("-" * 70)
        sys.stdout.flush()
        time.sleep(atraso)
    return saida


def main():
    ap = argparse.ArgumentParser(description="Simulador da Enigma I")
    ap.add_argument("texto", nargs="?", help="texto a cifrar/decifrar (se omitido, modo interativo)")
    ap.add_argument("--rotores", default="I II III", help='ordem esquerda→direita, ex.: "II IV V"')
    ap.add_argument("--refletor", default="B", choices=["A", "B", "C"])
    ap.add_argument("--aneis", default="AAA", help='Ringstellung, ex.: AAA ou "01 13 22"')
    ap.add_argument("--pos", default="AAA", help="Grundstellung (posição inicial), ex.: DKU")
    ap.add_argument("--painel", default="", help='pares do painel, ex.: "AM FI NV"')
    ap.add_argument("--atraso", type=float, default=0.35, help="pausa entre teclas (s)")
    ap.add_argument("--rapido", action="store_true", help="sem animação, só imprime o resultado")
    ap.add_argument("--sem-limpar", action="store_true", help="não limpa a tela entre as letras (log)")
    a = ap.parse_args()

    m = Enigma(a.rotores, a.refletor, a.aneis, a.pos, a.painel)

    if a.texto is not None:
        if a.rapido:
            print(em_grupos(m.cifrar(a.texto)))
        else:
            animar(m, a.texto, a.atraso, not a.sem_limpar)
        return

    print(f"Modo interativo (posição inicial {m.janelas()}). Digite o texto e Enter; Ctrl+D sai.")
    try:
        for linha in sys.stdin:
            if a.rapido:
                print(em_grupos(m.cifrar(linha)))
            else:
                animar(m, linha, a.atraso, not a.sem_limpar)
            print(f"\n(janelas agora: {m.janelas()})")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
