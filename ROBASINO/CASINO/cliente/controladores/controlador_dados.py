import threading

from modelos.modelo_dados import ResultadoLanzamiento
from vistas.casino_com import Jugador


class ControladorDados:
    """Cliente de red del juego de Craps.

    El servidor es la ÚNICA autoridad: decide los dados, descuenta y
    acredita créditos contra la base de datos, y guarda cada ronda en
    `partida`/`historial`. Este controlador NO calcula nada ni toca
    créditos localmente.

    Ya NO crea su propio hilo de escucha ni llama a recv(): el socket
    es compartido por todos los juegos, y el único que lo lee es
    `GestorConexion` (ver controladores/gestor_conexion.py). Este
    controlador solo:
      - envía la acción por `gestor_conexion.enviar(...)`
      - se suscribe con `register_handler` a las acciones que le
        interesan ("resultado_dados", "dados_error",
        "creditos_actualizados")
      - se desuscribe con `cerrar()` cuando la vista de Dados se cierra
    para no seguir recibiendo mensajes de un juego que ya no está en
    pantalla.
    """

    # Acciones del servidor que este controlador entiende.
    _ACCIONES = ("resultado_dados", "dados_error", "creditos_actualizados")

    def __init__(self, jugador: Jugador, gestor_conexion):
        self.jugador = jugador
        self.gestor = gestor_conexion

        self._on_resultado = None
        self._ronda_activa = False
        self._punto = None
        self._estado = "esperando"

        # Caché local solo para mostrar en pantalla; la verdad vive en
        # la tabla `partida`/`historial` del servidor. Se mantiene el
        # lock porque el hilo único de escucha (que llama a los
        # handlers) y el hilo de la GUI (que puede leer `historial`)
        # siguen siendo hilos distintos.
        self._historial: list[dict] = []
        self._lock_historial = threading.Lock()

        # Se guardan como bound methods para poder desuscribirlos
        # exactamente igual en cerrar().
        self._handlers = {
            "resultado_dados": self._manejar_resultado,
            "dados_error": self._manejar_error,
            "creditos_actualizados": self._manejar_creditos,
        }
        for accion, callback in self._handlers.items():
            self.gestor.register_handler(accion, callback)

    # ------------------------------------------------------------------
    # Validación (solo lectura — no descuenta nada, eso lo hace el server)
    # ------------------------------------------------------------------

    def validar_apuesta(self, monto: int) -> bool:
        creditos = getattr(self.jugador, "creditos", 0) or 0
        return isinstance(monto, int) and 0 < monto <= creditos

    # ------------------------------------------------------------------
    # Primer lanzamiento de la ronda (el servidor cobra la apuesta)
    # ------------------------------------------------------------------

    def iniciar_lanzamiento(self, monto: int, on_resultado) -> None:
        self._on_resultado = on_resultado
        self.gestor.enviar({"accion": "tirar_dados", "apuesta": monto})

    # ------------------------------------------------------------------
    # Lanzamientos siguientes (mientras haya un punto establecido)
    # ------------------------------------------------------------------

    def continuar_lanzamiento(self, on_resultado) -> None:
        self._on_resultado = on_resultado
        self.gestor.enviar({"accion": "tirar_dados"})

    # ------------------------------------------------------------------
    # Handlers registrados en GestorConexion (se ejecutan en el único
    # hilo de escucha compartido — igual que antes se ejecutaban en el
    # hilo propio de este controlador).
    # ------------------------------------------------------------------

    def _manejar_resultado(self, mensaje: dict) -> None:
        self._ronda_activa = mensaje.get("ronda_activa", False)
        self._punto = mensaje.get("punto")
        self._estado = mensaje.get("estado", self._estado)

        if "creditos" in mensaje:
            self.jugador.creditos = mensaje["creditos"]

        dado1 = mensaje.get("dado1")
        dado2 = mensaje.get("dado2")
        suma = mensaje.get("suma")
        premio = mensaje.get("premio", 0)

        if self._estado == "ganada":
            texto = (
                f"🎉 ¡GANASTE!  Salió {suma} ({dado1}-{dado2})\n"
                f"Premio: {premio} créditos"
            )
        elif self._estado == "perdida":
            texto = (
                f"😞 Perdiste.  Salió {suma} ({dado1}-{dado2})\n"
                f"Apuesta perdida."
            )
        else:
            texto = (
                f"Salió {suma} ({dado1}-{dado2}).\n"
                f"Punto establecido en {self._punto}. Vuelve a lanzar."
            )

        # Objeto con .dado1/.dado2/.suma (no un dict): la vista hace
        # resultado.suma, igual que con el ResultadoLanzamiento local
        # de antes.
        resultado = ResultadoLanzamiento(dado1, dado2)

        partida = {"dados": resultado.to_dict(), "estado": self._estado, "premio": premio}
        with self._lock_historial:
            self._historial.append(partida)

        if self._on_resultado:
            self._on_resultado(texto, resultado, premio, self._ronda_activa)

    def _manejar_error(self, mensaje: dict) -> None:
        self._ronda_activa = False
        if self._on_resultado:
            self._on_resultado(
                mensaje.get("mensaje", "Error del servidor."), None, 0, False
            )

    def _manejar_creditos(self, mensaje: dict) -> None:
        self.jugador.creditos = mensaje.get("creditos", self.jugador.creditos)

    # ------------------------------------------------------------------
    # Cierre — desuscribirse de GestorConexion
    # ------------------------------------------------------------------

    def cerrar(self) -> None:
        """Debe llamarse al cerrar la vista de Dados (botón Volver o
        cierre de ventana), para dejar de recibir mensajes de un juego
        que ya no está en pantalla. Es la contraparte del registro que
        se hizo en __init__ y sustituye al antiguo hilo `daemon=True`
        que se quedaba vivo indefinidamente."""
        self.gestor.unregister_all(self._handlers)

    # ------------------------------------------------------------------
    # Consultas de estado
    # ------------------------------------------------------------------

    @property
    def historial(self) -> list[dict]:
        with self._lock_historial:
            return list(self._historial)

    def hay_ronda_activa(self) -> bool:
        return self._ronda_activa

    def obtener_punto(self):
        return self._punto

    def obtener_estado(self) -> str:
        return self._estado
