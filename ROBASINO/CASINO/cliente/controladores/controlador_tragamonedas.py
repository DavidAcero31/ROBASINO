import threading

from modelos.modelo_tragamonedas import (
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
    """Cliente de red del juego de Tragamonedas.

    El servidor es la ÚNICA autoridad: decide los rodillos, descuenta y
    acredita créditos contra la base de datos, y guarda cada tirada en
    `partida`/`historial`. Este controlador NO calcula nada ni toca
    créditos localmente.

    Ya NO crea su propio hilo de escucha ni llama a recv(): el socket
    es compartido por todos los juegos, y el único que lo lee es
    `GestorConexion` (ver controladores/gestor_conexion.py). Este
    controlador solo envía acciones con `gestor_conexion.enviar(...)`
    y se suscribe/desuscribe con `register_handler`/`cerrar()` a las
    acciones que le interesan. Interfaz pública sin cambios:
    iniciar_giro, jugar, validar_apuesta, historial.
    """

    _ACCIONES = (
        "resultado_tragamonedas",
        "tragamonedas_error",
        "creditos_actualizados",
    )

    def __init__(self, jugador: Jugador, gestor_conexion):
        self.jugador = jugador
        self.gestor = gestor_conexion

        self._on_resultado = None

        # Caché local solo para mostrar en pantalla; la verdad vive en
        # la tabla `partida`/`historial` del servidor.
        self._historial: list[dict] = []
        self._lock_historial = threading.Lock()

        # Usado únicamente por jugar() (variante síncrona / bloqueante).
        self._resultado_sincrono = None
        self._evento_sincrono = threading.Event()

        # Se guardan como bound methods para poder desuscribirlos
        # exactamente igual en cerrar().
        self._handlers = {
            "resultado_tragamonedas": self._manejar_resultado,
            "tragamonedas_error": self._manejar_error,
            "creditos_actualizados": self._manejar_creditos,
        }
        for accion, callback in self._handlers.items():
            self.gestor.register_handler(accion, callback)

    # ------------------------------------------------------------------
    # Validación (solo lectura — no descuenta nada, eso lo hace el server)
    # ------------------------------------------------------------------

    def validar_apuesta(self, monto: int) -> bool:
        creditos = getattr(self.jugador, "creditos", 0) or 0
        return (
            isinstance(monto, int)
            and APUESTA_MINIMA <= monto <= APUESTA_MAXIMA
            and monto <= creditos
        )

    # ------------------------------------------------------------------
    # Giro asíncrono (con callback, para la vista con GUI)
    # ------------------------------------------------------------------

    def iniciar_giro(self, monto: int, on_resultado) -> None:
        self._on_resultado = on_resultado
        self.gestor.enviar({"accion": "jugar_tragamonedas", "apuesta": monto})

    # ------------------------------------------------------------------
    # Giro síncrono (bloqueante; se queda esperando la respuesta del server)
    # ------------------------------------------------------------------

    def jugar(self, monto: int, timeout: float = 10.0) -> dict:
        if not self.validar_apuesta(monto):
            return {"ganado": False, "premio": 0, "mensaje": "Apuesta inválida."}

        self._evento_sincrono.clear()
        self._resultado_sincrono = None
        self.gestor.enviar({"accion": "jugar_tragamonedas", "apuesta": monto})

        if not self._evento_sincrono.wait(timeout):
            return {"ganado": False, "premio": 0, "mensaje": "El servidor no respondió a tiempo."}

        return self._resultado_sincrono

    # ------------------------------------------------------------------
    # Handlers registrados en GestorConexion (se ejecutan en el único
    # hilo de escucha compartido — igual que antes se ejecutaban en el
    # hilo propio de este controlador).
    # ------------------------------------------------------------------

    def _manejar_resultado(self, mensaje: dict) -> None:
        if "creditos" in mensaje:
            self.jugador.creditos = mensaje["creditos"]

        nombres = mensaje.get("nombres", ("?", "?", "?"))
        premio = mensaje.get("premio", 0)
        multiplicador = mensaje.get("multiplicador", 0)

        if premio > 0:
            texto = (
                f"🎉 ¡GANASTE!  {nombres[0]} {nombres[1]} {nombres[2]}\n"
                f"Premio: {premio} créditos  (×{multiplicador})"
            )
        else:
            texto = (
                f"😞 Perdiste.  {nombres[0]} {nombres[1]} {nombres[2]}"
            )

        rodillos = tuple(mensaje.get("rodillos", ()))

        partida = {"rodillos": rodillos, "premio": premio}
        with self._lock_historial:
            self._historial.append(partida)

        if self._on_resultado:
            self._on_resultado(texto, rodillos, premio)

        self._resultado_sincrono = {
            "ganado": premio > 0,
            "premio": premio,
            "mensaje": f"{nombres[0]} {nombres[1]} {nombres[2]} — Premio: {premio}",
        }
        self._evento_sincrono.set()

    def _manejar_error(self, mensaje: dict) -> None:
        mensaje_error = mensaje.get("mensaje", "Error del servidor.")
        if self._on_resultado:
            self._on_resultado(mensaje_error, None, 0)
        self._resultado_sincrono = {
            "ganado": False, "premio": 0, "mensaje": mensaje_error,
        }
        self._evento_sincrono.set()

    def _manejar_creditos(self, mensaje: dict) -> None:
        self.jugador.creditos = mensaje.get("creditos", self.jugador.creditos)

    # ------------------------------------------------------------------
    # Cierre — desuscribirse de GestorConexion
    # ------------------------------------------------------------------

    def cerrar(self) -> None:
        """Debe llamarse al cerrar la vista de Tragamonedas (botón
        Volver o cierre de ventana), para dejar de recibir mensajes de
        un juego que ya no está en pantalla. Sustituye al antiguo hilo
        `daemon=True` que se quedaba vivo indefinidamente."""
        self.gestor.unregister_all(self._handlers)

    # ------------------------------------------------------------------
    # Consultas de estado
    # ------------------------------------------------------------------

    @property
    def historial(self) -> list[dict]:
        with self._lock_historial:
            return list(self._historial)
