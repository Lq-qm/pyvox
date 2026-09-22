# pyvox 🎙️

> CLI em Python que narra arquivos de texto (`.txt`) usando o motor **Kokoro TTS** ([Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)).

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Kokoro TTS](https://img.shields.io/badge/motor-Kokoro--82M-8A2BE2)](https://huggingface.co/hexgrad/Kokoro-82M)
[![Device](https://img.shields.io/badge/device-CPU-orange)](https://pytorch.org/)

## ✨ Funcionalidades

- 📖 Narra qualquer arquivo `.txt` (ou texto direto via `--text`)
- 🗣️ Motor **Kokoro-82M** com vozes em 9 idiomas (pt-br, en-us, en-gb, es, fr-fr, hi, it, ja, zh)
- ⚙️ **Somente CPU** por enquanto — sem GPU, sem CUDA
- 📊 Progresso em tempo real com tempo de áudio, tempo de CPU e RTF (razão tempo real)
- ▶️ Reprodução do resultado com `--play` (ffplay/mpv/aplay)
- 🎚️ Velocidade ajustável, múltiplas vozes por idioma, controle de threads

## 📋 Requisitos

| Item | Versão |
|---|---|
| Python | 3.10+ |
| gerenciador de pacotes | `uv` (ou `pip`) |
| disco | ~1 GB (venv) + ~330 MB (modelo, baixado na 1ª execução) |
| opcional (para `--play`) | `ffplay`, `mpv` ou `aplay` no `PATH` |

## 🚀 Instalação

```bash
# 1) Crie o ambiente virtual
uv venv .venv

# 2) PyTorch SOMENTE CPU (use o índice CPU para não baixar a build CUDA)
uv pip install -i https://download.pytorch.org/whl/cpu torch

# 3) Dependências do projeto
uv pip install -r requirements.txt
```

## 📖 Uso

```bash
# Narrar um arquivo (padrão: pt-br, voz pf_dora) → gera <arquivo>.wav
.venv/bin/python pyvox.py meu_texto.txt -o saida.wav

# Escolher voz, velocidade e tocar o resultado
.venv/bin/python pyvox.py meu_texto.txt --voice pm_lennon --speed 1.2 --play

# Listar as vozes disponíveis para um idioma
.venv/bin/python pyvox.py --list-voices --lang pt-br

# Narra texto direto, sem arquivo
.venv/bin/python pyvox.py --text "Olá, mundo."

# Teste rápido: limita a síntese aos primeiros N caracteres
.venv/bin/python pyvox.py meu_texto.txt --max-chars 500
```

### Opções

| Opção | Descrição |
|---|---|
| `file` | arquivo `.txt` a narrar (opcional com `--text`) |
| `--text TEXT` | narra texto direto, sem arquivo |
| `-l, --lang` | idioma: `pt-br` (padrão), `en-us`, `en-gb`, `es`, `fr-fr`, `hi`, `it`, `ja`, `zh` |
| `-v, --voice` | voz a usar (ex.: `pf_dora`, `pm_lennon` — veja `--list-voices`) |
| `-s, --speed` | velocidade da fala (`0.5` = metade, `1.5` = 50% mais rápido; padrão `1.0`) |
| `-o, --output` | arquivo `.wav` de saída (padrão: `<arquivo>.wav`) |
| `--threads N` | threads de CPU (padrão: todos os núcleos) |
| `--max-chars N` | limita a síntese aos N primeiros caracteres (útil para testes) |
| `--play` | toca o áudio ao final |
| `--list-voices` | lista as vozes do idioma e sai |

### Exemplo de saída

```
carregando modelo Kokoro-82M (pt-br, voz=pf_dora, cpu)…
modelo pronto em 1.3s
[  12]     18.9s de áudio |      4.8s cpu | “O comandante da União…”
✔ salva em saida.wav | 18.9s de áudio | 12 chunks | 4.8s de processamento | RTF 0.25
```

## ⚙️ Como funciona

```
.txt ──► segmentação (linhas + frases, ~400 chars)
         └─► G2P (texto → fonemas) via misaki
              └─► Kokoro-82M (CPU) gera áudio chunk a chunk (24 kHz)
                   └─► WAV gravado incrementalmente + progresso no terminal
```

1. O texto é dividido em segmentos (linhas, com chunking por sentenças).
2. O `KPipeline` converte cada segmento em fonemas (G2P) e sintetiza o áudio na CPU.
3. Os chunks (24 kHz, 16-bit PCM) são gravados incrementalmente no `.wav`, com progresso na linha de comando e RTF ao final.

## 📝 Notas

- A **1ª execução** baixa o modelo (~330 MB) e a voz escolhida do Hugging Face (cache em `~/.cache/huggingface`).
- Textos longos em CPU podem demorar — use `--max-chars` para testar; `Ctrl+C` interrompe mantendo o áudio já gerado.
- Para GPU no futuro: basta trocar `device="cpu"` por `"cuda"` em `pyvox.py`.

