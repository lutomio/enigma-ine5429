# Máquina Enigma I: simulador e ataque por crib

Trabalho em grupo de INE5429 (Segurança em Computação, UFSC, 2026/2).
Eduardo Bischoff Grasel, Lucas Tomio, Felipe Pierotti.

Python 3.10+ e só a biblioteca padrão (sem `pip install`). O relatório completo descreve a teoria, a implementação e os resultados.

## Arquivos

| arquivo | o que faz |
|---|---|
| `enigma.py` | núcleo da Enigma I: rotores I–V, refletores A/B/C, anéis, painel, duplo passo |
| `simulador.py` | simulador com animação no terminal (rotores girando, caminho do sinal, lâmpadas) |
| `ataque_crib.py` | elimina alinhamentos impossíveis do crib (nenhuma letra vira ela mesma) |
| `bombe.py` | Bombe de Turing-Welchman simplificada: recupera rotores, posição, anel e painel a partir do crib |
| `test_enigma.py` | plano de testes do relatório (17 testes) |
| `experimento.py` | experimentos E1–E4; grava `resultados/` (CSV, `resumo.md`, gráfico SVG) |

## Como rodar

```bash
git clone https://github.com/lutomio/enigma-ine5429.git
cd enigma-ine5429
python3 -m unittest -v test_enigma          # testes (~1 s)
```

### Simulador

```bash
python3 simulador.py AAAAA                               # → BDZGO (vetor de referência)
python3 simulador.py --pos ADT --atraso 0.8 XXXXX        # mostra o duplo passo (ADU→ADV→AEW→BFX)
python3 simulador.py --rapido --rotores "II I III" --refletor A --aneis "24 13 22" \
    --pos ABL --painel "AM FI NV PS TU WZ" \
    "GCDSE AHUGW TQGRK VLFGX UCALX VYMIG MMNMF DXTGN VHVRM MEVOU YFZSL RHDRR XFJWC FHUHM UNZEF RDISI KBGPM YVXUZ"
                                                         # mensagem histórica do manual de 1930
python3 simulador.py --pos DKU                           # modo interativo
```

Opções: `--rotores` (esquerda→direita), `--refletor`, `--aneis` (`AAA` ou `"01 01 01"`),
`--pos`, `--painel`, `--atraso`, `--rapido`, `--sem-limpar`.

### Ataque por crib (mini-exemplo do relatório parcial)

```bash
python3 ataque_crib.py JHKIHWSPMHLMMIXNLWAJNFIKQIUWPQNYFNANYEBTQFOOIVZGEHMHPKHXLKB PREVISAO
```

Verde = alinhamento candidato; vermelho = letra coincidente que descarta o alinhamento.

### Recuperação da chave com a Bombe

```bash
# 1) cifrar uma mensagem com uma chave "secreta"
C=$(python3 simulador.py --rapido --rotores "IV I V" --aneis CHL --pos XRK \
      --painel "AQ BW CE DR FT GY HU IJ KO LP" \
      "RELATORIO DO DIA PREVISAO DO TEMPO PARA FLORIANOPOLIS CEU NUBLADO COM PANCADAS DE CHUVA A TARDE VENTO SUL MODERADO TEMPERATURA MAXIMA DE VINTE E DOIS GRAUS NADA DE ESPECIAL A RELATAR")
# 2) atacar sabendo só o crib e onde ele está
python3 bombe.py "$C" PREVISAODOTEMPO --alinhamento 14 --rotores "IV I V" --buscar-anel
```

Sem `--rotores`, a Bombe testa as 60 ordens; sem `--alinhamento`, testa todos os
alinhamentos que sobrevivem ao teste de ponto fixo (mais lento).

### Experimentos

```bash
python3 experimento.py            # E1–E3 (alguns minutos)
python3 experimento.py --completo # + E4: Bombe testando as 60 ordens
```

## Limitações conhecidas

* Só a Enigma I de 3 rotores (sem a M4 naval nem o refletor D religável).
* A Bombe assume o anel do rotor do meio em A na hora de buscar as paradas (ele só
  importa se o duplo passo acontecer dentro do crib); depois ele é buscado na verificação.
  O anel do rotor da esquerda não pode ser determinado (é equivalente a mudar a posição).
* O painel restante é completado por *hill climbing* no índice de coincidência; com
  mensagens curtas (< ~100 letras) isso pode errar alguns cabos.
