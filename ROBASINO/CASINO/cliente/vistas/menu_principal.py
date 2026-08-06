import math
import os
import tkinter as tk

from PIL import Image, ImageTk

from vistas.ruleta import Ruleta
from vistas.tragamonedas import vistaTragamonedas
from vistas.dados import Dados
from vistas.client import BlackjackClient

# ── Reescalado responsive ───────────────────────────────────────────
# Todas las coordenadas/tamaños usados al construir el menú (más abajo,
# en cada método crear_*) son coordenadas de DISEÑO, pensadas para esta
# resolución de referencia. En cada resize se calcula un factor de
# escala y se reposiciona/reescala todo en base a él — mismo patrón que
# ya usa vistas/dados.py para escalar los dados con la ventana.
ANCHO_REF = 1366
ALTO_REF = 768
ESCALA_MIN = 0.6   # no se permite achicar el contenido más allá de esto
ESCALA_MAX = 2.0   # ni agrandarlo más allá de esto (para no pixelar los íconos)
RETARDO_RESIZE_MS = 120  # debounce: no redibujar en cada pixel de arrastre

ANCHO_MIN = int(ANCHO_REF * ESCALA_MIN)
ALTO_MIN = int(ALTO_REF * ESCALA_MIN)

TAM_ICONO_JUEGO = 180
PASO_ICONO_JUEGO = 250


class MenuPrincipal:

    def __init__(self, root, jugador, conexion):

        self.root = root
        self.jugador = jugador
        # GestorConexion ya autenticado (ver controladores/gestor_conexion.py),
        # reutilizado por todos los juegos. No es un socket crudo: es el
        # único punto del cliente que lee de él, así que se pasa tal
        # cual a cada juego en vez de dejar que cada uno abra su propio
        # hilo de escucha sobre el mismo socket.
        self.conexion = conexion

        self.root.title("ROBASINO")
        self.root.geometry(f"{ANCHO_REF}x{ALTO_REF}")

        # La ventana SIEMPRE se puede redimensionar/maximizar: se fija
        # un mínimo (ANCHO_MIN x ALTO_MIN) y todo el contenido se
        # reescala proporcionalmente (ver _aplicar_escala). Antes esto
        # quedaba fijo en resizable(False, False) para siempre — lo
        # cual también le tapaba el botón de agrandar a cualquier vista
        # de juego (Dados, Tragamonedas, ...) que se abre sobre esta
        # misma ventana compartida, aunque esa vista sí estuviera
        # pensada para ser responsive.
        self.root.resizable(True, True)
        self.root.minsize(ANCHO_MIN, ALTO_MIN)

        # Ruta base: cliente/
        self.ruta_base = os.path.dirname(os.path.dirname(__file__))

        # Elementos registrados para reposicionarse/reescalarse en cada
        # resize (ver _registrar / _aplicar_escala). Cada entrada guarda
        # coordenadas de DISEÑO, no las coordenadas reales en pantalla.
        self._elementos_responsive = []
        self._escala_actual = 1.0
        self._resize_after_id = None

        self._imagen_fondo_pil = None
        self._id_imagen_fondo = None
        self._imagen_fondo_tk = None

        # [{"pil": Image|None, "boton": Button, "tk": PhotoImage|None}]
        self._iconos_juegos = []

        self.crear_fondo()
        self.crear_panel_perfil()
        self.crear_panel_configuracion()
        self.crear_panel_central()
        self.crear_barra_juegos()

        self._id_bind_configure = self.root.bind(
            "<Configure>", self._on_configure_ventana, add="+"
        )
        # Primer reescalado: coloca todo en su posición/tamaño inicial
        # (antes de esto, nada tiene una posición real todavía, porque
        # los métodos crear_* solo REGISTRAN elementos, no los colocan).
        self._aplicar_escala()

    # =====================================================
    # ESCALADO RESPONSIVE
    # =====================================================

    def _registrar(self, widget, x=None, y=None, w=None, h=None,
                    anchor="nw", fuente_base=None):
        """Registra un widget para reposicionarse/reescalarse con la
        ventana. x/y/w/h son coordenadas de DISEÑO (para ANCHO_REF x
        ALTO_REF); se multiplican por el factor de escala vigente en
        cada resize. `fuente_base` es una tupla estilo Tk
        (familia, tamaño, *modificadores) si además hay que reescalar
        el tamaño de fuente del widget."""
        self._elementos_responsive.append({
            "widget": widget, "x": x, "y": y, "w": w, "h": h,
            "anchor": anchor, "fuente_base": fuente_base,
        })
        return widget

    def _on_configure_ventana(self, evento):
        if evento.widget is not self.root:
            return
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        # Debounce: espera a que el usuario suelte el arrastre antes de
        # recalcular, para no redibujar en cada pixel de resize.
        self._resize_after_id = self.root.after(
            RETARDO_RESIZE_MS, self._aplicar_escala
        )

    def _aplicar_escala(self):
        self._resize_after_id = None
        ancho = self.root.winfo_width()
        alto = self.root.winfo_height()
        if ancho <= 1 or alto <= 1:
            return

        escala = min(ancho / ANCHO_REF, alto / ALTO_REF)
        escala = max(ESCALA_MIN, min(ESCALA_MAX, escala))
        self._escala_actual = escala

        for el in self._elementos_responsive:
            if el["x"] is not None:
                kwargs = {"x": el["x"] * escala, "y": el["y"] * escala,
                          "anchor": el["anchor"]}
                if el["w"] is not None:
                    kwargs["width"] = el["w"] * escala
                if el["h"] is not None:
                    kwargs["height"] = el["h"] * escala
                el["widget"].place(**kwargs)
            if el["fuente_base"] is not None:
                familia, tam, *resto = el["fuente_base"]
                nuevo_tam = max(6, round(tam * escala))
                el["widget"].config(font=(familia, nuevo_tam, *resto))

        self._reescalar_fondo(ancho, alto)
        self._reescalar_iconos_juegos(escala)

    # =====================================================
    # FONDO
    # =====================================================

    def crear_fondo(self):

        self.canvas = tk.Canvas(self.root, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)

        ruta_fondo = os.path.join(
            self.ruta_base,
            "recursos",
            "fondo_principal.png"
        )

        print("Cargando fondo:", ruta_fondo)

        try:
            self._imagen_fondo_pil = Image.open(ruta_fondo).convert("RGB")
        except Exception:
            self._imagen_fondo_pil = None  # sin imagen: el canvas queda con su color de fondo por defecto

    def _reescalar_fondo(self, ancho, alto):
        if self._imagen_fondo_pil is None:
            return

        # Ajuste tipo "cover": escala la imagen para cubrir toda la
        # ventana y recorta el sobrante, sin deformarla — igual que el
        # fondo de fieltro en vistas/dados.py.
        im_ancho, im_alto = self._imagen_fondo_pil.size
        escala_img = max(ancho / im_ancho, alto / im_alto)
        nuevo_ancho = max(1, math.ceil(im_ancho * escala_img))
        nuevo_alto = max(1, math.ceil(im_alto * escala_img))
        redimensionada = self._imagen_fondo_pil.resize(
            (nuevo_ancho, nuevo_alto), Image.LANCZOS
        )
        x0 = (nuevo_ancho - ancho) // 2
        y0 = (nuevo_alto - alto) // 2
        recortada = redimensionada.crop((x0, y0, x0 + ancho, y0 + alto))

        self._imagen_fondo_tk = ImageTk.PhotoImage(recortada)
        if self._id_imagen_fondo is None:
            self._id_imagen_fondo = self.canvas.create_image(
                0, 0, anchor="nw", image=self._imagen_fondo_tk
            )
            # El fondo se crea primero, pero por las dudas se manda
            # detrás de todo lo demás (paneles/botones) ya dibujado.
            self.canvas.tag_lower(self._id_imagen_fondo)
        else:
            self.canvas.itemconfig(self._id_imagen_fondo, image=self._imagen_fondo_tk)
            self.canvas.coords(self._id_imagen_fondo, 0, 0)

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
        self._registrar(self.frame_perfil, x=20, y=20, w=350, h=90)

        tk.Label(
            self.frame_perfil,
            text="👤",
            font=("Arial", 24),
            bg="#001a00",
            fg="#66ff66"
        ).pack(side="left", padx=(15, 10))

        info = tk.Frame(self.frame_perfil, bg="#001a00")
        info.pack(side="left", fill="both", expand=True, pady=10)

        tk.Label(
            info,
            text=f"Nombre:  {self.jugador.usuario}",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11),
            anchor="w"
        ).pack(fill="x")

        tk.Label(
            info,
            text=f"Nivel: {self.jugador.nivel}",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11),
            anchor="w"
        ).pack(fill="x")

        tk.Label(
            info,
            text=f"País: {self.jugador.pais}",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 11),
            anchor="w"
        ).pack(fill="x")

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
        self._registrar(self.frame_config, x=1180, y=20, w=160, h=90)

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
        self._registrar(self.frame_info, x=420, y=150, w=530, h=90)

        tk.Label(
            self.frame_info,
            text="Juegos realizados: 0",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 14, "bold"),
            anchor="w"
        ).pack(fill="x", padx=20, pady=(15, 2))

        self.lbl_creditos = tk.Label(
            self.frame_info,
            text=f"Créditos: ${self.jugador.creditos:,}",
            bg="#001a00",
            fg="#66ff66",
            font=("Arial", 14, "bold"),
            anchor="w"
        )
        self.lbl_creditos.pack(fill="x", padx=20)

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

        self._iconos_juegos = []
        x = 60

        for archivo, comando in botones:

            ruta_imagen = os.path.join(
                self.ruta_base,
                "recursos",
                archivo
            )

            print("Cargando:", ruta_imagen)

            try:
                imagen_pil = Image.open(ruta_imagen)
            except Exception:
                imagen_pil = None  # ícono faltante: el botón queda sin imagen, no rompe el menú

            boton = tk.Button(
                self.root,
                command=comando,
                bd=0,
                cursor="hand2",
                bg="black",
                activebackground="black"
            )
            self._registrar(boton, x=x, y=520, w=TAM_ICONO_JUEGO, h=TAM_ICONO_JUEGO)
            self._iconos_juegos.append({"pil": imagen_pil, "boton": boton, "tk": None})

            x += PASO_ICONO_JUEGO

    def _reescalar_iconos_juegos(self, escala):
        tam = max(1, round(TAM_ICONO_JUEGO * escala))
        for icono in self._iconos_juegos:
            if icono["pil"] is None:
                continue
            redimensionada = icono["pil"].resize((tam, tam), Image.LANCZOS)
            icono["tk"] = ImageTk.PhotoImage(redimensionada)
            icono["boton"].config(image=icono["tk"])

    # =====================================================
    # EVENTOS
    # =====================================================

    def abrir_blackjack(self):
        # BlackjackClient se suscribe a GestorConexion en vez de abrir
        # su propio hilo de escucha; no se abre ninguna conexión nueva
        # aquí, se sigue usando la única de la sesión.
        BlackjackClient(self.root, self.jugador, self.conexion)

    def abrir_ruleta(self):
        # Ruleta ya está conectada al servidor (controlador_ruleta.py):
        # el saldo y el número ganador son autoritativos del servidor,
        # esta vista solo dibuja y envía apuestas.
        Ruleta(self.root, self.jugador, self.conexion)

    def abrir_info(self):
        print("Abrir Información")

    def abrir_tragamonedas(self):
        # Usa la sesión real (jugador + conexión ya autenticada), igual
        # que blackjack/ruleta: el servidor cobra y paga contra la BD,
        # esta vista ya no maneja créditos de prueba.
        vistaTragamonedas(self.jugador, self.root, self.conexion)

    def abrir_craps(self):
        # Igual patrón que tragamonedas: el servidor decide los dados y
        # descuenta/acredita créditos reales contra la BD.
        Dados(self.jugador, self.root, self.conexion)
