import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time
import serial.tools.list_ports
from tkinter import filedialog

class SerialCommunication:
    def __init__(self, port1, port2, baudrate, data_bits, parity, stop_bits, flow_control_var):
        self.port1 = port1
        self.port2 = port2
        self.baudrate = baudrate
        self.data_bits = data_bits
        self.parity = parity
        self.stop_bits = stop_bits
        self.flow_control_var = flow_control_var

        # flaga do włączania/wyłączania automatycznego odbioru
        self.receiving_enabled = True

    def setup_connection(self):
        """Ustawienie połączenia na obu portach"""
        try:
            self.ser1 = serial.Serial(self.port1, self.baudrate,
                                      bytesize=self.data_bits,
                                      parity=self.parity,
                                      stopbits=self.stop_bits)
            self.ser2 = serial.Serial(self.port2, self.baudrate,
                                      bytesize=self.data_bits,
                                      parity=self.parity,
                                      stopbits=self.stop_bits)

            if self.flow_control_var.get() == "dsrdtr":
                self.ser1.dsrdtr = True
                self.ser2.dsrdtr = True
            elif self.flow_control_var.get() == "rtscts":
                self.ser1.rtscts = True
                self.ser2.rtscts = True
            elif self.flow_control_var.get() == "xonxoff":
                self.ser1.xonxoff = True
                self.ser2.xonxoff = True

            print(f"Połączenie na portach {self.port1} ⇄ {self.port2} z flow-control={self.flow_control_var.get()}")
        except Exception as e:
            print(f"Błąd podczas otwierania portów: {e}")

    def disconnect(self):
        """
        Zamyka oba porty szeregowe i wyłącza odbiór w tle.
        """
        # wyłącz odbiór zanim zamkniesz porty
        self.receiving_enabled = False

        try:
            if hasattr(self, 'ser1') and self.ser1.is_open:
                self.ser1.close()
            if hasattr(self, 'ser2') and self.ser2.is_open:
                self.ser2.close()
            print("Połączenie zostało zamknięte.")
        except Exception as e:
            print(f"Błąd podczas rozłączania: {e}")

    def receive_data(self):
        """Odbieranie danych z portu 2 w tle (daemon thread)."""
        while True:
            try:
                # jeśli port zamknięty, przerywamy pętlę
                if not hasattr(self, 'ser2') or not self.ser2.is_open:
                    print("receive_data: port2 zamknięty, wychodzę z wątku.")
                    break

                # tylko gdy enabled i są dane
                if self.receiving_enabled and self.ser2.in_waiting > 0:
                    raw = self.ser2.read(self.ser2.in_waiting)
                    # konwersja wg trybu GUI
                    if app.mode_var.get() == 'hex':
                        display = raw.hex(' ').upper()
                    else:
                        display = raw.decode(errors='replace')
                    print(f"Odebrano dane na {self.port2}: {display}")
                    app.display_received_data(display)

            except serial.SerialException as e:
                # najczęściej: port został zamknięty pod spodem
                print(f"receive_data: SerialException ({e}), wychodzę z wątku.")
                break

            time.sleep(0.1)

    def start_receiving(self):
        """Uruchamiamy odbiór danych w osobnym wątku"""
        threading.Thread(target=self.receive_data, daemon=True).start()

    def transaction(self, data, timeout=1.0):
        """
        Wysyła `data` (bytes lub str) i czeka maksymalnie `timeout` sekund na odpowiedź.
        Zwraca odebraną odpowiedź jako str (tekst lub hex) lub None, jeśli timeout.
        """
        try:
            # 1) reset bufora
            self.ser2.reset_input_buffer()
            self.receiving_enabled = False

            # 2) wysyłka: bytes lub str
            if isinstance(data, (bytes, bytearray)):
                self.ser1.write(data)
            else:
                self.ser1.write(data.encode())

            start = time.perf_counter()
            received = b""

            # 3) czekanie na odpowiedź
            while time.perf_counter() - start < timeout:
                if self.ser2.in_waiting > 0:
                    received = self.ser2.read(self.ser2.in_waiting)
                    break
                time.sleep(0.005)

            if not received:
                print(f"Brak odpowiedzi w ciągu {timeout} sekundy.")
                return None

            print(f"Otrzymano w transakcji (raw): {received}")
            # zwracamy surowe bajty, GUI przekonwertuje do tekstu lub hex
            return received

        except Exception as e:
            print(f"Błąd w transaction: {e}")
            return None

        finally:
            self.receiving_enabled = True
            self.ser2.reset_input_buffer()

    def ping(self):
        """Funkcja PING: sprawdza czas round-trip"""
        try:
            ping_message = "PING"  # Wiadomość ping
            start_time = time.perf_counter()  # Czas przed wysłaniem

            # Wysyłamy wiadomość ping
            self.ser1.write(ping_message.encode())

            # Oczekiwanie na odpowiedź (czy port odbiorczy zareaguje)
            while self.ser2.in_waiting == 0:
                time.sleep(0.1)  # Czekamy na odpowiedź

            # Odczytujemy odpowiedź z portu odbiorczego
            response = self.ser2.read(self.ser2.in_waiting).decode()

            # Sprawdzamy, czy odpowiedź jest poprawna
            if response == ping_message:
                end_time = time.perf_counter()  # Czas po otrzymaniu odpowiedzi
                round_trip_delay = end_time - start_time  # Czas opóźnienia round trip
                print(f"Ping odpowiedź: {response}, czas opóźnienia: {round_trip_delay:.4f} sekundy")
                return round_trip_delay
            else:
                print("Błąd: Odpowiedź nie jest zgodna z pingiem.")
                return None
        except Exception as e:
            print(f"Błąd podczas pingowania: {e}")
            return None


class SerialPortGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Interfejs komunikacji szeregowej")
        self.root.geometry("750x900")

        # Wykrycie dostępnych portów COM
        available_ports = [p.device for p in serial.tools.list_ports.comports() if 'COM' in p.device]

        # Wybór portu nadawczego
        self.port_label1 = tk.Label(root, text="Wybierz port nadawczy")
        self.port_label1.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.port_combobox1 = ttk.Combobox(root, values=available_ports)
        self.port_combobox1.grid(row=0, column=1, padx=10, pady=5)

        self.check_port_button1 = tk.Button(root, text="Sprawdź port nadawczy", command=self.check_port1)
        self.check_port_button1.grid(row=0, column=2, padx=10, pady=5)

        # Parametry transmisji
        self.speed_label = tk.Label(root, text="Wybierz szybkość transmisji")
        self.speed_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.speed_combobox = ttk.Combobox(root,
                                           values=["150 bit/s", "300 bit/s", "600 bit/s", "1200 bit/s", "2400 bit/s",
                                                   "4800 bit/s", "9600 bit/s", "19200 bit/s", "38400 bit/s",
                                                   "57600 bit/s", "115200 bit/s"])
        self.speed_combobox.grid(row=2, column=1, padx=10, pady=5)
        self.speed_combobox.set("9600 bit/s")  # Domyślna prędkość

        self.data_bits_label = tk.Label(root, text="Wybierz liczbę bitów danych")
        self.data_bits_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        self.data_bits_combobox = ttk.Combobox(root, values=["7 bitów", "8 bitów"])
        self.data_bits_combobox.grid(row=3, column=1, padx=10, pady=5)
        self.data_bits_combobox.set("8 bitów")  # Domyślna liczba bitów danych

        self.parity_label = tk.Label(root, text="Wybierz kontrolę parzystości")
        self.parity_label.grid(row=4, column=0, padx=10, pady=5, sticky="w")

        self.parity_combobox = ttk.Combobox(root, values=["None", "Even", "Odd"])
        self.parity_combobox.grid(row=4, column=1, padx=10, pady=5)
        self.parity_combobox.set("None")  # Domyślna kontrola parzystości

        self.stop_bits_label = tk.Label(root, text="Wybierz liczbę bitów stopu")
        self.stop_bits_label.grid(row=5, column=0, padx=10, pady=5, sticky="w")

        self.stop_bits_combobox = ttk.Combobox(root, values=["1 bit", "2 bity"])
        self.stop_bits_combobox.grid(row=5, column=1, padx=10, pady=5)
        self.stop_bits_combobox.set("1 bit")  # Domyślna liczba bitów stopu

        # --- sekcja Kontrola przepływu ---
        self.flow_control_label = tk.Label(root, text="Kontrola przepływu")
        self.flow_control_label.grid(row=6, column=0, padx=10, pady=5, sticky="w")

        self.flow_control_var = tk.StringVar(value="None")

        self.none_radio = tk.Radiobutton(root, text="Brak", variable=self.flow_control_var, value="None")
        self.none_radio.grid(row=6, column=1, sticky="w")
        self.rtscts_radio = tk.Radiobutton(root, text="RTS/CTS", variable=self.flow_control_var, value="rtscts")
        self.rtscts_radio.grid(row=7, column=1, sticky="w")
        self.dsrdtr_radio = tk.Radiobutton(root, text="DSR/DTR", variable=self.flow_control_var, value="dsrdtr")
        self.dsrdtr_radio.grid(row=8, column=1, sticky="w")
        self.xonxoff_radio = tk.Radiobutton(root, text="XON/XOFF", variable=self.flow_control_var, value="xonxoff")
        self.xonxoff_radio.grid(row=9, column=1, sticky="w")

        # NOWA OPCJA: własna, manualna kontrola
        self.manual_radio = tk.Radiobutton(root, text="Własna", variable=self.flow_control_var, value="manual")
        self.manual_radio.grid(row=10, column=1, sticky="w")

        # przyciski do manualnego sterowania DTR/RTS
        self.dtr_var = tk.BooleanVar(value=False)
        self.dtr_check = tk.Checkbutton(root, text="DTR", variable=self.dtr_var, command=self.toggle_dtr)
        self.dtr_check.grid(row=9, column=4, sticky="w")
        self.rts_var = tk.BooleanVar(value=False)
        self.rts_check = tk.Checkbutton(root, text="RTS", variable=self.rts_var, command=self.toggle_rts)
        self.rts_check.grid(row=9, column=5, sticky="w")

        # na start wszystko wyłączone
        self.dtr_check.config(state="disabled")
        self.rts_check.config(state="disabled")

        # trace na zmianę flow_control_var
        self.flow_control_var.trace_add("write", self.on_flow_control_change)

        # Terminator
        self.terminator_label = tk.Label(root, text="Wybierz terminator")
        self.terminator_label.grid(row=13, column=0, padx=10, pady=5, sticky="w")

        self.terminator_var = tk.StringVar()
        self.terminator_var.set("None")  # Domyślny terminator

        self.none_terminator = tk.Radiobutton(root, text="Brak terminatora", variable=self.terminator_var, value="None")
        self.none_terminator.grid(row=13, column=1, padx=10, pady=5, sticky="w")

        # Podzial terminatorow standardowych na CR, LF, CR+LF
        self.cr_terminator = tk.Radiobutton(root, text="Carriage Return (CR)", variable=self.terminator_var, value="CR")
        self.cr_terminator.grid(row=14, column=1, padx=10, pady=5, sticky="w")

        self.lf_terminator = tk.Radiobutton(root, text="Line Feed (LF)", variable=self.terminator_var, value="LF")
        self.lf_terminator.grid(row=15, column=1, padx=10, pady=5, sticky="w")

        self.crlf_terminator = tk.Radiobutton(root, text="CR + LF", variable=self.terminator_var, value="CRLF")
        self.crlf_terminator.grid(row=16, column=1, padx=10, pady=5, sticky="w")

        # Własny terminator
        self.custom_terminator = tk.Radiobutton(root, text="Własny", variable=self.terminator_var, value="Custom")
        self.custom_terminator.grid(row=17, column=1, padx=10, pady=5, sticky="w")

        self.custom_terminator_entry = tk.Entry(root)
        self.custom_terminator_entry.grid(row=18, column=1, padx=10, pady=5)
        self.custom_terminator_entry.config(state="disabled")

        # Akcja na zmianę wyboru terminatora
        self.terminator_var.trace("w", self.toggle_custom_terminator)

        # Przycisk do uruchomienia komunikacji
        self.start_button = tk.Button(root, text="Uruchom komunikację", command=self.start_communication)
        self.start_button.grid(row=19, column=0, columnspan=3, padx=10, pady=10)

        # —————— Rozłącz ——————
        self.disconnect_button = tk.Button(root, text="Rozłącz", command=self.disconnect)
        self.disconnect_button.grid(row=20, column=0, columnspan=3, padx=10, pady=5)
        self.disconnect_button.config(state="disabled")

        # Przycisk PING
        self.ping_button = tk.Button(root, text="Ping", command=self.ping)
        self.ping_button.grid(row=21, column=0, columnspan=3, padx=10, pady=10)

        # --- TRYB TRANSMISJI (tekst vs HEX) ---
        self.mode_label = tk.Label(root, text="Tryb transmisji:")
        self.mode_label.grid(row=5, column=2, padx=10, pady=5, sticky="w")
        self.mode_var = tk.StringVar(value="text")
        self.text_radio = tk.Radiobutton(root, text="Text", variable=self.mode_var, value="text")
        self.text_radio.grid(row=6, column=2, sticky="w")
        self.hex_radio = tk.Radiobutton(root, text="HEX", variable=self.mode_var, value="hex")
        self.hex_radio.grid(row=6, column=3, sticky="w")

        # --- Przycisk wczytywania pliku binarnego ---
        self.load_file_button = tk.Button(root, text="Wczytaj plik BIN", command=self.load_binary_file)
        self.load_file_button.grid(row=7, column=2, columnspan=3, padx=10, pady=5)

        # Okno nadawania
        self.transmit_label = tk.Label(root, text="Nadawanie")
        self.transmit_label.grid(row=9, column=2, padx=10, pady=5, sticky="w")

        self.transmit_text = tk.Text(root, height=5, width=40)
        self.transmit_text.grid(row=10, column=2, columnspan=3, padx=10, pady=5)

        self.send_button = tk.Button(root, text="Wyślij", command=self.send_data)
        self.send_button.grid(row=11, column=2, columnspan=3, padx=10, pady=5)

        # Okno odbioru
        self.receive_label = tk.Label(root, text="Odbiór")
        self.receive_label.grid(row=12, column=2, padx=10, pady=5, sticky="w")

        self.receive_text = tk.Text(root, height=5, width=40)
        self.receive_text.grid(row=13, column=2, columnspan=3, padx=10, pady=5)

        self.start_button.config(state="disabled")
        self.send_button.config(state="disabled")
        self.ping_button.config(state="disabled")

        self.port_combobox1.bind("<<ComboboxSelected>>", self._update_start_button)

    def load_binary_file(self):
        """Wczytaj dowolny plik i zamień na hex w polu Nadawanie"""
        path = filedialog.askopenfilename(title="Wybierz plik binarny")
        if not path:
            return
        with open(path, 'rb') as f:
            data = f.read()
        hexstr = data.hex(' ').upper()
        self.transmit_text.delete('1.0', 'end')
        self.transmit_text.insert('1.0', hexstr)
        self.mode_var.set('hex')

    def on_flow_control_change(self, *args):
        mode = self.flow_control_var.get()
        if mode == "manual":
            if 'comm' in globals():
                # włącz przyciski DTR/RTS, użytkownik może je zmieniać
                self.dtr_check.config(state="normal")
                self.rts_check.config(state="normal")
        else:
            # wyłącz i zresetuj ich stan
            self.dtr_check.config(state="disabled")
            self.rts_check.config(state="disabled")
            self.dtr_var.set(False)
            self.rts_var.set(False)

    def toggle_dtr(self):
        comm.ser1.dtr = self.dtr_var.get()

    def toggle_rts(self):
        comm.ser1.rts = self.rts_var.get()

    def _update_start_button(self, event=None):
        if self.port_combobox1.get():
            self.start_button.config(state="normal")
        else:
            self.start_button.config(state="disabled")

    def check_port1(self):
        port = self.port_combobox1.get()
        ports = [p.device for p in serial.tools.list_ports.comports() if 'COM' in p.device]
        if port in ports:
            messagebox.showinfo("Informacja", f"Port {port} jest dostępny!")
        else:
            messagebox.showerror("Błąd", f"Port {port} nie istnieje lub jest niedostępny.")

    def toggle_custom_terminator(self, *args):
        if self.terminator_var.get() == "Custom":
            self.custom_terminator_entry.config(state="normal")
        else:
            self.custom_terminator_entry.config(state="disabled")

    def send_data(self):
        raw = self.transmit_text.get("1.0", "end-1c").strip()
        if not raw:
            messagebox.showerror("Błąd", "Brak danych do wysłania.")
            return
        # przygotowanie payload
        if self.mode_var.get() == 'hex':
            try:
                payload = bytes.fromhex(raw)
            except ValueError:
                messagebox.showerror("Błąd", "Nieprawidłowy format HEX.")
                return
        else:
            payload = raw.encode()
        # terminator
        term = self.terminator_var.get()
        if term == "Custom":
            custom = self.custom_terminator_entry.get()
            if not custom:
                messagebox.showerror("Błąd", "Proszę podać niestandardowy terminator.")
                return
            term_bytes = custom.encode() if self.mode_var.get()== 'text' else bytes.fromhex(custom)
        elif term == "CR":
            term_bytes = b"\r"
        elif term == "LF":
            term_bytes = b"\n"
        elif term == "CRLF":
            term_bytes = b"\r\n"
        else:
            term_bytes = b""
        payload += term_bytes
        # wysyłka jako transakcja
        timeout = 1.0
        resp = comm.transaction(payload, timeout=timeout)
        if resp is None:
            messagebox.showwarning("Transakcja", f"Brak odpowiedzi w ciągu {timeout:.2f} s.")
        else:
            # konwersja odpowiedzi wg trybu
            if self.mode_var.get() == 'hex':
                display = resp.hex(' ').upper()
            else:
                display = resp.decode(errors='replace')
            self.display_received_data(display)


    def display_received_data(self, data):
        self.receive_text.insert(tk.END, f"Odebrano: {data}\n")

    def detect_paired_port(self, port_tx):
        ports = list(serial.tools.list_ports.comports())
        # 1) jeśli są tylko dwa – bierz drugi
        if len(ports) == 2:
            return next(p.device for p in ports if p.device != port_tx)

        # 2) VID/PID
        target = next((p for p in ports if p.device == port_tx), None)
        if target and target.vid and target.pid:
            for p in ports:
                if p.device != port_tx and p.vid == target.vid and p.pid == target.pid:
                    return p.device

        # 3) fallback po manufacturer/product
        if target:
            for p in ports:
                if p.device != port_tx and p.manufacturer == target.manufacturer and p.product == target.product:
                    return p.device

        return None

    def start_communication(self):
        port1 = self.port_combobox1.get()
        if not port1:
            messagebox.showerror("Błąd", "Wybierz port nadawczy.")
            return

        port2 = self.detect_paired_port(port1)
        if not port2:
            print("=== dostępne porty ===")
            for p in serial.tools.list_ports.comports():
                print(f"{p.device}: vid={p.vid} pid={p.pid} hwid={p.hwid}")
            messagebox.showerror("Błąd", f"Nie wykryto sparowanego portu dla {port1}. Sprawdź konsolę.")
            return

        baudrate = int(self.speed_combobox.get().split()[0])
        data_bits = 8 if self.data_bits_combobox.get() == "8 bitów" else 7
        parity = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, "Odd": serial.PARITY_ODD}[self.parity_combobox.get()]
        stop_bits = serial.STOPBITS_ONE if self.stop_bits_combobox.get() == "1 bit" else serial.STOPBITS_TWO

        global comm
        comm = SerialCommunication(port1, port2, baudrate, data_bits, parity, stop_bits, self.flow_control_var)
        comm.setup_connection()
        comm.start_receiving()

        if self.flow_control_var.get() == "manual":
            if 'comm' in globals():
                self.dtr_check.config(state="normal")
                self.rts_check.config(state="normal")

        self.start_button.config(state="disabled", text="Połączono")
        self.send_button.config(state="normal")
        self.ping_button.config(state="normal")
        self.disconnect_button.config(state="normal")
        messagebox.showinfo("Informacja", f"Komunikacja uruchomiona!\nTX={port1} → RX={port2}")

    def disconnect(self):
        if 'comm' in globals():
            comm.disconnect()

        self.start_button.config(state="normal", text="Uruchom komunikację")
        self.send_button.config(state="disabled")
        self.ping_button.config(state="disabled")
        self.disconnect_button.config(state="disabled")
        try:    self.transaction_button.config(state="disabled")
        except: pass

        self.dtr_check.config(state="disabled"); self.dtr_var.set(False)
        self.rts_check.config(state="disabled"); self.rts_var.set(False)

        messagebox.showinfo("Informacja", "Połączenie zostało rozłączone.")
    def ping(self):
        delay = comm.ping()
        if delay is not None:
            messagebox.showinfo("Ping", f"Round trip delay: {delay:.4f} sekund")

# Główne okno
root = tk.Tk()
app = SerialPortGUI(root)
root.mainloop()