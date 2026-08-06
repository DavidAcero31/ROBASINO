import random
from pathlib import Path

# Ruta absoluta a la carpeta de recursos (independiente del cwd).
_DIR_ACTUAL = Path(__file__).resolve().parent
_RAIZ_PROYECTO = _DIR_ACTUAL.parent
_DIR_SIMBOLOS = _RAIZ_PROYECTO / "recursos" / "tragamonedas"

# Usados también por la vista y el controlador: no cambiar de nombre ni de forma.
SIMBOLOS_IMAGENES = {
    "cereza":   str(_DIR_SIMBOLOS / "cereza.png"),
    "limon":    str(_DIR_SIMBOLOS / "limon.png"),
    "campana":  str(_DIR_SIMBOLOS / "campana.png"),
    "estrella": str(_DIR_SIMBOLOS / "estrella.png"),
    "diamante": str(_DIR_SIMBOLOS / "diamante.png"),
    "comodin":  str(_DIR_SIMBOLOS / "comodin.png"),
}

NOMBRES_SIMBOLOS = {
    "cereza": "Cereza",
    "limon": "Limón",
    "campana": "Campana",
    "estrella": "Estrella",
    "diamante": "Diamante",
    "comodin": "Comodín",
}

SIMBOLOS = list(SIMBOLOS_IMAGENES.keys())

APUESTA_MINIMA = 10
APUESTA_MAXIMA = 500


# ======================================================================
# Configuración económica (todo lo ajustable vive aquí)
# ======================================================================

TARGET_RTP = 0.94
HOUSE_EDGE = 1 - TARGET_RTP

# Probabilidad de que una tirada gane algo, sin importar cuánto.
HIT_FREQUENCY = 0.30

# Pesos relativos entre premios (no probabilidades absolutas).
# Con HIT_FREQUENCY = 0.30, esta distribución da un RTP teórico ≈ 0.936
# (ver TablaDePagos.rtp_teorico() para recalcularlo tras cualquier ajuste).
PRIZE_WEIGHTS: dict[int, float] = {
    2:  64,
    3:  20,
    5:  8,
    8:  5,
    12: 2,
    20: 1,
}

# multiplicador -> combinación de rodillos que lo representa.
PREMIOS_A_SIMBOLOS: dict[int, tuple[str, str, str]] = {
    20: ("diamante", "diamante", "diamante"),
    12: ("estrella", "estrella", "estrella"),
    8:  ("campana", "campana", "campana"),
    5:  ("cereza", "cereza", "cereza"),
    3:  ("limon", "limon", "limon"),
    2:  ("comodin", "comodin", "comodin"),
}

# Pesos de aparición de símbolos en tiradas PERDEDORAS (solo estética,
# no afecta la probabilidad de ganar).
SYMBOL_WEIGHTS: dict[str, float] = {
    "cereza":   30,
    "limon":    25,
    "campana":  20,
    "estrella": 15,
    "comodin":  7,
    "diamante": 3,
}


class TablaDePagos:
    """Decide si una tirada gana y cuánto (hit frequency + distribución)."""

    def __init__(
        self,
        hit_frequency: float = HIT_FREQUENCY,
        prize_weights: dict[int, float] | None = None,
    ) -> None:
        self.hit_frequency = hit_frequency
        self.prize_weights = dict(prize_weights or PRIZE_WEIGHTS)
        self._multiplicadores = list(self.prize_weights.keys())
        self._pesos = list(self.prize_weights.values())

    def decidir_multiplicador(self) -> int:
        """0 = perdió; N > 0 = ganó con multiplicador N."""
        if random.random() >= self.hit_frequency:
            return 0
        return random.choices(self._multiplicadores, weights=self._pesos, k=1)[0]

    def rtp_teorico(self) -> float:
        """RTP teórico implícito en la configuración actual (para tuning)."""
        peso_total = sum(self._pesos)
        if peso_total == 0:
            return 0.0
        valor_esperado_dado_que_gana = sum(
            m * (w / peso_total) for m, w in zip(self._multiplicadores, self._pesos)
        )
        return self.hit_frequency * valor_esperado_dado_que_gana


class GeneradorDeRodillos:
    """Traduce un multiplicador ya decidido en símbolos para los rodillos."""

    def __init__(
        self,
        simbolos: list[str] = SIMBOLOS,
        pesos_simbolos: dict[str, float] | None = None,
        premios_a_simbolos: dict[int, tuple[str, str, str]] | None = None,
    ) -> None:
        self.simbolos = list(simbolos)
        self.pesos_simbolos = dict(pesos_simbolos or SYMBOL_WEIGHTS)
        self.premios_a_simbolos = dict(premios_a_simbolos or PREMIOS_A_SIMBOLOS)
        self._pesos = [self.pesos_simbolos[s] for s in self.simbolos]

    def generar(self, multiplicador: int) -> tuple[str, str, str]:
        if multiplicador > 0:
            return self.premios_a_simbolos[multiplicador]
        return self._generar_combinacion_perdedora()

    def _generar_combinacion_perdedora(self) -> tuple[str, str, str]:
        # Se evita que una tirada perdedora muestre por casualidad un
        # trío igual (que en este juego siempre representa un premio).
        for _ in range(50):
            combinacion = tuple(
                random.choices(self.simbolos, weights=self._pesos, k=3)
            )
            if len(set(combinacion)) > 1:
                return combinacion

        primero, segundo, _ = combinacion
        distinto = next(s for s in self.simbolos if s != primero)
        return (primero, segundo, distinto)


class ModeloTragamonedas:
    """Reglas puras del juego de Tragamonedas.

    No conoce hilos ni créditos: dado un monto de apuesta, decide el
    multiplicador, genera los símbolos de los rodillos y calcula el
    premio. El manejo de créditos, hilos y persistencia vive en
    ControladorTragamonedas — igual que ModeloDados/ControladorDados.
    """

    def __init__(
        self,
        tabla_pagos: TablaDePagos | None = None,
        generador_rodillos: GeneradorDeRodillos | None = None,
    ) -> None:
        self._tabla_pagos = tabla_pagos or TablaDePagos()
        self._generador_rodillos = generador_rodillos or GeneradorDeRodillos()

    def jugar(self, monto: int) -> dict:
        """Resuelve una tirada completa. No toca créditos del jugador."""
        multiplicador = self._tabla_pagos.decidir_multiplicador()
        resultado = self._generador_rodillos.generar(multiplicador)
        premio = monto * multiplicador
        nombres = tuple(NOMBRES_SIMBOLOS[s] for s in resultado)
        return {
            "multiplicador": multiplicador,
            "resultado": resultado,
            "premio": premio,
            "nombres": nombres,
        }

    def rtp_teorico(self) -> float:
        return self._tabla_pagos.rtp_teorico()