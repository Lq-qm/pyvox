#!/usr/bin/env python3
"""pyvox web — interface gráfica (Gradio) do narrador pyvox (Kokoro-82M, CPU).

Uso:
    .venv/bin/python app.py                      # abre em http://127.0.0.1:7860
    .venv/bin/python app.py --port 8080
    .venv/bin/python app.py --host 0.0.0.0       # acessível na rede local
    .venv/bin/python app.py --share              # link público temporário (túnel Gradio)

A interface reutiliza o motor do pyvox.py (mesmo cache de modelo, mesma
qualidade do áudio). O primeiro clique baixa o modelo (~330 MB) e depois
ele fica em cache na memória do processo.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import gradio as gr

import pyvox

# --------------------------------------------------------------------------- #
# Lógica de apoio
# --------------------------------------------------------------------------- #
SaidaDir = Path(__file__).resolve().parent / "saida"

NARRATOR_LABELS = ["automática (padrão)", "masculino", "feminino"]


def _voices_for(lang: str) -> list[str]:
    """Vozes do idioma (Hugging Face com fallback offline), sempre com 'automática'."""
    try:
        return ["automática"] + pyvox.list_voices(pyvox.LANGS[lang])
    except Exception:
        pool = set(pyvox.DEFAULT_VOICES.values())
        return ["automática"] + sorted(v for v in pool if v.startswith(pyvox.LANGS[lang]))


def resolve_voice(lang: str, narrator: str, voice: str) -> str:
    """Resolve a voz final: exata > narrador (m/f) > padrão do idioma."""
    code = pyvox.LANGS[lang]
    if voice and voice != "automática":
        return voice
    if narrator == "masculino":
        cands = pyvox.NARRATOR_VOICES.get(code, {})
        if "m" in cands:
            return cands["m"]
        raise ValueError(f"o idioma **{lang}** não tem voz masculina no Kokoro-82M — "
                         "escolha uma voz exata")
    if narrator == "feminino":
        cands = pyvox.NARRATOR_VOICES.get(code, {})
        if "f" in cands:
            return cands["f"]
        raise ValueError(f"o idioma **{lang}** não tem voz feminina no Kokoro-82M — "
                         "escolha uma voz exata")
    return pyvox.DEFAULT_VOICES[code]


def load_file(f):
    """Lê o arquivo enviado e devolve o texto para o editor."""
    if f is None:
        return gr.update()
    if isinstance(f, list):
        f = f[0]
    path = getattr(f, "path", None) or (f.get("path") if isinstance(f, dict) else f)
    if not path:
        return gr.update()
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return gr.update(value=text)


def _estimate(text: str) -> str | None:
    """Aviso grosseiro de duração para textos longos (≈15 chars/s de fala, RTF ~0.25)."""
    n = len(text)
    if n < 20_000:
        return None
    est_audio = n / 15.0
    est_cpu = est_audio * 0.3
    return (f"⚠️ **texto longo** ({n:,} chars) — estimativa: "
            f"~{est_audio / 60:.0f} min de áudio, ~{est_cpu / 60:.0f} min de CPU. "
            "Considere `--max-chars` via CLI para testes.")


# --------------------------------------------------------------------------- #
# Geração (generator → progresso em tempo real no Gradio)
# --------------------------------------------------------------------------- #
def generate(text: str, lang: str, narrator: str, voice: str,
             speed: float, threads: int, max_chars: float):
    text = (text or "").strip()
    if not text:
        yield "⚠️ informe um texto (cole ou envie um `.txt`).", None, None
        return
    if max_chars and max_chars > 0:
        text = text[: int(max_chars)]
    if not text.strip():
        yield "⚠️ o texto está vazio.", None, None
        return

    try:
        voice_name = resolve_voice(lang, narrator, voice)
    except ValueError as e:
        yield f"⚠️ {e}", None, None
        return

    est = _estimate(text)
    if est:
        yield est, None, None

    SaidaDir.mkdir(parents=True, exist_ok=True)
    out = SaidaDir / f"pyvox_{time.strftime('%Y%m%d_%H%M%S')}.wav"
    status0 = f"🎙️ iniciando síntese — voz **{voice_name}**, {lang}, " \
              f"velocidade {speed:.2f}x…"
    yield status0, None, None

    try:
        stats: dict | None = None
        for item in pyvox.synthesize_stream(text, lang, voice_name, float(speed),
                                            str(out), threads=int(threads or 0)):
            if isinstance(item, dict):
                stats = item
            else:
                yield f"🎙️ {item}", None, None

        assert stats is not None
        status = (
            f"✅ **pronto!** {stats['audio_seconds']:.1f}s de áudio · "
            f"{stats['chunks']} chunks · {stats['elapsed']:.1f}s de processamento "
            f"(RTF {stats['rtf']:.2f})\n\n"
            f"salvo em `{out}`"
        )
        yield status, str(out), None
    except KeyboardInterrupt:
        yield "⛔ interrompido — o áudio parcial ficou salvo em `" + str(out) + "`.", str(out), None
    except Exception as e:
        yield f"❌ erro na síntese: {e}", None, None


# --------------------------------------------------------------------------- #
# Interface
# --------------------------------------------------------------------------- #
def build_demo() -> gr.Blocks:
    lang_options = sorted(pyvox.LANGS)
    cpu = os.cpu_count() or 4

    with gr.Blocks(title="pyvox — narrador de textos") as demo:
        gr.Markdown(
            "# 🎙️ pyvox\n"
            "Narra textos com o motor **Kokoro-82M** (CPU). "
            "Cole um texto, envie um `.txt`, escolha a voz e clique em **Gerar**."
        )

        with gr.Row(equal_height=False):
            with gr.Column(scale=5):
                text_box = gr.Textbox(
                    label="Texto",
                    placeholder=(
                        "Cole seu texto aqui…\n\n"
                        "“Era uma noite de inverno, e a cidade dormia sob um "
                        "silêncio profundo. Mas quem percebeu a primeira estrela?”"
                    ),
                    lines=8,
                )
                with gr.Row():
                    file_in = gr.File(label="ou envie um arquivo .txt",
                                      file_types=[".txt", ".md"],
                                      file_count="single", scale=3)
                    load_btn = gr.Button("➜ carregar no editor", scale=1)
                load_btn.click(fn=load_file, inputs=[file_in], outputs=[text_box])
                with gr.Row():
                    lang = gr.Dropdown(lang_options, value="pt-br",
                                       label="Idioma", scale=1)
                    narrator = gr.Radio(NARRATOR_LABELS, value=NARRATOR_LABELS[0],
                                        label="Narrador", scale=2)
                voice = gr.Dropdown(["automática"], value="automática",
                                    label="Voz exata (opcional)")
                with gr.Row():
                    speed = gr.Slider(0.5, 2.0, value=1.0, step=0.05,
                                      label="Velocidade (1.0 = natural)")
                    threads = gr.Slider(1, max(4, cpu), value=cpu, step=1,
                                        label="Threads de CPU")
                max_chars_in = gr.Number(0, None, step=100, precision=0,
                                         label="Máx. de caracteres (0 = sem limite)")
                btn = gr.Button("🎧 Gerar narração", variant="primary")

            with gr.Column(scale=4):
                status = gr.Markdown("aguardando…")
                audio = gr.Audio(type="filepath", label="Áudio", autoplay=True)
                gr.Examples(
                    examples=[["Era uma noite de inverno, e a cidade dormia sob um silêncio profundo. "
                               "Mas quem percebeu a primeira estrela? O céu, até então apagado, "
                               "revelou um brilho inesperado. ACHARAM O NAVIO!",
                              "pt-br", "automática (padrão)", "automática", 1.0, cpu, 0]],
                    inputs=[text_box, lang, narrator, voice, speed, threads, max_chars_in],
                    label="exemplo rápido",
                )
        gr.Markdown(
            "<details><summary>💡 dicas</summary><br>"
            "• O **primeiro clique** baixa o modelo Kokoro-82M (~330 MB) — depois fica em cache.<br>"
            "• Vozes pt-br: `pf_dora` (narradora), `pm_alex` (narrador), `pm_santa`, `pf_emma`…<br>"
            "• Textos muito longos (livros): prefira o CLI `pyvox.py` — a web serve melhor trechos.<br>"
            "• Os arquivos ficam salvos na pasta `saida/` do projeto.<br>"
            "</details>"
        )

        # Vozes disponíveis mudam com o idioma
        lang.change(fn=lambda l: gr.Dropdown(choices=_voices_for(l), value="automática"),
                    inputs=[lang], outputs=[voice])

        btn.click(
            fn=generate,
            inputs=[text_box, lang, narrator, voice, speed, threads, max_chars_in],
            outputs=[status, audio],
        )

    return demo


def main() -> None:
    p = argparse.ArgumentParser(description="Interface web (Gradio) do pyvox")
    p.add_argument("--host", default="127.0.0.1",
                   help="interface de rede (padrão: 127.0.0.1; use 0.0.0.0 p/ rede local)")
    p.add_argument("--port", type=int, default=7860, help="porta (padrão: 7860)")
    p.add_argument("--share", action="store_true",
                   help="cria link público temporário via túnel do Gradio")
    args = p.parse_args()

    # Verificação amigável de porta ocupada (evita o traceback do Gradio)
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((args.host, args.port))
        except OSError:
            sys.exit(
                f"erro: a porta {args.port} já está em uso em {args.host}.\n"
                f"  • Se o pyvox-web já está rodando, basta abrir "
                f"http://{args.host}:{args.port} no navegador.\n"
                f"  • Para usar outra porta: .venv/bin/python app.py --port {args.port + 1}"
            )

    demo = build_demo()
    demo.queue(default_concurrency_limit=1, api_open=False)  # 1 síntese por vez (CPU)
    demo.launch(server_name=args.host, server_port=args.port,
                theme=gr.themes.Soft(),
                share=args.share, inbrowser=False)


if __name__ == "__main__":
    main()
