import tkinter as tk
from tkinter import ttk
import mido
from mido import Message
import math

# --------------------- CONFIGURAÇÃO E MAPEAMENTO ---------------------
# Mapeamento ajustado conforme z_config.ino

# Definições de Control Change (CC) conforme z_config.ino
# Sliders (S1..S9) mapeados para CC 0x11..0x18 e CC 0x12 para S9
SLIDER_VERTICAL_CC_BASE = 0x11  # S1 -> 0x11, S2 -> 0x12, ..., S8 -> 0x18
S9_CC = 0x12                    # S9

# Slider horizontal (H1) mapeado para CC 0x13
SLIDER_HORIZONTAL_CC = 0x13

# Knobs (R1..R8) mapeados para CC 0x10..0x17 e R9 para CC 0x12
KNOB_CC_BASE = 0x10             # R1 -> 0x10, R2 -> 0x11, ..., R8 -> 0x17
R9_CC = 0x12                     # R9

# Botões mapeados conforme z_config.ino
# Sustain -> CC 0x40
# Transport buttons (back, stop, start, rec) -> CC 0x52
# Upper row A1..A8 -> CC 0x50, A9 -> CC 0x53
# Lower row B1..B8 -> CC 0x51, B9 -> CC 0x53
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

# Definir o canal MIDI (0 = Canal 1)
CHANNEL = 0

# Ajustes do teclado virtual
KEYBOARD_BASE_NOTE = 60  # C3 = 60
WHITE_KEYS = 14          # Quantas brancas (ajuste se quiser mais)
BLACK_KEY_PATTERNS = [1, 3, 6, 8, 10]  # semitons pretos na oitava

# ---------------------------------------------------------------------

class PCR300Virtual(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PCR-300 Virtual - Python Demo")
        self.geometry("1600x800")  # Ajustado para acomodar mais botões
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
          - 8 sliders verticais (S1..S8),  
          - 1 slider vertical adicional (S9),
          - 1 slider horizontal (H1),  
          - 9 knobs verticais (R1..R9),  
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

        # ================== KNOBS (R1..R9) ==================
        knobs_frame = tk.Frame(top_frame, bg="#333", bd=2, relief=tk.RIDGE)
        knobs_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(knobs_frame, text="Rotary Knobs (R1..R9)", bg="#333", fg="white").pack()
        self.knob_vars = []
        for i in range(9):
            if i < 8:
                cc_num = KNOB_CC_BASE + i  # 0x10..0x17
            else:
                cc_num = R9_CC  # 0x12 para R9
            kv = tk.Scale(
                knobs_frame, from_=0, to=127, orient=tk.HORIZONTAL, length=80,
                command=lambda val, cc=cc_num: self.on_knob_change(cc, val)
            )
            kv.pack(padx=3, pady=2)
            kv.set(64)
            self.knob_vars.append(kv)

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
    #     KNOBS (R1..R9) => Enviar ControlChange
    # ---------------------------------------------------
    def on_knob_change(self, cc_num, value):
        """
        Envia CC para knobs.
        """
        val_int = int(float(value))
        self.send_cc(CHANNEL, cc_num, val_int)
        # Determinar qual knob foi ajustado
        if cc_num != R9_CC:
            knob_number = cc_num - KNOB_CC_BASE + 1
        else:
            knob_number = 9
        self.display_text.set(f"R{knob_number}={val_int}")

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
    #     TECLADO VIRTUAL => Notas On/Off
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
                # Evita desenhar teclas pretas além do número de teclas brancas
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
        self.kb_canvas.tag_bind("white_key", "<Button-1>", self.on_key_click)
        self.kb_canvas.tag_bind("black_key", "<Button-1>", self.on_key_click)

    def on_key_click(self, event):
        """
        Envia NoteOn/NoteOff ao clicar numa tecla.
        """
        item_id = self.kb_canvas.find_closest(event.x, event.y)[0]
        if item_id in self.white_key_ids:
            i = self.white_key_ids.index(item_id)
            note = KEYBOARD_BASE_NOTE + i
            color_pressed = "yellow"
            default_color = "white"
        elif item_id in self.black_key_ids:
            i = self.black_key_ids.index(item_id)
            # Calcula a nota com base na posição das teclas pretas
            # As teclas pretas correspondem aos semitons entre as brancas
            # Exemplo: C# = C + 1, D# = D + 3, etc.
            # Precisamos ajustar o cálculo conforme o padrão de teclas pretas
            octave = i // 5
            position_in_octave = i % 5
            semitone_offsets = [1, 3, 6, 8, 10]  # Correspondente a C#, D#, F#, G#, A#
            note = KEYBOARD_BASE_NOTE + (octave * 12) + semitone_offsets[position_in_octave]
            color_pressed = "red"
            default_color = "black"
        else:
            return

        # Enviar Note On
        self.send_note_on(CHANNEL, note, velocity=100)
        self.display_text.set(f"Note {note} ON")

        # Muda cor
        self.kb_canvas.itemconfig(item_id, fill=color_pressed)
        # Programar para enviar Note Off depois de 200ms
        self.after(200, lambda: self.release_note(item_id, note, default_color))

    def release_note(self, key_id, note, default_color):
        # Volta cor original
        self.kb_canvas.itemconfig(key_id, fill=default_color)
        # Envia Note Off
        self.send_note_off(CHANNEL, note)
        self.display_text.set(f"Note {note} OFF")

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
