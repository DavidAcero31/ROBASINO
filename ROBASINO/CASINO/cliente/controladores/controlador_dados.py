import threading

from modelos.modelo_dados import EstadoRonda, ModeloDados
from vistas.casino_com import Jugador


class ControladorDados:
    """Lógica del juego de Craps: hilos, apuestas y persistencia.

    No conoce Tkinter; se comunica con la vista solo mediante callbacks,
    igual que ControladorTragamonedas. Cada lanzamiento corre en su propio
    hilo para no bloquear la GUI, y el resultado se guarda en el log en
    otro hilo aparte.
    """

    def __init__(self, jugador: Jugador):
        self.jugador = jugador

        self._modelo: ModeloDados | None = None
        self._apuesta_actual = 0

        self._historial: list[dict] = []
        self._lock_historial = threading.Lock()

        self._hilo_lanzamiento: threading.Thread | None = None
        self._hilo_guardado: threading.Thread | None = None

    def validar_apuesta(self, monto: int) -> bool:
        return self.jugador.apostar(monto)

    # ------------------------------------------------------------------
    # Primer lanzamiento de la ronda (descuenta la apuesta y crea el modelo)
    # ------------------------------------------------------------------

    def iniciar_lanzamiento(self, monto: int, on_resultado) -> None:
        self._hilo_lanzamiento = threading.Thread(
            target=self._ejecutar_lanzamiento_inicial,
            args=(monto, on_resultado),
            daemon=True,
            name="hilo_lanzamiento",
        )
        self._hilo_lanzamiento.start()

    def _ejecutar_lanzamiento_inicial(self, monto: int, on_resultado) -> None:
        if not self.jugador.apostar(monto):
            on_resultado("Créditos insuficientes.", None, 0, False)
            return

        self._apuesta_actual = monto
        self._modelo = ModeloDados()
        resultado, estado = self._modelo.lanzar()
        self._procesar_resultado(resultado, estado, on_resultado)

    # ------------------------------------------------------------------
    # Lanzamientos siguientes (mientras haya un punto establecido)
    # ------------------------------------------------------------------

    def continuar_lanzamiento(self, on_resultado) -> None:
        self._hilo_lanzamiento = threading.Thread(
            target=self._ejecutar_lanzamiento_continuacion,
            args=(on_resultado,),
            daemon=True,
            name="hilo_lanzamiento",
        )
        self._hilo_lanzamiento.start()

    def _ejecutar_lanzamiento_continuacion(self, on_resultado) -> None:
        resultado, estado = self._modelo.lanzar()
        self._procesar_resultado(resultado, estado, on_resultado)

    # ------------------------------------------------------------------
    # Resolución común (premia, arma el mensaje y guarda el historial)
    # ------------------------------------------------------------------

    def _procesar_resultado(self, resultado, estado: EstadoRonda, on_resultado) -> None:
        premio = 0
        ronda_activa = estado in (EstadoRonda.TIRADA_INICIAL, EstadoRonda.PUNTO_ESTABLECIDO)

        if estado == EstadoRonda.GANADA:
            premio = self._apuesta_actual * 2
            self.jugador.acreditar(premio)
            mensaje = (
                f"🎉 ¡GANASTE!  Salió {resultado.suma} ({resultado.dado1}-{resultado.dado2})\n"
                f"Premio: {premio} créditos"
            )
        elif estado == EstadoRonda.PERDIDA:
            mensaje = (
                f"😞 Perdiste.  Salió {resultado.suma} ({resultado.dado1}-{resultado.dado2})\n"
                f"Apuesta perdida: {self._apuesta_actual} créditos."
            )
        else:
            punto = self._modelo.obtener_punto()
            mensaje = (
                f"Salió {resultado.suma} ({resultado.dado1}-{resultado.dado2}).\n"
                f"Punto establecido en {punto}. Vuelve a lanzar."
            )

        partida = {
            "dados": resultado.to_dict(),
            "apuesta": self._apuesta_actual,
            "premio": premio,
            "estado": estado.value,
            "saldo_tras_partida": self.jugador.creditos,
        }
        self._hilo_guardado = threading.Thread(
            target=self._guardar_resultado, args=(partida,),
            daemon=True, name="hilo_guardado",
        )
        self._hilo_guardado.start()

        on_resultado(mensaje, resultado, premio, ronda_activa)

    def _guardar_resultado(self, partida: dict) -> None:
        with self._lock_historial:
            self._historial.append(partida)

        try:
            with open("robasino_log.txt", "a", encoding="utf-8") as f:
                f.write(
                    f"[Dados] Dados={partida['dados']}  "
                    f"Apuesta={partida['apuesta']}  "
                    f"Premio={partida['premio']}  "
                    f"Estado={partida['estado']}  "
                    f"Saldo={partida['saldo_tras_partida']}\n"
                )
        except OSError:
            pass

    @property
    def historial(self) -> list[dict]:
        with self._lock_historial:
            return list(self._historial)

    def hay_ronda_activa(self) -> bool:
        return self._modelo is not None and self._modelo.ronda_activa()

    def obtener_punto(self):
        return self._modelo.obtener_punto() if self._modelo else None

    def obtener_estado(self) -> str:
        return self._modelo.obtener_estado().value if self._modelo else "esperando"