"""
casino_core.py
==============
Módulo central del sistema ROBASINO.

Define las clases base compartidas por todos los módulos del casino:
  - Jugador : gestión de créditos con control de condición de carrera
              mediante threading.Lock().
  - JuegoBase : clase abstracta que establece la interfaz común
                para Ruleta y Tragamonedas.

Autores : Juan David Acero Urbano
          Johan David Rodriguez Perez
          Harold Steven Alfonso Perez
Curso   : Programación Multihilo — Unitrópico, 2026
"""

import threading


# ---------------------------------------------------------------------------
# Clase Jugador
# ---------------------------------------------------------------------------

class Jugador:
    """
    Representa a un jugador dentro del sistema ROBASINO.

    Gestiona el saldo de créditos de forma segura ante accesos concurrentes:
    cuando dos hilos (por ejemplo, el de Ruleta y el de Tragamonedas)
    intentan modificar el saldo al mismo tiempo, el candado (_lock) garantiza
    que las operaciones se ejecuten de forma exclusiva, evitando la condición
    de carrera.

    Atributos
    ----------
    nombre : str
        Nombre visible del jugador.
    _creditos : int
        Saldo actual (privado; se accede a través de propiedades).
    _lock : threading.Lock
        Candado que protege las operaciones sobre _creditos.
    """

    def __init__(self, nombre: str, creditos_iniciales: int = 1000):
        """
        Inicializa un jugador con un nombre y un saldo de créditos.

        Parámetros
        ----------
        nombre : str
            Nombre del jugador.
        creditos_iniciales : int, opcional
            Saldo de inicio (por defecto 1 000 créditos).
        """
        self.nombre = nombre
        self._creditos = creditos_iniciales
        self._lock = threading.Lock()  # Candado compartido para el saldo

    # ------------------------------------------------------------------
    # Propiedad de solo lectura: créditos
    # ------------------------------------------------------------------

    @property
    def creditos(self) -> int:
        """Retorna el saldo actual del jugador (lectura segura)."""
        with self._lock:
            return self._creditos

    # ------------------------------------------------------------------
    # Métodos de modificación de saldo (protegidos por candado)
    # ------------------------------------------------------------------

    def apostar(self, monto: int) -> bool:
        """
        Descuenta ``monto`` créditos si el saldo es suficiente.

        La operación completa (verificar + descontar) se ejecuta dentro
        del candado para evitar que dos hilos descuenten el mismo saldo
        simultáneamente (condición de carrera).

        Parámetros
        ----------
        monto : int
            Cantidad de créditos a apostar.

        Retorna
        -------
        bool
            True si la apuesta fue aceptada, False si no hay saldo suficiente.
        """
        with self._lock:
            if monto <= 0:
                return False
            if self._creditos >= monto:
                self._creditos -= monto
                return True
            return False

    def acreditar(self, monto: int) -> None:
        """
        Suma ``monto`` créditos al saldo del jugador.

        Parámetros
        ----------
        monto : int
            Cantidad de créditos a acreditar (debe ser positiva).
        """
        with self._lock:
            if monto > 0:
                self._creditos += monto

    def __str__(self) -> str:
        return f"Jugador('{self.nombre}', créditos={self.creditos})"


# ---------------------------------------------------------------------------
# Clase base JuegoBase
# ---------------------------------------------------------------------------

class JuegoBase:
    """
    Clase abstracta que define la interfaz común para todos los juegos
    del casino ROBASINO.

    Cada juego concreto (Ruleta, Tragamonedas, etc.) debe heredar de esta
    clase e implementar el método ``jugar()``.

    Atributos
    ----------
    jugador : Jugador
        Referencia al jugador que participa en el juego.
    nombre_juego : str
        Nombre descriptivo del juego.
    en_ejecucion : bool
        Indicador de si hay una partida activa en este momento.
    """

    def __init__(self, jugador: Jugador, nombre_juego: str):
        """
        Inicializa el juego con un jugador y un nombre.

        Parámetros
        ----------
        jugador : Jugador
            El jugador que participará en el juego.
        nombre_juego : str
            Nombre identificador del juego (p. ej. 'Tragamonedas').
        """
        self.jugador = jugador
        self.nombre_juego = nombre_juego
        self.en_ejecucion = False

    def jugar(self, monto: int) -> dict:
        """
        Método abstracto: ejecuta una ronda del juego.

        Las subclases deben sobrescribir este método.

        Parámetros
        ----------
        monto : int
            Créditos apostados en esta ronda.

        Retorna
        -------
        dict
            Diccionario con al menos las claves:
            - 'ganado'  (bool)   : True si el jugador ganó.
            - 'premio'  (int)    : Créditos obtenidos (0 si perdió).
            - 'mensaje' (str)    : Descripción del resultado.

        Lanza
        -----
        NotImplementedError
            Si la subclase no implementa este método.
        """
        raise NotImplementedError(
            f"La clase '{type(self).__name__}' debe implementar el método jugar()."
        )

    def __str__(self) -> str:
        return f"{self.nombre_juego} — Jugador: {self.jugador.nombre}"
