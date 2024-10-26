import psutil
import pymem
import struct
import ctypes
import ctypes.wintypes
from ctypes import windll, Structure, c_uint, c_uint64, sizeof, byref
from ctypes.wintypes import DWORD, HANDLE, BOOL
import tkinter as tk
import threading

# Constants
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

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
            if all(read_bytes[i] == pattern_bytes[i] or mask[i] == '?' for i in range(len(pattern_bytes))):
                return current_address
        except:
            pass
        current_address += 1
    return None

def read_memory(process_handle, address):
    buffer = ctypes.c_uint32()
    bytes_read = ctypes.c_size_t()
    if windll.kernel32.ReadProcessMemory(process_handle, ctypes.c_void_p(address), byref(buffer), sizeof(buffer), byref(bytes_read)):
        return buffer.value
    else:
        return None

def update_value(pm, target_address, label):
    try:
        target_value = read_memory(pm.process_handle, target_address)
        if target_value is not None:
            label.config(text=f"Morts : {target_value}")
        else:
            label.config(text="Morts : Impossible de lire la valeur")
    except Exception as e:
        label.config(text=f"Morts : Erreur : {str(e)}")

def display_value_in_window():
    root = tk.Tk()
    root.title("Morts :")
    label = tk.Label(root, text="Calcul du nombre de morts...", font=("Helvetica", 16))
    label.pack(padx=20, pady=20)

    def update(pm, target_address):
        update_value(pm, target_address, label)
        root.after(1000, update, pm, target_address)  # Mettre à jour toutes les secondes

    def start_update(pm, target_address):
        update(pm, target_address)  # Première mise à jour immédiate

    return root, label, start_update

def search_and_update(root, label, start_update, process_name):
    if not is_process_running(process_name):
        label.config(text=f"Le processus {process_name} n'est pas en cours d'exécution.")
        return

    print(f"Le processus {process_name} est en cours d'exécution. Recherche de l'adresse...")
    pm = pymem.Pymem(process_name)
    module_base = find_module_base(pm, process_name)

    if not module_base:
        label.config(text="Impossible de trouver la base du module.")
        return

    print(f"Base du module trouvée : {hex(module_base)}")

    # Pattern AOB
    aob_pattern = "48 8B 05 ?? ?? ?? ?? 48 85 C0 74 05 48 8B 40 58 C3 C3"

    # Recherche du pattern dans le module
    result_address = pattern_scan(pm, aob_pattern, module_base, module_base + 0x1000000)  # Ajustez la plage de recherche si nécessaire

    if not result_address:
        label.config(text="Aucune adresse correspondante trouvée.")
        return

    print(f"Adresse du pattern trouvée : {hex(result_address)}")

    # Lecture de l'instruction pour obtenir le déplacement
    instruction_bytes = pm.read_bytes(result_address, 7)
    displacement = struct.unpack("<I", instruction_bytes[3:])[0]

    # Calcul de l'adresse finale
    final_address = result_address + 7 + displacement
    print(f"Adresse finale calculée : {hex(final_address)}")

    # Lecture de la valeur à l'adresse finale (qui est un pointeur)
    pointer_value = pm.read_longlong(final_address)
    print(f"Valeur du pointeur : {hex(pointer_value)}")

    # Ajout du décalage de 0x94 à l'adresse pointée
    target_address = pointer_value + 0x94
    print(f"Adresse cible après décalage : {hex(target_address)}")

    # Mettre à jour l'interface avec la valeur finale et continuer à rafraîchir la valeur toutes les secondes
    start_update(pm, target_address)

def main():
    process_name = "eldenring.exe"

    # Afficher l'interface avec le message "Calcul du nombre de morts..."
    root, label, start_update = display_value_in_window()

    # Lancer la recherche en arrière-plan
    search_thread = threading.Thread(target=search_and_update, args=(root, label, start_update, process_name))
    search_thread.start()

    # Lancer la boucle principale de tkinter
    root.mainloop()

if __name__ == "__main__":
    main()
