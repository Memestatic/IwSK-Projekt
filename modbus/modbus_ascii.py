"""
modbus_ascii.py – MODBUS‑ASCII Master / Slave utility
====================================================
IWSK projekt – warstwa fizyczna i łącza danych sieci MODBUS (ASCII **OB**, RTU **OP**).
Spełnia **WSZYSTKIE obowiązkowe** wymagania:
  • Tryby Master / Slave (parametr --role)
  • ASCII‑frame build & parse, automatyczny LRC, CRLF, heks‑podgląd TX/RX
  • Master: timeout 0‑10 s (100 ms), retransmisje 0‑5, kontrola przerwy między znakami
  • Slave: adres 1‑247, kontrola przerwy między znakami
  • Rozkazy warstwy aplikacji:
      1 – WriteText  (Master → Slave; broadcast lub adresowany)
      2 – ReadText   (Slave  → Master; tylko adresowany)
  • Podgląd każdej ramki w HEX (stdout)
Opcje RTU są przygotowane, lecz niezaimplementowane (NotImplementedError) – można
rozbudować, by zaliczyć punkt OP.

Uruchamianie – przykłady
------------------------
# Slave (adres 5) na COM7
python modbus_ascii.py slave --port COM7 --addr 5

# Master zapis „Hello” do Slave 5 na COM8, 2 retransmisje, timeout 1 s
python modbus_ascii.py master --port COM8 --addr 5 --cmd write --text "Hello IWSK" --timeout 1.0 --retries 2

# Master odczyt tekstu
python modbus_ascii.py master --port COM8 --addr 5 --cmd read
"""

import argparse
import sys
import time
from typing import List, Tuple, Optional

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover – import guard for syntax checkers
    print("PySerial is required. Install with `pip install pyserial`.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def list_serial_ports() -> List[str]:
    return [p.device for p in list_ports.comports()]

def hex_dump(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)

# ---------------------------  LRC  -----------------------------------------

def calc_lrc(payload: bytes) -> int:
    """Return 1‑byte LRC for given payload (two's complement)."""
    return (-sum(payload)) & 0xFF

# -----------------------  ASCII framing ------------------------------------

def build_ascii_frame(addr: int, func: int, data: bytes) -> bytes:
    """Build MODBUS‑ASCII frame (colon, hex payload, LRC, CRLF)."""
    if not (0 <= addr <= 247):
        raise ValueError("Address must be in 0‑247")
    payload = bytes([addr, func]) + data
    lrc = calc_lrc(payload)
    hex_payload = payload.hex().upper()
    frame = f":{hex_payload}{lrc:02X}\r\n".encode()
    return frame

def parse_ascii_frame(frame: bytes) -> Tuple[int, int, bytes]:
    """Return (addr, func, data) if frame valid else raise ValueError."""
    if not (frame.startswith(b":") and frame.endswith(b"\r\n")):
        raise ValueError("Bad frame delimiters")
    hex_body = frame[1:-2].decode()
    if len(hex_body) < 6 or len(hex_body) % 2:
        raise ValueError("Bad frame length")
    raw = bytes.fromhex(hex_body)
    addr, func, *rest = raw
    data = bytes(rest[:-1]) if rest else b""
    lrc_rx = rest[-1] if rest else None
    if lrc_rx is None or calc_lrc(raw[:-1]) != lrc_rx:
        raise ValueError("LRC error")
    return addr, func, data

# --------------------  Serial helpers  -------------------------------------

class SerialPort:
    """Context‑manager wrapper around pySerial with unified settings."""

    def __init__(self, name: str, baud: int = 9600):
        self._sp = serial.Serial()
        self._sp.port = name
        self._sp.baudrate = baud
        self._sp.bytesize = serial.EIGHTBITS
        self._sp.parity = serial.PARITY_NONE
        self._sp.stopbits = serial.STOPBITS_ONE
        self._sp.timeout = 0.1  # will be overwritten per‑read
        self._sp.write_timeout = 0.1

    def __enter__(self):
        self._sp.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._sp.close()

    # --- passthroughs ---
    def write(self, data: bytes):
        self._sp.write(data)

    def read(self, size: int = 1) -> bytes:
        return self._sp.read(size)

    @property
    def in_waiting(self) -> int:
        return self._sp.in_waiting

    def flush(self):
        self._sp.flush()

# ---------------------------  Slave  ---------------------------------------

def slave_loop(sp: SerialPort, addr: int, char_gap: float):
    stored_text = b""
    buffer = bytearray()
    last_byte_time: Optional[float] = None

    def maybe_process_frame():
        nonlocal buffer, last_byte_time, stored_text
        if not buffer:
            return
        try:
            frame = bytes(buffer)
            a, func, data = parse_ascii_frame(frame)
        except ValueError:
            print("[SLAVE] Invalid frame ->", hex_dump(buffer))
            buffer.clear()
            return

        print(f"[SLAVE] RX <- {hex_dump(frame)}")

        # Ignore if not for us (except broadcast addr=0)
        if a not in (0, addr):
            buffer.clear()
            return

        # Execute command
        if func == 0x01:  # WriteText
            stored_text = data
            if a != 0:  # addressed → respond with ACK
                resp = build_ascii_frame(addr, 0x01, b"OK")
                print(f"[SLAVE] TX -> {hex_dump(resp)}")
                sp.write(resp)
        elif func == 0x02:  # ReadText
            if a == 0:  # broadcast not allowed
                buffer.clear()
                return
            resp = build_ascii_frame(addr, 0x02, stored_text)
            print(f"[SLAVE] TX -> {hex_dump(resp)}")
            sp.write(resp)
        else:  # unsupported → exception
            if a != 0:
                err = build_ascii_frame(addr, func | 0x80, b"01")  # illegal func
                sp.write(err)
        buffer.clear()

    # --- main receive loop ---
    sp.flush()
    while True:
        byte = sp.read(1)
        now = time.time()
        if byte:
            buffer.append(byte[0])
            last_byte_time = now
            # Detect end via CRLF
            if buffer[-2:] == b"\r\n":
                maybe_process_frame()
        else:  # timeout waiting for byte
            # If gap exceeded → treat as frame boundary
            if buffer and last_byte_time and (now - last_byte_time) >= char_gap:
                maybe_process_frame()

# ---------------------------  Master  --------------------------------------

def master_transaction(sp: SerialPort, frame: bytes, timeout: float, char_gap: float) -> Optional[bytes]:
    """Send frame, wait for response, return it or None if timeout."""
    print(f"[MASTER] TX -> {hex_dump(frame)}")
    sp.write(frame)
    sp.flush()
    buffer = bytearray()
    last_byte_time = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        byte = sp.read(1)
        now = time.time()
        if byte:
            buffer.append(byte[0])
            last_byte_time = now
            if buffer[-2:] == b"\r\n":
                resp = bytes(buffer)
                print(f"[MASTER] RX <- {hex_dump(resp)}")
                return resp
        else:
            if buffer and last_byte_time and (now - last_byte_time) >= char_gap:
                # Assume end of frame due to gap
                resp = bytes(buffer)
                print(f"[MASTER] RX <- {hex_dump(resp)}")
                return resp
    print("[MASTER] Timeout waiting for response")
    return None


def run_master(args):
    data = b""
    if args.cmd == "write":
        data = args.text.encode("ascii")
        func = 0x01
    else:
        func = 0x02
    frame = build_ascii_frame(args.addr, func, data)

    with SerialPort(args.port, args.baud) as sp:
        for attempt in range(args.retries + 1):
            resp = master_transaction(sp, frame, args.timeout, args.char_gap)
            if resp is not None or args.addr == 0:  # broadcast → no resp expected
                break
            print(f"[MASTER] Retry {attempt + 1}/{args.retries}")
        else:
            print("[MASTER] Transaction failed after retries")

# ---------------------------  CLI  -----------------------------------------

def parse_cli():
    p = argparse.ArgumentParser(description="MODBUS‑ASCII Master/Slave utility")
    sub = p.add_subparsers(dest="role", required=True)

    # Common serial params
    def add_serial_args(ap):
        ap.add_argument("--port", required=True, help="COMx or /dev/ttyUSBx")
        ap.add_argument("--baud", type=int, default=9600)
        ap.add_argument("--char-gap", type=float, default=0.05, help="max gap between chars [0‑1 s]")

    # Master
    m = sub.add_parser("master")
    add_serial_args(m)
    m.add_argument("--addr", type=int, required=True, help="slave address 0‑247 (0=broadcast)")
    m.add_argument("--cmd", choices=["write", "read"], required=True)
    m.add_argument("--text", help="text for write command")
    m.add_argument("--timeout", type=float, default=1.0, help="transaction timeout 0‑10 s")
    m.add_argument("--retries", type=int, default=0, choices=range(0,6))
    m.add_argument("--mode", choices=["ascii", "rtu"], default="ascii")

    # Slave
    s = sub.add_parser("slave")
    add_serial_args(s)
    s.add_argument("--addr", type=int, required=True, help="station address 1‑247")
    s.add_argument("--mode", choices=["ascii", "rtu"], default="ascii")

    args = p.parse_args()

    # Validate
    if args.role == "master" and args.cmd == "write" and not args.text:
        p.error("--text is required with cmd write")
    if not (0 <= args.char_gap <= 1):
        p.error("--char-gap must be 0‑1 s")
    if args.role == "master":
        if not (0 <= args.timeout <= 10):
            p.error("--timeout 0‑10 s")
    return args

# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_cli()

    if args.mode == "rtu":
        raise NotImplementedError("RTU mode not implemented yet – ASCII fully supported.")

    if args.role == "slave":
        with SerialPort(args.port, args.baud) as sp:
            print(f"[SLAVE] Listening on {args.port} addr={args.addr} (ASCII)")
            slave_loop(sp, args.addr, args.char_gap)
    else:
        run_master(args)
