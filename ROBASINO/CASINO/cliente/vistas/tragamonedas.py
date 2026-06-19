import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from vistas.casino_com import Jugador, JuegoBase


SIMBOLOS = ["🍒", "🍋", "🔔", "⭐", "💎", "🃏"]


PREMIOS = {
    ("💎", "💎", "💎"): 10,   # jackpot
    ("⭐", "⭐", "⭐"):  7,
    ("🔔", "🔔", "🔔"):  5,
    ("🍒", "🍒", "🍒"):  4,
    ("🍋", "🍋", "🍋"):  3,
    ("🃏", "🃏", "🃏"):  2,
}

APUESTA_MINIMA = 10
APUESTA_MAXIMA = 500
FRAMES_ANIMACION = 15
DELAY_ANIMACION = 0.07


class vistaTragamonedas(JuegoBase):

    def __init__(self, jugador: Jugador, ventana_padre: tk.Tk):
        super().__init__(jugador, "Tragamonedas")

        self._ventana_padre = ventana_padre
        self._hilo_giro: threading.Thread | None = None
        self._hilo_sonido: threading.Thread | None = None
        self._hilo_guardado: threading.Thread | None = None

        # Historial de partidas (recurso compartido entre hilos)
        self._historial: list[dict] = []
        self._lock_historial = threading.Lock()   # Candado para el historial

        # Variables Tkinter (se crean en construir_ventana)
        self._var_apuesta: tk.IntVar | None = None
        self._var_creditos: tk.StringVar | None = None
        self._vars_rodillos: list[tk.StringVar] = []
        self._btn_girar: ttk.Button | None = None
        self._lbl_resultado: tk.Label | None = None
        self._lbl_estado_hilo: tk.Label | None = None

        self._construir_ventana()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _construir_ventana(self) -> None:
        """Crea y configura todos los widgets de la ventana de Tragamonedas."""

        self._ventana = tk.Toplevel(self._ventana_padre)
        self._ventana.title("🎰 ROBASINO — Tragamonedas")
        self._ventana.resizable(False, False)
        self._ventana.configure(bg="#1a1a2e")

        # ---- Título ----
        tk.Label(
            self._ventana,
            text="🎰  T R A G A M O N E D A S",
            font=("Helvetica", 18, "bold"),
            fg="#f5c518",
            bg="#1a1a2e",
        ).pack(pady=(16, 4))

        # ---- Créditos ----
        self._var_creditos = tk.StringVar(
            value=f"Créditos: {self.jugador.creditos}"
        )
        tk.Label(
            self._ventana,
            textvariable=self._var_creditos,
            font=("Helvetica", 13),
            fg="#00d4aa",
            bg="#1a1a2e",
        ).pack()

        # ---- Rodillos ----
        marco_rodillos = tk.Frame(self._ventana, bg="#16213e", padx=20, pady=16)
        marco_rodillos.pack(padx=20, pady=12)

        for i in range(3):
            var = tk.StringVar(value="❓")
            self._vars_rodillos.append(var)
            tk.Label(
                marco_rodillos,
                textvariable=var,
                font=("Helvetica", 48),
                width=3,
                relief="groove",
                bg="#0f3460",
                fg="white",
            ).grid(row=0, column=i, padx=8)

        # ---- Apuesta ----
        marco_apuesta = tk.Frame(self._ventana, bg="#1a1a2e")
        marco_apuesta.pack(pady=6)

        tk.Label(
            marco_apuesta, text="Apuesta:", font=("Helvetica", 11),
            fg="white", bg="#1a1a2e"
        ).grid(row=0, column=0, padx=4)

        self._var_apuesta = tk.IntVar(value=APUESTA_MINIMA)
        ttk.Spinbox(
            marco_apuesta,
            from_=APUESTA_MINIMA,
            to=APUESTA_MAXIMA,
            increment=10,
            textvariable=self._var_apuesta,
            width=6,
            font=("Helvetica", 11),
        ).grid(row=0, column=1, padx=4)

        # ---- Botón girar ----
        self._btn_girar = ttk.Button(
            self._ventana,
            text="🎰  GIRAR",
            command=self._iniciar_giro,
            width=18,
        )
        self._btn_girar.pack(pady=10)

        # ---- Resultado ----
        self._lbl_resultado = tk.Label(
            self._ventana,
            text="",
            font=("Helvetica", 12, "bold"),
            fg="#f5c518",
            bg="#1a1a2e",
            wraplength=320,
        )
        self._lbl_resultado.pack(pady=4)

        # ---- Estado de hilos (sección educativa) ----
        tk.Label(
            self._ventana,
            text="— Estado de hilos —",
            font=("Helvetica", 9, "italic"),
            fg="#888",
            bg="#1a1a2e",
        ).pack(pady=(12, 0))

        self._lbl_estado_hilo = tk.Label(
            self._ventana,
            text="Sin actividad.",
            font=("Helvetica", 9),
            fg="#aaa",
            bg="#1a1a2e",
            wraplength=340,
            justify="left",
        )
        self._lbl_estado_hilo.pack(padx=20, pady=(0, 16))

    # ------------------------------------------------------------------
    # Lógica de inicio de giro
    # ------------------------------------------------------------------

    def _iniciar_giro(self) -> None:

        monto = self._var_apuesta.get()

        if not self.jugador.apostar(monto):
            messagebox.showwarning(
                "Créditos insuficientes",
                f"No tienes suficientes créditos para apostar {monto}.\n"
                f"Saldo actual: {self.jugador.creditos}",
            )
            return

        # Deshabilitar botón mientras el giro está activo
        self._btn_girar.config(state="disabled")
        self._lbl_resultado.config(text="Girando…")
        self._actualizar_estado_hilo("🟡 hilo_giro: INICIANDO  |  hilo_sonido: EN ESPERA")

        # Lanzar hilos concurrentes
        self._hilo_giro = threading.Thread(
            target=self._ejecutar_giro, args=(monto,), daemon=True, name="hilo_giro"
        )
        self._hilo_sonido = threading.Thread(
            target=self._simular_sonido, daemon=True, name="hilo_sonido"
        )

        self._hilo_giro.start()
        self._hilo_sonido.start()

    # ------------------------------------------------------------------
    # Hilo de animación y cálculo del resultado
    # ------------------------------------------------------------------

    def _ejecutar_giro(self, monto: int) -> None:

        self._actualizar_estado_hilo(
            "🟢 hilo_giro: EJECUTANDO  |  hilo_sonido: EJECUTANDO"
        )

        # --- Animación de rodillos ---
        for _ in range(FRAMES_ANIMACION):
            simbolos_frame = [random.choice(SIMBOLOS) for _ in range(3)]
            for var, sym in zip(self._vars_rodillos, simbolos_frame):
                var.set(sym)
            time.sleep(DELAY_ANIMACION)

        # --- Resultado final ---
        resultado_final = tuple(random.choice(SIMBOLOS) for _ in range(3))
        for var, sym in zip(self._vars_rodillos, resultado_final):
            var.set(sym)

        # --- Calcular premio ---
        multiplicador = PREMIOS.get(resultado_final, 0)
        premio = monto * multiplicador

        if premio > 0:
            self.jugador.acreditar(premio)
            mensaje = (
                f"🎉 ¡GANASTE!  {resultado_final[0]} {resultado_final[1]} {resultado_final[2]}\n"
                f"Premio: {premio} créditos  (×{multiplicador})"
            )
        else:
            mensaje = (
                f"😞 Perdiste.  {resultado_final[0]} {resultado_final[1]} {resultado_final[2]}\n"
                f"Apuesta perdida: {monto} créditos."
            )

        # --- Lanzar hilo de guardado ---
        partida = {
            "rodillos": resultado_final,
            "apuesta": monto,
            "premio": premio,
            "saldo_tras_partida": self.jugador.creditos,
        }
        self._hilo_guardado = threading.Thread(
            target=self._guardar_resultado, args=(partida,),
            daemon=True, name="hilo_guardado"
        )
        self._hilo_guardado.start()

        # --- Actualizar UI desde el hilo (seguro con after()) ---
        self._ventana.after(0, self._finalizar_giro, mensaje)

    # ------------------------------------------------------------------
    # Hilo de sonido (simulado)
    # ------------------------------------------------------------------

    def _simular_sonido(self) -> None:

        tiempo_total = FRAMES_ANIMACION * DELAY_ANIMACION + 0.5
        time.sleep(tiempo_total)
        # Sonido finalizado — no hay acción visible en la UI

    # ------------------------------------------------------------------
    # Hilo de almacenamiento (con control de condición de carrera)
    # ------------------------------------------------------------------

    def _guardar_resultado(self, partida: dict) -> None:

        self._actualizar_estado_hilo(
            "🟢 hilo_giro: FINALIZANDO  |  hilo_guardado: ESCRIBIENDO"
        )

        # Acceso exclusivo al historial compartido
        with self._lock_historial:
            self._historial.append(partida)
            # Simula latencia de escritura en disco
            time.sleep(0.05)

        # Log en archivo de texto (opcional)
        try:
            with open("robasino_log.txt", "a", encoding="utf-8") as f:
                f.write(
                    f"[Tragamonedas] Rodillos={partida['rodillos']}  "
                    f"Apuesta={partida['apuesta']}  "
                    f"Premio={partida['premio']}  "
                    f"Saldo={partida['saldo_tras_partida']}\n"
                )
        except OSError:
            pass  # Si no se puede escribir el log, continúa sin error fatal

        self._actualizar_estado_hilo("⚪ Todos los hilos: EN REPOSO")

    # ------------------------------------------------------------------
    # Método público: jugar() — requerido por JuegoBase
    # ------------------------------------------------------------------

    def jugar(self, monto: int) -> dict:

        if not self.jugador.apostar(monto):
            return {"ganado": False, "premio": 0, "mensaje": "Créditos insuficientes."}

        resultado = tuple(random.choice(SIMBOLOS) for _ in range(3))
        multiplicador = PREMIOS.get(resultado, 0)
        premio = monto * multiplicador

        if premio > 0:
            self.jugador.acreditar(premio)

        return {
            "ganado": premio > 0,
            "premio": premio,
            "mensaje": f"{resultado[0]} {resultado[1]} {resultado[2]} — Premio: {premio}",
        }

    # ------------------------------------------------------------------
    # Helpers de actualización de UI
    # ------------------------------------------------------------------

    def _finalizar_giro(self, mensaje: str) -> None:

        self._lbl_resultado.config(text=mensaje)
        self._var_creditos.set(f"Créditos: {self.jugador.creditos}")
        self._btn_girar.config(state="normal")

    def _actualizar_estado_hilo(self, texto: str) -> None:

        self._ventana.after(0, lambda: self._lbl_estado_hilo.config(text=texto))


# ---------------------------------------------------------------------------
# Punto de entrada: lanzar solo la ventana de Tragamonedas para pruebas
# ---------------------------------------------------------------------------

# if __name__ == "__main__":
#     root = tk.Tk()
#     root.title("ROBASINO — Prueba Tragamonedas")
#     root.withdraw()   # Oculta la ventana raíz vacía

#     jugador_prueba = Jugador("TestPlayer", creditos_iniciales=2000)
#     juego = Tragamonedas(jugador_prueba, root)

#     root.mainloop()