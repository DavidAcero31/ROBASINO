import math
import random
import time
import tkinter as tk
from tkinter import messagebox

from controladores.controlador_dados import ControladorDados

# ----------------------------------------------------------------------
# Paleta consistente con tragamonedas.py
# ----------------------------------------------------------------------
BG_DARK = "#0a1f12"
BG_PANEL = "#0f2a1a"
BORDER = "#5a7a5a"
GOLD = "#f0c04a"
MINT_TEXT = "#8fd6a8"
GREEN_VALUE = "#4ade80"
BTN_BG = "#c8f0d0"
BTN_BG_HOVER = "#a9e6bb"
BTN_BG_OFF = "#4a5a4f"
BTN_FG = "#0a1f12"
BTN_FG_OFF = "#8a988e"

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

POSICIONES_PUNTOS = {
    1: [(0.5, 0.5)],
    2: [(0.25, 0.25), (0.75, 0.75)],
    3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
    4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
    5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
    6: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.5), (0.75, 0.5), (0.25, 0.75), (0.75, 0.75)],
}


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


class Dados(tk.Frame):
    """Vista del juego de Craps, con el mismo lenguaje visual de Tragamonedas."""

    def __init__(self, jugador, master: tk.Tk):
        super().__init__(master, bg=BG_DARK)
        self.master = master
        self.jugador = jugador
        self.controlador = ControladorDados(jugador)
        self.pack(fill="both", expand=True)

        self._animando = False

        self._construir_encabezado()
        self._construir_panel_dados()
        self._construir_barra_estadisticas()
        self._actualizar_creditos()

    # ------------------------------------------------------------------
    # Encabezado (doble marco, título dorado + subtítulo)
    # ------------------------------------------------------------------

    def _construir_encabezado(self) -> None:
        externo = tk.Frame(self, bg=BG_DARK, highlightbackground=BORDER,
                            highlightthickness=2, bd=0)
        externo.pack(fill="x", padx=15, pady=(15, 10))

        interno = tk.Frame(externo, bg=BG_PANEL, highlightbackground=BORDER,
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

    # ------------------------------------------------------------------
    # Panel de dados (doble marco central)
    # ------------------------------------------------------------------

    def _construir_panel_dados(self) -> None:
        externo = tk.Frame(self, bg=BG_DARK, highlightbackground=BORDER,
                            highlightthickness=2)
        externo.pack(fill="both", expand=True, padx=15, pady=10)

        medio = tk.Frame(externo, bg=BG_PANEL, highlightbackground=BORDER,
                          highlightthickness=1)
        medio.pack(fill="both", expand=True, padx=8, pady=8)

        interno = tk.Frame(medio, bg=BG_DARK, highlightbackground=BORDER,
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

        self.lbl_estado = tk.Label(
            medio, text="Estado: -", bg=BG_PANEL, fg=MINT_TEXT,
            font=("Arial", 12, "bold")
        )
        self.lbl_estado.pack(pady=(0, 4))

        self.lbl_punto = tk.Label(
            medio, text="Punto: -", bg=BG_PANEL, fg=GOLD,
            font=("Arial", 12, "bold")
        )
        self.lbl_punto.pack(pady=(0, 10))

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
        ancho_cara = CARA_TAM * escala_x
        prof = PROF * (0.4 + 0.6 * escala_x)  # el volumen también se atenúa un poco de canto

        x1 = MARGEN_IZQ + (CARA_TAM - ancho_cara) / 2
        x2 = x1 + ancho_cara
        y1 = MARGEN_SUP + offset_y
        y2 = y1 + CARA_TAM

        # Sombra proyectada en la "mesa": posición fija abajo, se angosta
        # con el giro y se achica/aleja cuando el dado salta.
        sombra_y1 = MARGEN_SUP + CARA_TAM + 8
        sombra_alto = max(4, 12 - abs(offset_y) * 0.35)
        sombra_ancho = (CARA_TAM + PROF) * max(0.5, 1 - abs(offset_y) / 70)
        sx1 = MARGEN_IZQ + (CARA_TAM + PROF - sombra_ancho) / 2
        rect_redondeado(canvas, sx1, sombra_y1, sx1 + sombra_ancho,
                         sombra_y1 + sombra_alto, sombra_alto / 2,
                         fill=COLOR_SOMBRA, outline="")

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
            r = 6.5 * min(1.0, 0.5 + escala_x * 0.6)
            for fx, fy in POSICIONES_PUNTOS.get(valor, []):
                cx = x1 + fx * ancho_cara
                cy = y1 + fy * CARA_TAM
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
                            highlightthickness=2)
        externo.pack(fill="x", padx=15, pady=(0, 15))

        barra = tk.Frame(externo, bg=BG_PANEL, highlightbackground=BORDER,
                          highlightthickness=1)
        barra.pack(fill="x", padx=6, pady=6)

        fila_stats = tk.Frame(barra, bg=BG_PANEL)
        fila_stats.pack(fill="x", padx=10, pady=(10, 0))

        self._crear_estadistica(fila_stats, "CREDITOS", "lbl_valor_creditos", GREEN_VALUE)
        self._crear_estadistica(fila_stats, "APUESTA", "lbl_valor_apuesta", GOLD)
        self._crear_estadistica(fila_stats, "ULTIMO RESULTADO", "lbl_valor_ultimo", MINT_TEXT)

        fila_control = tk.Frame(barra, bg=BG_PANEL)
        fila_control.pack(fill="x", padx=10, pady=10)

        tk.Label(fila_control, text="Apuesta:", bg=BG_PANEL, fg=MINT_TEXT,
                 font=("Arial", 10, "bold")).pack(side="left")

        self.entrada_apuesta = tk.Spinbox(fila_control, from_=10, to=500, width=8)
        self.entrada_apuesta.delete(0, "end")
        self.entrada_apuesta.insert(0, "10")
        self.entrada_apuesta.pack(side="left", padx=8)

        tk.Label(fila_control, text="(10-500)", bg=BG_PANEL, fg=MINT_TEXT,
                 font=("Arial", 9)).pack(side="left")

        self.btn_accion = BotonRedondeado(
            fila_control, "🎲  LANZAR", self._al_presionar_accion
        )
        self.btn_accion.pack(side="right")

    def _crear_estadistica(self, padre, texto_etiqueta, nombre_attr, color_valor) -> None:
        col = tk.Frame(padre, bg=BG_PANEL, highlightbackground=BORDER,
                        highlightthickness=1)
        col.pack(side="left", fill="x", expand=True, padx=6)

        tk.Label(col, text=texto_etiqueta, bg=BG_PANEL, fg=MINT_TEXT,
                 font=("Arial", 9, "bold")).pack(pady=(8, 0))
        etiqueta_valor = tk.Label(col, text="-", bg=BG_PANEL, fg=color_valor,
                                   font=("Arial", 16, "bold"))
        etiqueta_valor.pack(pady=(0, 8))
        setattr(self, nombre_attr, etiqueta_valor)

    # ------------------------------------------------------------------
    # Lógica de eventos
    # ------------------------------------------------------------------

    def _al_presionar_accion(self) -> None:
        if self._animando:
            return
        self.btn_accion.set_estado(False)

        if self.controlador.hay_ronda_activa():
            self.controlador.continuar_lanzamiento(self._on_resultado)
        else:
            try:
                apuesta = int(self.entrada_apuesta.get())
            except ValueError:
                messagebox.showerror("Error", "Apuesta inválida")
                self.btn_accion.set_estado(True)
                return

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

            self.lbl_estado.config(
                text=f"Estado: {self.controlador.obtener_estado()}" if ronda_activa or resultado else "Estado: -"
            )
            self.lbl_punto.config(text=f"Punto: {self.controlador.obtener_punto() or '-'}")
            self._actualizar_creditos()

            self.btn_accion.set_estado(True)
            self.btn_accion.set_texto("🎲  LANZAR" if ronda_activa else "🎲  APOSTAR")

            if not ronda_activa:
                messagebox.showinfo("Resultado", mensaje)

        if resultado is not None:
            self._animar_dados(resultado, finalizar)
        else:
            finalizar()

    def _actualizar_creditos(self) -> None:
        self.lbl_valor_creditos.config(text=f"{self.jugador.creditos:.0f}")


if __name__ == "__main__":
    from vistas.casino_com import Jugador

    root = tk.Tk()
    root.title("ROBASINO - Craps")
    root.geometry("700x750")
    root.configure(bg=BG_DARK)
    jugador_prueba = Jugador("TestPlayer", creditos_iniciales=2000)
    Dados(jugador_prueba, root)
    root.mainloop()