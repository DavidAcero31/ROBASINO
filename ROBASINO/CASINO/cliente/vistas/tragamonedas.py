import random
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from vistas.casino_com import Jugador, JuegoBase


SIMBOLOS = ["🍒", "🍋", "🔔", "⭐", "💎", "🃏"]

PREMIOS = {
    ("💎", "💎", "💎"): 10,
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

        self._historial: list[dict] = []
        self._lock_historial = threading.Lock()

        self._var_apuesta: tk.IntVar | None = None
        self._var_creditos: tk.StringVar | None = None
        self._vars_rodillos: list[tk.StringVar] = []
        self._btn_girar: ttk.Button | None = None
        self._lbl_resultado: tk.Label | None = None
        self._log_text: tk.Text | None = None          # ← panel de log en tiempo real

        self._construir_ventana()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _construir_ventana(self) -> None:

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
        self._var_creditos = tk.StringVar(value=f"Créditos: {self.jugador.creditos}")
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

        # ---- Botones (GIRAR + DEMO) ----
        marco_botones = tk.Frame(self._ventana, bg="#1a1a2e")
        marco_botones.pack(pady=10)

        self._btn_girar = ttk.Button(
            marco_botones,
            text="🎰  GIRAR",
            command=self._iniciar_giro,
            width=18,
        )
        self._btn_girar.grid(row=0, column=0, padx=6)

        self._btn_demo = ttk.Button(
            marco_botones,
            text="⚡ DEMO Race Condition",
            command=self._iniciar_demo_race,
            width=22,
        )
        self._btn_demo.grid(row=0, column=1, padx=6)

        # ---- Resultado ----
        self._lbl_resultado = tk.Label(
            self._ventana,
            text="",
            font=("Helvetica", 12, "bold"),
            fg="#f5c518",
            bg="#1a1a2e",
            wraplength=380,
        )
        self._lbl_resultado.pack(pady=4)

        # ---- Panel de log en tiempo real ----
        tk.Label(
            self._ventana,
            text="— Monitor de hilos en tiempo real —",
            font=("Helvetica", 9, "italic"),
            fg="#888",
            bg="#1a1a2e",
        ).pack(pady=(10, 0))

        marco_log = tk.Frame(self._ventana, bg="#0d0d1a")
        marco_log.pack(padx=16, pady=(2, 16), fill="both")

        self._log_text = tk.Text(
            marco_log,
            height=10,
            width=58,
            bg="#0d0d1a",
            fg="#c8c8c8",
            font=("Courier", 9),
            state="disabled",
            relief="flat",
            wrap="word",
        )
        scrollbar = tk.Scrollbar(marco_log, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        self._log_text.pack(side="left", fill="both")
        scrollbar.pack(side="right", fill="y")

        # Colores por tipo de evento
        self._log_text.tag_config("titulo",   foreground="#f5c518", font=("Courier", 9, "bold"))
        self._log_text.tag_config("ok",       foreground="#00d4aa")
        self._log_text.tag_config("warn",     foreground="#ff6b6b")
        self._log_text.tag_config("lock",     foreground="#a78bfa")
        self._log_text.tag_config("info",     foreground="#94a3b8")
        self._log_text.tag_config("separador",foreground="#444")

        self._log("Sistema iniciado. Jugador: "
                  f"{self.jugador.nombre} | Saldo: {self.jugador.creditos}", "ok")

    # ------------------------------------------------------------------
    # Helper: escribir en el panel de log (thread-safe vía after)
    # ------------------------------------------------------------------

    def _log(self, mensaje: str, tag: str = "info") -> None:
        hilo = threading.current_thread().name
        ts   = time.strftime("%H:%M:%S")
        linea = f"[{ts}][{hilo}] {mensaje}\n"

        def _escribir():
            self._log_text.config(state="normal")
            self._log_text.insert("end", linea, tag)
            self._log_text.see("end")
            self._log_text.config(state="disabled")

        self._ventana.after(0, _escribir)

    def _log_sep(self, titulo: str = "") -> None:
        sep = f"{'─'*20} {titulo} {'─'*20}\n" if titulo else "─" * 50 + "\n"
        def _escribir():
            self._log_text.config(state="normal")
            self._log_text.insert("end", sep, "separador")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self._ventana.after(0, _escribir)

    # ------------------------------------------------------------------
    # Lógica de inicio de giro normal
    # ------------------------------------------------------------------

    def _iniciar_giro(self) -> None:

        monto = self._var_apuesta.get()
        self._log_sep("GIRAR")
        self._log(f"Botón GIRAR presionado — apuesta: {monto}", "titulo")

        self._log(f"hilo_principal llama jugador.apostar({monto}) …", "info")
        if not self.jugador.apostar(monto):
            self._log(f"RECHAZADO — saldo insuficiente ({self.jugador.creditos})", "warn")
            messagebox.showwarning(
                "Créditos insuficientes",
                f"No tienes suficientes créditos para apostar {monto}.\n"
                f"Saldo actual: {self.jugador.creditos}",
            )
            return

        self._log(f"Apuesta aceptada → saldo ahora: {self.jugador.creditos}", "ok")

        self._btn_girar.config(state="disabled")
        self._btn_demo.config(state="disabled")
        self._lbl_resultado.config(text="Girando…")

        self._hilo_giro = threading.Thread(
            target=self._ejecutar_giro, args=(monto,), daemon=True, name="hilo_giro"
        )
        self._hilo_sonido = threading.Thread(
            target=self._simular_sonido, daemon=True, name="hilo_sonido"
        )

        self._log("Lanzando hilo_giro y hilo_sonido en paralelo …", "lock")
        self._hilo_giro.start()
        self._hilo_sonido.start()

    # ------------------------------------------------------------------
    # Hilo de animación y cálculo del resultado
    # ------------------------------------------------------------------

    def _ejecutar_giro(self, monto: int) -> None:

        self._log("hilo_giro ACTIVO — animando rodillos", "ok")

        for _ in range(FRAMES_ANIMACION):
            simbolos_frame = [random.choice(SIMBOLOS) for _ in range(3)]
            for var, sym in zip(self._vars_rodillos, simbolos_frame):
                var.set(sym)
            time.sleep(DELAY_ANIMACION)

        resultado_final = tuple(random.choice(SIMBOLOS) for _ in range(3))
        for var, sym in zip(self._vars_rodillos, resultado_final):
            var.set(sym)

        multiplicador = PREMIOS.get(resultado_final, 0)
        premio = monto * multiplicador

        if premio > 0:
            self._log(f"Premio calculado: {premio} — llamando jugador.acreditar({premio})", "info")
            self.jugador.acreditar(premio)
            self._log(f"Acreditado. Saldo ahora: {self.jugador.creditos}", "ok")
            mensaje = (
                f"🎉 ¡GANASTE!  {resultado_final[0]} {resultado_final[1]} {resultado_final[2]}\n"
                f"Premio: {premio} créditos  (×{multiplicador})"
            )
        else:
            self._log(f"Sin premio. Saldo tras apuesta: {self.jugador.creditos}", "info")
            mensaje = (
                f"😞 Perdiste.  {resultado_final[0]} {resultado_final[1]} {resultado_final[2]}\n"
                f"Apuesta perdida: {monto} créditos."
            )

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
        self._log("Lanzando hilo_guardado para escribir historial …", "lock")
        self._hilo_guardado.start()

        self._ventana.after(0, self._finalizar_giro, mensaje)

    # ------------------------------------------------------------------
    # Hilo de sonido
    # ------------------------------------------------------------------

    def _simular_sonido(self) -> None:
        self._log("hilo_sonido ACTIVO — simulando audio", "info")
        tiempo_total = FRAMES_ANIMACION * DELAY_ANIMACION + 0.5
        time.sleep(tiempo_total)
        self._log("hilo_sonido TERMINADO", "info")

    # ------------------------------------------------------------------
    # Hilo de guardado
    # ------------------------------------------------------------------

    def _guardar_resultado(self, partida: dict) -> None:

        self._log("hilo_guardado: esperando lock_historial …", "lock")
        with self._lock_historial:
            self._log("hilo_guardado: LOCK ADQUIRIDO — escribiendo historial", "lock")
            self._historial.append(partida)
            time.sleep(0.05)
            self._log(f"hilo_guardado: historial tiene {len(self._historial)} partidas — liberando lock", "lock")

        try:
            with open("robasino_log.txt", "a", encoding="utf-8") as f:
                f.write(
                    f"[Tragamonedas] Rodillos={partida['rodillos']}  "
                    f"Apuesta={partida['apuesta']}  "
                    f"Premio={partida['premio']}  "
                    f"Saldo={partida['saldo_tras_partida']}\n"
                )
        except OSError:
            pass

        self._log("hilo_guardado TERMINADO. Todos los hilos en reposo.", "ok")

    # ------------------------------------------------------------------
    # DEMO Race Condition
    # Lanza dos hilos que compiten por jugador.apostar() sobre el mismo
    # objeto Jugador, primero sin lock (subclase rota) y luego con lock.
    # ------------------------------------------------------------------

    def _iniciar_demo_race(self) -> None:
        self._btn_girar.config(state="disabled")
        self._btn_demo.config(state="disabled")
        threading.Thread(
            target=self._ejecutar_demo_race,
            daemon=True,
            name="hilo_demo"
        ).start()

    def _ejecutar_demo_race(self) -> None:
        # ── Capturamos saldo actual real del jugador ──────────────────
        saldo_real = self.jugador.creditos

        self._log_sep("DEMO RACE CONDITION")
        self._log(f"Saldo actual del jugador: {saldo_real}", "titulo")
        self._log("Vamos a lanzar DOS hilos que intentan apostar 200 al mismo tiempo.", "titulo")

        # ── FASE 1: SIN LOCK — subclase que bypasea el candado ───────
        self._log_sep("FASE 1: SIN Lock")
        self._log("Creamos JugadorSINLock con el mismo saldo actual …", "warn")

        jugador_roto = _JugadorSINLock(
            self.jugador.nombre + "_ROTO",
            creditos_iniciales=saldo_real,
            log_fn=self._log,
        )

        barrera = threading.Barrier(2)   # sincroniza los dos hilos para que arranquen juntos

        def apostar_sin_lock(nombre_hilo, monto):
            barrera.wait()               # espera a que ambos hilos estén listos → máxima colisión
            jugador_roto.apostar_inseguro(monto, nombre_hilo)

        h1 = threading.Thread(target=apostar_sin_lock, args=("juego_Ruleta", 200),        name="hilo_Ruleta_ROTO")
        h2 = threading.Thread(target=apostar_sin_lock, args=("juego_Tragamonedas", 200),  name="hilo_Tragamonedas_ROTO")

        h1.start(); h2.start()
        h1.join();  h2.join()

        saldo_roto = jugador_roto._creditos
        self._log(f"Saldo final SIN lock: {saldo_roto}  (esperado: nunca negativo)", "warn")
        if saldo_roto < 0:
            self._log(f"⚠️  SALDO NEGATIVO — se autorizaron {saldo_real - saldo_roto} créditos sobre {saldo_real} disponibles", "warn")
        else:
            self._log("Esta vez no hubo colisión visible — el planificador no interrumpió en el momento exacto.", "info")
            self._log("Eso es la naturaleza no determinista de las race conditions.", "info")

        time.sleep(0.4)

        # ── FASE 2: CON LOCK — jugador.apostar() real ─────────────────
        self._log_sep("FASE 2: CON Lock (casino_com.Jugador real)")
        self._log(f"Mismo escenario — saldo: {saldo_real} — dos hilos apostan 200 simultáneamente", "ok")

        # Creamos un jugador auxiliar con el mismo saldo para no afectar la partida real
        jugador_seguro = _JugadorCONLog(
            self.jugador.nombre + "_SEGURO",
            creditos_iniciales=saldo_real,
            log_fn=self._log,
        )

        barrera2 = threading.Barrier(2)

        def apostar_con_lock(nombre_hilo, monto):
            barrera2.wait()
            jugador_seguro.apostar_logeado(monto, nombre_hilo)

        h3 = threading.Thread(target=apostar_con_lock, args=("juego_Ruleta", 200),        name="hilo_Ruleta_OK")
        h4 = threading.Thread(target=apostar_con_lock, args=("juego_Tragamonedas", 200),  name="hilo_Tragamonedas_OK")

        h3.start(); h4.start()
        h3.join();  h4.join()

        saldo_ok = jugador_seguro.creditos
        self._log(f"Saldo final CON lock: {saldo_ok}", "ok")
        self._log("✅ El Lock garantizó que solo un hilo a la vez leyó-verificó-escribió el saldo.", "ok")
        self._log_sep("FIN DEMO")

        # Re-habilitar botones
        self._ventana.after(0, lambda: self._btn_girar.config(state="normal"))
        self._ventana.after(0, lambda: self._btn_demo.config(state="normal"))

    # ------------------------------------------------------------------
    # jugar() — requerido por JuegoBase
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
    # Helpers UI
    # ------------------------------------------------------------------

    def _finalizar_giro(self, mensaje: str) -> None:
        self._lbl_resultado.config(text=mensaje)
        self._var_creditos.set(f"Créditos: {self.jugador.creditos}")
        self._btn_girar.config(state="normal")
        self._btn_demo.config(state="normal")

    def _actualizar_estado_hilo(self, texto: str) -> None:
        # Mantenemos compatibilidad por si algo externo lo llama
        self._log(texto, "info")


# ---------------------------------------------------------------------------
# Clases auxiliares usadas SOLO por la demo — no forman parte del juego real
# ---------------------------------------------------------------------------

class _JugadorSINLock:
    """Replica el saldo de Jugador pero apostar_inseguro() no usa Lock.
       Expone la ventana de race condition idéntica a la descrita en clase."""

    def __init__(self, nombre: str, creditos_iniciales: int, log_fn):
        self.nombre = nombre
        self._creditos = creditos_iniciales
        self._log = log_fn

    def apostar_inseguro(self, monto: int, quien: str) -> bool:
        self._log(f"{quien} lee saldo → {self._creditos}", "warn")
        if self._creditos >= monto:
            time.sleep(0.002)                      # ← ventana donde el SO puede cambiar de hilo
            self._creditos -= monto                # escritura sin protección
            self._log(f"{quien} descuenta {monto} → saldo ahora: {self._creditos}", "warn")
            return True
        self._log(f"{quien} RECHAZADO (saldo={self._creditos} < {monto})", "warn")
        return False


class _JugadorCONLog(Jugador):
    """Jugador real con logging extra para visualizar el Lock en acción."""

    def __init__(self, nombre: str, creditos_iniciales: int, log_fn):
        super().__init__(nombre, creditos_iniciales)
        self._log_fn = log_fn

    def apostar_logeado(self, monto: int, quien: str) -> bool:
        self._log_fn(f"{quien} intenta adquirir Lock para apostar {monto} …", "lock")
        with self._lock:
            self._log_fn(f"{quien} LOCK ADQUIRIDO — saldo actual: {self._creditos}", "lock")
            if self._creditos >= monto:
                time.sleep(0.002)                  # misma latencia simulada
                self._creditos -= monto
                self._log_fn(f"{quien} descuenta {monto} → saldo: {self._creditos} — liberando Lock", "ok")
                return True
            self._log_fn(f"{quien} RECHAZADO (saldo={self._creditos} < {monto}) — liberando Lock", "warn")
            return False
