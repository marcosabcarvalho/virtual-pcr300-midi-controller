import tkinter as tk
from tkinter import ttk
import mido
from mido import Message
import math
import time

# Definições de Control Change (CC) conforme z_config.ino
SLIDER_VERTICAL_CC_BASE = 0x11  # S1 -> 0x11, S2 -> 0x12, ..., S8 -> 0x18
S9_CC = 0x12                    # S9

SLIDER_HORIZONTAL_CC = 0x13

KNOB_CC_BASE = 0x10             # R1 -> 0x10, R2 -> 0x11, ..., R8 -> 0x17
R9_CC = 0x12                     # R9

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

CHANNEL = 0

KEYBOARD_BASE_NOTE = 60  # C3 = 60
WHITE_KEYS = 14          # Quantas brancas (ajuste se quiser mais)
BLACK_KEY_PATTERNS = [1, 3, 6, 8, 10]  # semitons pretos na oitava

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
        
        # Atualizar o indicador com o valor inicial
        self.update_indicator()
    
    def value_to_angle(self, value):
        # Mapeia o valor para um ângulo (em radianos)
        # Vamos definir que min_val corresponde a 135 graus e max_val a -135 graus
        # Isso cria uma rotação de 270 graus no total
        angle_deg = 135 - ((value - self.min_val) / (self.max_val - self.min_val)) * 270
        angle_rad = math.radians(angle_deg)
        return angle_rad
    
    def update_indicator(self):
        angle = self.value_to_angle(self.value)
        x = self.center + self.indicator_length * math.cos(angle)
        y = self.center - self.indicator_length * math.sin(angle)
        self.coords(self.indicator, self.center, self.center, x, y)
    
    def set_value(self, value):
        # Limitar o valor dentro do intervalo
        value = max(self.min_val, min(self.max_val, value))
        if value != self.value:
            self.value = value
            self.update_indicator()
            if self.command:
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
        # Definir intervalos de tempo mínimo e máximo
        min_duration = 0.05  # 50 ms para máxima velocidade
        max_duration = 0.5   # 500 ms para mínima velocidade
        if duration < min_duration:
            duration = min_duration
        if duration > max_duration:
            duration = max_duration
        # Inverter o mapeamento: menor duração -> maior velocidade
        velocity = int(127 * (1 - (duration - min_duration) / (max_duration - min_duration)))
        velocity = max(1, min(127, velocity))  # Garantir dentro do intervalo
        
        # Enviar Note Off com a velocidade capturada
        # Aqui, precisamos ter uma referência ao ID da tecla para liberar corretamente
        # Para simplificação, isso será tratado na função on_key_release
        if self.command:
            self.command(self.value, velocity)
    
    def bind_release(self, func):
        self.bind("<ButtonRelease-1>", func)

class PCR300Virtual(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PCR-300 Virtual - Python Demo")
        self.geometry("2000x900")  # Ajustado para acomodar mais controles
        self.resizable(False, False)

        # Nome do cliente ALSA que aparecerá no aconnect
        self.midi_client_name = "PCR300Virtual"

        # Abre a saída MIDI ALSA (vai aparecer em aconnect)
        try:
            available_ports = mido.get_output_names()
            print("Portas MIDI disponíveis:", available_ports)

            # Cria uma porta MIDI virtual
            self.midi_out = mido.open_output(
                self.midi_client_name,
                virtual=True
            )
            print(f"Conectado à saída MIDI virtual '{self.midi_client_name}'.")
        except Exception as e:
            print("Erro ao abrir saída MIDI:", e)
            self.midi_out = None

        # Variável de exibição (display “LCD”)
        self.display_text = tk.StringVar(value="PCR-300")
        self.create_main_interface()

    def create_main_interface(self):
        """
        Monta toda a interface:  
          - 9 sliders verticais (S1..S9),  
          - 1 slider horizontal (H1),  
          - 18 knobs circulares (R1..R18) organizados em duas linhas,
          - 23 botões (sustain, transport, A1..A9, B1..B9),  
          - teclado virtual.  
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
            # Define uma referência para a tecla para usar no release
            knob = CircularKnob(
                self.knob_rows[i // 9], size=60, min_val=0, max_val=127,
                initial_val=64, command=lambda val, cc=cc_num: self.on_knob_change(cc, val)
            )
            knob.pack(side=tk.LEFT, padx=5, pady=5)
            knob.bind_release(lambda event, cc=cc_num, knob=knob: self.on_knob_release(event, cc, knob))
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

    # ---------------------------------------------------
    #     SLIDERS VERTICAIS => Enviar ControlChange
    # ---------------------------------------------------
    def on_vertical_slider(self, cc_num, value):
        """
        Envia CC para sliders verticais.
        """
        val_int = int(float(value))
        self.send_cc(CHANNEL, cc_num, val_int)
        # Atualizar display para indicar qual slider foi ajustado
        if cc_num == S9_CC:
            slider_number = 9
        else:
            slider_number = cc_num - SLIDER_VERTICAL_CC_BASE + 1
        self.display_text.set(f"S{slider_number}={val_int}")

    # ---------------------------------------------------
    #     SLIDER HORIZONTAL (H1) => Enviar ControlChange
    # ---------------------------------------------------
    def on_horizontal_slider(self, value):
        val_int = int(float(value))
        self.send_cc(CHANNEL, SLIDER_HORIZONTAL_CC, val_int)
        self.display_text.set(f"H1={val_int}")

    # ---------------------------------------------------
    #     KNOBS (R1..R18) => Enviar ControlChange
    # ---------------------------------------------------
    def on_knob_change(self, cc_num, value):
        """
        Envia CC para knobs.
        """
        val_int = int(float(value))
        self.send_cc(CHANNEL, cc_num, val_int)
        # Determinar qual knob foi ajustado
        knob_number = cc_num - KNOB_CC_BASE + 1
        self.display_text.set(f"R{knob_number}={val_int}")

    def on_knob_release(self, event, cc_num, knob):
        """
        Opcional: Implementar ações ao liberar o knob, se necessário.
        """
        pass  # Atualmente, não precisamos fazer nada aqui

    # ---------------------------------------------------
    #     BOTÕES => Enviar CC 127 ao pressionar e 0 ao soltar
    # ---------------------------------------------------
    def on_button_press(self, btn_name, cc_num):
        """
        Envia CC correspondente ao botão pressionado.
        Toggle: envia 127 quando pressionado, 0 quando solto.
        """
        # Alterna o estado do botão
        self.button_states[btn_name] = not self.button_states[btn_name]
        val = 127 if self.button_states[btn_name] else 0
        self.send_cc(CHANNEL, cc_num, val)
        self.display_text.set(f"{btn_name} -> {val}")
        # Atualiza a cor do botão para refletir o estado
        btn_widget = self.button_widgets.get(btn_name)
        if btn_widget:
            new_color = "green" if self.button_states[btn_name] else "grey"
            btn_widget.config(bg=new_color)

    # ---------------------------------------------------
    #     TECLADO VIRTUAL => Notas On/Off com Dinâmica
    # ---------------------------------------------------
    def create_virtual_keyboard(self, parent):
        """
        Cria um teclado virtual mais realista com teclas brancas e pretas.
        """
        key_width = 30
        key_height = 150
        black_key_width = key_width * 0.6
        black_key_height = key_height * 0.6
        num_octaves = WHITE_KEYS // 7
        remaining_keys = WHITE_KEYS % 7

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
            for offset in [1, 2, 4, 5, 6]:  # Posição relativa das teclas pretas
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
        if duration < min_duration:
            duration = min_duration
        if duration > max_duration:
            duration = max_duration

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

        # Enviar Note Off com a velocidade capturada
        self.send_note_off(CHANNEL, note, velocity)
        self.display_text.set(f"Note {note} OFF")

        # Volta a cor original da tecla
        self.kb_canvas.itemconfig(item_id, fill=default_color)

    # ----------------------- Funções MIDI -----------------------
    def send_cc(self, channel, cc_num, value):
        """
        Envia uma mensagem ControlChange no canal especificado.
        """
        if self.midi_out:
            msg = Message('control_change', channel=channel, control=cc_num, value=value)
            self.midi_out.send(msg)
            print(f"Enviado CC: Canal {channel+1}, Control {hex(cc_num)}, Valor {value}")

    def send_note_on(self, channel, note, velocity=100):
        if self.midi_out:
            msg = Message('note_on', channel=channel, note=note, velocity=velocity)
            self.midi_out.send(msg)
            print(f"Enviado Note On: Canal {channel+1}, Nota {note}, Velocidade {velocity}")

    def send_note_off(self, channel, note, velocity=0):
        if self.midi_out:
            msg = Message('note_off', channel=channel, note=note, velocity=velocity)
            self.midi_out.send(msg)
            print(f"Enviado Note Off: Canal {channel+1}, Nota {note}, Velocidade {velocity}")

    def on_closing(self):
        if self.midi_out:
            self.midi_out.close()
            print("Saída MIDI fechada.")
        self.destroy()

# --------------------------------------------------------------------
if __name__ == "__main__":
    app = PCR300Virtual()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
