"""
Núcleo da máquina Enigma I (Wehrmacht/Luftwaffe).

Implementa rotores I-V, refletores A/B/C, anéis (Ringstellung), posições
iniciais (Grundstellung), painel de conexões (Steckerbrett) e a anomalia de
duplo passo do rotor do meio.

Convenção: letras são tratadas internamente como inteiros 0..25 (A=0).
Os rotores são listados da ESQUERDA para a DIREITA, como na máquina real
(ex.: "I II III" significa rotor I à esquerda e rotor III à direita).

Referências das fiações: Crypto Museum, "Enigma I" / "Enigma wiring".
"""

from __future__ import annotations

from dataclasses import dataclass, field

ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# fiação, entalhe (letra visível na janela quando o rotor vizinho é empurrado)
ROTORES = {
    "I":   ("EKMFLGDQVZNTOWYHXUSPAIBRCJ", "Q"),
    "II":  ("AJDKSIRUXBLHWTMCQGZNPYFVOE", "E"),
    "III": ("BDFHJLCPRTXVZNYEIWGAKMUSQO", "V"),
    "IV":  ("ESOVPZJAYQUIRHXLNFTGKDCMWB", "J"),
    "V":   ("VZBRGITYUPSDNHLXAWMJQOFECK", "Z"),
}

REFLETORES = {
    "A": "EJMZALYXVBWFCRQUONTSPIKHGD",
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
}


def num(letra: str) -> int:
    return ord(letra) - 65


def letra(n: int) -> str:
    return chr(n + 65)


def limpar(texto: str) -> str:
    """Mantém apenas A-Z em maiúsculas (acentos simples são normalizados)."""
    import unicodedata
    t = unicodedata.normalize("NFKD", texto.upper())
    return "".join(c for c in t if "A" <= c <= "Z")


def em_grupos(texto: str, n: int = 5) -> str:
    return " ".join(texto[i:i + n] for i in range(0, len(texto), n))


@dataclass
class Rotor:
    nome: str
    fiacao: list[int]
    inversa: list[int]
    entalhe: int
    anel: int = 0      # Ringstellung (0 = A / 01)
    pos: int = 0       # posição visível na janela (0 = A)

    @classmethod
    def criar(cls, nome: str, anel: int = 0, pos: int = 0) -> "Rotor":
        fio, ent = ROTORES[nome]
        fiacao = [num(c) for c in fio]
        inversa = [0] * 26
        for i, s in enumerate(fiacao):
            inversa[s] = i
        return cls(nome, fiacao, inversa, num(ent), anel, pos)

    def no_entalhe(self) -> bool:
        return self.pos == self.entalhe

    def avancar(self) -> None:
        self.pos = (self.pos + 1) % 26

    def ida(self, c: int) -> int:
        """Sinal entrando pela direita (em direção ao refletor)."""
        d = (c + self.pos - self.anel) % 26
        return (self.fiacao[d] - self.pos + self.anel) % 26

    def volta(self, c: int) -> int:
        """Sinal voltando do refletor (da esquerda para a direita)."""
        d = (c + self.pos - self.anel) % 26
        return (self.inversa[d] - self.pos + self.anel) % 26


def montar_painel(pares: str | list[str] = "") -> list[int]:
    """Recebe pares como 'AM FI NV' e devolve a permutação (involução)."""
    if isinstance(pares, str):
        pares = pares.split()
    painel = list(range(26))
    usadas: set[str] = set()
    for par in pares:
        par = par.upper()
        if len(par) != 2 or not par.isalpha() or par[0] == par[1]:
            raise ValueError(f"par inválido no painel: {par!r}")
        if par[0] in usadas or par[1] in usadas:
            raise ValueError(f"letra repetida no painel: {par!r}")
        usadas.update(par)
        a, b = num(par[0]), num(par[1])
        painel[a], painel[b] = b, a
    if len(pares) > 13:
        raise ValueError("no máximo 13 cabos")
    return painel


@dataclass
class Passo:
    """Registro do caminho do sinal de uma letra (usado na animação/log)."""
    entrada: str
    janelas: str           # posições dos rotores APÓS o avanço
    caminho: list[tuple[str, str]] = field(default_factory=list)
    saida: str = ""
    girou: tuple[bool, bool, bool] = (False, False, True)


class Enigma:
    def __init__(self, rotores: str | list[str] = "I II III", refletor: str = "B",
                 aneis: str | list[int] = "AAA", posicoes: str = "AAA",
                 painel: str | list[str] = ""):
        nomes = rotores.split() if isinstance(rotores, str) else list(rotores)
        if len(nomes) != 3:
            raise ValueError("a Enigma I usa exatamente 3 rotores")
        if len(set(nomes)) != 3:
            raise ValueError("um mesmo rotor não pode ser usado duas vezes")
        aneis_n = self._ler_aneis(aneis)
        posicoes = limpar(posicoes)
        if len(posicoes) != 3:
            raise ValueError("posição inicial deve ter 3 letras (ex.: AAA)")
        self.config = dict(rotores=" ".join(nomes), refletor=refletor,
                           aneis="".join(letra(a) for a in aneis_n),
                           posicoes=posicoes, painel=painel if isinstance(painel, str) else " ".join(painel))
        self.esq, self.meio, self.dir = (
            Rotor.criar(n, a, num(p)) for n, a, p in zip(nomes, aneis_n, posicoes))
        self.refletor = [num(c) for c in REFLETORES[refletor]]
        self.painel = montar_painel(painel)

    @staticmethod
    def _ler_aneis(aneis) -> list[int]:
        # aceita "AAA", "BUL", [1, 13, 22] (base 1, como nas tabelas alemãs) ou "01 13 22"
        if isinstance(aneis, str):
            partes = aneis.split()
            if len(partes) == 3 and all(p.isdigit() for p in partes):
                return [int(p) - 1 for p in partes]
            letras = limpar(aneis)
            if len(letras) != 3:
                raise ValueError("anéis: use 'AAA' ou '01 01 01'")
            return [num(c) for c in letras]
        return [int(a) - 1 for a in aneis]

    # ------------------------------------------------------------------
    def janelas(self) -> str:
        return letra(self.esq.pos) + letra(self.meio.pos) + letra(self.dir.pos)

    def avancar_rotores(self) -> tuple[bool, bool, bool]:
        """Movimento dos rotores ANTES de fechar o circuito (com duplo passo)."""
        gira_esq = gira_meio = False
        if self.meio.no_entalhe():          # duplo passo
            gira_esq = gira_meio = True
        elif self.dir.no_entalhe():
            gira_meio = True
        if gira_esq:
            self.esq.avancar()
        if gira_meio:
            self.meio.avancar()
        self.dir.avancar()
        return gira_esq, gira_meio, True

    def cifrar_letra(self, L: str, registrar: bool = False) -> str | Passo:
        girou = self.avancar_rotores()
        c = self.painel[num(L)]
        if registrar:
            p = Passo(entrada=L, janelas=self.janelas(), girou=girou)
            p.caminho.append(("Painel", letra(c)))
        for nome, r in (("Rotor dir.", self.dir), ("Rotor meio", self.meio), ("Rotor esq.", self.esq)):
            c = r.ida(c)
            if registrar:
                p.caminho.append((f"{nome} ({r.nome})", letra(c)))
        c = self.refletor[c]
        if registrar:
            p.caminho.append(("Refletor", letra(c)))
        for nome, r in (("Rotor esq.", self.esq), ("Rotor meio", self.meio), ("Rotor dir.", self.dir)):
            c = r.volta(c)
            if registrar:
                p.caminho.append((f"{nome} ({r.nome})", letra(c)))
        c = self.painel[c]
        if registrar:
            p.caminho.append(("Painel", letra(c)))
            p.saida = letra(c)
            return p
        return letra(c)

    def cifrar(self, texto: str) -> str:
        return "".join(self.cifrar_letra(L) for L in limpar(texto))

    # decifrar é exatamente a mesma operação (E_t é uma involução)
    decifrar = cifrar

    def permutacoes_rotores(self, n: int) -> list[list[int]]:
        """Avança n teclas e devolve, para cada uma, a permutação dos rotores +
        refletor SEM o painel (S_t). A Enigma completa é E_t = P · S_t · P."""
        out = []
        for _ in range(n):
            self.avancar_rotores()
            perm = []
            for x in range(26):
                c = self.esq.ida(self.meio.ida(self.dir.ida(x)))
                c = self.refletor[c]
                perm.append(self.dir.volta(self.meio.volta(self.esq.volta(c))))
            out.append(perm)
        return out

    def permutacao_atual(self) -> list[int]:
        """Permutação E_t que será aplicada na PRÓXIMA tecla (sem alterar o estado)."""
        salvo = (self.esq.pos, self.meio.pos, self.dir.pos)
        perm = []
        for x in range(26):
            self.esq.pos, self.meio.pos, self.dir.pos = salvo
            perm.append(num(self.cifrar_letra(letra(x))))
        self.esq.pos, self.meio.pos, self.dir.pos = salvo
        return perm


def tamanho_espaco_chaves(cabos: int = 10, rotores_disponiveis: int = 5) -> dict[str, int]:
    from math import factorial, perm
    ordem = perm(rotores_disponiveis, 3)
    posicoes = 26 ** 3
    painel = factorial(26) // (factorial(26 - 2 * cabos) * factorial(cabos) * 2 ** cabos)
    return {"ordem dos rotores": ordem, "posicoes iniciais": posicoes,
            "painel": painel, "total": ordem * posicoes * painel}
