import tkinter as tk
from PIL import Image, ImageTk
import os


class MenuPrincipal:

    def __init__(self, root):

        self.root = root

        self.root.title("ROBASINO")
        self.root.geometry("1366x768")
        self.root.resizable(False, False)

        # Ruta base: cliente/
        self.ruta_base = os.path.dirname(os.path.dirname(__file__))

        self.crear_fondo()
        self.crear_panel_perfil()
        self.crear_panel_configuracion()
        self.crear_panel_central()
        self.crear_barra_juegos()

    # =====================================================
    # FONDO
    # =====================================================

    def crear_fondo(self):

        self.canvas = tk.Canvas(
            self.root,
            width=1366,
            height=768,
            highlightthickness=0
        )

        self.canvas.place(x=0, y=0)

        ruta_fondo = os.path.join(
            self.ruta_base,
            "recursos",
            "fondo_principal.png"
        )

        print("Cargando fondo:", ruta_fondo)

        fondo = Image.open(ruta_fondo)
        fondo = fondo.resize((1366, 768))

        self.img_fondo = ImageTk.PhotoImage(fondo)

        self.canvas.create_image(
            0,
            0,
            image=self.img_fondo,
            anchor="nw"
        )

    # =====================================================
    # PERFIL
    # =====================================================

    def crear_panel_perfil(self):

        self.frame_perfil = tk.Frame(
            self.root,
            bg="#001a00",
            bd=3,
            relief="ridge"
        )

        self.frame_perfil.place(
            x=20,
            y=20,
            width=350,
            height=90
        )

        tk.Label(
            self.frame_perfil,
            text="👤",
            font=("Arial", 24),
            bg="#001a00",
            fg="#66ff66"
        ).place(x=15, y=20)

        tk.Label(
            self.frame_perfil,
            text="Nombre: Invitado",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11)
        ).place(x=70, y=10)

        tk.Label(
            self.frame_perfil,
            text="Nivel: 1",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11)
        ).place(x=70, y=35)

        tk.Label(
            self.frame_perfil,
            text="País: Colombia",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11)
        ).place(x=70, y=60)

    # =====================================================
    # CONFIGURACIÓN
    # =====================================================

    def crear_panel_configuracion(self):

        self.frame_config = tk.Frame(
            self.root,
            bg="#001a00",
            bd=3,
            relief="ridge"
        )

        self.frame_config.place(
            x=1180,
            y=20,
            width=160,
            height=90
        )

        tk.Button(
            self.frame_config,
            text="⚙",
            font=("Arial", 22),
            bg="#001a00",
            fg="#66ff66",
            bd=0,
            cursor="hand2"
        ).pack(side="left", padx=20)

        tk.Label(
            self.frame_config,
            text="🟢",
            font=("Arial", 18),
            bg="#001a00"
        ).pack(side="right", padx=20)

    # =====================================================
    # PANEL CENTRAL
    # =====================================================

    def crear_panel_central(self):

        self.frame_info = tk.Frame(
            self.root,
            bg="#001a00",
            bd=3,
            relief="ridge"
        )

        self.frame_info.place(
            x=420,
            y=150,
            width=530,
            height=90
        )

        tk.Label(
            self.frame_info,
            text="Juegos realizados: 0",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 14, "bold")
        ).place(x=20, y=15)

        tk.Label(
            self.frame_info,
            text="Créditos: $100.000",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 14, "bold")
        ).place(x=20, y=50)

    # =====================================================
    # BARRA INFERIOR DE JUEGOS
    # =====================================================

    def crear_barra_juegos(self):

        botones = [
            ("blackjack.png", self.abrir_blackjack),
            ("ruleta.png", self.abrir_ruleta),
            ("info.png", self.abrir_info),
            ("tragamonedas.png", self.abrir_tragamonedas),
            ("craps.png", self.abrir_craps)
        ]

        self.imagenes_botones = []

        x = 60

        for archivo, comando in botones:

            ruta_imagen = os.path.join(
                self.ruta_base,
                "recursos",
                archivo
            )

            print("Cargando:", ruta_imagen)

            imagen = Image.open(ruta_imagen)
            imagen = imagen.resize((180, 180))

            foto = ImageTk.PhotoImage(imagen)

            self.imagenes_botones.append(foto)

            boton = tk.Button(
                self.root,
                image=foto,
                command=comando,
                bd=0,
                cursor="hand2",
                bg="black",
                activebackground="black"
            )

            boton.place(
                x=x,
                y=520
            )

            x += 250

    # =====================================================
    # EVENTOS
    # =====================================================

    def abrir_blackjack(self):
        print("Abrir Blackjack")

    def abrir_ruleta(self):
        print("Abrir Ruleta")

    def abrir_info(self):
        print("Abrir Información")

    def abrir_tragamonedas(self):
        print("Abrir Tragamonedas")

    def abrir_craps(self):
        print("Abrir Craps")