import tkinter as tk


class Registro:

    def __init__(self, root):

        self.ventana = tk.Toplevel(root)

        self.ventana.title("Registro")
        self.ventana.geometry("550x500")

        tk.Label(
            self.ventana,
            text="REGISTRO DE USUARIO",
            font=("Arial", 22, "bold")
        ).pack(pady=20)

        campos = [
            "Nombre",
            "Usuario",
            "Correo",
            "País",
            "Contraseña"
        ]

        for campo in campos:

            tk.Label(
                self.ventana,
                text=campo
            ).pack()

            tk.Entry(
                self.ventana,
                width=40
            ).pack(pady=5)

        tk.Button(
            self.ventana,
            text="Registrar",
            width=20
        ).pack(pady=20)