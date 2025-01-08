import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import math
import mido
import json
import os
from threading import Thread

# Definições de Control Change (CC) conforme z_config.ino
SLIDER_VERTICAL_CC_BASE = 0x11  # S1 -> 0x11, S2 -> 0x12, ..., S8 -> 0x18
S9_CC = 0x12                    # S9

SLIDER_HORIZONTAL_CC = 0x13

KNOB_CC_BASE = 0x10             # R1 -> 0x10, R2 -> 0x11, ..., R18 -> 0x21
R19_CC = 0x12                   # R19

BUTTON_MAPPINGS = [
    {"name": "Sustain", "cc": 0x40},
    {"name": "Back", "cc": 0x52},
    {"name": "Stop", "cc": 0x52},
    {"name": "Start", "cc": 0x52},
    {"name": "Rec", "cc": 0x52},
    {"name": "A1", "cc": 0x50},
    {"name": "A2", "cc": 0x50},
    {"name": "A3", "cc": 0x50},
    {"name": "A4", "cc": 0x50},
    {"name": "A5", "cc": 0x50},
    {"name": "A6", "cc": 0x50},
    {"name": "A7", "cc": 0x50},
    {"name": "A8", "cc": 0x50},
    {"name": "A9", "cc": 0x53},
    {"name": "B1", "cc": 0x51},
    {"name": "B2", "cc": 0x51},
    {"name": "B3", "cc": 0x51},
    {"name": "B4", "cc": 0x51},
    {"name": "B5", "cc": 0x51},
    {"name": "B6", "cc": 0x51},
    {"name": "B7", "cc": 0x51},
    {"name": "B8", "cc": 0x51},
    {"name": "B9", "cc": 0x53},
]

CHANNEL = 0  # Canal MIDI 1 (0-15)

KEYBOARD_BASE_NOTE = 36  # C2 = 36 (ajuste conforme sua preferência)
WHITE_KEYS = 42          # 6 oitavas * 7 teclas brancas por oitava
BLACK_KEY_PATTERNS = [1, 3, 6, 8, 10]  # Semitons pretos na oitava

CONFIG_FILE = "pcr300_config.json"

class CircularKnob(tk.Canvas):
    def __init__(self, parent, size=100, min_val=0, max_val=127, initial_val=64, command=None, **kwargs):
        super().__init__(parent, width=size, height=size, bg=kwargs.get('bg', '#333'), highlightthickness=0)
        self.size = size
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.command = command  # Callback function

        # Desenhar o knob
        self.center = size / 2
        self.radius = size * 0.4
        self.create_oval(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            fill=kwargs.get('fill', '#555'), outline='black', width=2
        )

        # Desenhar o indicador
        self.indicator_length = self.radius * 0.9
        self.indicator = self.create_line(
            self.center, self.center,
            self.center, self.center - self.indicator_length,
            fill='red', width=3
        )

        # Bind de eventos
        self.bind("<Button-1>", self.click)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)

        # Atualizar o indicador com o valor inicial
        self.update_indicator()

    def value_to_angle(self, value):
        # Mapeia o valor para um ângulo (em radianos)
        # Definindo min_val em 135 graus e max_val em -135 graus
        angle_deg = 135 - ((value - self.min_val) / (self.max_val - self.min_val)) * 270
        angle_rad = math.radians(angle_deg)
        return angle_rad

    def update_indicator(self):
        angle = self.value_to_angle(self.value)
        x = self.center + self.indicator_length * math.cos(angle)
        y = self.center - self.indicator_length * math.sin(angle)
        self.coords(self.indicator, self.center, self.center, x, y)

    def set_value(self, value, velocity=None):
        # Limitar o valor dentro do intervalo
        value = max(self.min_val, min(self.max_val, value))
        if value != self.value:
            self.value = value
            self.update_indicator()
            if self.command:
                if velocity is not None:
                    self.command(self.value, velocity)
                else:
                    self.command(self.value)

    def click(self, event):
        self.update_value(event.x, event.y)
        # Registrar o tempo de pressão
        self.press_time = time.time()

    def drag(self, event):
        self.update_value(event.x, event.y)

    def release(self, event):
        # Calcular a duração da pressão
        release_time = time.time()
        duration = release_time - self.press_time
        # Mapear a duração para velocidade
        min_duration = 0.05  # 50 ms para máxima velocidade
        max_duration = 0.5   # 500 ms para mínima velocidade
        duration = max(min_duration, min(duration, max_duration))
        # Inverter o mapeamento: menor duração -> maior velocidade
        velocity = int(127 * (1 - (duration - min_duration) / (max_duration - min_duration)))
        velocity = max(1, min(127, velocity))  # Garantir dentro do intervalo

        # Enviar Note Off com a velocidade capturada
        if self.command:
            self.command(self.value, velocity)

    def update_value(self, x, y):
        # Calcular o ângulo baseado na posição do mouse
        dx = x - self.center
        dy = self.center - y  # Invertido para coordenadas cartesianas
        angle = math.atan2(dy, dx)
        angle_deg = math.degrees(angle)
        if angle_deg < 0:
            angle_deg += 360

        # Mapear o ângulo para o valor do knob
        # Definindo que 135 graus é o mínimo e -135 (225) é o máximo
        if 135 <= angle_deg <= 225:
            # Fora do alcance, não atualizar
            return
        elif angle_deg < 135:
            normalized_angle = 135 - angle_deg
        else:
            normalized_angle = 135 + (360 - angle_deg)

        value = int((normalized_angle / 270) * (self.max_val - self.min_val) + self.min_val)
        self.set_value(value)

class PCR300Virtual(tk.Tk):
    def __init__(self, serial_port='/dev/ttyUSB0', baudrate=31250):
        super().__init__()
        self.title("PCR-300 Virtual - Python Demo")
        self.geometry("2500x1000")  # Ajustado para acomodar mais controles e 6 oitavas
        self.resizable(False, False)

        # Inicializar o dicionário de configuração
        self.config_data = self.load_config()

        # Configurações de Serial
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial_conn = None

        # Inicializa a conexão serial
        self.init_serial()

        # Variável de exibição (display “LCD”)
        self.display_text = tk.StringVar(value="PCR-300")
        self.create_main_interface()

        # Dicionário para armazenar notas ativas
        self.active_notes = {}

        # Definir o mapeamento controlador -> virtual
        self.controller_to_virtual_map = {note: note for note in range(36, 108)}  # Ajuste conforme necessário

        # Inicializar dispositivos MIDI
        self.init_midi()

    def init_serial(self):
        try:
            self.serial_conn = serial.Serial(
                self.serial_port,
                self.baudrate,
                timeout=0  # Não bloquear
            )
            print(f"Conectado à porta serial {self.serial_port} a {self.baudrate} baud.")
        except serial.SerialException as e:
            print(f"Erro ao conectar à porta serial {self.serial_port}: {e}")
            self.serial_conn = None

    def init_midi(self):
        # Inicializar porta MIDI de entrada com mido
        self.midi_input = None

        # Configurar a porta MIDI selecionada
        selected_port = self.config_data.get("midi_device", None)
        if selected_port and selected_port in mido.get_input_names():
            try:
                self.midi_input = mido.open_input(selected_port, callback=self.handle_midi_message)
                print(f"Porta MIDI '{selected_port}' aberta.")
            except IOError as e:
                print(f"Erro ao abrir a porta MIDI '{selected_port}': {e}")

    def create_main_interface(self):
        """
        Monta toda a interface:  
          - Combobox para dispositivos MIDI,
          - 9 sliders verticais (S1..S9),  
          - 1 slider horizontal (H1),  
          - 18 knobs circulares (R1..R18) organizados em duas linhas,
          - 23 botões (sustain, transport, A1..A9, B1..B9),  
          - teclado virtual de 6 oitavas.  
        """
        top_frame = tk.Frame(self, bg="#444")
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # ================== PARTE DO DISPLAY (LCD) ==================
        display_frame = tk.Frame(top_frame, bg="#222")
        display_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        lbl = tk.Label(display_frame, text="LCD Display:", fg="white", bg="#222")
        lbl.pack(anchor="w")
        lbl_display = tk.Label(display_frame, textvariable=self.display_text,
                               fg="#0f0", bg="#020", font=("Courier", 14, "bold"), width=20)
        lbl_display.pack(pady=5)

        # ================== CONTROLE MIDI ==================
        midi_frame = tk.Frame(top_frame, bg="#333", bd=2, relief=tk.RIDGE)
        midi_frame.pack(side=tk.LEFT, padx=10)

        tk.Label(midi_frame, text="Dispositivo MIDI:", bg="#333", fg="white").pack(anchor="w", padx=5, pady=2)
        self.midi_devices = mido.get_input_names()
        self.selected_midi_device = tk.StringVar()
        self.midi_combobox = ttk.Combobox(
            midi_frame, textvariable=self.selected_midi_device,
            values=self.midi_devices, state="readonly", width=30
        )
        self.midi_combobox.pack(padx=5, pady=5)
        # Selecionar dispositivo salvo ou padrão
        if self.config_data.get("midi_device", None) in self.midi_devices:
            self.midi_combobox.set(self.config_data["midi_device"])
        elif self.midi_devices:
            self.midi_combobox.set(self.midi_devices[0])
        else:
            self.midi_combobox.set("Nenhum dispositivo")

        self.midi_combobox.bind("<<ComboboxSelected>>", self.change_midi_device)

        # ================== SLIDERS VERTICAIS ==================
        sliders_frame = tk.Frame(top_frame, bg="#333", bd=2, relief=tk.RIDGE)
        sliders_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(sliders_frame, text="Sliders (S1..S9)", bg="#333", fg="white").pack()
        self.vertical_sliders = []
        for i in range(9):
            if i < 8:
                cc_num = SLIDER_VERTICAL_CC_BASE + i  # 0x11..0x18
            else:
                cc_num = S9_CC  # 0x12 para S9
            sv = tk.Scale(
                sliders_frame, from_=127, to=0, orient=tk.VERTICAL, length=180,
                command=lambda val, cc=cc_num: self.on_vertical_slider(cc, val)
            )
            sv.pack(side=tk.LEFT, padx=3, pady=10)
            sv.set(0)
            self.vertical_sliders.append(sv)

        # ================== SLIDER HORIZONTAL (H1) ==================
        hslider_frame = tk.Frame(top_frame, bg="#333", bd=2, relief=tk.RIDGE)
        hslider_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(hslider_frame, text="Slider H1", bg="#333", fg="white").pack()
        self.hslider = tk.Scale(
            hslider_frame, from_=0, to=127, orient=tk.HORIZONTAL, length=120,
            command=self.on_horizontal_slider
        )
        self.hslider.pack(padx=5, pady=30)
        self.hslider.set(64)

        # ================== KNOBS (R1..R18) ==================
        knobs_frame = tk.Frame(top_frame, bg="#333", bd=2, relief=tk.RIDGE)
        knobs_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(knobs_frame, text="Rotary Knobs (R1..R18)", bg="#333", fg="white").pack()

        self.knob_vars = []
        self.knob_rows = [tk.Frame(knobs_frame, bg="#333") for _ in range(2)]  # Duas linhas
        for row in self.knob_rows:
            row.pack(pady=5)

        for i in range(18):
            cc_num = KNOB_CC_BASE + i  # CC 0x10..0x21
            knob = CircularKnob(
                self.knob_rows[i // 9], size=60, min_val=0, max_val=127,
                initial_val=64, command=lambda val, cc=cc_num: self.on_knob_change(cc, val)
            )
            knob.pack(side=tk.LEFT, padx=5, pady=5)
            self.knob_vars.append(knob)

        # ================== BOTÕES ==================
        buttons_frame = tk.Frame(self, bg="#333", bd=2, relief=tk.RIDGE)
        buttons_frame.pack(side=tk.TOP, padx=10, pady=10)
        tk.Label(buttons_frame, text="Press Buttons", bg="#333", fg="white").pack()

        self.button_states = {}
        self.button_widgets = {}
        for btn in BUTTON_MAPPINGS:
            btn_name = btn["name"]
            btn_cc = btn["cc"]
            self.button_states[btn_name] = False  # Estado inicial

            btn_widget = tk.Button(
                buttons_frame, text=btn_name,
                width=6, height=2,
                bg="grey",
                command=lambda name=btn_name, cc=btn_cc: self.on_button_press(name, cc)
            )
            btn_widget.pack(side=tk.LEFT, padx=2, pady=2)
            self.button_widgets[btn_name] = btn_widget  # Armazena referência para alteração de cor

        # ================== TECLADO VIRTUAL ==================
        bottom_frame = tk.Frame(self, bg="#222")
        bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.create_virtual_keyboard(bottom_frame)

    def on_vertical_slider(self, cc_num, value):
        """
        Envia CC para sliders verticais.
        """
        val_int = int(float(value))
        self.send_control_change(cc_num, val_int)
        # Atualizar display para indicar qual slider foi ajustado
        if cc_num == S9_CC:
            slider_number = 9
        else:
            slider_number = cc_num - SLIDER_VERTICAL_CC_BASE + 1
        self.display_text.set(f"S{slider_number}={val_int}")

    def on_horizontal_slider(self, value):
        val_int = int(float(value))
        self.send_control_change(SLIDER_HORIZONTAL_CC, val_int)
        self.display_text.set(f"H1={val_int}")

    def on_knob_change(self, cc_num, value):
        """
        Envia CC para knobs.
        """
        val_int = int(float(value))
        self.send_control_change(cc_num, val_int)
        # Determinar qual knob foi ajustado
        knob_number = cc_num - KNOB_CC_BASE + 1
        self.display_text.set(f"R{knob_number}={val_int}")

    def on_button_press(self, btn_name, cc_num):
        """
        Envia CC correspondente ao botão pressionado.
        Toggle: envia 127 quando pressionado, 0 quando solto.
        """
        # Alterna o estado do botão
        self.button_states[btn_name] = not self.button_states[btn_name]
        val = 127 if self.button_states[btn_name] else 0
        self.send_control_change(cc_num, val)
        self.display_text.set(f"{btn_name} -> {val}")
        # Atualiza a cor do botão para refletir o estado
        btn_widget = self.button_widgets.get(btn_name)
        if btn_widget:
            new_color = "green" if self.button_states[btn_name] else "grey"
            btn_widget.config(bg=new_color)

    def create_virtual_keyboard(self, parent):
        """
        Cria um teclado virtual mais realista com 6 oitavas de teclas brancas e pretas.
        """
        key_width = 30
        key_height = 150
        black_key_width = key_width * 0.6
        black_key_height = key_height * 0.6
        num_octaves = WHITE_KEYS // 7  # 6 oitavas
        remaining_keys = WHITE_KEYS % 7  # 0, já que 6 * 7 = 42

        self.kb_canvas = tk.Canvas(parent, width=(WHITE_KEYS + remaining_keys) * key_width, height=key_height, bg="#222")
        self.kb_canvas.pack(pady=10)

        # Padrão de teclas pretas relativas às brancas
        black_key_offsets = [1, 2, 4, 5, 6]  # Intervalos onde as teclas pretas aparecem

        self.white_key_ids = []
        self.black_key_ids = []
        self.key_press_times = {}  # Armazena o tempo de pressão para cada tecla
        current_x = 0

        for octave in range(num_octaves):
            for i in range(7):
                # Desenhar tecla branca
                x1 = current_x
                y1 = 0
                x2 = current_x + key_width
                y2 = key_height
                rect_id = self.kb_canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="black", tags="white_key")
                self.white_key_ids.append(rect_id)
                current_x += key_width

            # Desenhar teclas pretas para a oitava atual
            for offset in black_key_offsets:
                if octave * 7 + offset >= WHITE_KEYS:
                    continue
                x = (octave * 7 + offset) * key_width - black_key_width / 2
                rect_id = self.kb_canvas.create_rectangle(
                    x, 0, x + black_key_width, black_key_height,
                    fill="black", outline="black", tags="black_key"
                )
                self.black_key_ids.append(rect_id)

        # Desenhar teclas brancas restantes, se houver
        for i in range(remaining_keys):
            x1 = current_x
            y1 = 0
            x2 = current_x + key_width
            y2 = key_height
            rect_id = self.kb_canvas.create_rectangle(x1, y1, x2, y2, fill="white", outline="black", tags="white_key")
            self.white_key_ids.append(rect_id)
            current_x += key_width

        # Bindings para interação
        self.kb_canvas.tag_bind("white_key", "<ButtonPress-1>", self.on_key_press)
        self.kb_canvas.tag_bind("white_key", "<ButtonRelease-1>", self.on_key_release)
        self.kb_canvas.tag_bind("black_key", "<ButtonPress-1>", self.on_key_press)
        self.kb_canvas.tag_bind("black_key", "<ButtonRelease-1>", self.on_key_release)

    def on_key_press(self, event):
        """
        Captura o pressionamento da tecla para iniciar a contagem de tempo.
        """
        item_id = self.kb_canvas.find_closest(event.x, event.y)[0]
        self.key_press_times[item_id] = time.time()

        if item_id in self.white_key_ids:
            i = self.white_key_ids.index(item_id)
            note = KEYBOARD_BASE_NOTE + i
            color_pressed = "yellow"
            default_color = "white"
        elif item_id in self.black_key_ids:
            i = self.black_key_ids.index(item_id)
            octave = i // 5
            position_in_octave = i % 5
            semitone_offsets = [1, 3, 6, 8, 10]  # Correspondente a C#, D#, F#, G#, A#
            note = KEYBOARD_BASE_NOTE + (octave * 12) + semitone_offsets[position_in_octave]
            color_pressed = "red"
            default_color = "black"
        else:
            return

        # Muda cor para indicar que a tecla está pressionada
        self.kb_canvas.itemconfig(item_id, fill=color_pressed)

        # Enviar Note On com velocidade inicial
        velocity = 100  # Velocidade padrão ou ajuste conforme necessário
        self.send_note_on(note, velocity)
        self.display_text.set(f"Note {note} ON (Vel: {velocity})")

    def on_key_release(self, event):
        """
        Calcula a duração da pressão e envia a mensagem MIDI com velocidade dinâmica.
        """
        item_id = self.kb_canvas.find_closest(event.x, event.y)[0]
        press_time = self.key_press_times.pop(item_id, None)

        if press_time is None:
            return  # Sem registro de pressionamento

        release_time = time.time()
        duration = release_time - press_time

        # Definir intervalos de tempo mínimo e máximo para mapeamento (em segundos)
        min_duration = 0.05  # 50 ms para máxima velocidade
        max_duration = 0.5   # 500 ms para mínima velocidade

        # Limitar a duração dentro dos limites
        duration = max(min_duration, min(duration, max_duration))

        # Inverter o mapeamento: menor duração -> maior velocidade
        velocity = int(127 * (1 - (duration - min_duration) / (max_duration - min_duration)))
        velocity = max(1, min(127, velocity))  # Garantir dentro do intervalo

        if item_id in self.white_key_ids:
            i = self.white_key_ids.index(item_id)
            note = KEYBOARD_BASE_NOTE + i
            default_color = "white"
        elif item_id in self.black_key_ids:
            i = self.black_key_ids.index(item_id)
            octave = i // 5
            position_in_octave = i % 5
            semitone_offsets = [1, 3, 6, 8, 10]  # Correspondente a C#, D#, F#, G#, A#
            note = KEYBOARD_BASE_NOTE + (octave * 12) + semitone_offsets[position_in_octave]
            default_color = "black"
        else:
            return

        # Enviar Note Off com a velocidade dinâmica
        self.send_note_off(note, velocity)
        self.display_text.set(f"Note {note} OFF (Vel: {velocity})")

        # Volta a cor original da tecla
        self.kb_canvas.itemconfig(item_id, fill=default_color)

    # ----------------------- Funções MIDI via pySerial -----------------------
    def send_control_change(self, control, value):
        """
        Envia uma mensagem Control Change via serial.
        """
        if self.serial_conn and self.serial_conn.is_open:
            status = 0xB0 | (CHANNEL & 0x0F)  # Control Change para o canal especificado
            message = bytes([status, control, value])
            try:
                self.serial_conn.write(message)
                print(f"Enviado CC: Control {hex(control)}, Valor {value}")
            except serial.SerialException as e:
                print(f"Erro ao enviar Control Change: {e}")
        else:
            print("Conexão serial não está aberta.")

    def send_note_on(self, note, velocity):
        """
        Envia uma mensagem Note On via serial.
        """
        if self.serial_conn and self.serial_conn.is_open:
            status = 0x90 | (CHANNEL & 0x0F)  # Note On para o canal especificado
            message = bytes([status, note, velocity])
            try:
                self.serial_conn.write(message)
                print(f"Enviado Note On: Nota {note}, Velocidade {velocity}")
                self.active_notes[note] = velocity
            except serial.SerialException as e:
                print(f"Erro ao enviar Note On: {e}")
        else:
            print("Conexão serial não está aberta.")

    def send_note_off(self, note, velocity):
        """
        Envia uma mensagem Note Off via serial.
        """
        if self.serial_conn and self.serial_conn.is_open:
            status = 0x80 | (CHANNEL & 0x0F)  # Note Off para o canal especificado
            message = bytes([status, note, velocity])
            try:
                self.serial_conn.write(message)
                print(f"Enviado Note Off: Nota {note}, Velocidade {velocity}")
                if note in self.active_notes:
                    del self.active_notes[note]
            except serial.SerialException as e:
                print(f"Erro ao enviar Note Off: {e}")
        else:
            print("Conexão serial não está aberta.")

    # ----------------------- Configuração de Persistência -----------------------
    def load_config(self):
        """
        Carrega as configurações do arquivo JSON.
        """
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                print("Configurações carregadas.")
                return config
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")
            return {}

    def save_config(self):
        """
        Salva as configurações no arquivo JSON.
        """
        config = {
            "midi_device": self.selected_midi_device.get(),
            "mappings": self.config_data.get("mappings", {})
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
                print("Configurações salvas.")
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    # ----------------------- Gerenciamento de Dispositivos MIDI -----------------------
    def change_midi_device(self, event=None):
        """
        Altera a porta MIDI de entrada quando o usuário seleciona um dispositivo diferente.
        """
        selected_port = self.selected_midi_device.get()
        # Fechar a porta MIDI atual
        if self.midi_input:
            self.midi_input.close()
            print(f"Porta MIDI '{self.midi_input.name}' fechada.")
            self.midi_input = None
        # Abrir a nova porta MIDI
        if selected_port in mido.get_input_names():
            try:
                self.midi_input = mido.open_input(selected_port, callback=self.handle_midi_message)
                print(f"Porta MIDI '{selected_port}' aberta.")
                # Salvar a seleção no config
                self.config_data["midi_device"] = selected_port
                self.save_config()
            except IOError as e:
                messagebox.showerror("Erro MIDI", f"Não foi possível abrir a porta MIDI '{selected_port}': {e}")
        else:
            messagebox.showwarning("Aviso MIDI", f"Porta MIDI '{selected_port}' não encontrada.")

    # ----------------------- Resolução de Mapeamentos -----------------------
    def handle_midi_message(self, message):
        """
        Callback para lidar com mensagens MIDI recebidas.
        """
        print(f"Mensagem MIDI recebida: {message}")
        # Processar a mensagem MIDI normalmente
        if message.type == "control_change":
            self.handle_midi_control_change(message.control, message.value, message.channel)
        elif message.type == "note_on":
            # Verificar se a nota está mapeada
            virtual_note = self.controller_to_virtual_map.get(message.note, None)
            if virtual_note:
                if message.velocity > 0:
                    self.press_virtual_key(virtual_note, message.velocity)
                else:
                    self.release_virtual_key(virtual_note, message.velocity)
        elif message.type == "note_off":
            # Verificar se a nota está mapeada
            virtual_note = self.controller_to_virtual_map.get(message.note, None)
            if virtual_note:
                self.release_virtual_key(virtual_note, message.velocity)

    def handle_midi_control_change(self, control, value, channel):
        """
        Atualiza o controle mapeado com o valor recebido via MIDI.
        """
        mappings = self.config_data.get("mappings", {})
        for control_id, midi_info in mappings.items():
            if midi_info["type"] == "control_change" and midi_info["control"] == control and midi_info["channel"] == channel:
                # Atualizar o controle correspondente no GUI
                if control_id.startswith("S"):  # Sliders
                    try:
                        slider_num = int(control_id[1:]) - 1
                        if 0 <= slider_num < len(self.vertical_sliders):
                            self.vertical_sliders[slider_num].set(value)
                    except:
                        pass
                elif control_id.startswith("H"):  # Slider Horizontal
                    if control_id == "H1":
                        self.hslider.set(value)
                elif control_id.startswith("R"):  # Knobs
                    try:
                        knob_num = int(control_id[1:]) - 1
                        if 0 <= knob_num < len(self.knob_vars):
                            self.knob_vars[knob_num].set_value(value)
                    except:
                        pass
                elif control_id in [btn["name"] for btn in BUTTON_MAPPINGS] + ["Sustain", "Back", "Stop", "Start", "Rec"]:
                    # Botões: definir estado
                    btn_name = control_id
                    state = value == 127
                    self.button_states[btn_name] = state
                    btn_widget = self.button_widgets.get(btn_name)
                    if btn_widget:
                        new_color = "green" if state else "grey"
                        btn_widget.config(bg=new_color)
                    self.display_text.set(f"{btn_name} -> {'127' if state else '0'}")

    def handle_midi_note_on(self, note, velocity, channel):
        """
        Atualiza o controle mapeado com a nota recebida via MIDI.
        """
        mappings = self.config_data.get("mappings", {})
        for control_id, midi_info in mappings.items():
            if midi_info["type"] == "note_on" and midi_info["note"] == note and midi_info["channel"] == channel:
                # Atualizar o controle correspondente no GUI
                if control_id.startswith("S"):  # Sliders
                    try:
                        slider_num = int(control_id[1:]) - 1
                        if 0 <= slider_num < len(self.vertical_sliders):
                            self.vertical_sliders[slider_num].set(velocity)
                    except:
                        pass
                elif control_id.startswith("H"):  # Slider Horizontal
                    if control_id == "H1":
                        self.hslider.set(velocity)
                elif control_id.startswith("R"):  # Knobs
                    try:
                        knob_num = int(control_id[1:]) - 1
                        if 0 <= knob_num < len(self.knob_vars):
                            self.knob_vars[knob_num].set_value(velocity)
                    except:
                        pass
                elif control_id in [btn["name"] for btn in BUTTON_MAPPINGS] + ["Sustain", "Back", "Stop", "Start", "Rec"]:
                    # Botões: definir estado
                    btn_name = control_id
                    state = velocity > 0
                    self.button_states[btn_name] = state
                    btn_widget = self.button_widgets.get(btn_name)
                    if btn_widget:
                        new_color = "green" if state else "grey"
                        btn_widget.config(bg=new_color)
                    self.display_text.set(f"{btn_name} -> {'127' if state else '0'}")

    # ----------------------- Funções para Pressionar/Solar Teclas Virtualmente -----------------------
    def press_virtual_key(self, virtual_note, velocity=100):
        """
        Pressiona a tecla virtual correspondente no GUI.
        """
        for i, rect_id in enumerate(self.white_key_ids):
            note = KEYBOARD_BASE_NOTE + i
            if note == virtual_note:
                self.kb_canvas.itemconfig(rect_id, fill="yellow")  # Cor para tecla branca pressionada
                self.send_note_on(virtual_note, velocity)
                self.display_text.set(f"Note {virtual_note} ON (Vel: {velocity})")
                break
        for i, rect_id in enumerate(self.black_key_ids):
            octave = i // 5
            position_in_octave = i % 5
            semitone_offsets = [1, 3, 6, 8, 10]  # Correspondente a C#, D#, F#, G#, A#
            note = KEYBOARD_BASE_NOTE + (octave * 12) + semitone_offsets[position_in_octave]
            if note == virtual_note:
                self.kb_canvas.itemconfig(rect_id, fill="red")  # Cor para tecla preta pressionada
                self.send_note_on(virtual_note, velocity)
                self.display_text.set(f"Note {virtual_note} ON (Vel: {velocity})")
                break

    def release_virtual_key(self, virtual_note, velocity=100):
        """
        Solta a tecla virtual correspondente no GUI.
        """
        for i, rect_id in enumerate(self.white_key_ids):
            note = KEYBOARD_BASE_NOTE + i
            if note == virtual_note:
                self.kb_canvas.itemconfig(rect_id, fill="white")  # Cor padrão para tecla branca
                self.send_note_off(virtual_note, velocity)
                self.display_text.set(f"Note {virtual_note} OFF (Vel: {velocity})")
                break
        for i, rect_id in enumerate(self.black_key_ids):
            octave = i // 5
            position_in_octave = i % 5
            semitone_offsets = [1, 3, 6, 8, 10]  # Correspondente a C#, D#, F#, G#, A#
            note = KEYBOARD_BASE_NOTE + (octave * 12) + semitone_offsets[position_in_octave]
            if note == virtual_note:
                self.kb_canvas.itemconfig(rect_id, fill="black")  # Cor padrão para tecla preta
                self.send_note_off(virtual_note, velocity)
                self.display_text.set(f"Note {virtual_note} OFF (Vel: {velocity})")
                break

    # ----------------------- Fechamento do Programa -----------------------
    def on_closing(self):
        if self.serial_conn and self.serial_conn.is_open:
            # Enviar Note Off para todas as notas ativas
            for note, velocity in list(self.active_notes.items()):
                self.send_note_off(note, velocity)
            self.serial_conn.close()
            print("Conexão serial fechada.")
        if self.midi_input:
            self.midi_input.close()
            print(f"Porta MIDI '{self.midi_input.name}' fechada.")
        self.save_config()
        self.destroy()

    # ----------------------- Função Principal -----------------------
    def run(self):
        # Iniciar a aplicação
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.mainloop()

if __name__ == "__main__":
    # Substitua '/dev/ttyUSB0' pela sua porta serial correta se necessário
    app = PCR300Virtual(serial_port='/dev/ttyUSB0', baudrate=31250)
    app.run()
