"""Servidor do Protocolo de Transferencia de Arquivos (PTA).

Implementa a especificacao descrita em pta.pdf:
  - TCP, porta padrao 11550;
  - pedido:   SEQ_NUM COMMAND [ARGS]
  - resposta: SEQ_NUM REPLY [ARGS]
  - estados: ESPERANDO (aguarda CUMP) -> PRONTO (LIST, PEGA, TERM).

Uso: python pta_server.py [porta]
"""

import logging
import os
import socket
import sys
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.txt")
FILES_DIR = os.path.join(BASE_DIR, "files")
DEFAULT_PORT = 11550
BUFFER_SIZE = 4096

ESPERANDO = "ESPERANDO"
PRONTO = "PRONTO"

log = logging.getLogger("pta")


def load_users(path=USERS_FILE):
    """Le a lista de usuarios validos (um por linha, sensivel a maiusculas)."""
    with open(path, "r", encoding="ascii") as f:
        return {line.strip() for line in f if line.strip()}


def list_files():
    """Retorna os nomes dos arquivos regulares disponiveis, em ordem."""
    return sorted(
        name for name in os.listdir(FILES_DIR)
        if os.path.isfile(os.path.join(FILES_DIR, name))
    )


def parse_request(raw):
    """Divide o pedido em (seq, comando, args).

    Retorna None para o comando quando o pedido foge ao formato
    (SEQ_NUM nao numerico ou ausencia de comando).
    """
    text = raw.decode("ascii", errors="replace").strip("\r\n")
    parts = text.split(" ")
    seq = parts[0] if parts and parts[0] else "0"
    if len(parts) < 2 or not parts[0].lstrip("-").isdigit():
        return seq, None, []
    return seq, parts[1], parts[2:]


class PTASession:
    """Atende uma conexao TCP seguindo a maquina de estados do PTA.

    Cada pedido e processado por completo antes de ler o proximo,
    o que garante a atomicidade exigida para LIST e PEGA.
    """

    def __init__(self, conn, addr, users):
        self.conn = conn
        self.addr = addr
        self.users = users
        self.state = ESPERANDO

    def reply(self, seq, reply, args=b""):
        msg = f"{seq} {reply}".encode("ascii")
        if args:
            msg += b" " + args
        self.conn.sendall(msg)
        log.info("%s <- %s", self.addr, msg[:80])

    def run(self):
        with self.conn:
            while True:
                try:
                    raw = self.conn.recv(BUFFER_SIZE)
                except OSError:
                    break
                if not raw:
                    break
                log.info("%s -> %s", self.addr, raw[:80])
                seq, cmd, args = parse_request(raw)
                if self.state == ESPERANDO:
                    keep_open = self.handle_waiting(seq, cmd, args)
                else:
                    keep_open = self.handle_ready(seq, cmd, args)
                if not keep_open:
                    break
        log.info("%s conexao encerrada", self.addr)

    def handle_waiting(self, seq, cmd, args):
        """Estado ESPERANDO: so CUMP com usuario valido avanca."""
        if cmd == "CUMP" and len(args) == 1 and args[0] in self.users:
            self.reply(seq, "OK")
            self.state = PRONTO
            return True
        self.reply(seq, "NOK")
        return False

    def handle_ready(self, seq, cmd, args):
        """Estado PRONTO: LIST, PEGA e TERM; demais pedidos -> NOK."""
        if cmd == "LIST" and not args:
            self.handle_list(seq)
        elif cmd == "PEGA" and args:
            # O PTA envia um arquivo por vez; nomes extras sao ignorados.
            self.handle_pega(seq, args[0])
        elif cmd == "TERM" and not args:
            self.reply(seq, "OK")
            return False
        else:
            self.reply(seq, "NOK")
        return True

    def handle_list(self, seq):
        try:
            names = list_files()
        except OSError:
            self.reply(seq, "NOK")
            return
        payload = f"{len(names)} {','.join(names)}".encode("ascii")
        self.reply(seq, "ARQS", payload)

    def handle_pega(self, seq, name):
        # Aceita apenas nomes presentes na listagem (evita ../users.txt etc.).
        try:
            if name not in list_files():
                raise FileNotFoundError(name)
            with open(os.path.join(FILES_DIR, name), "rb") as f:
                data = f.read()
        except OSError:
            self.reply(seq, "NOK")
            return
        # "SEQ ARQ <tam> <dados>": o espaco apos o tamanho e mantido mesmo
        # para arquivos vazios.
        header = f"{seq} ARQ {len(data)} ".encode("ascii")
        self.conn.sendall(header + data)
        log.info("%s <- %s<%d bytes>", self.addr, header, len(data))


def serve(port=DEFAULT_PORT, host="0.0.0.0"):
    users = load_users()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen()
        log.info("PTA ouvindo em %s:%d (usuarios: %s)", host, port, sorted(users))
        while True:
            conn, addr = srv.accept()
            session = PTASession(conn, f"{addr[0]}:{addr[1]}", users)
            threading.Thread(target=session.run, daemon=True).start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    try:
        serve(port)
    except KeyboardInterrupt:
        pass
