import tkinter as tk


class Login:

    def __init__(self, root):

        self.ventana = tk.Toplevel(root)

        self.ventana.title("Iniciar Sesión")
        self.ventana.geometry("500x400")
        self.ventana.resizable(False, False)

        tk.Label(
            self.ventana,
            text="INICIAR SESIÓN",
            font=("Arial", 22, "bold")
        ).pack(pady=30)

        tk.Label(self.ventana, text="Usuario").pack()

        self.usuario = tk.Entry(
            self.ventana,
            width=30
        )
        self.usuario.pack(pady=10)

        tk.Label(self.ventana, text="Contraseña").pack()

        self.password = tk.Entry(
            self.ventana,
            show="*",
            width=30
        )
        self.password.pack(pady=10)

        tk.Button(
            self.ventana,
            text="Ingresar",
            width=20
        ).pack(pady=30)