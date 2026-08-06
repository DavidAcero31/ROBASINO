"""
Lógica de ruleta que corre en el SERVIDOR: números, colores, validación
de apuestas y cálculo de premios. El cliente (vistas/ruleta.py) solo
dibuja la rueda y envía apuestas; nunca decide el número ganador.
"""

import random

REDS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

# Mismos tipos y multiplicadores que BetManager.TYPES en el cliente.
BET_TYPES = {
    "Rojo":    (lambda n: n != 0 and n in REDS, 2),
    "Negro":   (lambda n: n != 0 and n not in REDS, 2),
    "Par":     (lambda n: n != 0 and n % 2 == 0, 2),
    "Impar":   (lambda n: n != 0 and n % 2 == 1, 2),
    "1–18":    (lambda n: 1 <= n <= 18, 2),
    "19–36":   (lambda n: 19 <= n <= 36, 2),
    "1ª Doc.": (lambda n: 1 <= n <= 12, 3),
    "2ª Doc.": (lambda n: 13 <= n <= 24, 3),
    "3ª Doc.": (lambda n: 25 <= n <= 36, 3),
    "Col. 1":  (lambda n: n != 0 and n % 3 == 1, 3),
    "Col. 2":  (lambda n: n != 0 and n % 3 == 2, 3),
    "Col. 3":  (lambda n: n != 0 and n % 3 == 0, 3),
}


def spin():
    """Genera el número ganador (0–36) en el servidor. Nunca se debe confiar en el cliente."""
    return random.randint(0, 36)


def color_of(n):
    if n == 0:
        return "verde"
    return "rojo" if n in REDS else "negro"


def _normalizar_clave(clave):
    """JSON siempre convierte las claves de un diccionario en cadenas.
    Si la clave representa un número ("17"), se convierte a entero;
    de lo contrario, se asume que es un tipo de apuesta."""
    try:
        return int(clave)
    except (TypeError, ValueError):
        return clave


def validar_apuestas(apuestas_crudas, creditos_disponibles):
    """
    apuestas_crudas: diccionario recibido por JSON (claves str, valores int).
    Devuelve:
    (es_valido, mensaje_error, apuestas_normalizadas, total_apostado).
    """
    if not isinstance(apuestas_crudas, dict) or not apuestas_crudas:
        return False, "Debes hacer al menos una apuesta.", {}, 0

    apuestas = {}
    total = 0

    for clave_cruda, monto in apuestas_crudas.items():
        if not isinstance(monto, int) or monto <= 0:
            return False, "Cada apuesta debe ser un entero positivo.", {}, 0

        clave = _normalizar_clave(clave_cruda)

        if isinstance(clave, int):
            if not (0 <= clave <= 36):
                return False, f"Número de apuesta inválido: {clave}.", {}, 0
        elif clave not in BET_TYPES:
            return False, f"Tipo de apuesta desconocido: {clave}.", {}, 0

        apuestas[clave] = apuestas.get(clave, 0) + monto
        total += monto

    if total > creditos_disponibles:
        return False, (
            f"No tienes suficientes créditos (tienes {creditos_disponibles})."
        ), {}, 0

    return True, None, apuestas, total


def calcular_premio(apuestas, numero_ganador):
    """Calcula el premio total (bruto) para un conjunto de apuestas ya validadas."""
    premio = 0

    for clave, monto in apuestas.items():
        if isinstance(clave, int):
            if clave == numero_ganador:
                premio += monto * 36
        else:
            condicion, multiplicador = BET_TYPES[clave]
            if condicion(numero_ganador):
                premio += monto * multiplicador

    return premio
