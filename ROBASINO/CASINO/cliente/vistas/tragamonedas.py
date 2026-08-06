import math
import os
import tkinter as tk
from tkinter import messagebox

from vistas.casino_com import Jugador
from controladores.controlador_tragamonedas import (
    ControladorTragamonedas,
    APUESTA_MINIMA,
    APUESTA_MAXIMA,
    SIMBOLOS,
    SIMBOLOS_IMAGENES,
)
from modelos.modelo_tragamonedas import (
    NOMBRES_SIMBOLOS,
    PREMIOS_A_SIMBOLOS,
)

try:
    from PIL import Image, ImageTk
    _PIL_DISPONIBLE = True
except ImportError:
    _PIL_DISPONIBLE = False


# Paleta — ROBASINO
COLOR_BG = "#01150c"
COLOR_PANEL = "#0d2818"
COLOR_TEXTO = "#4dfa66"
COLOR_TEXTO_SEC = "#8fdba0"
COLOR_RODILLO_BG = "#050F0A"      # casi negro: más contraste para las frutas
COLOR_GANANCIA = "#7CFF9E"
COLOR_PERDIDA = "#ff6b6b"
COLOR_PAYLINE = "#FFD700"         # dorado encendido: marco de la fila ganadora (solo al ganar)
COLOR_PAYLINE_HOVER = "#ffe770"
COLOR_PAYLINE_GLOW = "#f2c94c"    # halo exterior dorado brillante, solo visible al ganar
COLOR_METAL_CLARO = "#3f5c4a"
COLOR_METAL_MEDIO = "#25392d"
COLOR_SOMBRA = "#000000"

# Botón "GIRAR": metálico dorado/ámbar en vez del verde neón, más acorde
# con el resto de la paleta dorada de la interfaz.
COLOR_BTN_GIRAR = "#c9a227"
COLOR_BTN_GIRAR_HOVER = "#e6c34f"
COLOR_BTN_GIRAR_TEXTO = "#1a1207"

# Imagen de fondo (fieltro verde), la misma que en dados.py.
NOMBRE_IMAGEN_FONDO = "FondoDados.png"

FILAS_VISIBLES = 3
ALTO_SIMBOLO_MIN = 90
ALTO_SIMBOLO_MAX = 280

MARGEN_FLECHA = 70
SEPARACION_RODILLOS = 40
PASO_APUESTA = 10  # incremento del stepper de apuesta (-/+)

# Debounce del resize: al empaquetarse dentro de la ventana del menú, el
# tamaño lo controla menu_principal.py — acá solo recalculamos el layout
# interno de los rodillos cuando cambia el tamaño disponible.
RETARDO_RESIZE_MS = 120  # no recalcular en cada pixel de arrastre

# Animación (sin cambios respecto a la versión anterior)
INTERVALO_ANIMACION_MS = 25
STEP_LIBRE_RATIO = 0.15
FRAMES_ACELERACION = 10
MIN_TICKS_LIBRE = (14, 22, 30)
FRAMES_FRENADO_BASE = 16
FRAMES_FRENADO_EXTRA = 4
MIN_VUELTAS_FRENADO = 3
FRAMES_REBOTE = 9
PROFUNDIDAD_REBOTE_RATIO = 0.08


def _localizar_imagen_fondo() -> "str | None":
    """Busca FondoDados.png en la carpeta 'recursos' del proyecto.

    Este archivo (tragamonedas.py) vive en CASINO/cliente/vistas/, y la
    imagen en CASINO/cliente/recursos/FondoDados.png — un nivel arriba de
    'vistas' y luego dentro de 'recursos'. Se dejan además un par de rutas
    alternativas por si se reorganiza el proyecto, para no romper la app
    si no la encuentra."""
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
    """Dibuja un rectángulo con esquinas redondeadas (mismo helper que en
    dados.py: Tkinter no lo soporta nativamente)."""
    puntos = [
        x1 + radio, y1, x2 - radio, y1, x2, y1, x2, y1 + radio,
        x2, y2 - radio, x2, y2, x2 - radio, y2, x1 + radio, y2,
        x1, y2, x1, y2 - radio, x1, y1 + radio, x1, y1,
    ]
    return canvas.create_polygon(puntos, smooth=True, **kwargs)


class BotonRedondeado(tk.Canvas):
    """Botón con esquinas redondeadas y hover, dibujado sobre un Canvas
    (igual patrón que en dados.py, con la paleta de tragamonedas)."""

    def __init__(self, master, texto, comando, ancho=220, alto=56, radio=26,
                 fuente=("Helvetica", 16, "bold"),
                 color_fondo=None, color_fondo_hover=None, color_texto=None):
        super().__init__(master, width=ancho, height=alto,
                          bg=master["bg"], highlightthickness=0, bd=0)
        self.comando = comando
        self.activo = True
        # Colores personalizables por instancia (p. ej. el botón GIRAR usa
        # un dorado metálico en vez del verde por defecto).
        self._color_fondo = color_fondo or COLOR_TEXTO
        self._color_fondo_hover = color_fondo_hover or COLOR_TEXTO_SEC
        self._color_texto = color_texto or COLOR_BG
        self._fondo = rect_redondeado(self, 1, 1, ancho - 1, alto - 1, radio,
                                       fill=self._color_fondo, outline="")
        self._texto = self.create_text(ancho / 2, alto / 2, text=texto,
                                        fill=self._color_texto, font=fuente)
        self.bind("<Button-1>", self._al_hacer_clic)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, dentro: bool) -> None:
        if self.activo:
            self.itemconfig(self._fondo, fill=self._color_fondo_hover if dentro else self._color_fondo)

    def _al_hacer_clic(self, _evento) -> None:
        if self.activo and self.comando:
            self.comando()

    def set_texto(self, texto: str) -> None:
        self.itemconfig(self._texto, text=texto)

    def set_estado(self, activo: bool) -> None:
        self.activo = activo
        self.itemconfig(self._fondo, fill=self._color_fondo if activo else COLOR_METAL_CLARO)
        self.itemconfig(self._texto, fill=self._color_texto if activo else COLOR_TEXTO_SEC)


class BotonCircular(tk.Canvas):
    """Botón circular tipo 'ficha' para el stepper de apuesta (-/+), mismo
    patrón que en dados.py, en vez del ttk.Spinbox anterior."""

    def __init__(self, master, texto, comando, diametro=38,
                 fuente=("Helvetica", 17, "bold")):
        super().__init__(master, width=diametro, height=diametro,
                          bg=master["bg"], highlightthickness=0, bd=0)
        self.comando = comando
        self.activo = True
        self._circulo = self.create_oval(1, 1, diametro - 1, diametro - 1,
                                          fill=COLOR_PAYLINE, outline="")
        self._texto = self.create_text(diametro / 2, diametro / 2, text=texto,
                                        fill=COLOR_BG, font=fuente)
        self.bind("<Button-1>", self._al_hacer_clic)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, dentro: bool) -> None:
        if self.activo:
            self.itemconfig(self._circulo, fill=COLOR_PAYLINE_HOVER if dentro else COLOR_PAYLINE)

    def _al_hacer_clic(self, _evento) -> None:
        if self.activo and self.comando:
            self.comando()

    def set_estado(self, activo: bool) -> None:
        self.activo = activo
        self.itemconfig(self._circulo, fill=COLOR_PAYLINE if activo else COLOR_METAL_MEDIO)
        self.itemconfig(self._texto, fill=COLOR_BG if activo else COLOR_TEXTO_SEC)


class VisorApuesta(tk.Canvas):
    """Pastilla que muestra el monto de apuesta seleccionado, entre los dos
    botones circulares del stepper (mismo patrón que en dados.py)."""

    def __init__(self, master, texto_inicial, ancho=110, alto=44, radio=20,
                 fuente=("Consolas", 17, "bold")):
        super().__init__(master, width=ancho, height=alto,
                          bg=master["bg"], highlightthickness=0, bd=0)
        rect_redondeado(self, 1, 1, ancho - 1, alto - 1, radio,
                         fill=COLOR_RODILLO_BG, outline=COLOR_PAYLINE, width=2)
        self._texto = self.create_text(ancho / 2, alto / 2, text=texto_inicial,
                                        fill=COLOR_PAYLINE, font=fuente)

    def set_valor(self, texto: str) -> None:
        self.itemconfig(self._texto, text=texto)


class CargadorImagenes:
    """Carga cada símbolo una vez y cachea sus PhotoImage por alto pedido."""

    def __init__(self, rutas_por_simbolo: dict[str, str]):
        self._pil_disponible = _PIL_DISPONIBLE
        self._originales: dict[str, "Image.Image"] = {}

        for clave, ruta in rutas_por_simbolo.items():
            if self._pil_disponible:
                self._originales[clave] = Image.open(ruta)
            else:
                self._originales[clave] = tk.PhotoImage(file=ruta)

        self._cache_alto: int | None = None
        self._cache_imagenes: dict[str, "tk.PhotoImage"] = {}

    def relacion_aspecto(self) -> float:
        referencia = next(iter(self._originales.values()))
        if self._pil_disponible:
            ancho, alto = referencia.size
        else:
            ancho, alto = referencia.width(), referencia.height()
        return ancho / alto if alto else 1.0

    def tamano_para_alto(self, alto: int) -> tuple[int, int]:
        if not self._pil_disponible:
            referencia = next(iter(self._originales.values()))
            return referencia.width(), referencia.height()
        ancho = max(1, round(alto * self.relacion_aspecto()))
        return ancho, alto

    def imagenes_para_alto(self, alto: int) -> dict[str, "tk.PhotoImage"]:
        if alto == self._cache_alto:
            return self._cache_imagenes

        if self._pil_disponible:
            ancho, alto = self.tamano_para_alto(alto)
            nuevas = {
                clave: ImageTk.PhotoImage(original.resize((ancho, alto), Image.LANCZOS))
                for clave, original in self._originales.items()
            }
        else:
            nuevas = dict(self._originales)

        self._cache_alto = alto
        self._cache_imagenes = nuevas
        return nuevas


class Rodillo:
    """Estado y animación de un rodillo. No dibuja nada."""

    def __init__(self, orden_simbolos: list, indice: int):
        self.orden = orden_simbolos
        self.indice = indice

        self.ancho = 0
        self.alto = 0

        self.offset = 0.0
        self.base = 0
        self.fase = "detenido"

        self._tick_acel = 0
        self._tick_libre = 0
        self._plan_frenado: list[float] | None = None
        self._plan_rebote: list[float] | None = None
        self._target_base: int | None = None

    def fijar_tamano(self, ancho: int, alto: int) -> None:
        """Cambia el tamaño lógico del símbolo, reescalando offset y
        planes en curso para no romper una animación en progreso."""
        if (ancho, alto) == (self.ancho, self.alto):
            return

        ratio = (alto / self.alto) if self.alto else 1.0
        self.ancho, self.alto = ancho, alto

        if ratio != 1.0:
            self.offset *= ratio
            if self._plan_frenado:
                self._plan_frenado = [p * ratio for p in self._plan_frenado]
            if self._plan_rebote:
                self._plan_rebote = [p * ratio for p in self._plan_rebote]

    def simbolos_visibles(self) -> list[tuple[str, float]]:
        """[(clave_simbolo, y_relativo), ...] en coordenadas locales."""
        n = len(self.orden)
        return [
            (self.orden[(self.base + k) % n], k * self.alto + self.offset)
            for k in (-1, 0, 1, 2)
        ]

    def _avanzar_offset(self, pixeles: float) -> None:
        n = len(self.orden)
        self.offset += pixeles
        while self.offset >= self.alto:
            self.offset -= self.alto
            self.base = (self.base - 1) % n

    def iniciar_giro(self) -> None:
        self.offset = 0.0
        self.fase = "acelerando"
        self._tick_acel = 0
        self._tick_libre = 0
        self._plan_frenado = None
        self._plan_rebote = None
        self._target_base = None

    def tick(self, simbolo_final: str | None) -> bool:
        """Avanza un fotograma de estado. True si sigue animándose."""
        paso_libre = self.alto * STEP_LIBRE_RATIO

        if self.fase == "acelerando":
            self._tick_acel += 1
            t = min(1.0, self._tick_acel / FRAMES_ACELERACION)
            paso = paso_libre * (1 - (1 - t) ** 2)
            self._avanzar_offset(paso)
            if t >= 1.0:
                self.fase = "libre"
            return True

        if self.fase == "libre":
            self._avanzar_offset(paso_libre)
            self._tick_libre += 1
            puede_frenar = (
                simbolo_final is not None
                and self._tick_libre >= MIN_TICKS_LIBRE[self.indice]
            )
            if puede_frenar:
                self._iniciar_frenado(simbolo_final)
            return True

        if self.fase == "frenando":
            paso = self._plan_frenado.pop(0)
            self._avanzar_offset(paso)
            if self._plan_frenado:
                return True
            self.offset = 0.0
            self.base = self._target_base
            self._iniciar_rebote()
            return True

        if self.fase == "rebote":
            paso = self._plan_rebote.pop(0)
            self.offset += paso
            if self._plan_rebote:
                return True
            self.offset = 0.0
            self.fase = "detenido"
            return False

        return False

    def _iniciar_frenado(self, simbolo_final: str) -> None:
        n = len(self.orden)
        target_base = (self.orden.index(simbolo_final) - 1) % n

        vueltas = (self.base - target_base) % n
        while vueltas < MIN_VUELTAS_FRENADO:
            vueltas += n

        distancia_total = (self.alto - self.offset) + (vueltas - 1) * self.alto
        frames = FRAMES_FRENADO_BASE + self.indice * FRAMES_FRENADO_EXTRA

        plan: list[float] = []
        acumulado_previo = 0.0
        for f in range(1, frames + 1):
            t = f / frames
            acumulado = distancia_total * (1 - (1 - t) ** 2)
            plan.append(acumulado - acumulado_previo)
            acumulado_previo = acumulado

        self._target_base = target_base
        self._plan_frenado = plan
        self.fase = "frenando"

    def _iniciar_rebote(self) -> None:
        profundidad = round(self.alto * PROFUNDIDAD_REBOTE_RATIO)
        plan: list[float] = []
        acumulado_previo = 0.0
        for f in range(1, FRAMES_REBOTE + 1):
            t = f / FRAMES_REBOTE
            acumulado = -profundidad * math.sin(math.pi * t)
            plan.append(acumulado - acumulado_previo)
            acumulado_previo = acumulado
        self._plan_rebote = plan
        self.fase = "rebote"


class RenderizadorTragamonedas:
    """Único dueño del Canvas maestro. Dibuja cabinet, rodillos,
    símbolos, payline, flechas, glow y overlays, en ese orden."""

    ORDEN_CAPAS = (
        "cabinet",
        "ventana_rodillo",
        "simbolo",
        "payline",
        "flecha",
        "glow",
        "mensaje_flotante",
        "efecto_temporal",
    )

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas

        self._imagenes: dict[str, "tk.PhotoImage"] = {}
        self._reel_layout: list[dict] = []

        self._id_cabinet: int | None = None
        self._ids_ventana: list[int] = []
        self._ids_simbolos: list[list[int]] = []
        self._ids_glow: list[int] = []
        self._ids_payline: list[int] = []
        self._id_flecha_izq: int | None = None
        self._id_flecha_der: int | None = None

        self._layout_listo = False

    def configurar_layout(
        self,
        ancho_canvas: int,
        alto_canvas: int,
        reel_layout: list[dict],
        imagenes: dict[str, "tk.PhotoImage"],
    ) -> None:
        """Recrea los ítems fijos con la nueva geometría (solo en resize)."""
        self._imagenes = imagenes
        self._reel_layout = reel_layout

        self.canvas.configure(width=ancho_canvas, height=alto_canvas)
        self.canvas.delete("all")
        self._crear_items_fijos(ancho_canvas, alto_canvas)
        self._layout_listo = True

    def _crear_items_fijos(self, ancho_canvas: int, alto_canvas: int) -> None:
        self._id_cabinet = self.canvas.create_rectangle(
            0, 0, ancho_canvas, alto_canvas,
            fill=COLOR_RODILLO_BG, outline="", tags=("cabinet",),
        )

        self._ids_ventana = []
        self._ids_simbolos = []
        self._ids_glow = []
        self._ids_payline = []

        for reel in self._reel_layout:
            x, y, ancho, alto = reel["x"], reel["y"], reel["ancho"], reel["alto"]
            alto_visible = alto * FILAS_VISIBLES

            id_ventana = self.canvas.create_rectangle(
                x, y, x + ancho, y + alto_visible,
                fill=COLOR_RODILLO_BG, outline=COLOR_METAL_MEDIO, width=2,
                tags=("ventana_rodillo",),
            )
            self._ids_ventana.append(id_ventana)

            ids_slots = [
                self.canvas.create_image(x, y, anchor="nw", tags=("simbolo",))
                for _ in range(4)
            ]
            self._ids_simbolos.append(ids_slots)

            # Marco de "fruta ganadora" (halo + borde dorado) por rodillo:
            # oculto por defecto. Solo se hace visible al ganar, mediante
            # mostrar_marco_ganador()/ocultar_marco_ganador(). Nada se
            # dibuja aquí encima de las frutas mientras se juega o en
            # reposo: los tres rodillos se ven iguales entre sí.
            id_glow = self.canvas.create_rectangle(
                x, y + alto, x + ancho, y + alto * 2,
                outline=COLOR_PAYLINE_GLOW, width=6,
                outlinestipple="gray50", state="hidden", tags=("glow",),
            )
            id_payline = self.canvas.create_rectangle(
                x, y + alto, x + ancho, y + alto * 2,
                outline=COLOR_PAYLINE, width=2, state="hidden",
                tags=("payline",),
            )
            self._ids_glow.append(id_glow)
            self._ids_payline.append(id_payline)

        centro_y = alto_canvas / 2
        if self._reel_layout:
            primero = self._reel_layout[0]
            ultimo = self._reel_layout[-1]
            x_izq = primero["x"] / 2
            x_der = ultimo["x"] + ultimo["ancho"] + (ancho_canvas - (ultimo["x"] + ultimo["ancho"])) / 2
        else:
            x_izq = ancho_canvas * 0.05
            x_der = ancho_canvas * 0.95

        self._id_flecha_izq = self.canvas.create_text(
            x_izq, centro_y, text="►",
            font=("Helvetica", 26, "bold"), fill=COLOR_PAYLINE, tags=("flecha",),
        )
        self._id_flecha_der = self.canvas.create_text(
            x_der, centro_y, text="◄",
            font=("Helvetica", 26, "bold"), fill=COLOR_PAYLINE, tags=("flecha",),
        )

        self._elevar_capas()

    def mostrar_marco_ganador(self) -> None:
        """Revela el halo + borde dorado sobre la fila central. Solo se
        llama cuando el giro terminó en una combinación ganadora."""
        self.canvas.itemconfigure("glow", state="normal")
        self.canvas.itemconfigure("payline", state="normal")
        self._elevar_capas()

    def ocultar_marco_ganador(self) -> None:
        """Esconde el halo + borde dorado: estado por defecto mientras se
        juega o en reposo, para que los tres rodillos luzcan iguales."""
        self.canvas.itemconfigure("glow", state="hidden")
        self.canvas.itemconfigure("payline", state="hidden")

    def _elevar_capas(self) -> None:
        for capa in self.ORDEN_CAPAS:
            self.canvas.tag_raise(capa)

    def redibujar_frame(self, rodillos: list[Rodillo]) -> None:
        """Redibuja todos los rodillos (pintado inicial / tras resize)."""
        if not self._layout_listo:
            return
        for rodillo in rodillos:
            self.actualizar_rodillo(rodillo)

    def actualizar_rodillo(self, rodillo: Rodillo) -> None:
        """Actualiza solo los ítems de un rodillo (un tick de animación)."""
        if not self._layout_listo:
            return
        layout = self._reel_layout[rodillo.indice]
        ids_slots = self._ids_simbolos[rodillo.indice]
        x = layout["x"]
        y_base = layout["y"]
        for slot, (clave, y_local) in enumerate(rodillo.simbolos_visibles()):
            item_id = ids_slots[slot]
            self.canvas.coords(item_id, x, y_base + y_local)
            self.canvas.itemconfig(item_id, image=self._imagenes[clave])
        self._elevar_capas()

    # Puntos de extensión para efectos futuros (paylines extra, jackpots,
    # partículas...) sin tocar el controlador ni Rodillo.

    def mostrar_mensaje_flotante(
        self, texto: str, x: float, y: float, color: str = COLOR_GANANCIA,
    ) -> int:
        item_id = self.canvas.create_text(
            x, y, text=texto, fill=color, font=("Helvetica", 20, "bold"),
            tags=("mensaje_flotante",),
        )
        self._elevar_capas()
        return item_id

    def quitar_efecto(self, item_id: int) -> None:
        self.canvas.delete(item_id)


class vistaTragamonedas(tk.Frame):
    """Vista del juego de Tragamonedas. Mismo patrón que Dados: un Frame
    que se empaqueta directamente en la ventana del menú principal, en
    vez de abrir una ventana (Toplevel) propia."""

    def __init__(self, jugador: Jugador, master: tk.Tk):
        super().__init__(
            master, bg=COLOR_BG,
            highlightbackground=COLOR_METAL_CLARO, highlightthickness=3,
        )
        self.master = master
        self.jugador = jugador
        self._controlador = ControladorTragamonedas(jugador)

        # Título nativo de la ventana: la raíz (tk.Tk) es compartida con
        # menu_principal.py, así que se actualiza aquí para reflejar el
        # nuevo nombre del juego mientras esta vista está activa.
        try:
            self.master.title("NOVATIC ROYALE - Tragamonedas")
        except tk.TclError:
            pass

        self._var_apuesta: tk.IntVar | None = None
        self._var_creditos: tk.StringVar | None = None
        self._var_ultimo_premio: tk.StringVar | None = None
        self._btn_girar: "BotonRedondeado | None" = None

        self._imagenes = CargadorImagenes(SIMBOLOS_IMAGENES)
        self._rodillos: list[Rodillo] = [Rodillo(SIMBOLOS, indice=i) for i in range(3)]
        self._canvas_maestro: tk.Canvas | None = None
        self._renderizador: RenderizadorTragamonedas | None = None
        self._gabinete_contenedor: tk.Frame | None = None
        self._dimension_actual: tuple[int, int] = (0, 0)
        self._resize_job = None

        self._simbolos_finales: tuple | None = None
        self._mensaje_pendiente: str | None = None
        self._rodillos_terminados: set[int] = set()

        # Banner de victoria: pequeño overlay temporal (no un Toplevel),
        # oculto por defecto; se muestra 1.5s al ganar y se puede ocultar
        # antes de tiempo si el jugador vuelve a presionar GIRAR.
        self._banner_victoria: tk.Frame | None = None
        self._lbl_banner_victoria: tk.Label | None = None
        self._banner_after_id: str | None = None

        self.pack(fill="both", expand=True)

        # ------------------------------------------------------------
        # Canvas de fondo (fieltro), mismo patrón que en dados.py: ocupa
        # toda la ventana y va detrás de todo lo demás. El resto de los
        # paneles se crea después (más abajo, en _construir_layout), por
        # lo que Tkinter los apila automáticamente por encima.
        # ------------------------------------------------------------
        self._imagen_fondo_pil = None
        self._imagen_fondo_tk = None
        self._id_imagen_fondo = None
        self._fondo_resize_after_id = None

        self.canvas_fondo = tk.Canvas(self, highlightthickness=0, bd=0, bg=COLOR_BG)
        self.canvas_fondo.place(x=0, y=0, relwidth=1, relheight=1)
        self._cargar_imagen_fondo()
        self.canvas_fondo.bind("<Configure>", self._on_configure_fondo)

        self._construir_layout()

        self.update_idletasks()
        self._recalcular_dimensiones(
            self._gabinete_contenedor.winfo_height(),
            self._gabinete_contenedor.winfo_width(),
        )

    def _construir_layout(self) -> None:
        # El tamaño y proporción de la ventana ya los administra
        # menu_principal.py sobre self.master — acá solo se arma la
        # disposición interna en 3 filas (header / gabinete / panel).
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=2)
        self.rowconfigure(1, weight=6)
        self.rowconfigure(2, weight=2)

        self._construir_header()
        self._construir_gabinete()
        self._construir_panel_inferior()

    def _crear_panel(self, parent, **kw):
        """Marco 'metal cepillado': realzado por fuera, hundido por dentro."""
        sombra = tk.Frame(parent, bg=COLOR_SOMBRA)
        metal = tk.Frame(sombra, bg=COLOR_METAL_MEDIO, relief="raised", bd=6)
        metal.pack(fill="both", expand=True, padx=(0, 6), pady=(0, 6))
        interior = tk.Frame(metal, bg=COLOR_PANEL, relief="sunken", bd=3, **kw)
        interior.pack(fill="both", expand=True, padx=6, pady=6)
        return sombra, interior

    def _construir_header(self) -> None:
        sombra, interior = self._crear_panel(self)
        sombra.grid(row=0, column=0, sticky="nsew", padx=40, pady=(20, 6))
        interior.columnconfigure(0, weight=1)
        interior.rowconfigure(0, weight=1)
        interior.rowconfigure(1, weight=1)

        self._var_apuesta = tk.IntVar(value=APUESTA_MINIMA)

        tk.Label(
            interior, text="✦ N O V A T I C   R O Y A L E ✦",
            font=("Helvetica", 30, "bold"), fg=COLOR_PAYLINE, bg=COLOR_PANEL,
        ).grid(row=0, column=0, sticky="s")

        tk.Label(
            interior, text="T R A G A M O N E D A S",
            font=("Helvetica", 13, "bold"), fg=COLOR_TEXTO_SEC, bg=COLOR_PANEL,
        ).grid(row=1, column=0, sticky="n", pady=(4, 0))

        # Botón de ayuda (❓), esquina superior derecha — mismo patrón que
        # en dados.py: no ensucia la pantalla si el jugador ya sabe jugar.
        self._panel_reglas_visible = False
        self.btn_ayuda = BotonCircular(
            interior, "❓", self._alternar_panel_reglas, diametro=32,
            fuente=("Helvetica", 14, "bold"),
        )
        self.btn_ayuda.place(relx=1.0, x=-14, y=14, anchor="ne")

        # Botón para volver al menú principal, esquina superior izquierda.
        self.btn_volver = BotonRedondeado(
            interior, "← Menú", self._volver_menu, ancho=110, alto=32, radio=16,
            fuente=("Helvetica", 12, "bold"),
        )
        self.btn_volver.place(x=14, y=14, anchor="nw")

        self._construir_panel_reglas()

    # ------------------------------------------------------------------
    # Panel de reglas (overlay desplegable, para quien no sepa jugar)
    # ------------------------------------------------------------------

    def _construir_panel_reglas(self) -> None:
        """Construye el panel de ayuda como overlay sobre toda la ventana
        (usa place() en vez de pack/grid para no alterar el layout fijo
        del gabinete). Arranca oculto; _alternar_panel_reglas lo muestra
        centrado, con lift() para quedar por encima de los rodillos."""
        self.panel_reglas = tk.Frame(self, bg=COLOR_SOMBRA)

        marco = tk.Frame(
            self.panel_reglas, bg=COLOR_PANEL,
            highlightbackground=COLOR_PAYLINE, highlightthickness=3,
        )
        marco.pack(padx=3, pady=3)

        cabecera = tk.Frame(marco, bg=COLOR_PANEL)
        cabecera.pack(fill="x", padx=22, pady=(18, 6))
        tk.Label(
            cabecera, text="¿Cómo se juega?", font=("Helvetica", 17, "bold"),
            fg=COLOR_PAYLINE, bg=COLOR_PANEL,
        ).pack(side="left")
        BotonCircular(
            cabecera, "✕", self._alternar_panel_reglas, diametro=26,
            fuente=("Helvetica", 12, "bold"),
        ).pack(side="right")

        reglas = (
            "• Elige tu apuesta con los botones – / + y presiona GIRAR.\n"
            "• Si los 3 rodillos caen en el mismo símbolo, ganas.\n"
            "• El premio = apuesta × multiplicador del símbolo ganador.\n"
            "• Cualquier otra combinación no paga nada.\n"
            "• Cuanto más raro el símbolo, mayor el premio."
        )
        tk.Label(
            marco, text=reglas, bg=COLOR_PANEL, fg=COLOR_TEXTO_SEC,
            font=("Helvetica", 11), justify="left", anchor="w",
        ).pack(anchor="w", padx=22, pady=(0, 12), fill="x")

        tk.Label(
            marco, text="Pagos por 3 símbolos iguales:",
            font=("Helvetica", 12, "bold"), fg=COLOR_PAYLINE, bg=COLOR_PANEL,
        ).pack(anchor="w", padx=22, pady=(0, 6))

        tabla = tk.Frame(marco, bg=COLOR_PANEL)
        tabla.pack(fill="x", padx=22)

        for multiplicador in sorted(PREMIOS_A_SIMBOLOS):
            simbolo = PREMIOS_A_SIMBOLOS[multiplicador][0]
            nombre = NOMBRES_SIMBOLOS[simbolo]
            fila = tk.Frame(tabla, bg=COLOR_PANEL)
            fila.pack(fill="x", pady=2)
            tk.Label(
                fila, text=f"{nombre}  ×3", font=("Helvetica", 11),
                fg=COLOR_TEXTO_SEC, bg=COLOR_PANEL, anchor="w",
            ).pack(side="left")
            tk.Label(
                fila, text=f"paga x{multiplicador}", font=("Helvetica", 11, "bold"),
                fg=COLOR_GANANCIA, bg=COLOR_PANEL, anchor="e",
            ).pack(side="right")

        tk.Frame(marco, bg=COLOR_PANEL, height=8).pack()

    def _alternar_panel_reglas(self) -> None:
        if self._panel_reglas_visible:
            self.panel_reglas.place_forget()
        else:
            self.panel_reglas.place(relx=0.5, rely=0.5, anchor="center")
            self.panel_reglas.lift()
        self._panel_reglas_visible = not self._panel_reglas_visible

    def _construir_gabinete(self) -> None:
        contenedor = tk.Frame(self, bg=COLOR_BG)
        contenedor.grid(row=1, column=0, sticky="nsew", padx=40, pady=10)
        contenedor.columnconfigure(0, weight=1)
        contenedor.rowconfigure(0, weight=1)
        self._gabinete_contenedor = contenedor

        sombra, interior = self._crear_panel(contenedor, padx=20, pady=20)
        sombra.grid(row=0, column=0)

        hueco = tk.Frame(interior, bg=COLOR_RODILLO_BG, relief="sunken", bd=6)
        hueco.pack(padx=10, pady=10)

        # Único Canvas maestro: cabinet, rodillos, símbolos, flechas,
        # payline y glow se dibujan todos aquí.
        self._canvas_maestro = tk.Canvas(hueco, bg=COLOR_RODILLO_BG, highlightthickness=0)
        self._canvas_maestro.pack(padx=20, pady=20)
        self._renderizador = RenderizadorTragamonedas(self._canvas_maestro)

        # Banner de victoria: pequeño overlay dorado sobre el gabinete,
        # flotando con place() (no un Toplevel) para poder ocultarlo al
        # instante sin depender de fundidos ni ventanas aparte. Arranca
        # sin colocar (oculto).
        self._banner_victoria = tk.Frame(
            hueco, bg=COLOR_PANEL, highlightbackground=COLOR_PAYLINE,
            highlightthickness=2,
        )
        self._lbl_banner_victoria = tk.Label(
            self._banner_victoria, text="", font=("Helvetica", 14, "bold"),
            fg=COLOR_PAYLINE, bg=COLOR_PANEL, padx=16, pady=6,
        )
        self._lbl_banner_victoria.pack()

        # Se escucha el resize de la ventana raíz (mismo patrón que
        # dados.py), no el de este Frame: así se recalcula el layout de
        # los rodillos cuando el jugador redimensiona la ventana del menú.
        # add="+" evita pisar el binding propio de MenuPrincipal.
        self._id_bind_configure = self.master.bind(
            "<Configure>", self._on_resize_ventana, add="+"
        )

    # ------------------------------------------------------------------
    # Fondo de fieltro (Canvas principal) — mismo mecanismo que dados.py
    # ------------------------------------------------------------------

    def _cargar_imagen_fondo(self) -> None:
        if not _PIL_DISPONIBLE:
            return  # sin Pillow: se mantiene el color sólido COLOR_BG
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

    def _on_resize_ventana(self, evento) -> None:
        if evento.widget is not self.master:
            return
        if self._resize_job is not None:
            self.master.after_cancel(self._resize_job)
        self._resize_job = self.master.after(RETARDO_RESIZE_MS, self._recalcular_dimensiones_actuales)

    def _recalcular_dimensiones_actuales(self) -> None:
        self._recalcular_dimensiones(
            self._gabinete_contenedor.winfo_height(),
            self._gabinete_contenedor.winfo_width(),
        )

    def _recalcular_dimensiones(self, alto_disponible: int, ancho_disponible: int) -> None:
        """Calcula el tamaño de símbolo según el espacio disponible y
        arma el layout de los 3 rodillos para el Canvas maestro."""
        self._resize_job = None
        if alto_disponible <= 1 or ancho_disponible <= 1:
            return

        margen_vertical = 0.85
        margen_horizontal_fijo = MARGEN_FLECHA * 2 + SEPARACION_RODILLOS * 2

        alto_reel = alto_disponible * margen_vertical
        alto_simbolo = int(alto_reel / FILAS_VISIBLES)

        ancho_estimado, _ = self._imagenes.tamano_para_alto(alto_simbolo)
        ancho_disponible_por_reel = max(1, (ancho_disponible - margen_horizontal_fijo) // 3)
        if ancho_estimado > ancho_disponible_por_reel:
            alto_simbolo = int(ancho_disponible_por_reel / self._imagenes.relacion_aspecto())

        alto_simbolo = max(ALTO_SIMBOLO_MIN, min(ALTO_SIMBOLO_MAX, alto_simbolo))
        ancho_simbolo, alto_simbolo = self._imagenes.tamano_para_alto(alto_simbolo)

        if (ancho_simbolo, alto_simbolo) == self._dimension_actual:
            return
        self._dimension_actual = (ancho_simbolo, alto_simbolo)

        imagenes_compartidas = self._imagenes.imagenes_para_alto(alto_simbolo)
        for rodillo in self._rodillos:
            rodillo.fijar_tamano(ancho_simbolo, alto_simbolo)

        reel_layout = [
            {
                "x": MARGEN_FLECHA + i * (ancho_simbolo + SEPARACION_RODILLOS),
                "y": 0,
                "ancho": ancho_simbolo,
                "alto": alto_simbolo,
            }
            for i in range(3)
        ]
        ancho_canvas = MARGEN_FLECHA * 2 + ancho_simbolo * 3 + SEPARACION_RODILLOS * 2
        alto_canvas = alto_simbolo * FILAS_VISIBLES

        self._renderizador.configurar_layout(
            ancho_canvas=ancho_canvas,
            alto_canvas=alto_canvas,
            reel_layout=reel_layout,
            imagenes=imagenes_compartidas,
        )
        self._renderizador.redibujar_frame(self._rodillos)

    def _construir_panel_inferior(self) -> None:
        sombra, interior = self._crear_panel(self)
        sombra.grid(row=2, column=0, sticky="nsew", padx=40, pady=(6, 24))
        interior.columnconfigure(0, weight=1)
        interior.rowconfigure(0, weight=1)
        interior.rowconfigure(1, weight=1)

        self._construir_indicadores(interior)
        self._construir_controles(interior)

    def _construir_indicadores(self, parent) -> None:
        marco_info = tk.Frame(parent, bg=COLOR_PANEL)
        marco_info.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 14))
        marco_info.columnconfigure(0, weight=1)
        marco_info.columnconfigure(1, weight=1)
        marco_info.columnconfigure(2, weight=1)

        self._var_creditos = tk.StringVar(value=str(self.jugador.creditos))
        self._var_ultimo_premio = tk.StringVar(value="0")

        self._crear_indicador(marco_info, "CREDITOS", self._var_creditos, COLOR_PAYLINE).grid(
            row=0, column=0, sticky="nsew", padx=8,
        )
        self._crear_indicador(marco_info, "APUESTA", self._var_apuesta, COLOR_PAYLINE).grid(
            row=0, column=1, sticky="nsew", padx=8,
        )
        self._crear_indicador(marco_info, "ULTIMO GANADO", self._var_ultimo_premio, COLOR_PAYLINE).grid(
            row=0, column=2, sticky="nsew", padx=8,
        )

    def _crear_indicador(self, parent, etiqueta: str, variable: tk.Variable, color_valor: str) -> tk.Frame:
        marco = tk.Frame(parent, bg=COLOR_RODILLO_BG, relief="sunken", bd=3)
        tk.Label(
            marco, text=etiqueta, font=("Helvetica", 11, "bold"),
            fg=COLOR_TEXTO_SEC, bg=COLOR_RODILLO_BG,
        ).pack(pady=(10, 2))
        tk.Label(
            marco, textvariable=variable, font=("Consolas", 22, "bold"),
            fg=color_valor, bg=COLOR_RODILLO_BG,
        ).pack(pady=(0, 10), padx=24)
        return marco

    def _construir_controles(self, parent) -> None:
        marco = tk.Frame(parent, bg=COLOR_PANEL)
        marco.grid(row=1, column=0, sticky="ew", padx=16)
        marco.columnconfigure(0, weight=1)
        marco.columnconfigure(1, weight=1)

        marco_apuesta = tk.Frame(marco, bg=COLOR_PANEL)
        marco_apuesta.grid(row=0, column=0, sticky="w")
        tk.Label(
            marco_apuesta, text="Apuesta:", font=("Helvetica", 14),
            fg=COLOR_TEXTO_SEC, bg=COLOR_PANEL,
        ).pack(side="left", padx=(0, 10))

        self._btn_apuesta_menos = BotonCircular(
            marco_apuesta, "–", lambda: self._cambiar_apuesta(-PASO_APUESTA)
        )
        self._btn_apuesta_menos.pack(side="left", padx=(0, 8))

        self._visor_apuesta = VisorApuesta(marco_apuesta, str(self._var_apuesta.get()))
        self._visor_apuesta.pack(side="left")

        self._btn_apuesta_mas = BotonCircular(
            marco_apuesta, "+", lambda: self._cambiar_apuesta(PASO_APUESTA)
        )
        self._btn_apuesta_mas.pack(side="left", padx=(8, 10))

        tk.Label(
            marco_apuesta, text=f"({APUESTA_MINIMA}-{APUESTA_MAXIMA})",
            font=("Helvetica", 11), fg=COLOR_TEXTO_SEC, bg=COLOR_PANEL,
        ).pack(side="left")

        self._btn_girar = BotonRedondeado(
            marco, "🎰  GIRAR", self._iniciar_giro,
            color_fondo=COLOR_BTN_GIRAR,
            color_fondo_hover=COLOR_BTN_GIRAR_HOVER,
            color_texto=COLOR_BTN_GIRAR_TEXTO,
        )
        self._btn_girar.grid(row=0, column=1, sticky="e")

    def _volver_menu(self) -> None:
        if not self._btn_girar.activo:
            return  # no se puede salir a mitad de un giro

        # Se cancela cualquier resize pendiente y se desengancha SOLO el
        # binding propio (por funcid), sin tocar el que usa MenuPrincipal
        # para reescalarse a sí mismo.
        if self._resize_job is not None:
            self.master.after_cancel(self._resize_job)
            self._resize_job = None
        if self._fondo_resize_after_id is not None:
            self.master.after_cancel(self._fondo_resize_after_id)
            self._fondo_resize_after_id = None
        if self._banner_after_id is not None:
            self.after_cancel(self._banner_after_id)
            self._banner_after_id = None
        self.master.unbind("<Configure>", self._id_bind_configure)

        self.destroy()

    def _cambiar_apuesta(self, delta: int) -> None:
        if not self._btn_girar.activo:
            return  # bloqueado mientras hay un giro en curso
        nuevo_valor = max(APUESTA_MINIMA, min(APUESTA_MAXIMA, self._var_apuesta.get() + delta))
        self._var_apuesta.set(nuevo_valor)
        self._visor_apuesta.set_valor(str(nuevo_valor))

    def _iniciar_giro(self) -> None:
        monto = self._var_apuesta.get()

        if not self._controlador.validar_apuesta(monto):
            messagebox.showwarning(
                "Créditos insuficientes",
                f"No tienes suficientes créditos para apostar {monto}.\n"
                f"Saldo actual: {self.jugador.creditos}",
            )
            return

        self._btn_girar.set_estado(False)
        self._btn_apuesta_menos.set_estado(False)
        self._btn_apuesta_mas.set_estado(False)
        self.btn_volver.set_estado(False)
        self._simbolos_finales = None
        self._mensaje_pendiente = None
        self._premio_pendiente = 0
        self._rodillos_terminados.clear()

        # Reset inmediato: si el banner de "¡GANASTE!" y el marco dorado de
        # la ronda anterior seguían visibles (el jugador presionó GIRAR
        # antes de que se ocultaran solos a los 1.5s), se esconden ya
        # mismo para dar paso a la nueva animación.
        self._ocultar_indicadores_victoria()

        # La apuesta ya se descontó de verdad en validar_apuesta() (arriba).
        # Se refleja aquí de inmediato para que el jugador vea el descuento
        # al instante, en vez de esperar a que termine la animación.
        self._var_creditos.set(str(self.jugador.creditos))

        for rodillo in self._rodillos:
            rodillo.iniciar_giro()
            self._programar_tick(rodillo)

        self._controlador.iniciar_giro(monto, on_resultado=self._on_resultado)

    def _programar_tick(self, rodillo: Rodillo) -> None:
        simbolo_final = (
            self._simbolos_finales[rodillo.indice]
            if self._simbolos_finales is not None else None
        )
        sigue = rodillo.tick(simbolo_final)
        self._renderizador.actualizar_rodillo(rodillo)
        if sigue:
            self.after(INTERVALO_ANIMACION_MS, self._programar_tick, rodillo)
            return

        # Este rodillo ya terminó de animarse. No asumimos que el índice
        # más alto siempre es el último en frenar: esperamos a que TODOS
        # los rodillos hayan terminado antes de mostrar el resultado, así
        # el indicador de créditos nunca se queda desactualizado aunque
        # cambie el orden en que frenan.
        self._rodillos_terminados.add(rodillo.indice)
        if len(self._rodillos_terminados) == len(self._rodillos):
            self._verificar_payline()
            self._finalizar_giro(self._mensaje_pendiente)

    def _verificar_payline(self) -> None:
        """Garantiza que el símbolo mostrado en la línea de pago (fila del
        medio) de cada rodillo coincida exactamente con resultado_final.

        La animación normalmente ya deja cada rodillo en el símbolo
        correcto, pero esto actúa como red de seguridad: si por cualquier
        razón (timing, reordenamiento de frenado, etc.) un rodillo quedó
        detenido en un símbolo distinto al que el controlador decidió,
        aquí se corrige la posición ANTES de mostrar el mensaje de
        ganaste/perdiste, para que la pantalla nunca contradiga el
        resultado real de la partida.
        """
        if self._simbolos_finales is None:
            return

        for rodillo in self._rodillos:
            esperado = self._simbolos_finales[rodillo.indice]
            n = len(rodillo.orden)
            simbolo_actual = rodillo.orden[(rodillo.base + 1) % n]

            if simbolo_actual != esperado:
                print(
                    f"[Tragamonedas] Aviso: rodillo {rodillo.indice} mostraba "
                    f"'{simbolo_actual}' pero el resultado real era '{esperado}'. "
                    f"Corrigiendo posición."
                )
                rodillo.base = (rodillo.orden.index(esperado) - 1) % n
                rodillo.offset = 0.0
                self._renderizador.actualizar_rodillo(rodillo)

    def _on_resultado(self, mensaje: str, resultado_final: tuple, premio: int) -> None:
        self.after(0, self._registrar_resultado, mensaje, resultado_final, premio)

    def _registrar_resultado(self, mensaje: str, resultado_final: tuple, premio: int) -> None:
        self._mensaje_pendiente = mensaje
        self._simbolos_finales = resultado_final
        self._premio_pendiente = premio

    def _finalizar_giro(self, mensaje: str) -> None:
        gano = "GANASTE" in mensaje.upper()
        premio = self._premio_pendiente

        self._var_ultimo_premio.set(str(premio))
        self._var_creditos.set(str(self.jugador.creditos))
        self._btn_girar.set_estado(True)
        self._btn_apuesta_menos.set_estado(True)
        self._btn_apuesta_mas.set_estado(True)
        self.btn_volver.set_estado(True)

        if gano:
            self._mostrar_indicadores_victoria(premio)
        else:
            # Por las dudas: en una ronda perdida no debe quedar visible
            # ni el marco dorado ni el banner de una ronda anterior.
            self._ocultar_indicadores_victoria()

    def _mostrar_indicadores_victoria(self, premio: int) -> None:
        """Muestra el marco dorado de la fila ganadora junto con un banner
        pequeño y elegante que se oculta solo a los 1.5s."""
        self._renderizador.mostrar_marco_ganador()

        self._lbl_banner_victoria.config(text=f"✦ ¡GANASTE! +{premio} ✦")
        self._banner_victoria.place(relx=0.5, rely=0.06, anchor="n")
        self._banner_victoria.lift()

        if self._banner_after_id is not None:
            self.after_cancel(self._banner_after_id)
        self._banner_after_id = self.after(1500, self._ocultar_indicadores_victoria)

    def _ocultar_indicadores_victoria(self) -> None:
        """Esconde el banner y el marco dorado. Se llama automáticamente
        a los 1.5s, y también de inmediato si el jugador vuelve a
        presionar GIRAR antes de que ese tiempo se cumpla."""
        if self._banner_after_id is not None:
            self.after_cancel(self._banner_after_id)
            self._banner_after_id = None
        if self._banner_victoria is not None:
            self._banner_victoria.place_forget()
        if self._renderizador is not None:
            self._renderizador.ocultar_marco_ganador()

    def jugar(self, monto: int) -> dict:
        return self._controlador.jugar(monto)