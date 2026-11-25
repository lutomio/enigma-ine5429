#!/usr/bin/env python3
"""
Bombe de Turing-Welchman simplificada (em software).

Dado um texto cifrado e um crib num alinhamento candidato, procura posições
dos rotores consistentes com o crib MESMO COM O PAINEL DE CONEXÕES DESCONHECIDO.

Ideia (Hodges, 2014; Welchman, 1982):
  Seja S_j a permutação dos rotores+refletor na j-ésima letra do crib (sem o
  painel) e P o painel (involução). A Enigma faz C_j = P(S_j(P(p_j))), logo

        P(c_j) = S_j(P(p_j))         (relação do "menu")

  Para cada posição dos rotores, a Bombe supõe P(t) = x para uma letra t do
  menu e propaga as consequências pelas arestas do menu. Como P é uma
  involução, P(t) = x implica P(x) = t (o "diagonal board" de Welchman). Se
  aparecer contradição (uma letra com dois parceiros), a hipótese cai. Uma
  posição em que alguma hipótese sobrevive é uma "parada" (stop).

Simplificações em relação à Bombe real:
  * a busca trabalha com a posição "efetiva" de cada rotor (janela - anel).
    O anel do rotor da esquerda é irrelevante; o do meio só altera o instante
    do duplo passo (raro dentro de um crib) e é tomado como A; o da direita
    define quando o rotor do meio gira e pode ser buscado (--buscar-anel);
  * o movimento dos rotores dentro do crib é simulado exatamente (com duplo
    passo), em vez de assumir que só o rotor da direita gira.

Depois das paradas, o painel parcial obtido é completado por subida de encosta
(hill climbing) maximizando o índice de coincidência do texto decifrado, e a
solução é verificada decifrando a mensagem inteira.
"""

from __future__ import annotations

import argparse
import itertools
import time
from collections import defaultdict
from dataclasses import dataclass

from enigma import REFLETORES, ROTORES, Enigma, em_grupos, letra, limpar, num

N_ESTADOS = 26 ** 3


def idx(e: int, m: int, d: int) -> int:
    return (e * 26 + m) * 26 + d


def desidx(s: int) -> tuple[int, int, int]:
    return s // 676, (s // 26) % 26, s % 26


class Embaralhador:
    """Tabelas pré-computadas para uma ordem de rotores (anéis AAA)."""

    _cache_tab: dict = {}

    def __init__(self, ordem: tuple[str, str, str], refletor: str = "B", anel_dir: int = 0):
        self.ordem = ordem
        self.refletor = refletor
        self.anel_dir = anel_dir
        U = [num(c) for c in REFLETORES[refletor]]
        ida, volta, ent = [], [], []
        for nome in ordem:
            fio = [num(c) for c in ROTORES[nome][0]]
            inv = [0] * 26
            for i, s in enumerate(fio):
                inv[s] = i
            ida.append([[(fio[(c + p) % 26] - p) % 26 for c in range(26)] for p in range(26)])
            volta.append([[(inv[(c + p) % 26] - p) % 26 for c in range(26)] for p in range(26)])
            ent.append(num(ROTORES[nome][1]))
        self.entalhes = ent
        chave = (ordem, refletor)
        if chave in Embaralhador._cache_tab:
            self.tab = Embaralhador._cache_tab[chave]
        else:
            self.tab = Embaralhador._cache_tab[chave] = self._tabela(ida, volta, U)
        self.prox = self._proximos(ent[1], (ent[2] - anel_dir) % 26)

    @staticmethod
    def _tabela(ida, volta, U):
        # permutação (sem painel) para cada estado efetivo dos rotores
        tab = [None] * N_ESTADOS
        Ie, Im, Id = ida
        Ve, Vm, Vd = volta
        for e in range(26):
            ie, ve = Ie[e], Ve[e]
            for m in range(26):
                im, vm = Im[m], Vm[m]
                for d in range(26):
                    id_, vd = Id[d], Vd[d]
                    tab[idx(e, m, d)] = [vd[vm[ve[U[ie[im[id_[x]]]]]]] for x in range(26)]
        return tab

    @staticmethod
    def _proximos(nm: int, nd: int):
        # próximo estado efetivo (movimento ANTES de cifrar a letra), com duplo passo
        prox = [0] * N_ESTADOS
        for e in range(26):
            for m in range(26):
                for d in range(26):
                    E, M, D = e, m, d
                    if M == nm:
                        E, M = (E + 1) % 26, (M + 1) % 26
                    elif D == nd:
                        M = (M + 1) % 26
                    D = (D + 1) % 26
                    prox[idx(e, m, d)] = idx(E, M, D)
        return prox

    def estados_a_partir(self, s: int, n: int) -> list[int]:
        """Estados usados nas n próximas teclas, partindo das janelas s."""
        out = []
        for _ in range(n):
            s = self.prox[s]
            out.append(s)
        return out


@dataclass
class Parada:
    ordem: tuple[str, str, str]
    refletor: str
    alinhamento: int
    anel_dir: int
    estado_crib: int                 # janelas imediatamente antes da 1ª letra do crib
    painel_parcial: dict[int, int]
    inicio: list[str] | None = None  # janelas iniciais compatíveis
    aneis: str = "AAA"
    painel: str = ""
    texto: str = ""
    ic: float = 0.0
    crib_ok: bool = False


def construir_menu(cifrado: str, crib: str, alinhamento: int):
    """Arestas (u, v, j): letra do crib u na posição j liga-se à letra cifrada v."""
    arestas = []
    for j, (p, c) in enumerate(zip(crib, cifrado[alinhamento:alinhamento + len(crib)])):
        arestas.append((num(p), num(c), j))
    adj = defaultdict(list)
    for u, v, j in arestas:
        adj[u].append((v, j))
        adj[v].append((u, j))
    return arestas, adj


def letra_de_teste(adj) -> int:
    return max(adj, key=lambda k: len(adj[k]))


def testar_hipotese(t: int, x: int, adj, perms) -> dict[int, int] | None:
    """Propaga P(t)=x pelo menu. Devolve o painel parcial ou None se contradição."""
    P = [-1] * 26
    pilha = []

    def atribuir(a, b) -> bool:
        if P[a] == -1 and P[b] == -1:
            P[a] = b
            P[b] = a
            pilha.append(a)
            if a != b:
                pilha.append(b)
            return True
        return P[a] == b and P[b] == a

    if not atribuir(t, x):
        return None
    while pilha:
        u = pilha.pop()
        pu = P[u]
        for v, j in adj.get(u, ()):
            if not atribuir(v, perms[j][pu]):
                return None
    return {a: P[a] for a in range(26) if P[a] != -1}


def bombe_alinhamento(emb: Embaralhador, cifrado: str, crib: str, alinhamento: int) -> list[Parada]:
    _, adj = construir_menu(cifrado, crib, alinhamento)
    t = letra_de_teste(adj)
    n = len(crib)
    paradas = []
    tab, prox = emb.tab, emb.prox
    for s in range(N_ESTADOS):
        # estados de cada letra do crib
        perms = []
        e = s
        for _ in range(n):
            e = prox[e]
            perms.append(tab[e])
        for x in range(26):
            r = testar_hipotese(t, x, adj, perms)
            if r is not None:
                paradas.append(Parada(emb.ordem, emb.refletor, alinhamento, emb.anel_dir, s, r))
    return paradas


# ---------------------------------------------------------------------------
# Verificação e reconstrução do restante do painel
# ---------------------------------------------------------------------------

def indice_coincidencia(texto: str) -> float:
    n = len(texto)
    if n < 2:
        return 0.0
    cont = [0] * 26
    for ch in texto:
        cont[ord(ch) - 65] += 1
    return sum(c * (c - 1) for c in cont) / (n * (n - 1))


def mapa_inicios(prox: list[int], alinhamento: int) -> dict[int, list[int]]:
    """estado imediatamente antes do crib -> estados iniciais que levam a ele."""
    # prox^alinhamento por exponenciação rápida (composição de funções)
    res = list(range(N_ESTADOS))
    base = prox
    e = alinhamento
    while e:
        if e & 1:
            res = [base[x] for x in res]
        base = [base[x] for x in base]
        e >>= 1
    mapa = defaultdict(list)
    for s0, s in enumerate(res):
        mapa[s].append(s0)
    return mapa


def painel_str(P: dict[int, int]) -> str:
    pares = sorted({tuple(sorted((a, b))) for a, b in P.items() if a != b})
    return " ".join(letra(a) + letra(b) for a, b in pares)


def _subir_encosta(cifrado: str, ordem, refletor, aneis: str, inicio: str, P: dict[int, int],
                    crib: str = "", alinhamento: int = 0, max_cabos: int = 10,
                    fixos: set | None = None, rng=None,
                    max_passos: int = 15) -> tuple[dict[int, int], str, float]:
    """Hill climbing nos cabos ainda desconhecidos.

    Pontuação = (letras do crib reproduzidas, índice de coincidência). O crib é
    uma restrição conhecida, então tem prioridade; o IC desempata e guia os
    cabos de letras que não aparecem no crib. Movimentos: ligar duas letras
    livres, trocar o parceiro de um cabo que o próprio hill climbing colocou
    (os cabos deduzidos pela Bombe ficam fixos).
    """
    fixos = set(P) if fixos is None else fixos
    P = dict(P)
    # a sequência de posições dos rotores não depende do painel: pré-computa S_t
    S = Enigma(" ".join(ordem), refletor, aneis, inicio).permutacoes_rotores(len(cifrado))
    cnum = [ord(ch) - 65 for ch in cifrado]

    def decifra(Pd):
        p = list(range(26))
        for a, b in Pd.items():
            p[a] = b
        return "".join([chr(65 + p[St[p[c]]]) for St, c in zip(S, cnum)])

    def nota(t):
        acertos = sum(x == y for x, y in zip(t[alinhamento:alinhamento + len(crib)], crib))
        return (acertos, indice_coincidencia(t))

    texto = decifra(P)
    melhor = nota(texto)
    for _ in range(max_passos):
        cabos = sum(1 for a, b in P.items() if a < b)
        livres = [a for a in range(26) if a not in P]
        moveis = sorted({tuple(sorted((a, b))) for a, b in P.items() if a not in fixos and a != b})
        vizinhos = []
        if cabos < max_cabos:                       # ligar duas letras livres
            for a, b in itertools.combinations(livres, 2):
                Q = dict(P)
                Q[a], Q[b] = b, a
                vizinhos.append(Q)
        for a, b in moveis:
            Q = dict(P)                             # remover um cabo
            del Q[a], Q[b]
            vizinhos.append(Q)
            for x, y in ((a, b), (b, a)):           # trocar o parceiro por uma letra livre
                for c in livres:
                    Q = dict(P)
                    del Q[y]
                    Q[x], Q[c] = c, x
                    vizinhos.append(Q)
        for (a, b), (c, d) in itertools.combinations(moveis, 2):   # trocar entre dois cabos
            for (x1, y1), (x2, y2) in (((a, c), (b, d)), ((a, d), (b, c))):
                Q = dict(P)
                Q[x1], Q[y1], Q[x2], Q[y2] = y1, x1, y2, x2
                vizinhos.append(Q)
        ganho = None
        if rng is not None:                     # estocástico: primeira melhora, ordem aleatória
            rng.shuffle(vizinhos)
        for Q in vizinhos:
            t = decifra(Q)
            n = nota(t)
            if n > melhor and (ganho is None or n > ganho[0]):
                ganho = (n, Q, t)
                if rng is not None and (n[0] > melhor[0] or n[1] > melhor[1] + 1e-9):
                    break
        if ganho is None or (ganho[0][0] == melhor[0] and ganho[0][1] <= melhor[1] + 1e-9):
            break
        melhor, P, texto = ganho
    return P, texto, melhor[1]


def completar_painel(cifrado: str, ordem, refletor, aneis: str, inicio: str, P: dict[int, int],
                     crib: str = "", alinhamento: int = 0, max_cabos: int = 10,
                     reinicios: int = 6, semente: int = 0) -> tuple[dict[int, int], str, float]:
    """Completa o painel: uma subida gulosa (melhor vizinho) e mais alguns
    reinícios estocásticos a partir dos cabos fixos da Bombe; fica com o melhor
    resultado por (crib reproduzido, IC). Os reinícios escapam de ótimos locais
    em que nenhum movimento isolado melhora a pontuação."""
    import random
    rng = random.Random(semente)
    fixos = set(P)

    def nota(r):
        t = r[1]
        return (sum(x == y for x, y in zip(t[alinhamento:alinhamento + len(crib)], crib)), r[2])

    melhor = _subir_encosta(cifrado, ordem, refletor, aneis, inicio, P, crib, alinhamento,
                            max_cabos, fixos)
    for _ in range(reinicios):
        cand = _subir_encosta(cifrado, ordem, refletor, aneis, inicio, P, crib, alinhamento,
                              max_cabos, fixos, rng)
        if nota(cand) > nota(melhor):
            melhor = cand
    return melhor


class Verificador:
    """Converte paradas em chaves completas, com cache das tabelas de início.

    Para cada parada:
      1. acha as janelas iniciais compatíveis e decifra com o painel parcial,
         medindo o índice de coincidência (IC) — etapa barata;
      2. as melhores paradas são reavaliadas com os 26 anéis do rotor do meio
         (que só afeta o duplo passo) e passam pelo hill climbing do painel;
      3. confere se o crib é reproduzido no alinhamento.
    """

    def __init__(self, cifrado: str, crib: str):
        self.cifrado, self.crib = cifrado, crib
        self._cache: dict = {}

    def _inicios(self, emb: Embaralhador, am: int, alinhamento: int):
        chave = (emb.ordem, emb.anel_dir, am, alinhamento)
        if chave not in self._cache:
            ent_dir = (emb.entalhes[2] - emb.anel_dir) % 26
            prox = emb.prox if am == 0 else Embaralhador._proximos((emb.entalhes[1] - am) % 26, ent_dir)
            self._cache[chave] = mapa_inicios(prox, alinhamento)
        return self._cache[chave]

    def pre_avaliar(self, p: Parada, emb: Embaralhador, aneis_meio=(0,)) -> Parada | None:
        k = p.anel_dir
        painel = painel_str(p.painel_parcial)
        melhor = None
        for am in aneis_meio:
            aneis = "A" + letra(am) + letra(k)
            for s0 in self._inicios(emb, am, p.alinhamento).get(p.estado_crib, ()):
                e, m, d = desidx(s0)
                inicio = letra(e) + letra((m + am) % 26) + letra((d + k) % 26)  # janela = efetiva + anel
                t = Enigma(" ".join(p.ordem), p.refletor, aneis, inicio, painel).decifrar(self.cifrado)
                ic = indice_coincidencia(t)
                if melhor is None or ic > melhor.ic + 1e-12:
                    melhor = Parada(p.ordem, p.refletor, p.alinhamento, k, p.estado_crib,
                                    p.painel_parcial, [inicio], aneis, painel, t, ic, False)
        return melhor

    def finalizar(self, p: Parada, reinicios: int = 0) -> Parada:
        P, texto, ic = completar_painel(self.cifrado, p.ordem, p.refletor, p.aneis, p.inicio[0],
                                        p.painel_parcial, self.crib, p.alinhamento, reinicios=reinicios)
        ok = texto[p.alinhamento:p.alinhamento + len(self.crib)] == self.crib
        return Parada(p.ordem, p.refletor, p.alinhamento, p.anel_dir, p.estado_crib,
                      p.painel_parcial, p.inicio, p.aneis, painel_str(P), texto, ic, ok)


def recuperar_chave(cifrado: str, crib: str, alinhamentos: list[int], ordens=None,
                    refletor: str = "B", verbose: bool = False, finalistas: int = 8,
                    buscar_anel: bool = False, limite_paradas: int = 3000,
                    estatisticas: dict | None = None):
    """Roda a Bombe para cada ordem/anel/alinhamento e devolve as soluções ordenadas.

    Se uma combinação (ordem, anel, alinhamento) gerar mais de `limite_paradas`
    paradas, o menu é fraco demais (crib curto ou sem laços) e ela não é
    verificada — na prática, os operadores de Bletchley Park também descartavam
    menus assim. `estatisticas`, se fornecido, recebe contagens e tempos.
    """
    cifrado, crib = limpar(cifrado), limpar(crib)
    if ordens is None:
        ordens = list(itertools.permutations(ROTORES.keys(), 3))
    else:
        ordens = [tuple(o.split()) if isinstance(o, str) else tuple(o) for o in ordens]
    ver = Verificador(cifrado, crib)
    pre = []
    total_paradas = 0
    menus_fracos = 0
    t0 = time.process_time()
    aneis = range(26) if buscar_anel else [0]
    for ordem in ordens:
        for k in aneis:
            emb = Embaralhador(ordem, refletor, k)
            for al in alinhamentos:
                paradas = bombe_alinhamento(emb, cifrado, crib, al)
                total_paradas += len(paradas)
                if verbose and (paradas or not buscar_anel):
                    print(f"  ordem {' '.join(ordem):<11} anel dir. {letra(k)}  alinhamento {al:3d}: "
                          f"{len(paradas):3d} parada(s)   [{time.process_time() - t0:6.1f}s]")
                if len(paradas) > limite_paradas:
                    menus_fracos += 1
                    continue
                for p in paradas:
                    r = ver.pre_avaliar(p, emb)
                    if r is not None:
                        pre.append((r, emb))
    pre.sort(key=lambda x: x[0].ic, reverse=True)
    sols = []
    for r, emb in pre[:finalistas]:
        r2 = ver.pre_avaliar(r, emb, aneis_meio=range(26)) or r
        sols.append((r2, ver.finalizar(r2)))
    # reinícios estocásticos só para as soluções que já reproduzem o crib
    sols.sort(key=lambda x: (x[1].crib_ok, x[1].ic), reverse=True)
    sols = [ver.finalizar(r2, reinicios=6) if i < 2 and f.crib_ok else f
            for i, (r2, f) in enumerate(sols)]
    sols.sort(key=lambda s: (s.crib_ok, s.ic), reverse=True)
    if verbose:
        print(f"  total: {total_paradas} parada(s); {len(sols)} finalista(s) com painel completado"
              f"   [{time.process_time() - t0:6.1f}s]")
        if menus_fracos:
            print(f"  aviso: {menus_fracos} combinação(ões) com mais de {limite_paradas} paradas "
                  f"não foram verificadas (crib curto demais)")
    if estatisticas is not None:
        estatisticas.update(paradas=total_paradas, menus_fracos=menus_fracos,
                            tempo_s=time.process_time() - t0)
    return sols


def imprimir_solucoes(sols: list[Parada], cifrado: str, n: int = 3):
    if not sols:
        print("Nenhuma parada encontrada.")
        return
    print(f"\n{len(sols)} solução(ões) verificada(s); melhores:")
    for s in sols[:n]:
        print(f"\n  rotores {' '.join(s.ordem)} | refletor {s.refletor} | anéis {s.aneis} | posição inicial {s.inicio[0]}"
              f" | alinhamento {s.alinhamento} | crib reproduzido: {'SIM' if s.crib_ok else 'não'}")
        print(f"  painel parcial (Bombe): {painel_str(s.painel_parcial)}")
        print(f"  painel completo (IC):   {s.painel}")
        print(f"  IC = {s.ic:.4f}")
        print(f"  texto: {em_grupos(s.texto)}")


def main():
    ap = argparse.ArgumentParser(description="Bombe simplificada: recupera a chave a partir de um crib")
    ap.add_argument("cifrado")
    ap.add_argument("crib")
    ap.add_argument("--alinhamento", type=int, nargs="*", default=None,
                    help="posições do crib a testar (padrão: todos os candidatos)")
    ap.add_argument("--rotores", default=None, help='ordem fixa (ex.: "II V III"); padrão: as 60')
    ap.add_argument("--refletor", default="B")
    ap.add_argument("--buscar-anel", action="store_true",
                    help="testa os 26 anéis do rotor da direita (26x mais lento)")
    a = ap.parse_args()
    cifrado, crib = limpar(a.cifrado), limpar(a.crib)
    if a.alinhamento is None:
        from ataque_crib import ataque_crib
        al, _ = ataque_crib(cifrado, crib)
        print(f"{len(al)} alinhamento(s) candidato(s) pelo teste de ponto fixo: {al}")
    else:
        al = a.alinhamento
    ordens = [a.rotores] if a.rotores else None
    t0 = time.process_time()
    sols = recuperar_chave(cifrado, crib, al, ordens, a.refletor, verbose=True,
                           buscar_anel=a.buscar_anel)
    imprimir_solucoes(sols, cifrado)
    print(f"\nTempo total: {time.process_time() - t0:.1f}s")


if __name__ == "__main__":
    main()
