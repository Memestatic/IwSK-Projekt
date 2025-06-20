import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time
import serial.tools.list_ports

class SerialCommunication:
    def __init__(self, port1, port2, baudrate, data_bits, parity, stop_bits, flow_control_var):
        self.port1 = port1
        self.port2 = port2
        self.baudrate = baudrate
        self.data_bits = data_bits
        self.parity = parity
        self.stop_bits = stop_bits
        self.flow_control_var = flow_control_var

    def setup_connection(self):
        """Ustawienie połączenia na obu portach"""
        try:
            # Wybór kontroli przepływu dla portu nadawczego
            if self.flow_control_var.get() == "Hardware":
                # Jeśli używamy sprzętowej kontroli przepływu (RTS/CTS, DTR/DSR)
                self.ser1 = serial.Serial(port=self.port1, baudrate=self.baudrate, bytesize=self.data_bits,
                                          parity=self.parity, stopbits=self.stop_bits, dsrdtr=True)

                self.ser2 = serial.Serial(port=self.port2, baudrate=self.baudrate, bytesize=self.data_bits,
                                          parity=self.parity, stopbits=self.stop_bits, dsrdtr=True)

            elif self.flow_control_var.get() == "Software":
                self.ser1 = serial.Serial(port=self.port1, baudrate=self.baudrate, bytesize=self.data_bits,
                                          parity=self.parity, stopbits=self.stop_bits, xonxoff=True)

                self.ser2 = serial.Serial(port=self.port2, baudrate=self.baudrate, bytesize=self.data_bits,
                                          parity=self.parity, stopbits=self.stop_bits, xonxoff=True)
            else:
                self.ser1 = serial.Serial(self.port1, self.baudrate, self.data_bits, self.parity, self.stop_bits)
                self.ser2 = serial.Serial(self.port2, self.baudrate, self.data_bits, self.parity, self.stop_bits)

            print(f"Połączenie zostało nawiązane na portach {self.port1} i {self.port2}.")
        except Exception as e:
            print(f"Błąd podczas otwierania portów: {e}")

    def send_data(self, data):
        """Wysyłanie danych przez port 1"""
        try:
            self.ser1.write(data.encode())  # Przesyłamy dane na port1
            print(f"Wysłano dane na {self.port1}: {data}")
        except Exception as e:
            print(f"Błąd wysyłania danych: {e}")

    def receive_data(self):
        """Odbieranie danych z portu 2"""
        while True:
            if self.ser2.in_waiting > 0:
                data = self.ser2.read(self.ser2.in_waiting).decode()  # Odczytujemy dane z portu 2
                print(f"Odebrano dane na {self.port2}: {data}")
                # Wywołanie metody do wyświetlenia odebranych danych w GUI
                app.display_received_data(data)
            time.sleep(1)

    def start_receiving(self):
        """Uruchamiamy odbiór danych w osobnym wątku"""
        threading.Thread(target=self.receive_data, daemon=True).start()

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
        self.root.geometry("800x800")

        # Wykrycie dostępnych portów COM
        available_ports = [p.device for p in serial.tools.list_ports.comports() if 'COM' in p.device]

        # Wybór portu nadawczego
        self.port_label1 = tk.Label(root, text="Wybierz port nadawczy")
        self.port_label1.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.port_combobox1 = ttk.Combobox(root, values=available_ports)
        self.port_combobox1.grid(row=0, column=1, padx=10, pady=5)

        self.check_port_button1 = tk.Button(root, text="Sprawdź port nadawczy", command=self.check_port1)
        self.check_port_button1.grid(row=0, column=2, padx=10, pady=5)

        # Wybór portu odbiorczego
        self.port_label2 = tk.Label(root, text="Wybierz port odbiorczy")
        self.port_label2.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.port_combobox2 = ttk.Combobox(root, values=available_ports)
        self.port_combobox2.grid(row=1, column=1, padx=10, pady=5)

        self.check_port_button2 = tk.Button(root, text="Sprawdź port odbiorczy", command=self.check_port2)
        self.check_port_button2.grid(row=1, column=2, padx=10, pady=5)

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

        # Kontrola przepływu
        self.flow_control_label = tk.Label(root, text="Kontrola przepływu")
        self.flow_control_label.grid(row=6, column=0, padx=10, pady=5, sticky="w")

        self.flow_control_var = tk.StringVar()
        self.flow_control_var.set("None")

        self.none_radio = tk.Radiobutton(root, text="Brak kontroli", variable=self.flow_control_var, value="None")
        self.none_radio.grid(row=6, column=1, padx=10, pady=5, sticky="w")

        self.hardware_radio = tk.Radiobutton(root, text="Sprzętowa (RTS/CTS, DTR/DSR)", variable=self.flow_control_var,
                                             value="Hardware")
        self.hardware_radio.grid(row=7, column=1, padx=10, pady=5, sticky="w")

        self.software_radio = tk.Radiobutton(root, text="Programowa (XON/XOFF)", variable=self.flow_control_var,
                                             value="Software")
        self.software_radio.grid(row=8, column=1, padx=10, pady=5, sticky="w")

        # Terminator
        self.terminator_label = tk.Label(root, text="Wybierz terminator")
        self.terminator_label.grid(row=9, column=0, padx=10, pady=5, sticky="w")

        self.terminator_var = tk.StringVar()
        self.terminator_var.set("None")  # Domyślny terminator

        self.none_terminator = tk.Radiobutton(root, text="Brak terminatora", variable=self.terminator_var, value="None")
        self.none_terminator.grid(row=9, column=1, padx=10, pady=5, sticky="w")

        # Rozdzielamy terminatory standardowe na CR, LF, CR+LF
        self.cr_terminator = tk.Radiobutton(root, text="Carriage Return (CR)", variable=self.terminator_var, value="CR")
        self.cr_terminator.grid(row=10, column=1, padx=10, pady=5, sticky="w")

        self.lf_terminator = tk.Radiobutton(root, text="Line Feed (LF)", variable=self.terminator_var, value="LF")
        self.lf_terminator.grid(row=11, column=1, padx=10, pady=5, sticky="w")

        self.crlf_terminator = tk.Radiobutton(root, text="CR + LF", variable=self.terminator_var, value="CRLF")
        self.crlf_terminator.grid(row=12, column=1, padx=10, pady=5, sticky="w")

        # Własny terminator
        self.custom_terminator = tk.Radiobutton(root, text="Własny", variable=self.terminator_var, value="Custom")
        self.custom_terminator.grid(row=13, column=1, padx=10, pady=5, sticky="w")

        self.custom_terminator_entry = tk.Entry(root)
        self.custom_terminator_entry.grid(row=14, column=1, padx=10, pady=5)
        self.custom_terminator_entry.config(state="disabled")

        # Akcja na zmianę wyboru terminatora
        self.terminator_var.trace("w", self.toggle_custom_terminator)

        # Przycisk do uruchomienia komunikacji
        self.start_button = tk.Button(root, text="Uruchom komunikację", command=self.start_communication)
        self.start_button.grid(row=15, column=0, columnspan=3, padx=10, pady=10)

        # Przycisk PING
        self.ping_button = tk.Button(root, text="Ping", command=self.ping)
        self.ping_button.grid(row=16, column=0, columnspan=3, padx=10, pady=10)

        # Okno nadawania
        self.transmit_label = tk.Label(root, text="Nadawanie")
        self.transmit_label.grid(row=3, column=2, padx=10, pady=5, sticky="w")

        self.transmit_text = tk.Text(root, height=5, width=40)
        self.transmit_text.grid(row=4, column=2, columnspan=3, padx=10, pady=5)

        self.send_button = tk.Button(root, text="Wyślij", command=self.send_data)
        self.send_button.grid(row=5, column=2, columnspan=3, padx=10, pady=5)

        # Okno odbioru
        self.receive_label = tk.Label(root, text="Odbiór")
        self.receive_label.grid(row=6, column=2, padx=10, pady=5, sticky="w")

        self.receive_text = tk.Text(root, height=5, width=40)
        self.receive_text.grid(row=7, column=2, columnspan=3, padx=10, pady=5)

        self.start_button.config(state="disabled")
        self.send_button.config(state="disabled")
        self.ping_button.config(state="disabled")

        self.port_combobox1.bind("<<ComboboxSelected>>", self._update_start_button)
        self.port_combobox2.bind("<<ComboboxSelected>>", self._update_start_button)

    def _update_start_button(self, event=None):
        # włączamy Start tylko gdy oba porty są wybrane
        if self.port_combobox1.get() and self.port_combobox2.get():
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

    def check_port2(self):
        port = self.port_combobox2.get()
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
        data = self.transmit_text.get("1.0", "end-1c")
        if data:
            flow_control = self.flow_control_var.get()

            # Wysyłanie danych z odpowiednim terminatorem
            terminator = self.terminator_var.get()
            if terminator == "Custom":
                custom_terminator = self.custom_terminator_entry.get()
                if custom_terminator:  # Upewniamy się, że użytkownik wprowadził wartość
                    data += custom_terminator
                else:
                    messagebox.showerror("Błąd", "Proszę podać niestandardowy terminator.")
                    return
            elif terminator == "CR":
                data += "\r"  # Tylko CR
            elif terminator == "LF":
                data += "\n"  # Tylko LF
            elif terminator == "CRLF":
                data += "\r\n"  # CR + LF

            comm.send_data(data)  # Wysyłamy dane
        else:
            messagebox.showerror("Błąd", "Brak danych do wysłania.")

    def display_received_data(self, data):
        self.receive_text.insert(tk.END, f"Odebrano: {data}\n")

    def start_communication(self):
        if not self.port_combobox1.get() or not self.port_combobox2.get():
            messagebox.showerror("Błąd", "Wybierz oba porty przed uruchomieniem.")
            return

        if not hasattr(self,
                       'comm') or self.comm.ser1.is_open == False:  # Sprawdzamy, czy połączenie nie jest już otwarte
            port1 = self.port_combobox1.get()  # Nadawczy port
            port2 = self.port_combobox2.get()  # Odbiorczy port
            baudrate = int(self.speed_combobox.get().split()[0])  # Prędkość transmisji
            data_bits = 8 if self.data_bits_combobox.get() == "8 bitów" else 7
            parity = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, "Odd": serial.PARITY_ODD}[
                self.parity_combobox.get()]
            stop_bits = serial.STOPBITS_ONE if self.stop_bits_combobox.get() == "1 bit" else serial.STOPBITS_TWO

            global comm
            comm = SerialCommunication(port1, port2, baudrate, data_bits, parity, stop_bits, self.flow_control_var)
            comm.setup_connection()
            comm.start_receiving()

            self.start_button.config(state="disabled", text="Połączono")
            self.send_button.config(state="normal")
            self.ping_button.config(state="normal")

            messagebox.showinfo("Informacja", "Komunikacja uruchomiona!")
        else:
            messagebox.showinfo("Komunikacja", "Połączenie już zostało nawiązane!")

    def ping(self):
        """Funkcja PING"""
        delay = comm.ping()
        if delay is not None:
            messagebox.showinfo("Ping", f"Round trip delay: {delay:.4f} sekund")

# Główne okno
root = tk.Tk()
app = SerialPortGUI(root)
root.mainloop()
