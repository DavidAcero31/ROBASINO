import random
from dataclasses import dataclass
from enum import Enum


class EstadoRonda(Enum):
    """Estados posibles de una ronda de Craps."""

    TIRADA_INICIAL = "tirada_inicial"        # Primer lanzamiento (come-out roll)
    PUNTO_ESTABLECIDO = "punto_establecido"  # Ya se fijó un punto
    GANADA = "ganada"
    PERDIDA = "perdida"


@dataclass
class ResultadoLanzamiento:
    """Resultado de un lanzamiento de dos dados."""

    dado1: int
    dado2: int

    @property
    def suma(self) -> int:
        return self.dado1 + self.dado2

    def to_dict(self) -> dict:
        return {"dado1": self.dado1, "dado2": self.dado2, "suma": self.suma}


class ModeloDados:
    """Reglas del juego de Craps (apuesta simple a pass line).

    No conoce hilos ni créditos: solo decide, tirada a tirada, si la
    ronda se gana, se pierde o continúa. El manejo de créditos y de
    concurrencia vive en ControladorDados, igual que en Tragamonedas.

    - Tirada inicial (come-out roll):
        * 7 u 11  -> gana de inmediato
        * 2, 3, 12 -> pierde de inmediato ("craps")
        * cualquier otro valor -> se fija como "punto"
    - Con punto establecido:
        * Si se repite el punto -> gana
        * Si sale 7 -> pierde ("seven out")
        * Cualquier otro valor -> la ronda continúa
    """

    NUMEROS_GANADORES_INICIAL = {7, 11}
    NUMEROS_PERDEDORES_INICIAL = {2, 3, 12}

    def __init__(self) -> None:
        self._punto: int | None = None
        self._estado = EstadoRonda.TIRADA_INICIAL

    def lanzar(self) -> tuple[ResultadoLanzamiento, EstadoRonda]:
        """Realiza un lanzamiento y actualiza el estado interno de la ronda."""
        dado1 = random.randint(1, 6)
        dado2 = random.randint(1, 6)
        resultado = ResultadoLanzamiento(dado1, dado2)
        suma = resultado.suma

        if self._estado == EstadoRonda.TIRADA_INICIAL:
            self._procesar_tirada_inicial(suma)
        elif self._estado == EstadoRonda.PUNTO_ESTABLECIDO:
            self._procesar_tirada_con_punto(suma)

        return resultado, self._estado

    def _procesar_tirada_inicial(self, suma: int) -> None:
        if suma in self.NUMEROS_GANADORES_INICIAL:
            self._estado = EstadoRonda.GANADA
        elif suma in self.NUMEROS_PERDEDORES_INICIAL:
            self._estado = EstadoRonda.PERDIDA
        else:
            self._punto = suma
            self._estado = EstadoRonda.PUNTO_ESTABLECIDO

    def _procesar_tirada_con_punto(self, suma: int) -> None:
        if suma == self._punto:
            self._estado = EstadoRonda.GANADA
        elif suma == 7:
            self._estado = EstadoRonda.PERDIDA
        # cualquier otro valor: la ronda continúa, no cambia el estado

    def obtener_punto(self) -> int | None:
        return self._punto

    def obtener_estado(self) -> EstadoRonda:
        return self._estado

    def ronda_activa(self) -> bool:
        return self._estado in (EstadoRonda.TIRADA_INICIAL, EstadoRonda.PUNTO_ESTABLECIDO)