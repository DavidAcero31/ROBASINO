"""
GestorConexion — el ÚNICO lugar del cliente que lee del socket compartido.

Antes, cada controlador (ControladorDados, ControladorTragamonedas,
BlackjackClient) creaba su propio hilo con un `while True: sock.recv(...)`
sobre el MISMO socket. Con varios juegos abiertos (o cerrados sin haber
sido destruidos correctamente), había varios hilos compitiendo por leer
el mismo stream TCP: la línea que el servidor mandaba como respuesta a
"jugar_tragamonedas" podía terminar en el buffer del hilo de Craps, o al
revés, según cuál hilo ganara la carrera por `recv()`. Eso explica los
síntomas: tragamonedas "gira para siempre", dados se queda en "Listo
para jugar", el botón Volver no se reactiva — el mensaje SÍ llegó, pero
lo consumió el hilo equivocado.

Este módulo resuelve el problema de raíz, no lo esconde:

- Hay exactamente UN hilo (`_hilo_escucha`) que llama a `sock.recv()`
  en todo el proceso cliente, sin importar cuántos juegos se abran o
  cierren.
- Ese hilo separa el stream en líneas JSON (un mensaje por línea) y
  despacha cada mensaje según su campo "accion" a quien esté
  suscrito — no hay "carrera" posible porque no hay nadie más leyendo.
- Los controladores de juego ya NO llaman a recv() ni crean hilos.
  Se suscriben con `register_handler(accion, callback)` a las acciones
  que les interesan, y se desuscriben con `unregister_handler(...)`
  cuando el juego se cierra.
- El envío (`enviar`) sigue estando disponible para cualquier hilo
  (varios controladores podrían mandar mensajes "a la vez"); se
  protege con un lock solo para que dos `sendall()` no se entrelacen
  en el mismo paquete TCP — esto NO es un parche para el problema de
  `recv()`, es la sincronización normal y mínima que necesita un
  socket de escritura compartido.

El protocolo del servidor no cambia: sigue siendo JSON con un objeto
por línea (terminado en "\n") y cada mensaje sigue trayendo "accion".
"""

from __future__ import annotations

import json
import socket
import threading
import traceback
from collections import defaultdict


# Acción interna (no viene del servidor) que se despacha cuando la
# conexión se cae, para que cualquier controlador suscrito pueda
# reaccionar (ej. mostrar "Desconectado del servidor.") sin tener que
# sondear el socket por su cuenta.
ACCION_DESCONEXION = "_desconexion"


class GestorConexion:
    """Único lector del socket compartido; despacha por "accion"."""

    def __init__(self, sock: socket.socket):
        self._sock = sock

        # Protege sendall(): puede ser llamado desde varios hilos
        # (distintos controladores/vistas), pero NUNCA se usa para
        # serializar lecturas — solo hay un lector, así que no hace
        # falta ningún lock alrededor de recv().
        self._lock_envio = threading.Lock()

        self._lock_handlers = threading.Lock()
        self._handlers: dict[str, list] = defaultdict(list)

        self._activo = True

        self._hilo_escucha = threading.Thread(
            target=self._escuchar,
            daemon=True,
            name="gestor_conexion_hilo_unico",
        )
        self._hilo_escucha.start()

    # ------------------------------------------------------------------
    # Suscripción de controladores/vistas
    # ------------------------------------------------------------------

    def register_handler(self, accion: str, callback) -> None:
        """Suscribe `callback(mensaje: dict)` a los mensajes cuyo campo
        "accion" sea `accion`. Se puede llamar desde cualquier hilo
        (normalmente desde el hilo principal de Tkinter, al abrir un
        juego). Varias vistas pueden suscribirse a la misma acción
        (por ejemplo, "creditos_actualizados")."""
        with self._lock_handlers:
            if callback not in self._handlers[accion]:
                self._handlers[accion].append(callback)

    def unregister_handler(self, accion: str, callback) -> None:
        """Se debe llamar SIEMPRE que un juego se cierra, para dejar de
        recibir mensajes destinados a una vista que ya no existe."""
        with self._lock_handlers:
            lista = self._handlers.get(accion)
            if not lista:
                return
            if callback in lista:
                lista.remove(callback)
            if not lista:
                del self._handlers[accion]

    def unregister_all(self, handlers_por_accion: dict) -> None:
        """Azúcar sintáctica: desuscribe de una sola vez todos los
        handlers de un controlador. `handlers_por_accion` es el mismo
        dict {accion: callback} que se usó para registrarlos."""
        for accion, callback in handlers_por_accion.items():
            self.unregister_handler(accion, callback)

    # ------------------------------------------------------------------
    # Envío (puede llamarse desde cualquier hilo)
    # ------------------------------------------------------------------

    def enviar(self, mensaje: dict) -> None:
        if not self._sock:
            return
        datos = (json.dumps(mensaje) + "\n").encode("utf-8")
        try:
            with self._lock_envio:
                self._sock.sendall(datos)
        except OSError:
            self._despachar(ACCION_DESCONEXION, {"accion": ACCION_DESCONEXION})

    # ------------------------------------------------------------------
    # El ÚNICO lugar de todo el cliente que llama a sock.recv()
    # ------------------------------------------------------------------

    def _escuchar(self) -> None:
        buffer = ""
        while self._activo:
            try:
                datos = self._sock.recv(4096)
                if not datos:
                    break
                buffer += datos.decode("utf-8")
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    if linea.strip():
                        try:
                            mensaje = json.loads(linea)
                        except json.JSONDecodeError:
                            continue
                        self._despachar(mensaje.get("accion"), mensaje)
            except (ConnectionResetError, OSError):
                break

        self._activo = False
        self._despachar(ACCION_DESCONEXION, {"accion": ACCION_DESCONEXION})

    def _despachar(self, accion, mensaje: dict) -> None:
        with self._lock_handlers:
            callbacks = list(self._handlers.get(accion, ()))

        if not callbacks:
            # Ningún juego abierto está suscrito a esta acción: se
            # descarta, igual que antes se ignoraba silenciosamente
            # "cualquier otra accion" en cada controlador.
            return

        for callback in callbacks:
            try:
                callback(mensaje)
            except Exception:
                # Un handler roto no puede tumbar el único hilo de
                # escucha de todo el cliente.
                traceback.print_exc()

    # ------------------------------------------------------------------
    # Cierre explícito (logout / salir de la aplicación)
    # ------------------------------------------------------------------

    def cerrar(self) -> None:
        self._activo = False
        try:
            self._sock.close()
        except OSError:
            pass
