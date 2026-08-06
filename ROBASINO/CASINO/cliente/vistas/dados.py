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
BTN_FG = "#0a1f12"

POSICIONES_PUNTOS = {
    1: [(0.5, 0.5)],
    2: [(0.25, 0.25), (0.75, 0.75)],
    3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
    4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
    5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
    6: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.5), (0.75, 0.5), (0.25, 0.75), (0.75, 0.75)],
}


class Dados(tk.Frame):
    """Vista del juego de Craps, con el mismo lenguaje visual de Tragamonedas."""

    def __init__(self, jugador, master: tk.Tk):
        super().__init__(master, bg=BG_DARK)
        self.master = master
        self.jugador = jugador
        self.controlador = ControladorDados(jugador)
        self.pack(fill="both", expand=True)

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

        self.canvas_dado1 = tk.Canvas(fila_dados, width=110, height=110,
                                       bg="#173420", highlightthickness=2,
                                       highlightbackground=GOLD)
        self.canvas_dado1.pack(side="left", padx=15)

        self.canvas_dado2 = tk.Canvas(fila_dados, width=110, height=110,
                                       bg="#173420", highlightthickness=2,
                                       highlightbackground=GOLD)
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

    def _dibujar_dado(self, canvas: tk.Canvas, valor: int) -> None:
        canvas.delete("all")
        tam = 110
        r = 6
        for (fx, fy) in POSICIONES_PUNTOS.get(valor, []):
            x, y = fx * tam, fy * tam
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=GOLD, outline="")

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

        self.btn_accion = tk.Button(
            fila_control, text="🎲  LANZAR", bg=BTN_BG, fg=BTN_FG,
            font=("Arial", 13, "bold"), relief="flat", padx=25, pady=8,
            command=self._al_presionar_accion
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
        self.btn_accion.config(state=tk.DISABLED)

        if self.controlador.hay_ronda_activa():
            self.controlador.continuar_lanzamiento(self._on_resultado)
        else:
            try:
                apuesta = int(self.entrada_apuesta.get())
            except ValueError:
                messagebox.showerror("Error", "Apuesta inválida")
                self.btn_accion.config(state=tk.NORMAL)
                return

            self.lbl_valor_apuesta.config(text=f"{apuesta:.0f}")
            self.controlador.iniciar_lanzamiento(apuesta, self._on_resultado)

    def _on_resultado(self, mensaje, resultado, premio, ronda_activa) -> None:
        # Llamado desde el hilo secundario del controlador: se reenvía
        # al hilo principal de Tkinter antes de tocar cualquier widget.
        self.master.after(0, lambda: self._actualizar_interfaz(mensaje, resultado, premio, ronda_activa))

    def _actualizar_interfaz(self, mensaje, resultado, premio, ronda_activa) -> None:
        if resultado is not None:
            self._dibujar_dado(self.canvas_dado1, resultado.dado1)
            self._dibujar_dado(self.canvas_dado2, resultado.dado2)
            self.lbl_valor_ultimo.config(text=str(resultado.suma))

        self.lbl_estado.config(text=f"Estado: {self.controlador.obtener_estado()}" if ronda_activa or resultado else "Estado: -")
        self.lbl_punto.config(text=f"Punto: {self.controlador.obtener_punto() or '-'}")
        self._actualizar_creditos()

        self.btn_accion.config(
            state=tk.NORMAL,
            text="🎲  LANZAR" if ronda_activa else "🎲  APOSTAR",
        )

        if not ronda_activa:
            messagebox.showinfo("Resultado", mensaje)

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