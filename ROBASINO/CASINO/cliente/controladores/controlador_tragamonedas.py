import threading

from modelos.modelo_tragamonedas import (
    ModeloTragamonedas,
    SIMBOLOS_IMAGENES,
    NOMBRES_SIMBOLOS,
    SIMBOLOS,
    APUESTA_MINIMA,
    APUESTA_MAXIMA,
)
from vistas.casino_com import Jugador

# Re-exportados para que la vista siga importándolos igual que antes:
# from controladores.controlador_tragamonedas import (
#     ControladorTragamonedas, APUESTA_MINIMA, APUESTA_MAXIMA, SIMBOLOS, SIMBOLOS_IMAGENES,
# )
__all__ = [
    "ControladorTragamonedas",
    "APUESTA_MINIMA",
    "APUESTA_MAXIMA",
    "SIMBOLOS",
    "SIMBOLOS_IMAGENES",
]


class ControladorTragamonedas:
    """Lógica del juego: hilos, cálculo de premios y persistencia.

    No conoce Tkinter; se comunica con la vista solo mediante callbacks.
    Interfaz pública sin cambios: iniciar_giro, jugar, validar_apuesta,
    historial.
    """

    def __init__(self, jugador: Jugador):
        self.jugador = jugador

        self._historial: list[dict] = []
        self._lock_historial = threading.Lock()

        self._hilo_giro: threading.Thread | None = None
        self._hilo_guardado: threading.Thread | None = None

        self._modelo = ModeloTragamonedas()

    def validar_apuesta(self, monto: int) -> bool:
        return self.jugador.apostar(monto)

    def iniciar_giro(self, monto: int, on_resultado) -> None:
        self._hilo_giro = threading.Thread(
            target=self._ejecutar_giro,
            args=(monto, on_resultado),
            daemon=True,
            name="hilo_giro",
        )
        self._hilo_giro.start()

    def _ejecutar_giro(self, monto: int, on_resultado) -> None:
        jugada = self._modelo.jugar(monto)
        resultado_final = jugada["resultado"]
        premio = jugada["premio"]
        nombres = jugada["nombres"]

        if premio > 0:
            self.jugador.acreditar(premio)
            mensaje = (
                f"🎉 ¡GANASTE!  {nombres[0]} {nombres[1]} {nombres[2]}\n"
                f"Premio: {premio} créditos  (×{jugada['multiplicador']})"
            )
        else:
            mensaje = (
                f"😞 Perdiste.  {nombres[0]} {nombres[1]} {nombres[2]}\n"
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
            daemon=True, name="hilo_guardado",
        )
        self._hilo_guardado.start()

        on_resultado(mensaje, resultado_final, premio)

    def _guardar_resultado(self, partida: dict) -> None:
        with self._lock_historial:
            self._historial.append(partida)

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

    @property
    def historial(self) -> list[dict]:
        with self._lock_historial:
            return list(self._historial)

    def jugar(self, monto: int) -> dict:
        if not self.jugador.apostar(monto):
            return {"ganado": False, "premio": 0, "mensaje": "Créditos insuficientes."}

        jugada = self._modelo.jugar(monto)
        premio = jugada["premio"]

        if premio > 0:
            self.jugador.acreditar(premio)

        nombres = jugada["nombres"]
        return {
            "ganado": premio > 0,
            "premio": premio,
            "mensaje": f"{nombres[0]} {nombres[1]} {nombres[2]} — Premio: {premio}",
        }