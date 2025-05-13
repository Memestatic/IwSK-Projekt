# IwSK-Projekt

Projekt realizuje dwa główne zadania związane z komunikacją w systemach przemysłowych.

## Zadania

### MODBUS-ASCII Utility
- Implementacja warstwy fizycznej i łącza danych sieci MODBUS w trybach Master/Slave z obsługą ASCII-frame build & parse oraz automatycznym LRC.
- Opcje dodatkowe: timeout, retransmisje, kontrola przerwy między znakami.
  
#### Przykłady uruchamiania:
```bash
# Slave (adres 5) na COM7
python modbus_ascii.py slave --port COM7 --addr 5

# Master zapis „Hello” do Slave 5 na COM8, 2 retransmisje, timeout 1s
python modbus_ascii.py master --port COM8 --addr 5 --cmd write --text "Hello IWSK" --timeout 1.0 --retries 2

# Master odczyt tekstu
python modbus_ascii.py master --port COM8 --addr 5 --cmd read
```

---

### RS-232 Chat Utility
- Minimalistyczne narzędzie do komunikacji RS-232 z trybami Chat, Ping, Echo.
- Obsługa pełnej konfiguracji transmisji (data bits, parity, stop bits) i kontroli przepływu.

#### Przykłady uruchamiania:
```bash
# CHAT (interaktywnie)
python chat.py --port COM7 --mode chat --baud 9600 --parity N --terminator crlf

# PING (pomiar 5 pakietów)
python chat.py --port COM8 --mode ping --count 5 --flow dsrdtr

# ECHO (pasywny responder po drugiej stronie)
python chat.py --port COM7 --mode echo

# SERWER:
python chat.py --port COM7 --mode echo --data-bits 8 --parity N --stop-bits 1 --flow dsrdtr

# KLIENT:
python chat.py --port COM8 --mode ping --count 5 --terminator none --flow dsrdtr
```
