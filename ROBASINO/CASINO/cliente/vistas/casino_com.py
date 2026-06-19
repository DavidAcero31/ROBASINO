import threading


class Jugador:


    def __init__(self, nombre: str, creditos_iniciales: int = 1000):
        self.nombre = nombre
        self._creditos = creditos_iniciales
        self._lock = threading.Lock()  # Candado compartido para el saldo


    @property
    def creditos(self) -> int:
        with self._lock:
            return self._creditos


    def apostar(self, monto: int) -> bool:

        with self._lock:
            if monto <= 0:
                return False
            if self._creditos >= monto:
                self._creditos -= monto
                return True
            return False

    def acreditar(self, monto: int) -> None:
        with self._lock:
            if monto > 0:
                self._creditos += monto

    def __str__(self) -> str:
        return f"Jugador('{self.nombre}', créditos={self.creditos})"


# ---------------------------------------------------------------------------
# Clase base JuegoBase
# ---------------------------------------------------------------------------

class JuegoBase:

    def __init__(self, jugador: Jugador, nombre_juego: str):
        self.jugador = jugador
        self.nombre_juego = nombre_juego
        self.en_ejecucion = False

    def jugar(self, monto: int) -> dict:

        raise NotImplementedError(
            f"La clase '{type(self).__name__}' debe implementar el método jugar()."
        )

    def __str__(self) -> str:
        return f"{self.nombre_juego} — Jugador: {self.jugador.nombre}"