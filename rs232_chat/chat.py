# chat.py – RS‑232 Chat / Ping / Echo utility for IWSK project (v2)
# --------------------------------------------------------------------
#   author : <twoje‑nazwisko>
#   date   : 2025‑05‑13
#
# Wersja 2 – uzupełniona o wszystkie OB‑wymagania:
#   • Pełna konfiguracja znaku: --data-bits, --parity, --stop-bits
#   • Tryb kontroli przepływu DTR/DSR: --flow dsrdtr
#   • Dowolny terminator: --terminator none|cr|lf|crlf|hex:XXXX
#
# --------------------------------------------------------------------
"""Minimalistic multi‑purpose serial utility for laboratory RS‑232 tasks.

USAGE EXAMPLES
--------------
# CHAT (interaktywnie)
python chat.py --port COM7 --mode chat --baud 9600 --parity N --terminator crlf

# PING (pomiar 5 pakietów)
python chat.py --port COM8 --mode ping --count 5 --flow dsrdtr

# ECHO (pasywny responder po drugiej stronie)
python chat.py --port COM7 --mode echo


#SERWER:
    python chat.py --port COM7 --mode echo --data-bits 8 --parity N --stop-bits 1 --flow dsrdtr

#KLIENT:
    python chat.py --port COM8 --mode ping --count 5 --terminator none --flow dsrdtr
"""

import argparse
import sys
import threading
import time
from typing import Optional

import serial
from serial.tools import list_ports

# -------------------------------------------------- helpers

TERMINATORS = {
    "none": b"",
    "cr": b"\r",
    "lf": b"\n",
    "crlf": b"\r\n",
}


def parse_terminator(spec: str) -> bytes:
    """Return terminator bytes for given CLI spec."""
    spec = spec.lower()
    if spec in TERMINATORS:
        return TERMINATORS[spec]
    if spec.startswith("hex:"):
        hex_part = spec[4:]
        if len(hex_part) % 2 != 0 or not all(c in "0123456789abcdef" for c in hex_part):
            raise argparse.ArgumentTypeError("hex terminator must be even‑length hex string, e.g. hex:0d0a")
        if len(hex_part) // 2 not in (1, 2):
            raise argparse.ArgumentTypeError("terminator may contain max 2 bytes")
        return bytes.fromhex(hex_part)
    raise argparse.ArgumentTypeError("invalid terminator spec")


PARITY_MAP = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
}

STOPBITS_MAP = {
    1: serial.STOPBITS_ONE,
    2: serial.STOPBITS_TWO,
}

BYTESIZE_MAP = {
    7: serial.SEVENBITS,
    8: serial.EIGHTBITS,
}

PING_HEADER = b"\x55\xAA"  # sync pattern


class SerialPort:
    """Light wrapper adding hex‑dump helpers and thread‑safe close."""

    def __init__(self, port: str, **kwargs):
        self._sp = serial.Serial(port, **kwargs)
        self._lock = threading.Lock()

    def write(self, data: bytes):
        with self._lock:
            self._sp.write(data)

    def read(self, size: int = 1) -> bytes:
        with self._lock:
            return self._sp.read(size)

    def read_until(self, terminator: bytes = b"\n", timeout: Optional[float] = None) -> bytes:
        """Read until *terminator* seen or *timeout* elapsed (simple variant)."""
        start = time.perf_counter()
        data = bytearray()
        while True:
            chunk = self.read(1)
            if chunk:
                data.extend(chunk)
                if data.endswith(terminator):
                    return bytes(data)
            if timeout is not None and time.perf_counter() - start > timeout:
                return bytes(data)

    @property
    def in_waiting(self) -> int:
        return self._sp.in_waiting

    def close(self):
        self._sp.close()


# -------------------------------------------------- CLI handlers

def mode_chat(sp: SerialPort, term: bytes):
    stop = False

    def rx_thread():
        nonlocal stop
        try:
            while not stop:
                data = sp.read(sp.in_waiting or 1)
                if data:
                    try:
                        # attempt utf‑8 decoding, fallback to hex
                        text = data.decode()
                        print(text, end="", flush=True)
                    except UnicodeDecodeError:
                        print("[RX]", data.hex(" "))
        except serial.SerialException:
            pass

    t = threading.Thread(target=rx_thread, daemon=True)
    t.start()
    try:
        for line in sys.stdin:
            sp.write(line.encode() + term)
    except KeyboardInterrupt:
        pass
    finally:
        stop = True
        t.join()


def mode_echo(sp: SerialPort):
    try:
        while True:
            data = sp.read(sp.in_waiting or 1)
            if data:
                print(f"Echo {len(data)} B")
                sp.write(data)
    except KeyboardInterrupt:
        pass


def mode_ping(sp: SerialPort, count: int, term: bytes):
    seq = 0
    try:
        for i in range(count if count > 0 else 1_000_000_000):
            payload = PING_HEADER + seq.to_bytes(2, "big") + b"\x00\x0A" + term
            t0 = time.perf_counter()
            sp.write(payload)
            reply = sp.read(len(payload))
            if reply:
                rtt = (time.perf_counter() - t0) * 1_000  # ms
                print(f"Reply {seq} in {rtt:.2f} ms ({len(reply)} B)")
            else:
                print(f"Timeout {seq}")
            seq = (seq + 1) & 0xFFFF
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


# -------------------------------------------------- main

def available_ports() -> str:
    ports = list_ports.comports()
    if not ports:
        return "<brak portów>"
    return ", ".join(p.device for p in ports)


def build_cli():
    p = argparse.ArgumentParser(description="RS‑232 Chat / Ping / Echo utility")
    p.add_argument("--port", required=True, help="COM port, np. COM7 (dostępne: " + available_ports() + ")")
    p.add_argument("--mode", choices=["chat", "echo", "ping"], default="chat")
    p.add_argument("--baud", type=int, default=9600, help="Szybkość bit/s (150…115000)")
    p.add_argument("--data-bits", type=int, choices=[7, 8], default=8)
    p.add_argument("--parity", choices=["N", "E", "O"], default="N")
    p.add_argument("--stop-bits", type=int, choices=[1, 2], default=1)
    p.add_argument("--flow", choices=["none", "rtscts", "xonxoff", "dsrdtr"], default="none")
    p.add_argument("--terminator", default="crlf", help="none|cr|lf|crlf|hex:XXXX (max 2 bajty)")
    p.add_argument("--count", type=int, default=10, help="Liczba pakietów w trybie ping (0 = nieskończoność)")
    return p


def main():
    cli = build_cli().parse_args()

    term = parse_terminator(cli.terminator)

    flow_args = {
        "rtscts": cli.flow == "rtscts",
        "xonxoff": cli.flow == "xonxoff",
        "dsrdtr": cli.flow == "dsrdtr",
    }

    sp = SerialPort(
        cli.port,
        baudrate=cli.baud,
        bytesize=BYTESIZE_MAP[cli.data_bits],
        parity=PARITY_MAP[cli.parity],
        stopbits=STOPBITS_MAP[cli.stop_bits],
        timeout=1,
        write_timeout=1,
        **flow_args,
    )

    try:
        if cli.mode == "chat":
            mode_chat(sp, term)
        elif cli.mode == "echo":
            mode_echo(sp)
        else:  # ping
            mode_ping(sp, cli.count, term)
    finally:
        sp.close()


if __name__ == "__main__":
    main()
