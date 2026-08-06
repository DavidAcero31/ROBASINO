"""
ControladorRuleta — sigue exactamente el mismo patrón que
ControladorDados y ControladorTragamonedas: es el ÚNICO punto del
cliente que le habla al servidor sobre la ruleta.

- No abre socket ni hilo propio. Usa el GestorConexion COMPARTIDO que
  recibe en el constructor (ver gestor_conexion.py) — el mismo que ya
  usan Dados y Tragamonedas.
- Se suscribe con `conexion.register_handler(accion, callback)` a las
  dos acciones que el servidor ya manda para ruleta
  (`server.handle_girar_ruleta`): "resultado_ruleta" y "ruleta_error".
- Se desuscribe con `conexion.unregister_all(...)` en `cerrar()`,
  exactamente igual que Dados/Tragamonedas deben hacerlo al cerrar su
  vista — así ningún mensaje tardío termina despachado a una vista ya
  destruida.
- NUNCA decide el número ganador ni calcula premios: solo arma el
  mensaje "girar_ruleta" con las apuestas crudas del jugador y le pasa
  a la vista, sin tocar, lo que el servidor responda. La autoridad
  sobre número/color/premio/créditos es 100% del servidor
  (ruleta_logic.py, ejecutado en server.py).
- La vista (vistas/ruleta.py) nunca importa json/socket ni conoce al
  GestorConexion: solo llama a `girar(apuestas)` y expone los métodos
  de callback que este controlador invoca.

Si el ControladorDados/ControladorTragamonedas real usa nombres de
métodos de callback distintos a `on_resultado_servidor` /
`on_error_servidor`, ajusta esos dos nombres aquí y en ruleta.py — el
resto del patrón (registro/desregistro, envío, "el servidor manda") no
cambia.
"""

from __future__ import annotations


class ControladorRuleta:
    ACCION_GIRAR = "girar_ruleta"          # → servidor (mensaje saliente)
    ACCION_RESULTADO = "resultado_ruleta"  # ← servidor (ver server.py:700)
    ACCION_ERROR = "ruleta_error"          # ← servidor (ver server.py:641 etc.)

    def __init__(self, conexion, jugador, vista):
        """
        conexion: instancia COMPARTIDA de GestorConexion (la misma que
                   usan Dados/Tragamonedas/Blackjack). Nunca se crea
                   una nueva aquí ni se llama a sock.recv().
        jugador:   objeto Jugador de la sesión actual, para reflejar
                   los créditos autoritativos que devuelva el servidor.
        vista:     la instancia de Ruleta (Tk). Debe exponer:
                     - on_resultado_servidor(numero, color, premio, creditos)
                     - on_error_servidor(mensaje)
        """
        self._conexion = conexion
        self._jugador = jugador
        self._vista = vista

        # Mismo diccionario {accion: callback} que se pasa tal cual a
        # unregister_all() al cerrar — así no hay que repetir la lista
        # de acciones en dos lugares distintos.
        self._handlers = {
            self.ACCION_RESULTADO: self._on_resultado,
            self.ACCION_ERROR: self._on_error,
        }
        for accion, callback in self._handlers.items():
            self._conexion.register_handler(accion, callback)

    # ------------------------------------------------------------------
    # Llamado por la vista cuando el jugador presiona "GIRAR"
    # ------------------------------------------------------------------

    def girar(self, apuestas: dict) -> None:
        """`apuestas` es el dict crudo {clave: monto} que arma la vista
        (BetManager.bets): clave puede ser un int 0-36 o uno de los
        nombres de apuesta externa ("Rojo", "1ª Doc.", etc). Este
        controlador NO valida montos ni resuelve nada — solo lo manda
        tal cual; server.handle_girar_ruleta / ruleta_logic.py son
        quienes validan, cobran, giran y pagan."""
        if not apuestas:
            return
        # JSON exige claves string; el servidor las vuelve a convertir
        # a int cuando corresponde (ruleta_logic._normalizar_clave).
        apuestas_json = {str(clave): monto for clave, monto in apuestas.items()}
        self._conexion.enviar({
            "accion": self.ACCION_GIRAR,
            "apuestas": apuestas_json,
        })

    # ------------------------------------------------------------------
    # Cierre — SIEMPRE debe llamarse al destruir la vista de ruleta
    # ------------------------------------------------------------------

    def cerrar(self) -> None:
        self._conexion.unregister_all(self._handlers)

    # ------------------------------------------------------------------
    # Callbacks del GestorConexion (corren en el hilo único de escucha)
    # ------------------------------------------------------------------

    def _on_resultado(self, mensaje: dict) -> None:
        creditos = mensaje.get("creditos")
        if self._jugador is not None and creditos is not None:
            # Único lugar donde se actualiza el saldo real del jugador
            # para esta jugada: viene del servidor, no se inventa aquí.
            self._jugador.creditos = creditos

        self._vista.on_resultado_servidor(
            numero=mensaje.get("numero"),
            color=mensaje.get("color"),
            premio=mensaje.get("premio", 0),
            creditos=creditos,
        )

    def _on_error(self, mensaje: dict) -> None:
        self._vista.on_error_servidor(mensaje.get("mensaje", "Error desconocido."))
