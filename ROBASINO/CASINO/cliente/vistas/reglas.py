import tkinter as tk


class Reglas:

    def __init__(self, root):

        self.ventana = tk.Toplevel(root)

        self.ventana.title("Reglas")
        self.ventana.geometry("900x600")

        texto = """
REGLAS GENERALES DE ROBASINO

BLACKJACK
------------
Objetivo: llegar a 21 puntos sin pasarse.

RULETA
------------
Apostar a número, color o rango.

CRAPS
------------
Apostar al resultado de los dados.

TRAGAMONEDAS
------------
Obtener combinaciones ganadoras.

REGLAS GENERALES
--------------------
- Cada jugador posee créditos.
- Las apuestas se descuentan antes de jugar.
- Los premios se acreditan automáticamente.
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