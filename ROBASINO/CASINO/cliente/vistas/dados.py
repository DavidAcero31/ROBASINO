from __future__ import annotations

import math
import os
import random
import time
import tkinter as tk
from tkinter import messagebox

try:
    from PIL import Image, ImageTk
    PIL_DISPONIBLE = True
except ImportError:  # Pillow no instalado: se usa un color sólido de respaldo.
    PIL_DISPONIBLE = False

from controladores.controlador_dados import ControladorDados

# ----------------------------------------------------------------------
# Paleta "mesa de fieltro" — tonos casi negros con incrustaciones doradas.
# ----------------------------------------------------------------------
BG_DARK = "#07140e"       # contenedores principales: casi negro-verde
BG_PANEL = "#081a12"      # variante sutil para paneles internos
BORDER = "#c5a059"        # borde dorado suave ("incrustación metálica")
BORDER_SOFT = "#8a7336"   # dorado apagado, para bordes secundarios
GOLD = "#f0c04a"
GOLD_HOVER = "#f5d67a"
GOLD_MUTED = "#a39262"    # etiquetas de título (CREDITOS / APUESTA / ...)
GOLD_BRIGHT = "#ffd700"   # valores numéricos grandes
MINT_TEXT = "#8fd6a8"

# Placa de estado del juego.
VERDE_GANADA = "#2ecc71"
ROJO_PERDIDA = "#e74c3c"
AMARILLO_PUNTO = "#f1c40f"

# Imagen de fondo (fieltro verde). Se busca en varias rutas comunes del
# proyecto; si no se encuentra, la interfaz simplemente usa BG_DARK.
NOMBRE_IMAGEN_FONDO = "FondoDados.png"

# Botón principal (ROLL/APOSTAR): rojo sólido con texto blanco, como los
# botones "píldora" de la referencia (OK, CLEAR, REBET, ROLL).
BTN_BG = "#c62828"
BTN_BG_HOVER = "#e0473c"
BTN_BG_OFF = "#5c3a37"
BTN_FG = "#fdf6ec"
BTN_FG_OFF = "#a08c86"

# Stepper de apuesta (-/+): dorado, para diferenciarlo del botón de acción.
APUESTA_MIN = 10
APUESTA_MAX = 500
PASO_APUESTA = 10

CARA_TAM = 84            # tamaño de la cara frontal (más chica para dejar lugar al volumen)
PROF = 20                # "profundidad" isométrica de las caras superior/lateral
CANVAS_ANCHO = 118
CANVAS_ALTO = 150         # más alto que ancho: deja espacio arriba para el "salto"
MARGEN_SUP = 44           # posición Y de la cara en reposo (antes de rebotar)
MARGEN_IZQ = 4
COLOR_SOMBRA = "#04170c"
COLOR_CARA = "#f5f0e1"    # cara frontal
COLOR_TOP = "#fffaf0"     # cara superior: recibe más luz, más clara
COLOR_LADO = "#c9bd93"    # cara lateral derecha: en sombra, más oscura
COLOR_CANTO = "#c9a227"   # visto de canto (girando de perfil)
COLOR_PIP = "#1a1a1a"

# Duración total de la animación y velocidad de giro (en semi-vueltas) de
# cada dado. Se usan valores distintos por dado para que no giren
# sincronizados, como pasa con dados reales al caer.
DURACION_ANIMACION_MS = 900
VUELTAS_DADO_1 = 5.5 * math.pi
VUELTAS_DADO_2 = 4.7 * math.pi

# Referencia para el escalado responsive: tamaño "de diseño" de la
# ventana contra el cual se calcula el factor de escala de los dados.
ANCHO_REF = 700
ALTO_REF = 750
ESCALA_MIN = 0.7
ESCALA_MAX = 1.6
RETARDO_RESIZE_MS = 120  # debounce: no redibujar en cada pixel de arrastre

# Límites de la ventana derivados de la misma escala: así lo que se ve
# "más chico" o "más grande" en pantalla coincide con lo que se puede
# efectivamente redimensionar.
ANCHO_MIN = int(ANCHO_REF * ESCALA_MIN)
ALTO_MIN = int(ALTO_REF * ESCALA_MIN)
ANCHO_MAX = int(ANCHO_REF * ESCALA_MAX)
ALTO_MAX = int(ALTO_REF * ESCALA_MAX)

POSICIONES_PUNTOS = {
    1: [(0.5, 0.5)],
    2: [(0.25, 0.25), (0.75, 0.75)],
    3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
    4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
    5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
    6: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.5), (0.75, 0.5), (0.25, 0.75), (0.75, 0.75)],
}


def _localizar_imagen_fondo() -> str | None:
    """Busca FondoDados.png en la carpeta 'recursos' del proyecto.

    Este archivo (dados.py) vive en CASINO/cliente/vistas/, y la imagen
    en CASINO/cliente/recursos/FondoDados.png — es decir, un nivel arriba
    de 'vistas' y luego dentro de 'recursos'. Se dejan además un par de
    rutas alternativas por si se reorganiza el proyecto, para no romper
    la app si no la encuentra."""
    base = os.path.dirname(os.path.abspath(__file__))  # .../CASINO/cliente/vistas
    raiz_cliente = os.path.dirname(base)                # .../CASINO/cliente
    candidatos = [
        os.path.join(raiz_cliente, "recursos", NOMBRE_IMAGEN_FONDO),
        os.path.join(base, NOMBRE_IMAGEN_FONDO),
        os.path.join(base, "recursos", NOMBRE_IMAGEN_FONDO),
        os.path.join(base, "assets", NOMBRE_IMAGEN_FONDO),
        os.path.join(base, "imagenes", NOMBRE_IMAGEN_FONDO),
    ]
    for ruta in candidatos:
        if os.path.isfile(ruta):
            return ruta
    return None


def rect_redondeado(canvas: tk.Canvas, x1, y1, x2, y2, radio=18, **kwargs):
    """Dibuja un rectángulo con esquinas redondeadas (Tkinter no lo soporta
    de forma nativa, así que se aproxima con un polígono suavizado)."""
    puntos = [
        x1 + radio, y1, x2 - radio, y1, x2, y1, x2, y1 + radio,
        x2, y2 - radio, x2, y2, x2 - radio, y2, x1 + radio, y2,
        x1, y2, x1, y2 - radio, x1, y1 + radio, x1, y1,
    ]
    return canvas.create_polygon(puntos, smooth=True, **kwargs)


class BotonRedondeado(tk.Canvas):
    """Botón con esquinas redondeadas y efecto hover, dibujado sobre un
    Canvas (los widgets Button de Tkinter no permiten border-radius)."""

    def __init__(self, master, texto, comando, ancho=200, alto=48, radio=24,
                 fuente=("Arial", 13, "bold")):
        super().__init__(master, width=ancho, height=alto,
                          bg=master["bg"], highlightthickness=0, bd=0)
        self.comando = comando
        self.activo = True
        self._fondo = rect_redondeado(self, 1, 1, ancho - 1, alto - 1, radio,
                                       fill=BTN_BG, outline="")
        self._texto = self.create_text(ancho / 2, alto / 2, text=texto,
                                        fill=BTN_FG, font=fuente)
        self.bind("<Button-1>", self._al_hacer_clic)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, dentro: bool) -> None:
        if self.activo:
            self.itemconfig(self._fondo, fill=BTN_BG_HOVER if dentro else BTN_BG)

    def _al_hacer_clic(self, _evento) -> None:
        if self.activo and self.comando:
            self.comando()

    def set_texto(self, texto: str) -> None:
        self.itemconfig(self._texto, text=texto)

    def set_estado(self, activo: bool) -> None:
        self.activo = activo
        self.itemconfig(self._fondo, fill=BTN_BG if activo else BTN_BG_OFF)
        self.itemconfig(self._texto, fill=BTN_FG if activo else BTN_FG_OFF)


class BotonCircular(tk.Canvas):
    """Botón circular tipo 'ficha' para el stepper de apuesta (-/+), en
    vez del típico Spinbox con flechitas nativas de Tkinter."""

    def __init__(self, master, texto, comando, diametro=34,
                 fuente=("Arial", 15, "bold")):
        super().__init__(master, width=diametro, height=diametro,
                          bg=master["bg"], highlightthickness=0, bd=0)
        self.comando = comando
        self.activo = True
        # Fondo oscuro con borde e ícono dorado: integrado con el resto
        # de contenedores oscuros de la interfaz.
        self._circulo = self.create_oval(1, 1, diametro - 1, diametro - 1,
                                          fill=BG_PANEL, outline=BORDER, width=1)
        self._texto = self.create_text(diametro / 2, diametro / 2, text=texto,
                                        fill=GOLD, font=fuente)
        self.bind("<Button-1>", self._al_hacer_clic)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, dentro: bool) -> None:
        if self.activo:
            self.itemconfig(self._circulo, outline=GOLD_HOVER if dentro else BORDER)
            self.itemconfig(self._texto, fill=GOLD_HOVER if dentro else GOLD)

    def _al_hacer_clic(self, _evento) -> None:
        if self.activo and self.comando:
            self.comando()

    def set_estado(self, activo: bool) -> None:
        self.activo = activo
        self.itemconfig(self._circulo, outline=BORDER if activo else BORDER_SOFT)
        self.itemconfig(self._texto, fill=GOLD if activo else "#5a5140")


class VisorApuesta(tk.Canvas):
    """Pastilla dorada que muestra el monto de apuesta seleccionado,
    entre los dos botones circulares del stepper."""

    def __init__(self, master, texto_inicial, ancho=92, alto=38, radio=18,
                 fuente=("Arial", 15, "bold")):
        super().__init__(master, width=ancho, height=alto,
                          bg=master["bg"], highlightthickness=0, bd=0)
        rect_redondeado(self, 1, 1, ancho - 1, alto - 1, radio,
                         fill=BG_DARK, outline=GOLD, width=2)
        self._texto = self.create_text(ancho / 2, alto / 2, text=texto_inicial,
                                        fill=GOLD, font=fuente)

    def set_valor(self, texto: str) -> None:
        self.itemconfig(self._texto, text=texto)


class PlacaEstado(tk.Canvas):
    """Tarjeta dedicada para el estado de la ronda, justo debajo de los
    dados: cambia de color según si la ronda fue ganada, perdida o si
    hay un punto establecido."""

    COLORES = {
        "ganada": VERDE_GANADA,
        "perdida": ROJO_PERDIDA,
        "punto": AMARILLO_PUNTO,
        "neutral": GOLD_MUTED,
    }

    def __init__(self, master, ancho=230, alto=38, radio=10,
                 fuente=("Arial", 13, "bold")):
        super().__init__(master, width=ancho, height=alto,
                          bg=master["bg"], highlightthickness=0, bd=0)
        self._ancho, self._alto = ancho, alto
        self._fondo = rect_redondeado(
            self, 1, 1, ancho - 1, alto - 1, radio,
            fill=BG_DARK, outline=GOLD_MUTED, width=1,
        )
        self._texto = self.create_text(
            ancho / 2, alto / 2, text="—", fill=GOLD_MUTED, font=fuente
        )

    def set_estado(self, texto: str, tipo: str = "neutral") -> None:
        color = self.COLORES.get(tipo, GOLD_MUTED)
        # Placa oscura con acento de color en el borde y el texto (en vez
        # de un bloque sólido) para que siga integrada con el resto de la
        # interfaz sobre el fieltro.
        self.itemconfig(self._fondo, outline=color, fill=BG_DARK)
        self.itemconfig(self._texto, text=texto, fill=color)


class Dados(tk.Frame):
    """Vista del juego de Craps, con el mismo lenguaje visual de Tragamonedas."""

    def __init__(self, jugador, master: tk.Tk):
        super().__init__(master, bg=BG_DARK)
        self.master = master
        self.jugador = jugador
        self.controlador = ControladorDados(jugador)
        self.pack(fill="both", expand=True)

        self._animando = False
        self._apuesta_seleccionada = APUESTA_MIN

        # Escalado responsive de los dados.
        self._escala = 1.0
        self._resize_after_id = None
        self._valor_dado1 = 1
        self._valor_dado2 = 1

        # Panel de reglas (oculto por defecto).
        self._panel_reglas_visible = False

        # ------------------------------------------------------------
        # Canvas de fondo (fieltro): ocupa toda la ventana y va detrás
        # de todo lo demás. Los paneles se crean después de este punto,
        # por lo que Tkinter los apila automáticamente por encima.
        # ------------------------------------------------------------
        self._imagen_fondo_pil = None
        self._imagen_fondo_tk = None
        self._id_imagen_fondo = None
        self._fondo_resize_after_id = None

        self.canvas_fondo = tk.Canvas(self, highlightthickness=0, bd=0, bg=BG_DARK)
        self.canvas_fondo.place(x=0, y=0, relwidth=1, relheight=1)
        self._cargar_imagen_fondo()
        self.canvas_fondo.bind("<Configure>", self._on_configure_fondo)

        self._construir_encabezado()
        self._construir_panel_reglas()
        self._construir_panel_dados()
        self._construir_barra_estadisticas()
        self._actualizar_creditos()

        self._id_bind_configure = self.master.bind(
            "<Configure>", self._on_configure_ventana, add="+"
        )

    # ------------------------------------------------------------------
    # Encabezado (doble marco, título dorado + subtítulo)
    # ------------------------------------------------------------------

    def _construir_encabezado(self) -> None:
        externo = tk.Frame(self, bg=BG_DARK, highlightbackground=BORDER,
                            highlightthickness=1, bd=0)
        externo.pack(fill="x", padx=15, pady=(15, 10))
        self._frame_encabezado = externo  # ancla para insertar el panel de reglas

        interno = tk.Frame(externo, bg=BG_PANEL, highlightbackground=BORDER_SOFT,
                            highlightthickness=1)
        interno.pack(fill="x", padx=6, pady=6)

        tk.Label(
            interno, text="✦ R O B A S I N O ✦", bg=BG_PANEL, fg=GOLD,
            font=("Arial", 22, "bold")
        ).pack(pady=(10, 0))
        tk.Label(
            interno, text="C R A P S", bg=BG_PANEL, fg=MINT_TEXT,
            font=("Arial", 11, "bold")
        ).pack(pady=(0, 10))

        # Botón de ayuda (❓), esquina superior derecha, igual que el ⚙️
        # de la referencia: no ensucia la pantalla si el jugador ya sabe jugar.
        self.btn_ayuda = BotonCircular(
            interno, "❓", self._alternar_panel_reglas, diametro=30,
            fuente=("Arial", 13, "bold"),
        )
        self.btn_ayuda.place(relx=1.0, x=-10, y=10, anchor="ne")

        # Botón para volver al menú principal, esquina superior izquierda.
        self.btn_volver = BotonRedondeado(
            interno, "← Menú", self._volver_menu, ancho=100, alto=30, radio=15,
            fuente=("Arial", 11, "bold"),
        )
        self.btn_volver.place(x=10, y=10, anchor="nw")

    # ------------------------------------------------------------------
    # Panel de reglas (desplegable, para quien no sepa jugar)
    # ------------------------------------------------------------------

    def _construir_panel_reglas(self) -> None:
        self.panel_reglas = tk.Frame(
            self, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1
        )
        # No se empaqueta todavía: arranca oculto.

        tk.Label(
            self.panel_reglas, text="¿Cómo se juega? — Pase simple",
            bg=BG_PANEL, fg=GOLD, font=("Arial", 12, "bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        reglas = (
            "• Primera tirada: si sale 7 u 11, ganas de inmediato.\n"
            "• Primera tirada: si sale 2, 3 o 12 (\"craps\"), pierdes de inmediato.\n"
            "• Cualquier otro número (4, 5, 6, 8, 9 o 10) se fija como \"el punto\".\n"
            "• Con el punto establecido: si vuelve a salir ese número, ganas.\n"
            "• Con el punto establecido: si sale 7 (\"seven out\"), pierdes.\n"
            "• Cualquier otro valor no decide nada: vuelves a lanzar."
        )
        tk.Label(
            self.panel_reglas, text=reglas, bg=BG_PANEL, fg=MINT_TEXT,
            font=("Arial", 10), justify="left", anchor="w",
        ).pack(anchor="w", padx=14, pady=(0, 12), fill="x")

    def _alternar_panel_reglas(self) -> None:
        if self._panel_reglas_visible:
            self.panel_reglas.pack_forget()
        else:
            self.panel_reglas.pack(
                fill="x", padx=15, pady=(0, 10), after=self._frame_encabezado
            )
        self._panel_reglas_visible = not self._panel_reglas_visible

    # ------------------------------------------------------------------
    # Panel de dados (doble marco central)
    # ------------------------------------------------------------------

    def _construir_panel_dados(self) -> None:
        externo = tk.Frame(self, bg=BG_DARK, highlightbackground=BORDER,
                            highlightthickness=1)
        externo.pack(fill="both", expand=True, padx=15, pady=10)

        medio = tk.Frame(externo, bg=BG_PANEL, highlightbackground=BORDER_SOFT,
                          highlightthickness=1)
        medio.pack(fill="both", expand=True, padx=8, pady=8)

        interno = tk.Frame(medio, bg=BG_DARK, highlightbackground=BORDER_SOFT,
                            highlightthickness=1)
        interno.pack(padx=20, pady=20)

        fila_dados = tk.Frame(interno, bg=BG_DARK)
        fila_dados.pack(padx=30, pady=30)

        self.canvas_dado1 = tk.Canvas(fila_dados, width=CANVAS_ANCHO, height=CANVAS_ALTO,
                                       bg=BG_DARK, highlightthickness=0, bd=0)
        self.canvas_dado1.pack(side="left", padx=15)

        self.canvas_dado2 = tk.Canvas(fila_dados, width=CANVAS_ANCHO, height=CANVAS_ALTO,
                                       bg=BG_DARK, highlightthickness=0, bd=0)
        self.canvas_dado2.pack(side="left", padx=15)

        self._dibujar_dado(self.canvas_dado1, 1)
        self._dibujar_dado(self.canvas_dado2, 1)

        # Placa de estado: tarjeta dedicada justo debajo de los dados que
        # cambia de color según gane/pierda la ronda o se marque un punto.
        self.placa_estado = PlacaEstado(medio)
        self.placa_estado.pack(pady=(0, 12))

    # ------------------------------------------------------------------
    # Fondo de fieltro (Canvas principal)
    # ------------------------------------------------------------------

    def _cargar_imagen_fondo(self) -> None:
        if not PIL_DISPONIBLE:
            return  # sin Pillow: se mantiene el color sólido BG_DARK
        ruta = _localizar_imagen_fondo()
        if ruta is None:
            return
        try:
            self._imagen_fondo_pil = Image.open(ruta).convert("RGB")
        except Exception:
            self._imagen_fondo_pil = None

    def _on_configure_fondo(self, evento) -> None:
        if self._imagen_fondo_pil is None:
            return
        if self._fondo_resize_after_id is not None:
            self.master.after_cancel(self._fondo_resize_after_id)
        # Debounce: evita re-escalar la imagen en cada pixel de arrastre.
        self._fondo_resize_after_id = self.master.after(
            RETARDO_RESIZE_MS, lambda: self._aplicar_imagen_fondo(evento.width, evento.height)
        )

    def _aplicar_imagen_fondo(self, ancho: int, alto: int) -> None:
        self._fondo_resize_after_id = None
        if ancho <= 1 or alto <= 1 or self._imagen_fondo_pil is None:
            return

        # Ajuste tipo "cover": escala la imagen para cubrir todo el
        # Canvas y recorta el sobrante, sin deformarla.
        im_ancho, im_alto = self._imagen_fondo_pil.size
        escala = max(ancho / im_ancho, alto / im_alto)
        nuevo_ancho = max(1, math.ceil(im_ancho * escala))
        nuevo_alto = max(1, math.ceil(im_alto * escala))
        redimensionada = self._imagen_fondo_pil.resize(
            (nuevo_ancho, nuevo_alto), Image.LANCZOS
        )
        x0 = (nuevo_ancho - ancho) // 2
        y0 = (nuevo_alto - alto) // 2
        recortada = redimensionada.crop((x0, y0, x0 + ancho, y0 + alto))

        self._imagen_fondo_tk = ImageTk.PhotoImage(recortada)
        if self._id_imagen_fondo is None:
            self._id_imagen_fondo = self.canvas_fondo.create_image(
                0, 0, anchor="nw", image=self._imagen_fondo_tk
            )
        else:
            self.canvas_fondo.itemconfig(self._id_imagen_fondo, image=self._imagen_fondo_tk)
            self.canvas_fondo.coords(self._id_imagen_fondo, 0, 0)

    # ------------------------------------------------------------------
    # Escalado responsive (dados dibujados con coordenadas fijas en
    # píxeles: sin esto, al agrandar la ventana se ven "achicados" en
    # el medio en vez de crecer con el resto de la interfaz)
    # ------------------------------------------------------------------

    def _on_configure_ventana(self, evento) -> None:
        if evento.widget is not self.master:
            return
        if self._resize_after_id is not None:
            self.master.after_cancel(self._resize_after_id)
        # Debounce: espera a que el usuario suelte el arrastre antes de
        # recalcular, para no redibujar en cada pixel de resize.
        self._resize_after_id = self.master.after(RETARDO_RESIZE_MS, self._aplicar_escala)

    def _aplicar_escala(self) -> None:
        self._resize_after_id = None
        ancho = self.master.winfo_width()
        alto = self.master.winfo_height()
        if ancho <= 1 or alto <= 1:
            return

        nueva_escala = min(ancho / ANCHO_REF, alto / ALTO_REF)
        nueva_escala = max(ESCALA_MIN, min(ESCALA_MAX, nueva_escala))
        if abs(nueva_escala - self._escala) < 0.03:
            return  # cambio insignificante: evita redibujos innecesarios

        self._escala = nueva_escala
        ancho_canvas = int(CANVAS_ANCHO * self._escala)
        alto_canvas = int(CANVAS_ALTO * self._escala)
        for canvas in (self.canvas_dado1, self.canvas_dado2):
            canvas.config(width=ancho_canvas, height=alto_canvas)

        if not self._animando:
            self._dibujar_dado(self.canvas_dado1, self._valor_dado1)
            self._dibujar_dado(self.canvas_dado2, self._valor_dado2)

    def _dibujar_dado(self, canvas: tk.Canvas, valor: int,
                       escala_x: float = 1.0, offset_y: float = 0.0) -> None:
        """Dibuja el dado como un cubo isométrico: cara frontal (con pips),
        cara superior (más clara, "recibe luz") y cara lateral derecha
        (más oscura, "en sombra"), más la sombra proyectada en la mesa.

        escala_x < 1 comprime el ancho de la cara frontal: simula estar
        viendo el dado de canto mientras gira sobre su eje vertical.
        offset_y < 0 levanta el dado (rebote); la sombra se queda abajo y
        se achica, dando sensación de profundidad.
        """
        canvas.delete("all")
        escala_x = max(0.12, min(1.0, escala_x))
        e = self._escala  # factor responsive: recalculado en cada resize

        cara_tam = CARA_TAM * e
        prof_base = PROF * e
        margen_sup = MARGEN_SUP * e
        margen_izq = MARGEN_IZQ * e
        offset_y = offset_y * e

        ancho_cara = cara_tam * escala_x
        prof = prof_base * (0.4 + 0.6 * escala_x)  # el volumen también se atenúa un poco de canto

        x1 = margen_izq + (cara_tam - ancho_cara) / 2
        x2 = x1 + ancho_cara
        y1 = margen_sup + offset_y
        y2 = y1 + cara_tam

        # Sombra proyectada en la "mesa": posición fija abajo, se angosta
        # con el giro y se achica/aleja cuando el dado salta.
        sombra_y1 = margen_sup + cara_tam + 8 * e
        sombra_alto = max(4, 12 - abs(offset_y) * 0.35) * e
        sombra_ancho = (cara_tam + prof_base) * max(0.5, 1 - abs(offset_y) / 70)
        sx1 = margen_izq + (cara_tam + prof_base - sombra_ancho) / 2
        rect_redondeado(canvas, sx1, sombra_y1, sx1 + sombra_ancho,
                         sombra_y1 + sombra_alto, sombra_alto / 2,
                         fill=COLOR_SOMBRA, outline="")

        # Recuerda el último valor "asentado" (sin giro ni rebote) para
        # poder redibujarlo si cambia la escala por un resize.
        if escala_x >= 0.999 and offset_y == 0.0:
            if canvas is self.canvas_dado1:
                self._valor_dado1 = valor
            elif canvas is self.canvas_dado2:
                self._valor_dado2 = valor

        # Cara superior (paralelogramo): une el borde de arriba de la
        # cara frontal con una "cara trasera" desplazada arriba-derecha.
        canvas.create_polygon(
            x1, y1, x2, y1, x2 + prof, y1 - prof, x1 + prof, y1 - prof,
            fill=COLOR_TOP, outline=GOLD, width=1,
        )
        # Cara lateral derecha (paralelogramo, en sombra).
        canvas.create_polygon(
            x2, y1, x2 + prof, y1 - prof, x2 + prof, y2 - prof, x2, y2,
            fill=COLOR_LADO, outline=GOLD, width=1,
        )

        if escala_x > 0.24:
            canvas.create_rectangle(x1, y1, x2, y2, fill=COLOR_CARA, outline=GOLD, width=2)
            r = 6.5 * e * min(1.0, 0.5 + escala_x * 0.6)
            for fx, fy in POSICIONES_PUNTOS.get(valor, []):
                cx = x1 + fx * ancho_cara
                cy = y1 + fy * cara_tam
                canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    fill=COLOR_PIP, outline="")
        else:
            # De canto: no se alcanza a ver la cara, solo un filo angosto.
            canvas.create_rectangle(x1, y1, x2, y2, fill=COLOR_CANTO, outline=GOLD, width=1)

    def _animar_dados(self, resultado, al_terminar) -> None:
        """Simula que los dados giran y rebotan sobre la mesa antes de
        posarse en el resultado real, ya calculado por el controlador."""
        self._animando = True
        inicio_ms = time.perf_counter() * 1000
        secuencia1 = [random.randint(1, 6) for _ in range(12)]
        secuencia2 = [random.randint(1, 6) for _ in range(12)]

        def cuadro() -> None:
            t = (time.perf_counter() * 1000 - inicio_ms) / DURACION_ANIMACION_MS

            if t >= 1:
                self._dibujar_dado(self.canvas_dado1, resultado.dado1)
                self._dibujar_dado(self.canvas_dado2, resultado.dado2)
                self._animando = False
                al_terminar()
                return

            # Ease-out: gira rápido al principio y se frena, como si la
            # fricción de la mesa lo fuera deteniendo.
            avance = 1 - (1 - t) ** 2
            rebote = math.sin(math.pi * t) * (1 - t) * 24

            angulo1 = VUELTAS_DADO_1 * avance
            angulo2 = VUELTAS_DADO_2 * avance
            cara1 = secuencia1[min(int(angulo1 // math.pi), len(secuencia1) - 1)]
            cara2 = secuencia2[min(int(angulo2 // math.pi), len(secuencia2) - 1)]

            self._dibujar_dado(self.canvas_dado1, cara1,
                                escala_x=abs(math.cos(angulo1)), offset_y=-rebote)
            self._dibujar_dado(self.canvas_dado2, cara2,
                                escala_x=abs(math.cos(angulo2)), offset_y=-rebote * 0.85)

            self.master.after(16, cuadro)

        cuadro()

    # ------------------------------------------------------------------
    # Barra inferior de estadísticas (CREDITOS / APUESTA / control)
    # ------------------------------------------------------------------

    def _construir_barra_estadisticas(self) -> None:
        externo = tk.Frame(self, bg=BG_DARK, highlightbackground=BORDER,
                            highlightthickness=1)
        externo.pack(fill="x", padx=15, pady=(0, 15))

        barra = tk.Frame(externo, bg=BG_PANEL, highlightbackground=BORDER_SOFT,
                          highlightthickness=1)
        barra.pack(fill="x", padx=6, pady=6)

        fila_stats = tk.Frame(barra, bg=BG_PANEL)
        fila_stats.pack(fill="x", padx=10, pady=(10, 0))

        self._crear_estadistica(fila_stats, "CREDITOS", "lbl_valor_creditos")
        self._crear_estadistica(fila_stats, "APUESTA", "lbl_valor_apuesta")
        self._crear_estadistica(fila_stats, "ULTIMO RESULTADO", "lbl_valor_ultimo")

        fila_control = tk.Frame(barra, bg=BG_PANEL)
        fila_control.pack(fill="x", padx=10, pady=10)

        tk.Label(fila_control, text="Apuesta:", bg=BG_PANEL, fg=GOLD_MUTED,
                 font=("Arial", 10, "bold")).pack(side="left")

        self.btn_apuesta_menos = BotonCircular(
            fila_control, "–", lambda: self._cambiar_apuesta(-PASO_APUESTA)
        )
        self.btn_apuesta_menos.pack(side="left", padx=(8, 6))

        self.visor_apuesta = VisorApuesta(fila_control, str(self._apuesta_seleccionada))
        self.visor_apuesta.pack(side="left")

        self.btn_apuesta_mas = BotonCircular(
            fila_control, "+", lambda: self._cambiar_apuesta(PASO_APUESTA)
        )
        self.btn_apuesta_mas.pack(side="left", padx=(6, 10))

        tk.Label(fila_control, text=f"(Mín {APUESTA_MIN} · Máx {APUESTA_MAX})",
                 bg=BG_PANEL, fg=GOLD_MUTED, font=("Arial", 9)).pack(side="left")

        # Botón de acción principal: un poco más grande y con más aire
        # interno para que resalte como el CTA de la barra.
        self.btn_accion = BotonRedondeado(
            fila_control, "🎲  LANZAR", self._al_presionar_accion,
            ancho=190, alto=52, radio=26, fuente=("Arial", 14, "bold"),
        )
        self.btn_accion.pack(side="right")

    def _crear_estadistica(self, padre, texto_etiqueta, nombre_attr) -> None:
        col = tk.Frame(padre, bg=BG_PANEL, highlightbackground=BORDER_SOFT,
                        highlightthickness=1)
        col.pack(side="left", fill="x", expand=True, padx=6)

        # Etiqueta de título: chica, en negrita, dorado apagado.
        tk.Label(col, text=texto_etiqueta, bg=BG_PANEL, fg=GOLD_MUTED,
                 font=("Arial", 9, "bold")).pack(pady=(8, 0))
        # Valor numérico: bien grande y en dorado brillante.
        etiqueta_valor = tk.Label(col, text="-", bg=BG_PANEL, fg=GOLD_BRIGHT,
                                   font=("Arial", 22, "bold"))
        etiqueta_valor.pack(pady=(0, 8))
        setattr(self, nombre_attr, etiqueta_valor)

    # ------------------------------------------------------------------
    # Lógica de eventos
    # ------------------------------------------------------------------

    def _volver_menu(self) -> None:
        if self._animando:
            return  # no se puede salir a mitad de la animación de los dados

        if self.controlador.hay_ronda_activa():
            seguro = messagebox.askyesno(
                "Ronda en curso",
                "Tienes una ronda de Craps en curso. Si vuelves al menú "
                "se perderá la apuesta de esta ronda.\n\n¿Volver al menú de todos modos?",
            )
            if not seguro:
                return

        # Se cancela cualquier resize pendiente y se desengancha SOLO el
        # binding propio (por funcid), sin tocar el que usa MenuPrincipal
        # para reescalarse a sí mismo.
        if self._resize_after_id is not None:
            self.master.after_cancel(self._resize_after_id)
            self._resize_after_id = None
        if self._fondo_resize_after_id is not None:
            self.master.after_cancel(self._fondo_resize_after_id)
            self._fondo_resize_after_id = None
        self.master.unbind("<Configure>", self._id_bind_configure)

        self.destroy()

    def _cambiar_apuesta(self, delta: int) -> None:
        if self._animando or self.controlador.hay_ronda_activa():
            return
        self._apuesta_seleccionada = max(
            APUESTA_MIN, min(APUESTA_MAX, self._apuesta_seleccionada + delta)
        )
        self.visor_apuesta.set_valor(str(self._apuesta_seleccionada))

    def _al_presionar_accion(self) -> None:
        if self._animando:
            return
        self.btn_accion.set_estado(False)
        self.btn_volver.set_estado(False)

        if self.controlador.hay_ronda_activa():
            self.controlador.continuar_lanzamiento(self._on_resultado)
        else:
            self.btn_apuesta_menos.set_estado(False)
            self.btn_apuesta_mas.set_estado(False)
            apuesta = self._apuesta_seleccionada
            self.lbl_valor_apuesta.config(text=f"{apuesta:.0f}")
            self.controlador.iniciar_lanzamiento(apuesta, self._on_resultado)

    def _on_resultado(self, mensaje, resultado, premio, ronda_activa) -> None:
        # Llamado desde el hilo secundario del controlador: se reenvía
        # al hilo principal de Tkinter antes de tocar cualquier widget.
        self.master.after(0, lambda: self._actualizar_interfaz(mensaje, resultado, premio, ronda_activa))

    def _actualizar_interfaz(self, mensaje, resultado, premio, ronda_activa) -> None:
        def finalizar() -> None:
            if resultado is not None:
                self.lbl_valor_ultimo.config(text=str(resultado.suma))

            self._actualizar_placa_estado(ronda_activa, resultado)
            self._actualizar_creditos()

            self.btn_accion.set_estado(True)
            self.btn_accion.set_texto("🎲  LANZAR" if ronda_activa else "🎲  APOSTAR")
            self.btn_volver.set_estado(True)

            if not ronda_activa:
                self.btn_apuesta_menos.set_estado(True)
                self.btn_apuesta_mas.set_estado(True)
                messagebox.showinfo("Resultado", mensaje)

        if resultado is not None:
            self._animar_dados(resultado, finalizar)
        else:
            finalizar()

    def _actualizar_creditos(self) -> None:
        self.lbl_valor_creditos.config(text=f"{self.jugador.creditos:.0f}")

    def _actualizar_placa_estado(self, ronda_activa, resultado) -> None:
        """Colorea la placa de estado según el resultado de la ronda:
        verde si se ganó, rojo si se perdió, amarillo si hay un punto
        establecido y a la espera del siguiente lanzamiento."""
        punto = self.controlador.obtener_punto()

        if not ronda_activa and resultado is None:
            self.placa_estado.set_estado("LISTO PARA JUGAR", "neutral")
            return

        estado_texto = (self.controlador.obtener_estado() or "").lower()

        if "gan" in estado_texto:
            self.placa_estado.set_estado(f"¡GANASTE! ({resultado.suma})" if resultado else "¡GANASTE!", "ganada")
        elif "perd" in estado_texto:
            self.placa_estado.set_estado(f"PERDISTE ({resultado.suma})" if resultado else "PERDISTE", "perdida")
        elif punto:
            self.placa_estado.set_estado(f"PUNTO: {punto}", "punto")
        else:
            self.placa_estado.set_estado(
                self.controlador.obtener_estado() or "—", "neutral"
            )


if __name__ == "__main__":
    from vistas.casino_com import Jugador

    root = tk.Tk()
    root.title("ROBASINO - Craps")
    root.geometry(f"{ANCHO_REF}x{ALTO_REF}")

    # Ventana normal: se puede maximizar/achicar como cualquier app de
    # escritorio, pero entre estos límites y siempre en proporción 700:750
    # (evita que se deforme el layout al estirar solo un eje).
    root.minsize(ANCHO_MIN, ALTO_MIN)
    root.maxsize(ANCHO_MAX, ALTO_MAX)
    root.wm_aspect(ANCHO_REF, ALTO_REF, ANCHO_REF, ALTO_REF)

    root.configure(bg=BG_DARK)
    jugador_prueba = Jugador("TestPlayer", creditos_iniciales=2000)
    Dados(jugador_prueba, root)
    root.mainloop()