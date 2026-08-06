import tkinter as tk
from PIL import Image, ImageTk
from vistas.ruleta import Ruleta
from vistas.casino_com import Jugador
from vistas.tragamonedas import vistaTragamonedas
from vistas.client import BlackjackClient
import os

# Tamaño "de diseño" de la ventana (con el que están calculadas todas las
# posiciones fijas del menú) y límites entre los que se puede redimensionar
# sin dejar de tener sentido esa disposición.
ANCHO_REF = 1366
ALTO_REF = 768
ESCALA_MIN = 0.75
ESCALA_MAX = 1.3
RETARDO_RESIZE_MS = 120  # debounce: no redibujar en cada pixel de arrastre


class MenuPrincipal:

    def __init__(self, root, jugador, conexion):

        self.root = root
        self.jugador = jugador
        self.conexion = conexion  # socket ya autenticado, reutilizado por todos los juegos

        self.root.title("ROBASINO")
        self.root.geometry(f"{ANCHO_REF}x{ALTO_REF}")

        # Ventana normal: se puede maximizar y redimensionar como cualquier
        # app de escritorio, entre estos límites y siempre en proporción
        # 1366:768 (wm_aspect la mantiene fija incluso durante el arrastre).
        self.root.resizable(True, True)
        self.root.minsize(int(ANCHO_REF * ESCALA_MIN), int(ALTO_REF * ESCALA_MIN))
        self.root.maxsize(int(ANCHO_REF * ESCALA_MAX), int(ALTO_REF * ESCALA_MAX))
        self.root.wm_aspect(ANCHO_REF, ALTO_REF, ANCHO_REF, ALTO_REF)

        # Ruta base: cliente/
        self.ruta_base = os.path.dirname(os.path.dirname(__file__))

        self._escala = 1.0
        self._resize_after_id = None

        self.crear_fondo()
        self.crear_panel_perfil()
        self.crear_panel_configuracion()
        self.crear_panel_central()
        self.crear_barra_juegos()

        # add="+" para no pisar bindings de <Configure> que otra vista
        # (Dados, Tragamonedas) pueda agregar sobre este mismo root.
        self.root.bind("<Configure>", self._on_configure_ventana, add="+")

    # =====================================================
    # FONDO
    # =====================================================

    def crear_fondo(self):

        self.canvas = tk.Canvas(
            self.root,
            width=ANCHO_REF,
            height=ALTO_REF,
            highlightthickness=0
        )

        self.canvas.place(x=0, y=0)

        ruta_fondo = os.path.join(
            self.ruta_base,
            "recursos",
            "fondo_principal.png"
        )

        print("Cargando fondo:", ruta_fondo)

        # Se guarda la imagen original a su resolución nativa para poder
        # reescalarla con buena calidad en cada resize, en vez de reescalar
        # una copia ya reducida.
        self._fondo_original = Image.open(ruta_fondo)

        self.img_fondo = ImageTk.PhotoImage(self._fondo_original.resize((ANCHO_REF, ALTO_REF)))
        self._fondo_item = self.canvas.create_image(0, 0, image=self.img_fondo, anchor="nw")

    def _actualizar_fondo(self, ancho: int, alto: int) -> None:
        self.canvas.place(x=0, y=0, width=ancho, height=alto)
        self.canvas.config(width=ancho, height=alto)
        self.img_fondo = ImageTk.PhotoImage(self._fondo_original.resize((ancho, alto)))
        self.canvas.itemconfig(self._fondo_item, image=self.img_fondo)

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

        self.lbl_perfil_icono = tk.Label(
            self.frame_perfil,
            text="👤",
            font=("Arial", 24),
            bg="#001a00",
            fg="#66ff66"
        )
        self.lbl_perfil_icono.place(x=15, y=20)

        self.lbl_perfil_nombre = tk.Label(
            self.frame_perfil,
            text=f"Nombre:  {self.jugador.usuario}",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11)
        )
        self.lbl_perfil_nombre.place(x=70, y=10)

        self.lbl_perfil_nivel = tk.Label(
            self.frame_perfil,
            text=f"Nivel: {self.jugador.nivel}",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11)
        )
        self.lbl_perfil_nivel.place(x=70, y=35)

        self.lbl_perfil_pais = tk.Label(
            self.frame_perfil,
            text=f"País: {self.jugador.pais}",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11)
        )
        self.lbl_perfil_pais.place(x=70, y=60)

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

        self.btn_config = tk.Button(
            self.frame_config,
            text="⚙",
            font=("Arial", 22),
            bg="#001a00",
            fg="#66ff66",
            bd=0,
            cursor="hand2"
        )
        self.btn_config.pack(side="left", padx=20)

        self.lbl_config_estado = tk.Label(
            self.frame_config,
            text="🟢",
            font=("Arial", 18),
            bg="#001a00"
        )
        self.lbl_config_estado.pack(side="right", padx=20)

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

        self.lbl_info_juegos = tk.Label(
            self.frame_info,
            text="Juegos realizados: 0",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 14, "bold")
        )
        self.lbl_info_juegos.place(x=20, y=15)

        # Nota: mismo bug de f-string que en el perfil — faltaba la "f".
        self.lbl_info_creditos = tk.Label(
            self.frame_info,
            text=f"Créditos: ${self.jugador.creditos:,}",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 14, "bold")
        )
        self.lbl_info_creditos.place(x=20, y=50)

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

        # Referencias vivas a las PhotoImage actuales (si se pierden por
        # garbage collection, los botones se quedan sin imagen).
        self.imagenes_botones = []
        # Specs de cada botón: posición/tamaño de diseño + imagen PIL
        # original a resolución nativa, para reescalar con calidad.
        self._botones_juegos = []

        x = 60
        y = 520
        tam_base = 180

        for archivo, comando in botones:

            ruta_imagen = os.path.join(
                self.ruta_base,
                "recursos",
                archivo
            )

            print("Cargando:", ruta_imagen)

            imagen_original = Image.open(ruta_imagen)
            foto = ImageTk.PhotoImage(imagen_original.resize((tam_base, tam_base)))
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
                y=y
            )

            self._botones_juegos.append({
                "boton": boton,
                "imagen_original": imagen_original,
                "x": x,
                "y": y,
                "tam": tam_base,
            })

            x += 250

    # =====================================================
    # RESPONSIVE: reescalado de todo el menú al redimensionar
    # =====================================================

    def _on_configure_ventana(self, evento) -> None:
        if evento.widget is not self.root:
            return
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(RETARDO_RESIZE_MS, self._aplicar_escala)

    def _aplicar_escala(self) -> None:
        self._resize_after_id = None
        ancho = self.root.winfo_width()
        alto = self.root.winfo_height()
        if ancho <= 1 or alto <= 1:
            return

        escala = min(ancho / ANCHO_REF, alto / ALTO_REF)
        escala = max(ESCALA_MIN, min(ESCALA_MAX, escala))
        if abs(escala - self._escala) < 0.02:
            return  # cambio insignificante: evita redibujos innecesarios
        self._escala = escala

        self._actualizar_fondo(ancho, alto)
        self._reposicionar_panel_perfil(escala)
        self._reposicionar_panel_configuracion(escala)
        self._reposicionar_panel_central(escala)
        self._reposicionar_botones_juegos(escala)

    def _reposicionar_panel_perfil(self, escala: float) -> None:
        self.frame_perfil.place(
            x=int(20 * escala), y=int(20 * escala),
            width=int(350 * escala), height=int(90 * escala),
        )
        self.lbl_perfil_icono.place(x=int(15 * escala), y=int(20 * escala))
        self.lbl_perfil_icono.config(font=("Arial", max(10, int(24 * escala))))

        self.lbl_perfil_nombre.place(x=int(70 * escala), y=int(10 * escala))
        self.lbl_perfil_nombre.config(font=("Arial", max(7, int(11 * escala))))

        self.lbl_perfil_nivel.place(x=int(70 * escala), y=int(35 * escala))
        self.lbl_perfil_nivel.config(font=("Arial", max(7, int(11 * escala))))

        self.lbl_perfil_pais.place(x=int(70 * escala), y=int(60 * escala))
        self.lbl_perfil_pais.config(font=("Arial", max(7, int(11 * escala))))

    def _reposicionar_panel_configuracion(self, escala: float) -> None:
        self.frame_config.place(
            x=int(1180 * escala), y=int(20 * escala),
            width=int(160 * escala), height=int(90 * escala),
        )
        self.btn_config.config(font=("Arial", max(12, int(22 * escala))))
        self.lbl_config_estado.config(font=("Arial", max(9, int(18 * escala))))

    def _reposicionar_panel_central(self, escala: float) -> None:
        self.frame_info.place(
            x=int(420 * escala), y=int(150 * escala),
            width=int(530 * escala), height=int(90 * escala),
        )
        self.lbl_info_juegos.place(x=int(20 * escala), y=int(15 * escala))
        self.lbl_info_juegos.config(font=("Arial", max(9, int(14 * escala)), "bold"))

        self.lbl_info_creditos.place(x=int(20 * escala), y=int(50 * escala))
        self.lbl_info_creditos.config(font=("Arial", max(9, int(14 * escala)), "bold"))

    def _reposicionar_botones_juegos(self, escala: float) -> None:
        for spec in self._botones_juegos:
            tam = max(40, int(spec["tam"] * escala))
            foto = ImageTk.PhotoImage(spec["imagen_original"].resize((tam, tam)))
            spec["foto_actual"] = foto  # mantiene la referencia viva
            spec["boton"].config(image=foto)
            spec["boton"].place(x=int(spec["x"] * escala), y=int(spec["y"] * escala))

    # =====================================================
    # EVENTOS
    # =====================================================

    def abrir_blackjack(self):
        # TODO: una vez que BlackjackClient acepte una conexión ya
        # abierta (en lugar de crear la suya con self._connect()),
        # abrir aquí pasando self.jugador y self.conexion, por ejemplo:
        #   BlackjackClient(self.root, self.jugador, self.conexion)
        # Mientras tanto no se abre una conexión nueva desde aquí,
        # para no violar la regla de "una sola conexión por sesión".
        BlackjackClient(self.root, self.jugador, self.conexion)

    def abrir_ruleta(self):
        # TODO: Ruleta necesita self.jugador / self.conexion para
        # apostar con créditos reales en lugar de datos de prueba.
        Ruleta(self.root)

    def abrir_info(self):
        print("Abrir Información")

    def abrir_tragamonedas(self):
        # TODO: reemplazar este Jugador de prueba por self.jugador
        # una vez que vistas/casino_com.Jugador y el jugador que
        # entrega Login compartan la misma representación (o se
        # adapte uno al otro). Por ahora esto NO usa créditos reales.
        jugador_prueba = Jugador("TestPlayer", creditos_iniciales=2000)
        vistaTragamonedas(jugador_prueba, self.root)

    def abrir_craps(self):
        print("Abrir Craps")
