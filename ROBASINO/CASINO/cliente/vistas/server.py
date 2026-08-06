import socket
import threading
import tkinter as tk
from tkinter import ttk
import json
import queue
from datetime import datetime

import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from controladores.blackjack_game import BlackjackGame

import controladores.database as database
from controladores.database import UsuarioExistente, CorreoExistente, CreditosInsuficientes
import controladores.ruleta_logic as ruleta_logic
from modelos.modelo_dados import ModeloDados, EstadoRonda
from modelos.modelo_tragamonedas import ModeloTragamonedas


SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5555


class CasinoServer:

    def __init__(self):

        self.waiting_players = []
        # ------------------------
        # SOCKET
        # ------------------------
        self.server_socket = None
        self.running = True
        # ------------------------
        # CLIENTES
        # ------------------------
        self.clients = {}
        self.client_counter = 1
        # ------------------------
        # PARTIDAS
        # ------------------------
        self.games = {}
        self.game_id_counter = 1
        # Apuesta (créditos) asociada a cada partida activa, por game_id.
        # Ambos jugadores de una partida siempre apuestan el mismo monto.
        self.game_bets = {}
        # ------------------------
        # BASE DE DATOS
        # ------------------------
        # Cacheamos el id_juego de "blackjack" para no consultarlo
        # en cada partida. None si la BD no está disponible.
        self.id_juego_blackjack = None
        self.id_juego_ruleta = None
        self.id_juego_dados = None
        self.id_juego_tragamonedas = None
        self.ruleta_round_counter = 1
        self.dados_round_counter = 1
        self.tragamonedas_round_counter = 1
        # Rondas de dados activas por client_id: {"modelo": ModeloDados(),
        # "apuesta": int}. El craps tiene varios lanzamientos por ronda
        # (tirada inicial + posibles continuaciones hasta ganar/perder),
        # así que el estado vive aquí mientras la ronda esté abierta.
        self.dados_rondas = {}
        # Tragamonedas no tiene estado entre tiradas: una sola instancia
        # del modelo alcanza para todos los jugadores.
        self.modelo_tragamonedas = ModeloTragamonedas()
        # ------------------------
        # LOCK PARA ESTADO COMPARTIDO
        # ------------------------
        # RLock porque process_message mantiene el lock mientras
        # llama a match_player, que también necesita el lock.
        self.lock = threading.RLock()
        # ------------------------
        # COLA PARA TKINTER
        # ------------------------
        self.ui_queue = queue.Queue()
        # ------------------------
        # INTERFAZ
        # ------------------------

        self.root = tk.Tk()
        self.root.title("Casino Server")
        self.root.geometry("1200x720")
        self.root.configure(bg="#1b1b1b")
        self.build_ui()
        threading.Thread(
            target=self.init_database,
            daemon=True
        ).start()
        threading.Thread(
            target=self.start_server,
            daemon=True
        ).start()
        self.root.after(
            100,
            self.process_queue
        )
        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_server
        )
        self.root.mainloop()

    # ======================================================
    # INTERFAZ
    # ======================================================

    def build_ui(self):
        titulo = tk.Label(
            self.root,
            text="CASINO SERVER",
            font=("Arial", 24, "bold"),
            bg="#1b1b1b",
            fg="white"
        )
        titulo.pack(pady=10)

        estado = tk.LabelFrame(
            self.root,
            text="Estado del servidor",
            bg="#1b1b1b",
            fg="white"
        )
        estado.pack(fill="x", padx=10)
        self.lbl_server = tk.Label(
            estado,
            text="Servidor: Iniciando...",
            bg="#1b1b1b",
            fg="lime"
        )
        self.lbl_server.pack(anchor="w", padx=10)
        self.lbl_db = tk.Label(
            estado,
            text="Base de datos: Desconectada",
            bg="#1b1b1b",
            fg="orange"
        )
        self.lbl_db.pack(anchor="w", padx=10)
        self.lbl_clients = tk.Label(
            estado,
            text="Clientes conectados: 0",
            bg="#1b1b1b",
            fg="white"
        )
        self.lbl_clients.pack(anchor="w", padx=10)
        self.lbl_games = tk.Label(
            estado,
            text="Partidas activas: 0",
            bg="#1b1b1b",
            fg="white"
        )
        self.lbl_games.pack(anchor="w", padx=10)

        jugadores = tk.LabelFrame(
            self.root,
            text="Jugadores conectados",
            bg="#1b1b1b",
            fg="white"
        )
        jugadores.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )
        columnas = (
            "id",
            "usuario",
            "estado",
            "juego"
        )
        self.tree = ttk.Treeview(
            jugadores,
            columns=columnas,
            show="headings",
            height=10
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("usuario", text="Usuario")
        self.tree.heading("estado", text="Estado")
        self.tree.heading("juego", text="Juego")
        self.tree.column("id", width=80)
        self.tree.column("usuario", width=250)
        self.tree.column("estado", width=180)
        self.tree.column("juego", width=180)
        self.tree.pack(fill="both", expand=True)
        log_frame = tk.LabelFrame(
            self.root,
            text="Registro del servidor",
            bg="#1b1b1b",
            fg="white"
        )
        log_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )
        self.log = tk.Text(
            log_frame,
            bg="black",
            fg="lime",
            height=12,
            insertbackground="white"
        )
        self.log.pack(
            fill="both",
            expand=True
        )

    # ======================================================
    # REGISTRO
    # ======================================================

    def registrar_evento(self, mensaje):
        hora = datetime.now().strftime("%H:%M:%S")
        self.ui_queue.put(
            (
                "log",
                f"[{hora}] {mensaje}"
            )
        )

    # ======================================================
    # BASE DE DATOS
    # ======================================================

    def init_database(self):
        """Conecta el pool de MariaDB. Si falla, el servidor sigue
        funcionando (sockets, matchmaking, juego) pero login/registro
        y la persistencia de historial devolverán error hasta que la
        BD esté disponible."""
        try:
            database.init_pool()
            self.id_juego_blackjack = database.obtener_id_juego("blackjack")
            if self.id_juego_blackjack is None:
                self.registrar_evento(
                    "Advertencia: no se encontró el juego 'blackjack' en la "
                    "tabla `juego`. Revisa la semilla de base_casino.sql."
                )
            self.id_juego_ruleta = database.obtener_id_juego("ruleta")
            if self.id_juego_ruleta is None:
                self.registrar_evento(
                    "Advertencia: no se encontró el juego 'ruleta' en la tabla "
                    "`juego`. Revisa la semilla de base_casino.sql."
                )
            self.id_juego_dados = database.obtener_id_juego("dados")
            if self.id_juego_dados is None:
                self.registrar_evento(
                    "Advertencia: no se encontró el juego 'dados' en la tabla "
                    "`juego`. Revisa la semilla de base_casino.sql."
                )
            self.id_juego_tragamonedas = database.obtener_id_juego("tragamonedas")
            if self.id_juego_tragamonedas is None:
                self.registrar_evento(
                    "Advertencia: no se encontró el juego 'tragamonedas' en la "
                    "tabla `juego`. Revisa la semilla de base_casino.sql."
                )
            self.ui_queue.put(("db_estado", ("Base de datos: Conectada", "lime")))
            self.registrar_evento("Conexión a la base de datos establecida.")
        except Exception as e:
            self.ui_queue.put(("db_estado", (f"Base de datos: Error ({e})", "red")))
            self.registrar_evento(f"No se pudo conectar a la base de datos: {e}")

    # ======================================================
    # SOCKET
    # ======================================================

    def start_server(self):
        try:
            self.server_socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )
            self.server_socket.bind(
                (
                    SERVER_HOST,
                    SERVER_PORT
                )
            )
            self.server_socket.listen()
            self.registrar_evento(
                f"Servidor iniciado en {SERVER_HOST}:{SERVER_PORT}"
            )
            self.ui_queue.put(
                (
                    "estado",
                    "Servidor: ACTIVO"
                )
            )
            while self.running:
                client_socket, address = self.server_socket.accept()
                threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address),
                    daemon=True
                ).start()
        except Exception as e:
            self.registrar_evento(str(e))
    # ======================================================
    # CLIENTES
    # ======================================================

    def handle_client(self, client_socket, address):
        with self.lock:
            client_id = self.client_counter
            self.client_counter += 1
            self.clients[client_id] = {
                "socket": client_socket,
                "address": address,
                "usuario": f"Invitado {client_id}",
                "estado": "Conectado",
                "juego": "-",
                "partida": None,
                "id_jugador": None,
                "creditos": None,
                "apuesta": None
            }
        self.registrar_evento(
            f"Cliente {client_id} conectado desde {address}"
        )
        self.ui_queue.put(
            ("refresh", None)
        )
        buffer = ""
        while self.running:
            try:
                datos = client_socket.recv(4096)
                if not datos:
                    break
                buffer += datos.decode("utf-8")
                while "\n" in buffer:
                    linea, buffer = buffer.split("\n", 1)
                    if linea.strip():
                        mensaje = json.loads(linea)
                        self.process_message(
                            client_id,
                            mensaje
                        )
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
                self.registrar_evento(
                    f"Error con cliente {client_id}: {e}"
                )
                break

        self.registrar_evento(
            f"Cliente {client_id} desconectado."
        )
        client_socket.close()

        with self.lock:
            self.forfeit_game_for(client_id)
            self.dados_rondas.pop(client_id, None)
            if client_id in self.waiting_players:
                self.waiting_players.remove(client_id)
            if client_id in self.clients:
                del self.clients[client_id]

        self.ui_queue.put(
            ("refresh", None)
        )
    # ======================================================
    # MENSAJES
    # ======================================================

    def process_message(self, client_id, mensaje):
        accion = mensaje.get("accion")

        with self.lock:

            if client_id not in self.clients:
                return

            # -------------------------------
            # REGISTRO DE CUENTA NUEVA
            # -------------------------------
            if accion == "registro":
                self.handle_registro(client_id, mensaje)
            # -------------------------------
            # LOGIN
            # -------------------------------
            elif accion == "login":
                self.handle_login(client_id, mensaje)
            # -------------------------------
            # BUSCAR PARTIDA
            # -------------------------------
            elif accion == "buscar_partida":
                self.handle_buscar_partida(client_id, mensaje)
            # -------------------------------
            # HIT (PEDIR CARTA)
            # -------------------------------
            elif accion == "hit":
                self.handle_game_action(client_id, "hit")
            # -------------------------------
            # STAND (PLANTARSE)
            # -------------------------------
            elif accion == "stand":
                self.handle_game_action(client_id, "stand")
            # -------------------------------
            # DESCONECTAR
            # -------------------------------
            elif accion == "logout":
                self.registrar_evento(
                    f"{self.clients[client_id]['usuario']} cerró sesión."
                )
                self.forfeit_game_for(client_id)
                if client_id in self.waiting_players:
                    self.waiting_players.remove(client_id)
                self.clients[client_id]["estado"] = "Desconectado"
                self.ui_queue.put(
                    ("refresh", None)
                )
            elif accion == "girar_ruleta":
                self.handle_girar_ruleta(client_id, mensaje)
            # -------------------------------
            # DADOS (CRAPS)
            # -------------------------------
            elif accion == "tirar_dados":
                self.handle_tirar_dados(client_id, mensaje)
            # -------------------------------
            # TRAGAMONEDAS
            # -------------------------------
            elif accion == "jugar_tragamonedas":
                self.handle_jugar_tragamonedas(client_id, mensaje)
            # -------------------------------
            # DESCONOCIDO
            # -------------------------------
            else:
                self.registrar_evento(
                    f"Acción desconocida: {accion}"
                )

    # ======================================================
    # REGISTRO DE CUENTA
    # ======================================================

    def handle_registro(self, client_id, mensaje):
        # Se asume que ya se posee self.lock.

        nombre = mensaje.get("nombre", "")
        apellido = mensaje.get("apellido", "")
        correo = mensaje.get("correo", "")
        usuario = mensaje.get("usuario", "")
        contrasena = mensaje.get("contrasena", "")
        pais = mensaje.get("pais", "")

        if not usuario or not contrasena or not correo:
            self.send_message(
                client_id,
                {
                    "accion": "registro_error",
                    "mensaje": "Usuario, correo y contraseña son obligatorios."
                }
            )
            return

        try:
            jugador = database.registrar_jugador(
                nombre, apellido, correo, usuario, contrasena, pais
            )
            self.registrar_evento(
                f"Nueva cuenta registrada: {usuario}"
            )
            self.send_message(
                client_id,
                {
                    "accion": "registro_ok",
                    "usuario": jugador["usuario"]
                }
            )
        except (UsuarioExistente, CorreoExistente) as e:
            self.send_message(
                client_id,
                {"accion": "registro_error", "mensaje": str(e)}
            )
        except Exception as e:
            self.registrar_evento(f"Error al registrar {usuario}: {e}")
            self.send_message(
                client_id,
                {
                    "accion": "registro_error",
                    "mensaje": "No se pudo completar el registro "
                               "(¿está la base de datos disponible?)."
                }
            )

    # ======================================================
    # LOGIN
    # ======================================================

    def handle_login(self, client_id, mensaje):
        # Se asume que ya se posee self.lock.

        usuario = mensaje.get("usuario", "")
        contrasena = mensaje.get("contrasena", "")

        if not usuario or not contrasena:
            self.send_message(
                client_id,
                {
                    "accion": "login_error",
                    "mensaje": "Usuario y contraseña son obligatorios."
                }
            )
            return

        try:
            jugador = database.autenticar_jugador(usuario, contrasena)
        except Exception as e:
            self.registrar_evento(f"Error de BD al autenticar {usuario}: {e}")
            self.send_message(
                client_id,
                {
                    "accion": "login_error",
                    "mensaje": "Base de datos no disponible. Intenta más tarde."
                }
            )
            return

        if jugador is None:
            self.send_message(
                client_id,
                {
                    "accion": "login_error",
                    "mensaje": "Usuario o contraseña incorrectos."
                }
            )
            return

        self.clients[client_id]["usuario"] = jugador["usuario"]
        self.clients[client_id]["id_jugador"] = jugador["id_jugador"]
        self.clients[client_id]["creditos"] = jugador["creditos"]
        self.clients[client_id]["estado"] = "Conectado"

        self.registrar_evento(
            f"{jugador['usuario']} inició sesión."
        )
        self.send_message(
            client_id,
            {
                "accion": "login_ok",
                "client_id": client_id,
                "id_jugador": jugador["id_jugador"],
                "usuario": jugador["usuario"],
                "nombre": jugador["nombre"],
                "apellido": jugador["apellido"],
                "pais": jugador["pais"],
                "nivel": jugador["nivel"],
                "creditos": jugador["creditos"]
            }
        )
        self.ui_queue.put(
            ("refresh", None)
        )

    # ======================================================
    # SOLICITAR PARTIDA (valida la apuesta antes de emparejar)
    # ======================================================

    def handle_buscar_partida(self, client_id, mensaje):
        # Se asume que ya se posee self.lock.

        juego = mensaje.get("juego", "blackjack")
        apuesta = mensaje.get("apuesta")
        creditos = self.clients[client_id].get("creditos")

        if not isinstance(apuesta, int) or apuesta <= 0:
            self.send_message(
                client_id,
                {
                    "accion": "apuesta_error",
                    "mensaje": "La apuesta debe ser un número entero positivo."
                }
            )
            return

        if creditos is None:
            self.send_message(
                client_id,
                {
                    "accion": "apuesta_error",
                    "mensaje": "Debes iniciar sesión antes de apostar."
                }
            )
            return

        if apuesta > creditos:
            self.send_message(
                client_id,
                {
                    "accion": "apuesta_error",
                    "mensaje": f"No tienes suficientes créditos (tienes {creditos})."
                }
            )
            return

        self.clients[client_id]["juego"] = juego
        self.clients[client_id]["apuesta"] = apuesta

        self.registrar_evento(
            f"{self.clients[client_id]['usuario']} pidió partida de {juego} "
            f"apostando {apuesta}."
        )

        self.match_player(client_id)

        self.ui_queue.put(
            ("refresh", None)
        )
    # ======================================================
    # GIRAR RULETA (apuesta + resultado en una sola acción)
    # ======================================================

    def handle_girar_ruleta(self, client_id, mensaje):
        # Se asume que ya se posee self.lock.

        creditos = self.clients[client_id].get("creditos")
        id_jugador = self.clients[client_id].get("id_jugador")

        if creditos is None or id_jugador is None:
            self.send_message(
                client_id,
                {"accion": "ruleta_error", "mensaje": "Debes iniciar sesión antes de apostar."}
            )
            return

        apuestas_crudas = mensaje.get("apuestas", {})
        es_valido, error, apuestas, total_apostado = ruleta_logic.validar_apuestas(
            apuestas_crudas, creditos
        )
        if not es_valido:
            self.send_message(
                client_id,
                {"accion": "ruleta_error", "mensaje": error}
            )
            return

        # Cobrar el total apostado.
        try:
            nuevo_saldo = database.actualizar_creditos(id_jugador, -total_apostado)
        except CreditosInsuficientes:
            self.send_message(
                client_id,
                {"accion": "ruleta_error", "mensaje": "No tienes suficientes créditos."}
            )
            return
        except Exception as e:
            self.registrar_evento(f"Error de BD al cobrar apuesta de ruleta: {e}")
            self.send_message(
                client_id,
                {"accion": "ruleta_error", "mensaje": "Error de base de datos. Intenta más tarde."}
            )
            return

        self.clients[client_id]["creditos"] = nuevo_saldo

        # Resultado autoritativo: SOLO el servidor decide el número.
        numero = ruleta_logic.spin()
        premio = ruleta_logic.calcular_premio(apuestas, numero)

        if premio > 0:
            try:
                nuevo_saldo = database.actualizar_creditos(id_jugador, premio)
                self.clients[client_id]["creditos"] = nuevo_saldo
            except Exception as e:
                self.registrar_evento(f"Error de BD al pagar premio de ruleta: {e}")

        self.registrar_evento(
            f"{self.clients[client_id]['usuario']} jugó a la ruleta: "
            f"apostó {total_apostado}, salió {numero} ({ruleta_logic.color_of(numero)}), "
            f"ganó {premio}."
        )

        ronda_id = self.ruleta_round_counter
        self.ruleta_round_counter += 1

        if premio > total_apostado:
            resultado_bd = "gano"
        elif premio == total_apostado:
            resultado_bd = "empate"
        else:
            resultado_bd = "perdio"

        self._guardar_resultado_bd(
            ronda_id, client_id, resultado_bd,
            valor_apuesta=total_apostado, premio=premio,
            id_juego=self.id_juego_ruleta
        )

        self.send_message(
            client_id,
            {
                "accion": "resultado_ruleta",
                "numero": numero,
                "color": ruleta_logic.color_of(numero),
                "premio": premio,
                "creditos": self.clients[client_id]["creditos"]
            }
        )

        self.ui_queue.put(("refresh", None))

    # ======================================================
    # TIRAR DADOS (CRAPS) — puede requerir varios lanzamientos por ronda
    # ======================================================

    def handle_tirar_dados(self, client_id, mensaje):
        # Se asume que ya se posee self.lock.

        id_jugador = self.clients[client_id].get("id_jugador")
        creditos = self.clients[client_id].get("creditos")

        if id_jugador is None or creditos is None:
            self.send_message(
                client_id,
                {"accion": "dados_error", "mensaje": "Debes iniciar sesión antes de apostar."}
            )
            return

        ronda = self.dados_rondas.get(client_id)

        if ronda is None:
            # No hay ronda abierta: este lanzamiento es la tirada inicial,
            # así que se requiere y se cobra la apuesta.
            apuesta = mensaje.get("apuesta")

            if not isinstance(apuesta, int) or apuesta <= 0:
                self.send_message(
                    client_id,
                    {"accion": "dados_error", "mensaje": "La apuesta debe ser un entero positivo."}
                )
                return

            if apuesta > creditos:
                self.send_message(
                    client_id,
                    {"accion": "dados_error", "mensaje": f"No tienes suficientes créditos (tienes {creditos})."}
                )
                return

            try:
                nuevo_saldo = database.actualizar_creditos(id_jugador, -apuesta)
            except CreditosInsuficientes:
                self.send_message(
                    client_id,
                    {"accion": "dados_error", "mensaje": "No tienes suficientes créditos."}
                )
                return
            except Exception as e:
                self.registrar_evento(f"Error de BD al cobrar apuesta de dados: {e}")
                self.send_message(
                    client_id,
                    {"accion": "dados_error", "mensaje": "Error de base de datos. Intenta más tarde."}
                )
                return

            self.clients[client_id]["creditos"] = nuevo_saldo

            self.dados_rondas[client_id] = {
                "modelo": ModeloDados(),
                "apuesta": apuesta
            }
            ronda = self.dados_rondas[client_id]
        elif mensaje.get("apuesta") is not None:
            # Ya hay una ronda en curso (punto establecido): no se vuelve
            # a cobrar aunque el cliente mande una apuesta por error.
            self.registrar_evento(
                f"{self.clients[client_id]['usuario']} envió una apuesta en un "
                f"lanzamiento de continuación de dados; se ignora."
            )

        modelo = ronda["modelo"]
        apuesta = ronda["apuesta"]

        # Resultado autoritativo: SOLO el servidor tira los dados.
        resultado, estado = modelo.lanzar()

        premio = 0
        ronda_activa = estado in (EstadoRonda.TIRADA_INICIAL, EstadoRonda.PUNTO_ESTABLECIDO)

        if estado == EstadoRonda.GANADA:
            premio = apuesta * 2
            try:
                nuevo_saldo = database.actualizar_creditos(id_jugador, premio)
                self.clients[client_id]["creditos"] = nuevo_saldo
            except Exception as e:
                self.registrar_evento(f"Error de BD al pagar premio de dados: {e}")

        if not ronda_activa:
            del self.dados_rondas[client_id]

        self.registrar_evento(
            f"{self.clients[client_id]['usuario']} tiró los dados: "
            f"{resultado.dado1}-{resultado.dado2} (suma {resultado.suma}), "
            f"estado {estado.value}, apuesta {apuesta}, premio {premio}."
        )

        if estado in (EstadoRonda.GANADA, EstadoRonda.PERDIDA):
            resultado_bd = "gano" if estado == EstadoRonda.GANADA else "perdio"
            ronda_id = self.dados_round_counter
            self.dados_round_counter += 1
            self._guardar_resultado_bd(
                ronda_id, client_id, resultado_bd,
                valor_apuesta=apuesta, premio=premio,
                id_juego=self.id_juego_dados
            )

        self.send_message(
            client_id,
            {
                "accion": "resultado_dados",
                "dado1": resultado.dado1,
                "dado2": resultado.dado2,
                "suma": resultado.suma,
                "estado": estado.value,
                "punto": modelo.obtener_punto(),
                "ronda_activa": ronda_activa,
                "premio": premio,
                "creditos": self.clients[client_id]["creditos"]
            }
        )

        self.ui_queue.put(("refresh", None))

    # ======================================================
    # JUGAR TRAGAMONEDAS (apuesta + resultado en una sola acción)
    # ======================================================

    def handle_jugar_tragamonedas(self, client_id, mensaje):
        # Se asume que ya se posee self.lock.

        id_jugador = self.clients[client_id].get("id_jugador")
        creditos = self.clients[client_id].get("creditos")

        if id_jugador is None or creditos is None:
            self.send_message(
                client_id,
                {"accion": "tragamonedas_error", "mensaje": "Debes iniciar sesión antes de apostar."}
            )
            return

        apuesta = mensaje.get("apuesta")

        if not isinstance(apuesta, int) or apuesta <= 0:
            self.send_message(
                client_id,
                {"accion": "tragamonedas_error", "mensaje": "La apuesta debe ser un entero positivo."}
            )
            return

        if apuesta > creditos:
            self.send_message(
                client_id,
                {"accion": "tragamonedas_error", "mensaje": f"No tienes suficientes créditos (tienes {creditos})."}
            )
            return

        try:
            nuevo_saldo = database.actualizar_creditos(id_jugador, -apuesta)
        except CreditosInsuficientes:
            self.send_message(
                client_id,
                {"accion": "tragamonedas_error", "mensaje": "No tienes suficientes créditos."}
            )
            return
        except Exception as e:
            self.registrar_evento(f"Error de BD al cobrar apuesta de tragamonedas: {e}")
            self.send_message(
                client_id,
                {"accion": "tragamonedas_error", "mensaje": "Error de base de datos. Intenta más tarde."}
            )
            return

        self.clients[client_id]["creditos"] = nuevo_saldo

        # Resultado autoritativo: SOLO el servidor decide los rodillos.
        jugada = self.modelo_tragamonedas.jugar(apuesta)
        premio = jugada["premio"]

        if premio > 0:
            try:
                nuevo_saldo = database.actualizar_creditos(id_jugador, premio)
                self.clients[client_id]["creditos"] = nuevo_saldo
            except Exception as e:
                self.registrar_evento(f"Error de BD al pagar premio de tragamonedas: {e}")

        self.registrar_evento(
            f"{self.clients[client_id]['usuario']} jugó tragamonedas: "
            f"{jugada['nombres'][0]} {jugada['nombres'][1]} {jugada['nombres'][2]}, "
            f"apostó {apuesta}, ganó {premio}."
        )

        ronda_id = self.tragamonedas_round_counter
        self.tragamonedas_round_counter += 1

        resultado_bd = "gano" if premio > 0 else "perdio"

        self._guardar_resultado_bd(
            ronda_id, client_id, resultado_bd,
            valor_apuesta=apuesta, premio=premio,
            id_juego=self.id_juego_tragamonedas
        )

        self.send_message(
            client_id,
            {
                "accion": "resultado_tragamonedas",
                "rodillos": jugada["resultado"],
                "nombres": jugada["nombres"],
                "multiplicador": jugada["multiplicador"],
                "premio": premio,
                "creditos": self.clients[client_id]["creditos"]
            }
        )

        self.ui_queue.put(("refresh", None))

    # ======================================================
    # EMPAREJAR JUGADORES
    # ======================================================

    def match_player(self, client_id):
        # Se asume que ya se posee self.lock (llamado desde process_message).

        apuesta = self.clients[client_id]["apuesta"]

        # Buscar, entre los que ya esperan, uno que apueste lo mismo.
        rival = None
        for i, candidato in enumerate(self.waiting_players):
            if candidato == client_id:
                continue
            if candidato not in self.clients:
                continue  # se desconectó mientras esperaba; se limpia abajo
            if self.clients[candidato]["apuesta"] == apuesta:
                rival = candidato
                del self.waiting_players[i]
                break

        # Limpiar del listado de espera a cualquiera que ya no esté conectado
        self.waiting_players = [
            wid for wid in self.waiting_players if wid in self.clients
        ]

        if rival is None:
            if client_id not in self.waiting_players:
                self.waiting_players.append(client_id)

            self.clients[client_id]["estado"] = "Esperando jugador"

            self.registrar_evento(
                f"{self.clients[client_id]['usuario']} está esperando un rival "
                f"(apuesta: {apuesta})."
            )

            self.send_message(
                client_id,
                {
                    "accion": "esperando"
                }
            )

            self.ui_queue.put(
                ("refresh", None)
            )

            return

        # ------------------------------------------
        # Se encontró rival con la misma apuesta: cobrar ambas apuestas
        # (quedan "en la mesa" hasta que la partida termine).
        # ------------------------------------------

        if not self._cobrar_apuesta(rival, apuesta):
            # El rival ya no tiene fondos suficientes (pudo cambiar desde
            # que se puso en espera). Se descarta y este jugador reintenta.
            self.clients[rival]["apuesta"] = None
            self.send_message(
                rival,
                {
                    "accion": "apuesta_error",
                    "mensaje": "Tu apuesta ya no es válida. Elige un nuevo monto."
                }
            )
            self.match_player(client_id)
            return

        if not self._cobrar_apuesta(client_id, apuesta):
            # Reembolsar al rival, ya que este jugador no puede pagar.
            self._reembolsar_apuesta(rival, apuesta)
            self.waiting_players.append(rival)
            self.send_message(
                client_id,
                {
                    "accion": "apuesta_error",
                    "mensaje": "No tienes suficientes créditos para esa apuesta."
                }
            )
            return

        game_id = self.game_id_counter
        self.game_id_counter += 1

        partida = BlackjackGame(
            game_id,
            rival,
            client_id
        )

        self.games[game_id] = partida
        self.game_bets[game_id] = apuesta

        self.clients[rival]["estado"] = "Jugando"
        self.clients[client_id]["estado"] = "Jugando"

        self.clients[rival]["partida"] = game_id
        self.clients[client_id]["partida"] = game_id

        self.registrar_evento(
            f"Partida #{game_id} creada entre "
            f"{self.clients[rival]['usuario']} y "
            f"{self.clients[client_id]['usuario']} "
            f"(apuesta: {apuesta} c/u)."
        )

        estado = partida.get_state()

        for pid in (rival, client_id):
            self.send_message(
                pid,
                {
                    "accion": "iniciar_partida",
                    "estado": estado,
                    "apuesta": apuesta,
                    "tus_creditos": self.clients[pid]["creditos"]
                }
            )

        self.ui_queue.put(
            ("refresh", None)
        )

    # ======================================================
    # COBRAR / REEMBOLSAR APUESTA (escrow)
    # ======================================================

    def _cobrar_apuesta(self, client_id, apuesta):
        """Descuenta `apuesta` créditos del jugador (BD + caché local).
        Devuelve True si se pudo cobrar, False si no tiene fondos o hay
        error de BD (en cuyo caso ya se registró el evento)."""

        id_jugador = self.clients[client_id].get("id_jugador")
        if id_jugador is None:
            return False

        try:
            nuevo_saldo = database.actualizar_creditos(id_jugador, -apuesta)
        except CreditosInsuficientes:
            return False
        except Exception as e:
            self.registrar_evento(
                f"Error de BD al cobrar apuesta de "
                f"{self.clients[client_id]['usuario']}: {e}"
            )
            return False

        self.clients[client_id]["creditos"] = nuevo_saldo
        return True

    def _pagar_premio(self, client_id, premio):
        """Acredita `premio` (puede ser 0) al jugador y le avisa su nuevo
        saldo. Si premio es 0 igual se notifica, para que el cliente
        refresque el label de créditos tras una partida perdida."""

        if client_id not in self.clients:
            return
        id_jugador = self.clients[client_id].get("id_jugador")
        if id_jugador is None:
            return

        try:
            if premio > 0:
                nuevo_saldo = database.actualizar_creditos(id_jugador, premio)
                self.clients[client_id]["creditos"] = nuevo_saldo
            else:
                nuevo_saldo = self.clients[client_id]["creditos"]
        except Exception as e:
            self.registrar_evento(
                f"Error de BD al pagar premio a "
                f"{self.clients[client_id]['usuario']}: {e}"
            )
            nuevo_saldo = self.clients[client_id]["creditos"]

        self.send_message(
            client_id,
            {"accion": "creditos_actualizados", "creditos": nuevo_saldo}
        )

    def _reembolsar_apuesta(self, client_id, apuesta):
        if client_id not in self.clients:
            return
        id_jugador = self.clients[client_id].get("id_jugador")
        if id_jugador is None:
            return
        try:
            nuevo_saldo = database.actualizar_creditos(id_jugador, apuesta)
            self.clients[client_id]["creditos"] = nuevo_saldo
            self.send_message(
                client_id,
                {"accion": "creditos_actualizados", "creditos": nuevo_saldo}
            )
        except Exception as e:
            self.registrar_evento(
                f"Error de BD al reembolsar apuesta: {e}"
            )

    # ======================================================
    # PROCESAR ACCIÓN DE JUEGO (hit / stand)
    # ======================================================

    def handle_game_action(self, client_id, accion):
        # Se asume que ya se posee self.lock (llamado desde process_message).

        game_id = self.clients[client_id].get("partida")

        if game_id is None or game_id not in self.games:
            self.send_message(
                client_id,
                {
                    "accion": "error",
                    "mensaje": "No estás en ninguna partida activa."
                }
            )
            return

        partida = self.games[game_id]

        if not partida.has_player(client_id):
            self.send_message(
                client_id,
                {
                    "accion": "error",
                    "mensaje": "No perteneces a esta partida."
                }
            )
            return

        if partida.is_finished():
            return

        if not partida.is_player_turn(client_id):
            self.send_message(
                client_id,
                {
                    "accion": "error",
                    "mensaje": "No es tu turno."
                }
            )
            return

        if accion == "hit":
            partida.hit(client_id)
        elif accion == "stand":
            partida.stand(client_id)

        estado = partida.get_state()

        self.send_message(
            partida.player1,
            {
                "accion": "estado_partida",
                "estado": estado
            }
        )
        self.send_message(
            partida.player2,
            {
                "accion": "estado_partida",
                "estado": estado
            }
        )

        self.registrar_evento(
            f"{self.clients[client_id]['usuario']} jugó '{accion}' en partida #{game_id}."
        )

        if partida.is_finished():
            self.finish_game(game_id)

        self.ui_queue.put(
            ("refresh", None)
        )

    # ======================================================
    # PERSISTIR RESULTADO EN LA BASE DE DATOS
    # ======================================================

    def _guardar_resultado_bd(self, game_id, client_id, resultado,
                            valor_apuesta=0, premio=0, id_juego=None):
        """... (docstring unchanged) ...
        `id_juego` permite reutilizar este método para juegos distintos a
        blackjack; por defecto usa self.id_juego_blackjack."""

        if id_juego is None:
            id_juego = self.id_juego_blackjack

        if id_juego is None:
            return  # BD no disponible o juego no encontrado; no bloquea el juego

        datos_cliente = self.clients.get(client_id)
        if datos_cliente is None:
            return

        id_jugador = datos_cliente.get("id_jugador")
        if id_jugador is None:
            return

        try:
            id_partida = database.registrar_partida(
                id_ronda=game_id,
                id_jugador=id_jugador,
                id_juego=id_juego,
                valor_apuesta=valor_apuesta,
                resultado=resultado,
                premio=premio
            )
            database.registrar_historial(
                id_partida,
                estado_anterior="en_curso",
                estado_nuevo=resultado
            )
        except Exception as e:
            self.registrar_evento(
                f"Error al guardar en BD la partida #{game_id} "
                f"de {datos_cliente['usuario']}: {e}"
            )

    # ======================================================
    # FINALIZAR PARTIDA (normal, ambos jugadores presentes)
    # ======================================================

    def finish_game(self, game_id):
        # Se asume que ya se posee self.lock.

        partida = self.games.pop(game_id, None)
        if partida is None:
            return

        resultado = partida.get_result()
        mensaje = resultado["message"] if resultado else "Partida finalizada."
        self.registrar_evento(
            f"Partida #{game_id} finalizada: {mensaje}"
        )

        apuesta = self.game_bets.pop(game_id, 0)
        pot = apuesta * 2

        if resultado:
            ganador = resultado.get("winner")
            for pid in (partida.player1, partida.player2):
                if ganador is None:
                    # Empate: se devuelve su propia apuesta a cada uno.
                    resultado_bd = "empate"
                    premio = apuesta
                elif pid == ganador:
                    # Gana el bote completo (su apuesta + la del rival).
                    resultado_bd = "gano"
                    premio = pot
                else:
                    # Pierde su apuesta, que ya estaba descontada.
                    resultado_bd = "perdio"
                    premio = 0

                self._pagar_premio(pid, premio)
                self._guardar_resultado_bd(
                    game_id, pid, resultado_bd,
                    valor_apuesta=apuesta, premio=premio
                )

        for pid in (partida.player1, partida.player2):
            if pid in self.clients:
                self.clients[pid]["estado"] = "Conectado"
                self.clients[pid]["juego"] = "-"
                self.clients[pid]["partida"] = None
                self.clients[pid]["apuesta"] = None

    # ======================================================
    # DAR POR PERDIDA LA PARTIDA DE UN JUGADOR QUE SE VA
    # ======================================================

    def forfeit_game_for(self, client_id):
        # Se asume que ya se posee self.lock.
        # Usado cuando un jugador se desconecta o hace logout
        # mientras tenía una partida activa: el rival gana por abandono.

        if client_id not in self.clients:
            return

        game_id = self.clients[client_id].get("partida")
        if game_id is None or game_id not in self.games:
            return

        partida = self.games.pop(game_id)

        rival_id = (
            partida.player2
            if client_id == partida.player1
            else partida.player1
        )

        self.registrar_evento(
            f"Partida #{game_id} terminada: "
            f"{self.clients[client_id]['usuario']} abandonó la partida."
        )

        apuesta = self.game_bets.pop(game_id, 0)
        pot = apuesta * 2

        # El que abandona ya perdió su apuesta (estaba descontada al empezar).
        self._guardar_resultado_bd(
            game_id, client_id, "abandono",
            valor_apuesta=apuesta, premio=0
        )
        self.clients[client_id]["apuesta"] = None

        if rival_id in self.clients:
            self._pagar_premio(rival_id, pot)
            self._guardar_resultado_bd(
                game_id, rival_id, "gano",
                valor_apuesta=apuesta, premio=pot
            )
            self.clients[rival_id]["estado"] = "Conectado"
            self.clients[rival_id]["juego"] = "-"
            self.clients[rival_id]["partida"] = None
            self.clients[rival_id]["apuesta"] = None
            self.send_message(
                rival_id,
                {
                    "accion": "rival_desconectado",
                    "mensaje": "Tu rival se desconectó. Ganaste la partida."
                }
            )

    # ======================================================
    # ENVIAR MENSAJE
    # ======================================================
    def send_message(self, client_id, mensaje):
        if client_id not in self.clients:
            return
        try:
            socket_cliente = self.clients[client_id]["socket"]
            socket_cliente.sendall(
                (
                    json.dumps(mensaje)
                    + "\n"
                ).encode("utf-8")
            )
        except Exception as e:
            self.registrar_evento(
                str(e)
            )
    # ======================================================
    # ENVIAR A TODOS
    # ======================================================
    def broadcast(self, mensaje):
        for client_id in list(self.clients.keys()):
            self.send_message(
                client_id,
                mensaje
            )
    # ======================================================
    # ACTUALIZAR TABLA
    # ======================================================
    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        with self.lock:
            clientes = list(self.clients.items())
            n_clientes = len(self.clients)
            n_juegos = len(self.games)
        for client_id, datos in clientes:
            self.tree.insert(
                "",
                "end",
                values=(
                    client_id,
                    datos["usuario"],
                    datos["estado"],
                    datos["juego"]
                )
            )
        self.lbl_clients.config(
            text=f"Clientes conectados: {n_clientes}"
        )
        self.lbl_games.config(
            text=f"Partidas activas: {n_juegos}"
        )

    # ======================================================
    # COLA TKINTER
    # ======================================================

    def process_queue(self):
        while not self.ui_queue.empty():
            tipo, dato = self.ui_queue.get()
            if tipo == "log":
                self.log.insert(
                    "end",
                    dato + "\n"
                )
                self.log.see("end")
            elif tipo == "refresh":
                self.refresh_tree()
            elif tipo == "estado":
                self.lbl_server.config(
                    text=dato
                )
            elif tipo == "db_estado":
                texto, color = dato
                self.lbl_db.config(
                    text=texto,
                    fg=color
                )
        self.root.after(
            100,
            self.process_queue
        )
    # ======================================================
    # CERRAR
    # ======================================================
    def close_server(self):
        self.running = False
        self.registrar_evento(
            "Servidor detenido."
        )
        try:
            self.server_socket.close()
        except:
            pass
        with self.lock:
            for cliente in self.clients.values():
                try:
                    cliente["socket"].close()
                except:
                    pass
        self.root.destroy()

# ======================================================
# MAIN
# ======================================================

if __name__ == "__main__":
    CasinoServer()
