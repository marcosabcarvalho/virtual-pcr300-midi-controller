import serial
import time

# Configurar a porta serial
ser = serial.Serial('/dev/ttyUSB0', 31250)  # Substitua pela sua porta serial

def send_midi_note_on(note, velocity, channel=0):
    status = 0x90 | (channel & 0x0F)
    ser.write(bytes([status, note, velocity]))
    print(f"Enviado Note On: Nota={note}, Velocidade={velocity}, Canal={channel+1}")

def send_midi_note_off(note, velocity, channel=0):
    status = 0x80 | (channel & 0x0F)
    ser.write(bytes([status, note, velocity]))
    print(f"Enviado Note Off: Nota={note}, Velocidade={velocity}, Canal={channel+1}")

try:
    while True:
        # Exemplo: Enviar C4 (nota 60) com velocidade 100 no canal 1
        send_midi_note_on(60, 100, channel=0)
        time.sleep(1)
        send_midi_note_off(60, 100, channel=0)
        time.sleep(1)
except KeyboardInterrupt:
    ser.close()
    print("Porta serial fechada.")
