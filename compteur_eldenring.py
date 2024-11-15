import psutil
import pymem
import struct
import ctypes
import math
import tkinter as tk
from tkinter import ttk
import threading
from PIL import Image, ImageTk

class CircularCounter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("")
        self.setup_window()
        self.create_widgets()

    def setup_window(self):
        # Configuration de la fenêtre principale avec des dimensions réduites
        self.width = 200  # Réduit de 300 à 200
        self.height = 200  # Réduit de 300 à 200
        self.center_x = self.width // 2
        self.center_y = self.height // 2
        self.radius = 80  # Réduit de 120 à 80

        self.root.geometry(f"{self.width}x{self.height}")
        self.root.configure(bg='grey')
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.root.attributes('-transparentcolor', 'grey')

    def create_widgets(self):
        # Création du canvas principal
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height,
                              bg='grey', highlightthickness=0)
        self.canvas.pack()

        # Réduire le rayon du cercle principal
        self.circle_radius = 60  # Réduit de 80 à 60

        # Dessiner le cercle principal
        self.canvas.create_oval(
            self.center_x - self.circle_radius,
            self.center_y - self.circle_radius,
            self.center_x + self.circle_radius,
            self.center_y + self.circle_radius,
            fill='black', outline='red'
        )

        # Label pour le compteur avec taille de police ajustée
        self.counter_label = tk.Label(
            self.root,
            text="Le jeu n'est\npas lancé",
            font=("Helvetica", 12, "bold"),  # Taille de police réduite de 14 à 12
            fg='white',
            bg='black',
            justify='center'
        )
        self.counter_label.place(x=self.center_x, y=self.center_y, anchor='center')

        # Boutons de contrôle
        self.create_control_buttons()

        # Configuration des événements de déplacement
        self.canvas.bind('<Button-1>', self.start_move)
        self.canvas.bind('<ButtonRelease-1>', self.stop_move)
        self.canvas.bind('<B1-Motion>', self.do_move)

    def create_control_buttons(self):
        # Calcul des positions pour les boutons
        close_x = self.center_x + int(self.radius * math.cos(-math.pi/4))
        close_y = self.center_y + int(self.radius * math.sin(-math.pi/4))

        # Bouton de fermeture
        self.close_button = tk.Label(
            self.root,
            text="X",
            font=("Helvetica", 10, "bold"),  # Taille de police réduite de 12 à 10
            fg='red',
            bg='black',
            width=2
        )
        self.close_button.place(x=close_x, y=close_y, anchor='center')
        self.close_button.bind('<Button-1>', lambda e: self.root.destroy())

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def update_counter(self, value):
        # Formater le texte pour qu'il soit centré et limité à 2 mots par ligne
        words = value.split()
        formatted_text = ""
        for i in range(0, len(words), 2):
            formatted_text += " ".join(words[i:i+2]) + "\n"
        formatted_text = formatted_text.strip()

        self.counter_label.config(text=formatted_text)
        self.adjust_circle_size()

    def adjust_circle_size(self):
        # Ajuster la taille du cercle en fonction de la taille du texte
        text_width = self.counter_label.winfo_width()
        text_height = self.counter_label.winfo_height()
        padding = 10
        new_radius = max(text_width, text_height) // 2 + padding
        self.circle_radius = new_radius
        self.canvas.coords(1,
            self.center_x - self.circle_radius,
            self.center_y - self.circle_radius,
            self.center_x + self.circle_radius,
            self.center_y + self.circle_radius
        )

def read_memory(process_handle, address):
    buffer = ctypes.c_uint32()
    bytes_read = ctypes.c_size_t()
    if ctypes.windll.kernel32.ReadProcessMemory(
            process_handle,
            ctypes.c_void_p(address),
            ctypes.byref(buffer),
            ctypes.sizeof(buffer),
            ctypes.byref(bytes_read)):
        return buffer.value
    return None

def is_process_running(process_name):
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() == process_name.lower():
            return True
    return False

def find_module_base(pm, module_name):
    for module in pm.list_modules():
        if module.name.lower() == module_name.lower():
            return module.lpBaseOfDll
    return None

def pattern_scan(pm, pattern, start_address, end_address):
    pattern_bytes = bytes([int(x, 16) if x != '??' else 0 for x in pattern.split()])
    mask = ''.join(['x' if x != '??' else '?' for x in pattern.split()])

    current_address = start_address
    while current_address < end_address:
        try:
            read_bytes = pm.read_bytes(current_address, len(pattern_bytes))
            if all(read_bytes[i] == pattern_bytes[i] or mask[i] == '?'
                  for i in range(len(pattern_bytes))):
                return current_address
        except:
            pass
        current_address += 1
    return None

def update_value(pm, target_address, counter_app):
    try:
        target_value = read_memory(pm.process_handle, target_address)
        if target_value is not None:
            counter_app.update_counter(f"Morts : {target_value}")
        else:
            counter_app.update_counter("Erreur de lecture")
    except Exception as e:
        counter_app.update_counter("Erreur de lecture")

def search_and_update(counter_app, process_name):
    if not is_process_running(process_name):
        counter_app.update_counter("Le jeu n'est\npas lancé")
        return

    counter_app.update_counter("Calcul en\ncours...")
    pm = pymem.Pymem(process_name)
    module_base = find_module_base(pm, process_name)

    if not module_base:
        counter_app.update_counter("Erreur de\nlecture")
        return

    aob_pattern = "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 05 48 8B 40 58 C3 C3"
    result_address = pattern_scan(pm, aob_pattern, module_base, module_base + 0x1000000)

    if not result_address:
        counter_app.update_counter("Erreur de\nlecture")
        return

    instruction_bytes = pm.read_bytes(result_address, 7)
    displacement = struct.unpack("<I", instruction_bytes[3:])[0]
    final_address = result_address + 7 + displacement
    pointer_value = pm.read_longlong(final_address)
    target_address = pointer_value + 0x94

    def update():
        update_value(pm, target_address, counter_app)
        counter_app.root.after(1000, update)

    update()

def main():
    process_name = "eldenring.exe"
    app = CircularCounter()

    def check_process():
        if not is_process_running(process_name):
            app.update_counter("Le jeu n'est\npas lancé")
            app.root.after(1000, check_process)
        else:
            search_thread = threading.Thread(target=search_and_update,
                                          args=(app, process_name))
            search_thread.start()

    check_process()
    app.root.mainloop()

if __name__ == "__main__":
    main()
