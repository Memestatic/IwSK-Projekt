import serial, time
tx = serial.Serial('COM7', 9600, timeout=1)
rx = serial.Serial('COM8', 9600, timeout=1)

tx.write(b'PING')
time.sleep(0.1)
print("Odebrane:", rx.read(4))