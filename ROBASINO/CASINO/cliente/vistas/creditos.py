import tkinter as tk


class Creditos:

    def __init__(self, root):

        self.ventana = tk.Toplevel(root)

        self.ventana.title("Créditos")
        self.ventana.geometry("700x500")

        texto = """
UNITRÓPICO CASINO

Proyecto académico desarrollado para
Ingeniería de Sistemas.

Autores:

• Juan David Acero Urbano
• Johan David Rodriguez Perez
• Harold Steven Alfonso Perez

Docente:
• Cesar Dayan Martelo Varela

Tecnologías:

• Python
• Tkinter
• SQLite
• Socket TCP
• JSON

Universidad Internacional del Trópico Americano
UNITRÓPICO
        """

        tk.Label(
            self.ventana,
            text=texto,
            justify="left",
            font=("Arial", 12)
        ).pack(
            padx=20,
            pady=20
        )