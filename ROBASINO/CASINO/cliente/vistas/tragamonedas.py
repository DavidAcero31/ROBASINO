import math
import tkinter as tk
from tkinter import ttk, messagebox

from vistas.casino_com import Jugador, JuegoBase
from controladores.controlador_tragamonedas import (
    ControladorTragamonedas,
    APUESTA_MINIMA,
    APUESTA_MAXIMA,
    SIMBOLOS,
    SIMBOLOS_IMAGENES,
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
COLOR_RODILLO_BG = "#062012"
COLOR_GANANCIA = "#7CFF9E"
COLOR_PERDIDA = "#ff6b6b"
COLOR_PAYLINE = "#ffd54f"
COLOR_PAYLINE_GLOW = "#8a6d1f"
COLOR_METAL_CLARO = "#3f5c4a"
COLOR_METAL_MEDIO = "#25392d"
COLOR_SOMBRA = "#000000"

FILAS_VISIBLES = 3
ALTO_SIMBOLO_MIN = 90
ALTO_SIMBOLO_MAX = 280

MARGEN_FLECHA = 70
SEPARACION_RODILLOS = 40

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

            id_glow = self.canvas.create_rectangle(
                x, y + alto, x + ancho, y + alto * 2,
                outline=COLOR_PAYLINE_GLOW, width=6, tags=("glow",),
            )
            id_payline = self.canvas.create_rectangle(
                x, y + alto, x + ancho, y + alto * 2,
                outline=COLOR_PAYLINE, width=3, tags=("payline",),
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


class vistaTragamonedas(JuegoBase):
    """Vista pura: construye la ventana y traduce eventos de UI en
    llamadas al controlador. No contiene lógica de juego."""

    def __init__(self, jugador: Jugador, ventana_padre: tk.Tk):
        super().__init__(jugador, "Tragamonedas")

        self._ventana_padre = ventana_padre
        self._controlador = ControladorTragamonedas(jugador)

        self._var_apuesta: tk.IntVar | None = None
        self._var_creditos: tk.StringVar | None = None
        self._var_ultimo_premio: tk.StringVar | None = None
        self._btn_girar: ttk.Button | None = None

        self._imagenes = CargadorImagenes(SIMBOLOS_IMAGENES)
        self._rodillos: list[Rodillo] = [Rodillo(SIMBOLOS, indice=i) for i in range(3)]
        self._canvas_maestro: tk.Canvas | None = None
        self._renderizador: RenderizadorTragamonedas | None = None
        self._gabinete_contenedor: tk.Frame | None = None
        self._dimension_actual: tuple[int, int] = (0, 0)
        self._resize_job = None

        self._simbolos_finales: tuple | None = None
        self._mensaje_pendiente: str | None = None

        self._construir_ventana()

        self._ventana.update_idletasks()
        self._recalcular_dimensiones(
            self._gabinete_contenedor.winfo_height(),
            self._gabinete_contenedor.winfo_width(),
        )

    def _construir_ventana(self) -> None:
        self._ventana = tk.Toplevel(self._ventana_padre)
        self._ventana.title("ROBASINO - Tragamonedas")
        self._ventana.resizable(True, True)
        self._ventana.minsize(900, 640)
        self._ventana.configure(
            bg=COLOR_BG, highlightbackground=COLOR_METAL_CLARO, highlightthickness=3,
        )

        self._ventana.update_idletasks()
        ancho, alto = 1400, 900
        ancho_pantalla = self._ventana.winfo_screenwidth()
        alto_pantalla = self._ventana.winfo_screenheight()
        x = max(0, (ancho_pantalla - ancho) // 2)
        y = max(0, (alto_pantalla - alto) // 2)
        self._ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

        self._configurar_estilos()

        self._ventana.columnconfigure(0, weight=1)
        self._ventana.rowconfigure(0, weight=2)
        self._ventana.rowconfigure(1, weight=6)
        self._ventana.rowconfigure(2, weight=2)

        self._construir_header()
        self._construir_gabinete()
        self._construir_panel_inferior()

    def _configurar_estilos(self) -> None:
        estilo = ttk.Style()
        estilo.theme_use("clam")
        estilo.configure(
            "Girar.TButton",
            font=("Helvetica", 22, "bold"),
            padding=(50, 26),
            background=COLOR_TEXTO,
            foreground=COLOR_BG,
            borderwidth=0,
        )
        estilo.map(
            "Girar.TButton",
            background=[("active", COLOR_TEXTO_SEC), ("disabled", COLOR_METAL_CLARO)],
            foreground=[("disabled", COLOR_TEXTO_SEC)],
        )

    def _crear_panel(self, parent, **kw):
        """Marco 'metal cepillado': realzado por fuera, hundido por dentro."""
        sombra = tk.Frame(parent, bg=COLOR_SOMBRA)
        metal = tk.Frame(sombra, bg=COLOR_METAL_MEDIO, relief="raised", bd=6)
        metal.pack(fill="both", expand=True, padx=(0, 6), pady=(0, 6))
        interior = tk.Frame(metal, bg=COLOR_PANEL, relief="sunken", bd=3, **kw)
        interior.pack(fill="both", expand=True, padx=6, pady=6)
        return sombra, interior

    def _construir_header(self) -> None:
        sombra, interior = self._crear_panel(self._ventana)
        sombra.grid(row=0, column=0, sticky="nsew", padx=40, pady=(20, 6))
        interior.columnconfigure(0, weight=1)
        interior.rowconfigure(0, weight=1)
        interior.rowconfigure(1, weight=1)

        self._var_apuesta = tk.IntVar(value=APUESTA_MINIMA)

        tk.Label(
            interior, text="✦ R O B A S I N O ✦",
            font=("Helvetica", 30, "bold"), fg=COLOR_PAYLINE, bg=COLOR_PANEL,
        ).grid(row=0, column=0, sticky="s")

        tk.Label(
            interior, text="T R A G A M O N E D A S",
            font=("Helvetica", 13, "bold"), fg=COLOR_TEXTO_SEC, bg=COLOR_PANEL,
        ).grid(row=1, column=0, sticky="n", pady=(4, 0))

    def _construir_gabinete(self) -> None:
        contenedor = tk.Frame(self._ventana, bg=COLOR_BG)
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

        self._ventana.bind("<Configure>", self._on_resize_ventana)

    def _on_resize_ventana(self, evento) -> None:
        if evento.widget is not self._ventana:
            return
        if self._resize_job is not None:
            self._ventana.after_cancel(self._resize_job)
        self._resize_job = self._ventana.after(80, self._recalcular_dimensiones_actuales)

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
        sombra, interior = self._crear_panel(self._ventana)
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

        self._crear_indicador(marco_info, "CREDITOS", self._var_creditos, COLOR_TEXTO).grid(
            row=0, column=0, sticky="nsew", padx=8,
        )
        self._crear_indicador(marco_info, "APUESTA", self._var_apuesta, COLOR_PAYLINE).grid(
            row=0, column=1, sticky="nsew", padx=8,
        )
        self._crear_indicador(marco_info, "ULTIMO GANADO", self._var_ultimo_premio, COLOR_GANANCIA).grid(
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
        ).pack(side="left", padx=(0, 8))
        ttk.Spinbox(
            marco_apuesta, from_=APUESTA_MINIMA, to=APUESTA_MAXIMA, increment=10,
            textvariable=self._var_apuesta, width=8, font=("Helvetica", 14),
        ).pack(side="left")
        tk.Label(
            marco_apuesta, text=f"({APUESTA_MINIMA}-{APUESTA_MAXIMA})",
            font=("Helvetica", 11), fg=COLOR_TEXTO_SEC, bg=COLOR_PANEL,
        ).pack(side="left", padx=(8, 0))

        self._btn_girar = ttk.Button(
            marco, text="🎰  GIRAR", command=self._iniciar_giro, style="Girar.TButton",
        )
        self._btn_girar.grid(row=0, column=1, sticky="e")

    def _iniciar_giro(self) -> None:
        monto = self._var_apuesta.get()

        if not self._controlador.validar_apuesta(monto):
            messagebox.showwarning(
                "Créditos insuficientes",
                f"No tienes suficientes créditos para apostar {monto}.\n"
                f"Saldo actual: {self.jugador.creditos}",
            )
            return

        self._btn_girar.config(state="disabled")
        self._simbolos_finales = None
        self._mensaje_pendiente = None
        self._premio_pendiente = 0

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
            self._ventana.after(INTERVALO_ANIMACION_MS, self._programar_tick, rodillo)
        elif rodillo.indice == len(self._rodillos) - 1:
            self._finalizar_giro(self._mensaje_pendiente)

    def _on_resultado(self, mensaje: str, resultado_final: tuple, premio: int) -> None:
        self._ventana.after(0, self._registrar_resultado, mensaje, resultado_final, premio)

    def _registrar_resultado(self, mensaje: str, resultado_final: tuple, premio: int) -> None:
        self._mensaje_pendiente = mensaje
        self._simbolos_finales = resultado_final
        self._premio_pendiente = premio

    def _finalizar_giro(self, mensaje: str) -> None:
        gano = "GANASTE" in mensaje.upper()
        premio = self._premio_pendiente

        self._var_ultimo_premio.set(str(premio))
        self._var_creditos.set(str(self.jugador.creditos))
        self._btn_girar.config(state="normal")

        if gano:
            self._mostrar_popup_ganancia(premio)

    def _mostrar_popup_ganancia(self, premio: int) -> None:
        popup = tk.Toplevel(self._ventana)
        popup.overrideredirect(True)
        popup.transient(self._ventana)
        popup.configure(bg=COLOR_PAYLINE)

        marco = tk.Frame(
            popup, bg=COLOR_PANEL, highlightbackground=COLOR_PAYLINE, highlightthickness=4,
        )
        marco.pack(padx=3, pady=3)

        tk.Label(
            marco, text="TÚ GANASTE!", font=("Helvetica", 26, "bold"),
            fg=COLOR_PAYLINE, bg=COLOR_PANEL,
        ).pack(padx=60, pady=(32, 6))
        tk.Label(
            marco, text=f"+{premio} Creditos", font=("Helvetica", 28, "bold"),
            fg=COLOR_GANANCIA, bg=COLOR_PANEL,
        ).pack(padx=60, pady=(0, 32))

        popup.update_idletasks()
        ref = self._gabinete_contenedor
        x = ref.winfo_rootx() + (ref.winfo_width() - popup.winfo_width()) // 2
        y = ref.winfo_rooty() + (ref.winfo_height() - popup.winfo_height()) // 2
        popup.geometry(f"+{max(0, x)}+{max(0, y)}")

        try:
            popup.attributes("-alpha", 0.0)
            self._desvanecer_entrada(popup, 0.0)
        except tk.TclError:
            pass

        self._ventana.after(2500, lambda p=popup: self._cerrar_popup(p))

    def _desvanecer_entrada(self, popup: tk.Toplevel, alpha: float) -> None:
        if not popup.winfo_exists():
            return
        alpha = min(1.0, alpha + 0.15)
        try:
            popup.attributes("-alpha", alpha)
        except tk.TclError:
            return
        if alpha < 1.0:
            popup.after(20, self._desvanecer_entrada, popup, alpha)

    def _cerrar_popup(self, popup: tk.Toplevel) -> None:
        if popup.winfo_exists():
            popup.destroy()

    def jugar(self, monto: int) -> dict:
        return self._controlador.jugar(monto)
