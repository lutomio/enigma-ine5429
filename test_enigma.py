"""
Plano de testes do relatório (seção 3.5).  Rodar com:
    python3 -m unittest -v test_enigma
"""

import random
import unittest

from ataque_crib import ataque_crib, ataque_crib_rapido
from bombe import recuperar_chave
from enigma import ALFABETO, REFLETORES, ROTORES, Enigma, limpar, tamanho_espaco_chaves

MSG_1930 = ("GCDSE AHUGW TQGRK VLFGX UCALX VYMIG MMNMF DXTGN VHVRM MEVOU YFZSL RHDRR "
            "XFJWC FHUHM UNZEF RDISI KBGPM YVXUZ")
CLARO_1930 = ("FEINDLIQEINFANTERIEKOLONNEBEOBAQTETXANFANGSUEDAUSGANGBAERWALDEXENDEDREI"
              "KMOSTWAERTSNEUSTADT")

CLARO_RELATORIO = "NADAADECLARARHOJEPREVISAODETEMPOBOMPARAAMANHAUFSCCONFIRMADO"
CIFRADO_RELATORIO = "JHKIHWSPMHLMMIXNLWAJNFIKQIUWPQNYFNANYEBTQFOOIVZGEHMHPKHXLKB"


def maquina_aleatoria(rng: random.Random) -> Enigma:
    rot = rng.sample(list(ROTORES), 3)
    letras = rng.sample(ALFABETO, 20)
    painel = " ".join(letras[i] + letras[i + 1] for i in range(0, 20, 2))
    return Enigma(rot, rng.choice("BC"), "".join(rng.choices(ALFABETO, k=3)),
                  "".join(rng.choices(ALFABETO, k=3)), painel)


class TesteSimulador(unittest.TestCase):
    # 1. validação do simulador
    def test_vetor_referencia(self):
        self.assertEqual(Enigma().cifrar("AAAAA"), "BDZGO")

    def test_reciprocidade(self):
        self.assertEqual(Enigma().decifrar("BDZGO"), "AAAAA")
        rng = random.Random(1)
        for _ in range(200):
            cfg = maquina_aleatoria(rng).config
            texto = "".join(rng.choices(ALFABETO, k=rng.randint(1, 300)))
            c = Enigma(cfg["rotores"], cfg["refletor"], cfg["aneis"], cfg["posicoes"], cfg["painel"]).cifrar(texto)
            d = Enigma(cfg["rotores"], cfg["refletor"], cfg["aneis"], cfg["posicoes"], cfg["painel"]).decifrar(c)
            self.assertEqual(d, texto)

    def test_mensagem_historica_1930(self):
        """Exemplo do manual de instruções da Enigma (1930), refletor A."""
        m = Enigma("II I III", "A", "24 13 22", "ABL", "AM FI NV PS TU WZ")
        self.assertEqual(m.decifrar(MSG_1930), CLARO_1930)

    def test_mini_exemplo_relatorio(self):
        self.assertEqual(Enigma(posicoes="DKU").cifrar(CLARO_RELATORIO), CIFRADO_RELATORIO)

    # 2. teste da falha estrutural
    def test_sem_ponto_fixo(self):
        rng = random.Random(2)
        for _ in range(300):
            m = maquina_aleatoria(rng)
            texto = "".join(rng.choices(ALFABETO, k=200))
            c = m.cifrar(texto)
            self.assertTrue(all(a != b for a, b in zip(texto, c)))

    def test_permutacao_involucao_sem_ponto_fixo(self):
        rng = random.Random(3)
        for _ in range(200):
            m = maquina_aleatoria(rng)
            for _ in range(rng.randint(0, 50)):
                m.cifrar_letra("A")
            p = m.permutacao_atual()
            for x in range(26):
                self.assertNotEqual(p[x], x)
                self.assertEqual(p[p[x]], x)

    def test_refletores_sao_involucoes(self):
        for fio in REFLETORES.values():
            for i, c in enumerate(fio):
                self.assertNotEqual(ord(c) - 65, i)
                self.assertEqual(ord(fio[ord(c) - 65]) - 65, i)

    # 3. duplo passo
    def test_duplo_passo(self):
        m = Enigma("I II III", posicoes="ADU")
        seq = []
        for _ in range(4):
            m.avancar_rotores()
            seq.append(m.janelas())
        self.assertEqual(seq, ["ADV", "AEW", "BFX", "BFY"])

    def test_periodo_16900(self):
        m = Enigma("I II III", posicoes="AAA")
        vistos = {}
        for t in range(20000):
            j = m.janelas()
            if j in vistos:
                self.assertEqual(t - vistos[j], 16900)
                return
            vistos[j] = t
            m.avancar_rotores()
        self.fail("ciclo não encontrado")

    def test_aneis_formatos(self):
        a = Enigma("I II III", "B", "BUL", "AAA").cifrar("TESTE")
        b = Enigma("I II III", "B", "02 21 12", "AAA").cifrar("TESTE")
        self.assertEqual(a, b)

    def test_painel_invalido(self):
        with self.assertRaises(ValueError):
            Enigma(painel="AB AC")
        with self.assertRaises(ValueError):
            Enigma(painel="AA")

    def test_limpar(self):
        self.assertEqual(limpar("Previsão do tempo: 22°!"), "PREVISAODOTEMPO")

    def test_espaco_de_chaves(self):
        t = tamanho_espaco_chaves()
        self.assertEqual(t["painel"], 150_738_274_937_250)
        self.assertEqual(t["total"], 60 * 17576 * 150_738_274_937_250)


class TesteAtaque(unittest.TestCase):
    # 4. demonstração do ataque
    def test_tabela_1_relatorio(self):
        cand, desc = ataque_crib(CIFRADO_RELATORIO, "PREVISAO")
        self.assertEqual(len(cand) + len(desc), 52)
        self.assertEqual(len(desc), 12)
        self.assertIn(17, cand)
        d = dict(desc)
        self.assertEqual(d[1], [5])
        self.assertEqual(d[28], [0, 6])
        self.assertEqual(d[35], [2, 7])

    def test_versao_rapida_igual(self):
        rng = random.Random(4)
        for _ in range(50):
            c = "".join(rng.choices(ALFABETO, k=120))
            crib = "".join(rng.choices(ALFABETO, k=rng.randint(3, 25)))
            self.assertEqual(ataque_crib(c, crib)[0], ataque_crib_rapido(c, crib))

    def test_alinhamento_correto_sempre_sobrevive(self):
        rng = random.Random(5)
        for _ in range(200):
            m = maquina_aleatoria(rng)
            texto = "".join(rng.choices(ALFABETO, k=150))
            i = rng.randint(0, 130)
            crib = texto[i:i + 20]
            cand, _ = ataque_crib(m.cifrar(texto), crib)
            self.assertIn(i, cand)

    def test_bombe_recupera_chave(self):
        claro = limpar("RELATORIO DO DIA PREVISAO DO TEMPO PARA FLORIANOPOLIS CEU NUBLADO COM "
                       "PANCADAS DE CHUVA A TARDE VENTO SUL MODERADO TEMPERATURA MAXIMA DE VINTE "
                       "E DOIS GRAUS NADA DE ESPECIAL A RELATAR")
        c = Enigma("III I II", "B", "AAA", "UFS", "AQ BW CE DR FT GY HU IJ KO LP").cifrar(claro)
        crib = "PREVISAODOTEMPO"
        sols = recuperar_chave(c, crib, [claro.index(crib)], ordens=["III I II"])
        s = sols[0]
        self.assertTrue(s.crib_ok)
        self.assertEqual(s.texto, claro)
        self.assertEqual(s.painel, "AQ BW CE DR FT GY HU IJ KO LP")


if __name__ == "__main__":
    unittest.main()
