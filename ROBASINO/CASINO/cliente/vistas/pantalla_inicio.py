import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from pathlib import Path
from vistas.login import Login
from vistas.registro import Registro
from vistas.creditos import Creditos
from vistas.reglas import Reglas


class PantallaInicio:

    def __init__(self, root):

        self.root = root

        self.root.title("UNITRÓPICO CASINO")
        self.root.geometry("1366x768")
        self.root.resizable(False, False)

        self.base_path = Path(__file__).parent.parent

        self.crear_fondo()
        self.crear_logo()
        self.crear_botones_superiores()
        self.crear_botones_principales()

    # =====================================================
    # FONDO
    # =====================================================

    def crear_fondo(self):

        ruta_fondo = self.base_path / "recursos" / "fondo_principal.png"

        fondo = Image.open(ruta_fondo)
        fondo = fondo.resize((1366, 768))

        self.img_fondo = ImageTk.PhotoImage(fondo)

        self.canvas = tk.Canvas(
            self.root,
            width=1366,
            height=768,
            highlightthickness=0
        )

        self.canvas.pack(fill="both", expand=True)

        self.canvas.create_image(
            0,
            0,
            image=self.img_fondo,
            anchor="nw"
        )

    # =====================================================
    # LOGO
    # =====================================================

    def crear_logo(self):

        ruta_logo = self.base_path / "recursos" / "logo.png"

        logo = Image.open(ruta_logo)

        logo = logo.resize((450, 450))

        self.img_logo = ImageTk.PhotoImage(logo)

        self.canvas.create_image(
            683,
            220,
            image=self.img_logo
        )

    # =====================================================
    # BOTONES SUPERIORES
    # =====================================================

    def crear_botones_superiores(self):

        btn_creditos = tk.Button(
            self.root,
            text="©",
            font=("Arial", 20, "bold"),
            width=3,
            bg="#001a00",
            fg="#66ff66",
            bd=2,
            command=self.abrir_creditos,
            cursor="hand2"
        )

        btn_creditos.place(
            x=40,
            y=40
        )

        btn_reglas = tk.Button(
            self.root,
            text="?",
            font=("Arial", 20, "bold"),
            width=3,
            bg="#001a00",
            fg="#66ff66",
            bd=2,
            command=self.abrir_reglas,
            cursor="hand2"
        )

        btn_reglas.place(
            x=1270,
            y=40
        )

    # =====================================================
    # BOTONES CENTRALES
    # =====================================================

    def crear_botones_principales(self):

        btn_login = tk.Button(
            self.root,
            text="INICIAR SESIÓN",
            font=("Arial", 18, "bold"),
            width=20,
            bg="#003300",
            fg="#66ff66",
            activebackground="#004d00",
            activeforeground="white",
            cursor="hand2",
            command=self.abrir_login
        )

        btn_login.place(
            x=540,
            y=470
        )

        btn_registro = tk.Button(
            self.root,
            text="REGISTRARSE",
            font=("Arial", 18, "bold"),
            width=20,
            bg="#003300",
            fg="#66ff66",
            activebackground="#004d00",
            activeforeground="white",
            cursor="hand2",
            command=self.abrir_registro
        )

        btn_registro.place(
            x=540,
            y=550
        )

    # =====================================================
    # EVENTOS
    # =====================================================

    def abrir_login(self):
        Login(self.root)


    def abrir_registro(self):
        Registro(self.root)


    def abrir_creditos(self):
        Creditos(self.root)


    def abrir_reglas(self):
        Reglas(self.root)