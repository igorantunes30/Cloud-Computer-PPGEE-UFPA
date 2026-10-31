"""Gera os diagramas PNG do fluxo do PTA.

As mensagens dos diagramas de sequencia sao capturadas de sessoes reais
contra um servidor em execucao (por padrao 127.0.0.1:11550).

Uso:
  python pta-server/pta_server.py          # em outro terminal
  python docs/gerar_diagramas.py [ip] [porta]
"""

import math
import os
import socket
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

INK = "#1f2937"
MUTED = "#6b7280"
CLIENT = "#2563eb"
SERVER = "#059669"
ERROR = "#dc2626"
PANEL = "#f3f4f6"


# ---------------------------------------------------------------- captura

def capture(ip, port, requests):
    """Envia os pedidos em uma conexao e devolve [(pedido, resposta, fechou)]."""
    s = socket.create_connection((ip, port))
    s.settimeout(2)
    out = []
    for req in requests:
        s.sendall(req.encode())
        resp = b""
        while True:
            chunk = s.recv(65536)
            resp += chunk
            parts = resp.split(b" ", 3)
            if not chunk or len(parts) < 3 or parts[1] != b"ARQ":
                break
            if len(parts) == 4 and len(parts[3]) >= int(parts[2]):
                break
        try:
            closed = s.recv(1) == b""
        except socket.timeout:
            closed = False
        out.append((req, resp, closed))
        if closed:
            break
    s.close()
    return out


def short(resp, limit=58):
    """Resume a resposta para caber na seta (dados binarios viram <n bytes>)."""
    parts = resp.split(b" ", 3)
    if len(parts) == 4 and parts[1] == b"ARQ":
        return f"{parts[0].decode()} ARQ {parts[2].decode()} <{len(parts[3])} bytes>"
    text = resp.decode("ascii", errors="replace")
    return text if len(text) <= limit else text[:limit - 3] + "..."


# ---------------------------------------------------------------- desenho

def lifeline_diagram(sessions, path, note=None):
    """Diagrama de sequencia: cada sessao e uma lista de (pedido, resposta, fechou)."""
    bottom = -0.2 - sum(0.8 + 1.68 * len(sess) for sess in sessions) - 0.3
    fig, ax = plt.subplots(figsize=(11, 1.0 + (1.4 - bottom) * 0.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(bottom, 1.4)
    ax.axis("off")
    xc, xs = 1.6, 8.4

    for x, label, color in ((xc, "Cliente", CLIENT), (xs, "Servidor PTA\n:11550", SERVER)):
        ax.add_patch(FancyBboxPatch((x - 0.9, 0.35), 1.8, 0.9, boxstyle="round,pad=0.05",
                                    fc=color, ec="none"))
        ax.text(x, 0.8, label, ha="center", va="center", color="white",
                fontsize=11, weight="bold")
        ax.plot([x, x], [0.3, bottom], color=MUTED, ls="--", lw=1)

    y = -0.2
    for i, sess in enumerate(sessions):
        ax.text(5, y, f"conexao TCP #{i + 1}", ha="center", va="center", fontsize=9,
                color=MUTED, style="italic",
                bbox=dict(fc="white", ec=MUTED, lw=0.6, boxstyle="round,pad=0.25"))
        y -= 0.8
        for req, resp, closed in sess:
            arrow(ax, xc, xs, y, req, CLIENT)
            y -= 0.84
            bad = b"NOK" in resp
            arrow(ax, xs, xc, y, short(resp), ERROR if bad else SERVER)
            if closed:
                ax.text(xs + 0.15, y - 0.32, "servidor fecha a conexao", fontsize=8.5,
                        color=ERROR, ha="right", va="center")
            y -= 0.84

    if note:
        fig.text(0.02, 0.01, note, fontsize=8.5, color=MUTED)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def arrow(ax, x0, x1, y, label, color):
    ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle="-|>", mutation_scale=16,
                                 color=color, lw=1.6))
    ax.text((x0 + x1) / 2, y + 0.13, label, ha="center", va="bottom", fontsize=9.5,
            family="monospace", color=INK)


def box(ax, x, y, w, h, text, fc, tc="white", fs=10, weight="bold"):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.08",
                                fc=fc, ec="none"))
    ax.text(x, y, text, ha="center", va="center", color=tc, fontsize=fs, weight=weight)


def link(ax, p0, p1, label="", color=INK, rad=0.0, fs=9, offset=(0, 0.15), style="-|>"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=15, color=color,
                                 lw=1.5, connectionstyle=f"arc3,rad={rad}"))
    if label:
        mx, my = (p0[0] + p1[0]) / 2 + offset[0], (p0[1] + p1[1]) / 2 + offset[1]
        ax.text(mx, my, label, ha="center", va="center", fontsize=fs, color=color,
                family="monospace", bbox=dict(fc="white", ec="none", pad=1))


def architecture(path):
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")

    box(ax, 1.5, 3, 2.2, 1.2, "pta-client.py\n(cliente)", CLIENT)
    ax.add_patch(FancyBboxPatch((3.9, 0.5), 7.7, 5.0, boxstyle="round,pad=0.1",
                                fc=PANEL, ec=MUTED, lw=1))
    ax.text(4.1, 5.25, "pta_server.py", fontsize=11, weight="bold", color=INK)

    box(ax, 5.4, 3, 2.2, 1.2, "socket de escuta\nbind 0.0.0.0:11550\naccept()", SERVER, fs=9)
    for i, yy in enumerate((4.4, 3.0, 1.6)):
        box(ax, 8.3, yy, 2.4, 0.95, f"Thread {i + 1}: PTASession\nestado ESPERANDO/PRONTO",
            "#10b981", fs=8.5)
        link(ax, (6.55, 3), (7.05, yy), color=SERVER)
    box(ax, 10.75, 4.2, 1.3, 0.8, "users.txt", "#9ca3af", fs=9)
    box(ax, 10.75, 1.8, 1.3, 0.8, "files/\n(16 arq.)", "#9ca3af", fs=9)
    link(ax, (10.1, 4.2), (9.55, 4.4), "le", color=MUTED, offset=(0, 0.25))
    link(ax, (10.1, 1.8), (9.55, 1.6), "le", color=MUTED, offset=(0, -0.25))

    link(ax, (2.65, 3.15), (4.25, 3.15), "TCP connect", color=CLIENT, offset=(0, 0.3))
    link(ax, (4.25, 2.85), (2.65, 2.85), "", color=SERVER)
    ax.text(3.45, 2.4, "pedido / resposta\nSEQ CMD ARGS", ha="center", fontsize=8.5,
            color=MUTED, family="monospace")
    ax.text(7.7, 0.75, "uma thread por conexao: cada pedido e processado inteiro antes "
            "do proximo (atomicidade de LIST/PEGA)", ha="center", fontsize=8.5, color=MUTED)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def state_machine(path):
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.5)
    ax.axis("off")
    pe, pp = (3.0, 3.2), (8.0, 3.2)
    r = 0.95
    for (x, y), label in ((pe, "ESPERANDO"), (pp, "PRONTO")):
        ax.add_patch(Circle((x, y), r, fc="#2563eb", ec="none"))
        ax.text(x, y, label, ha="center", va="center", color="white", fontsize=11,
                weight="bold")
    box(ax, 11.0, 3.2, 1.5, 0.8, "conexao\nfechada", ERROR, fs=9)

    link(ax, (0.6, 4.9), (2.35, 3.9), "conexao TCP\naceita", color=MUTED, offset=(-0.4, 0.3))
    link(ax, (pe[0] + r, pe[1] + 0.15), (pp[0] - r, pp[1] + 0.15),
         "CUMP <usuario valido>\n/ OK", color=SERVER, offset=(0, 0.45))
    link(ax, (pe[0] + 0.2, pe[1] - r), (11.0, 2.75), "", color=ERROR, rad=0.45)
    ax.text(5.6, 0.25,"qualquer outro pedido / usuario invalido\n/ NOK", ha="center",
            fontsize=9, color=ERROR, family="monospace")
    link(ax, (pp[0] + r, pp[1]), (10.25, 3.2), "TERM\n/ OK", color=SERVER, offset=(0, 0.45))

    def on_circle(deg):
        return (pp[0] + r * math.cos(math.radians(deg)), pp[1] + r * math.sin(math.radians(deg)))

    # (angulo de saida, angulo de chegada): percorridos no sentido horario, o
    # arco de cada laco fica do lado de fora do circulo.
    loops = [
        (150, 115, "LIST / ARQS <n> a1,a2,...", (pp[0] - 1.75, pp[1] + 1.4), SERVER),
        (65, 30, "outro comando / NOK\n(conexao continua)", (pp[0] + 1.75, pp[1] + 1.4),
         "#d97706"),
        (245, 210, "PEGA <arq existente>\n/ ARQ <tam> <dados>", (pp[0] - 1.75, pp[1] - 1.4),
         SERVER),
        (330, 295, "PEGA <arq inexistente>\n/ NOK", (pp[0] + 1.75, pp[1] - 1.4), "#d97706"),
    ]
    for a0, a1, label, (lx, ly), color in loops:
        ax.add_patch(FancyArrowPatch(on_circle(a0), on_circle(a1), arrowstyle="-|>",
                                     mutation_scale=14, color=color, lw=1.4,
                                     connectionstyle="arc3,rad=-1.6"))
        ax.text(lx, ly, label, ha="center", va="center", fontsize=8.5, color=color,
                family="monospace", zorder=5, bbox=dict(fc="white", ec="none", pad=2))

    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def message_format(arq_example, path):
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.2)
    ax.axis("off")

    def row(y, title, fields, color):
        ax.text(0.2, y + 0.55, title, fontsize=10.5, weight="bold", color=INK)
        x = 0.2
        for label, width, example in fields:
            ax.add_patch(FancyBboxPatch((x, y - 0.35), width - 0.08, 0.7,
                                        boxstyle="square,pad=0", fc=color, ec="white"))
            ax.text(x + width / 2, y, label, ha="center", va="center", color="white",
                    fontsize=9.5, weight="bold")
            ax.text(x + width / 2, y - 0.6, example, ha="center", va="center", fontsize=8.5,
                    family="monospace", color=MUTED)
            x += width

    row(4.0, "Pedido (cliente -> servidor), campos separados por 1 espaco",
        [("SEQ_NUM", 1.6, "3"), ("COMMAND", 2.0, "PEGA"),
         ("ARGS (CUMP/PEGA)", 8.0, "dummyfile05-with-a-bigger-name-...txt")], CLIENT)
    row(2.3, "Resposta (servidor -> cliente), SEQ_NUM ecoa o do pedido",
        [("SEQ_NUM", 1.6, "3"), ("REPLY", 2.0, "ARQ"), ("<tam>", 1.4, arq_example[0]),
         ("<dados> (bytes crus do arquivo)", 6.6, arq_example[1])], SERVER)
    ax.text(0.2, 0.75,
            "CUMP -> OK | NOK      LIST -> ARQS <num> n1,n2,... | NOK      "
            "PEGA -> ARQ <tam> <dados> | NOK      TERM -> OK",
            fontsize=9, family="monospace", color=INK)
    ax.text(0.2, 0.3, "Arquivo vazio: '3 ARQ 0 ' (espaco final mantido para o cliente "
            "separar 4 campos).", fontsize=8.5, color=MUTED)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- main

def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 11550

    first = capture(ip, port, ["0 LIST"])
    listing = capture(ip, port, ["0 CUMP user1", "1 LIST"])
    names = listing[1][1].decode().split(" ", 3)[3].split(",")
    sample = next(n for n in names if n.startswith("dummyfile05"))

    happy = capture(ip, port, [
        "0 CUMP user1",
        "1 LIST",
        "2 FOO",
        f"3 PEGA {sample}",
        "4 PEGA novo_arquivo",
        "5 TERM",
    ])
    rejected = [
        first,
        capture(ip, port, ["0 CUMP laser1212"]),
    ]

    architecture(os.path.join(OUT_DIR, "01_arquitetura.png"))
    state_machine(os.path.join(OUT_DIR, "02_maquina_estados.png"))
    lifeline_diagram([happy],
                     os.path.join(OUT_DIR, "03_sequencia_sessao.png"),
                     note="LIST abreviada; PEGA mostra <n bytes> no lugar do conteudo.")
    lifeline_diagram(rejected,
                     os.path.join(OUT_DIR, "04_sequencia_rejeicoes.png"),
                     note="#1: comando antes de CUMP. #2: usuario fora de users.txt. "
                          "Ambos: NOK e conexao fechada.")
    parts = happy[3][1].split(b" ", 3)
    data = parts[3][:34].decode("ascii", errors="replace").replace("\n", " ")
    message_format((parts[2].decode(), repr(data)[1:-1] + "..."),
                   os.path.join(OUT_DIR, "05_formato_mensagens.png"))
    print("PNGs gerados em", OUT_DIR)


if __name__ == "__main__":
    main()
