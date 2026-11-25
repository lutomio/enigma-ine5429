#!/usr/bin/env python3
"""
Ataque por crib: explora a falha estrutural da Enigma (nenhuma letra é
cifrada nela mesma) para descartar alinhamentos impossíveis de um trecho de
texto claro conhecido (crib) sob o texto cifrado.

Exemplo (mini-exemplo do relatório parcial):
    python3 ataque_crib.py JHKIHWSPMHLMMIXNLWAJNFIKQIUWPQNYFNANYEBTQFOOIVZGEHMHPKHXLKB PREVISAO

Com --recuperar, cada alinhamento sobrevivente é passado para a Bombe
(bombe.py), que tenta reconstruir a chave completa.
"""

import argparse
import sys

from enigma import limpar

R = "\033[0m"
NEG = "\033[1m"
VER = "\033[32m"
VERM = "\033[31m"
DIM = "\033[2m"


def ataque_crib(cifrado: str, crib: str):
    """Devolve (candidatos, descartados). Cada descartado é (posição, [índices em conflito])."""
    candidatos, descartados = [], []
    n = len(crib)
    for i in range(len(cifrado) - n + 1):
        conflitos = [j for j in range(n) if cifrado[i + j] == crib[j]]
        if conflitos:
            descartados.append((i, conflitos))
        else:
            candidatos.append(i)
    return candidatos, descartados


def ataque_crib_rapido(cifrado: str, crib: str) -> list[int]:
    """Versão do pseudocódigo do relatório (interrompe na 1ª coincidência)."""
    cand = []
    n = len(crib)
    for i in range(len(cifrado) - n + 1):
        for j in range(n):
            if cifrado[i + j] == crib[j]:
                break
        else:
            cand.append(i)
    return cand


def mostrar(cifrado: str, crib: str, candidatos, descartados, cor=True, todos=True):
    V, X, N, D, Z = (VER, VERM, NEG, DIM, R) if cor else ("", "", "", "", "")
    conf = dict(descartados)
    n = len(crib)
    total = len(cifrado) - n + 1
    print(f"{N}Texto cifrado ({len(cifrado)} letras):{Z} {cifrado}")
    print(f"{N}Crib ({n} letras):{Z} {crib}\n")
    for i in range(total):
        if not todos and i in conf:
            continue
        trecho = cifrado[i:i + n]
        if i in conf:
            bonito = "".join(f"{X}{N}{ch}{Z}" if j in conf[i] else f"{D}{ch}{Z}" for j, ch in enumerate(trecho))
            coinc = ", ".join(f"{crib[j]}={trecho[j]} (idx {j})" for j in conf[i])
            print(f"  pos {i:3d}  {' ' * 0}{bonito}   {X}descartado{Z}  {D}{coinc}{Z}")
        else:
            print(f"  pos {i:3d}  {V}{trecho}{Z}   {V}candidato{Z}")
    sobr = len(candidatos) / total if total else 0
    print(f"\n{N}Resumo:{Z} {total} alinhamentos, {len(descartados)} descartados, "
          f"{V}{len(candidatos)} candidatos{Z} (sobrevivência {sobr:.2f}; "
          f"esperado (25/26)^{n} = {(25 / 26) ** n:.2f})")
    print(f"Candidatos: {candidatos}")


def main():
    ap = argparse.ArgumentParser(description="Eliminação de alinhamentos por crib")
    ap.add_argument("cifrado")
    ap.add_argument("crib")
    ap.add_argument("--so-candidatos", action="store_true", help="omite os alinhamentos descartados")
    ap.add_argument("--sem-cor", action="store_true")
    ap.add_argument("--recuperar", action="store_true", help="roda a Bombe em cada candidato")
    ap.add_argument("--rotores", default=None,
                    help='ordem dos rotores para a Bombe (ex.: "I II III"); padrão: todas as 60')
    ap.add_argument("--refletor", default="B")
    a = ap.parse_args()

    cifrado, crib = limpar(a.cifrado), limpar(a.crib)
    if len(crib) > len(cifrado):
        sys.exit("crib maior que o texto cifrado")
    cand, desc = ataque_crib(cifrado, crib)
    mostrar(cifrado, crib, cand, desc, cor=not a.sem_cor, todos=not a.so_candidatos)

    if a.recuperar:
        from bombe import recuperar_chave, imprimir_solucoes
        ordens = [a.rotores] if a.rotores else None
        print()
        sols = recuperar_chave(cifrado, crib, cand, ordens=ordens, refletor=a.refletor, verbose=True)
        imprimir_solucoes(sols, cifrado)


if __name__ == "__main__":
    main()
