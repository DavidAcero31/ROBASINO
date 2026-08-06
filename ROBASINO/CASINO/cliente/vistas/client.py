"""
Cliente de Blackjack (hace de Jugador).
Pantalla completa por defecto (Esc para salir, F11 para alternar) y layout
responsive: todo se ubica con coordenadas relativas y las cartas/el fondo
se reescalan automáticamente al cambiar el tamaño de la ventana.

Este cliente NO contiene lógica de juego ni acceso a base de datos.
Solo:
    - envía acciones de juego ("buscar_partida", "hit", "stand")
    - recibe el estado autoritativo del servidor y lo dibuja
"""



import threading
import json
import queue
import tkinter as tk
from tkinter import simpledialog, messagebox

from controladores.game_logic import calculate_score
from .ui_base import BaseGameUI
import vistas.theme as theme

SERVER_HOST = "127.0.0.1"  # cambiar por la IP del servidor si es otra máquina
SERVER_PORT = 5555

class BetDialog(simpledialog.Dialog):
    """Ventana modal para elegir cuánto apostar antes de buscar partida.
    Resultado en self.result: int (la apuesta), o None si se canceló
    (cancelar aquí cierra el cliente, ya que sin apuesta no hay partida)."""

    def __init__(self, parent, creditos_disponibles, error_text=None):
        self._creditos = creditos_disponibles
        self._error_text = error_text
        self._valor = None
        super().__init__(parent, title="Casino - Elegir apuesta")

    def body(self, master):
        row = 0
        if self._error_text:
            tk.Label(master, text=self._error_text, fg="red",
                    wraplength=280, justify="left").grid(
                row=row, column=0, columnspan=2, pady=(0, 8), sticky="w")
            row += 1

        tk.Label(master, text=f"Créditos disponibles: {self._creditos}").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row += 1

        tk.Label(master, text="Apuesta:").grid(row=row, column=0, sticky="e")
        self.e_apuesta = tk.Entry(master)
        default = min(100, self._creditos) if self._creditos else 0
        self.e_apuesta.insert(0, str(default))
        self.e_apuesta.grid(row=row, column=1, pady=2)

        return self.e_apuesta

    def validate(self):
        texto = self.e_apuesta.get().strip()
        if not texto.isdigit():
            messagebox.showwarning(
                "Apuesta inválida", "Ingresa un número entero positivo.",
                parent=self)
            return False
        valor = int(texto)
        if valor <= 0:
            messagebox.showwarning(
                "Apuesta inválida", "La apuesta debe ser mayor que 0.",
                parent=self)
            return False
        if self._creditos is not None and valor > self._creditos:
            messagebox.showwarning(
                "Créditos insuficientes",
                f"Solo tienes {self._creditos} créditos.", parent=self)
            return False
        self._valor = valor
        return True

    def apply(self):
        self.result = self._valor


class BlackjackClient(BaseGameUI):
    def __init__(self, parent, jugador, conexion):
        # ---- identidad ----
        self.parent = parent
        self.jugador = jugador
        self.sock = conexion
        threading.Thread(
            target=self._listen_server,
            daemon=True
        ).start()

        self.player_id = jugador.client_id  
        self.username = jugador.usuario
        self.creditos = jugador.creditos

        # ---- estado de partida ----
        self.player_hand = []
        self.dealer_hand = []
        self.player_score = 0
        self.dealer_score = 0
        self.is_my_turn = False
        self.finished = False
        self.result_text = None

        # ---- apuesta ----
        self.apuesta_actual = 0

        # ---- estado de conexión / matchmaking ----
        self.in_game = False
        self.waiting_for_match = False
        self.logged_in = True

        self.sock = conexion
        self.msg_queue = queue.Queue()

        self._init_window("Blackjack - Cliente (Jugador)")
        self._build_ui()
        self.root.update_idletasks()
        self._apply_background()

        self.refresh_ui()

        self.root.after(100, self._process_queue)

        self._pedir_apuesta()

    def _pedir_apuesta(self, error_text=None):
        """Abre el diálogo de apuesta y, si el jugador eligió un monto,
        pide partida con esa apuesta. Si cancela, se cierra el cliente
        (no tiene sentido quedarse conectado sin poder jugar)."""
        dialogo = BetDialog(self.root, creditos_disponibles=self.creditos,
                            error_text=error_text)
        apuesta = dialogo.result
        if apuesta is None:
            self._on_close()
            return

        self.apuesta_actual = apuesta
        self.finished = False
        self.result_text = None
        self.waiting_for_match = True
        self.msg_queue.put(("status", f"Buscando partida (apuesta: {apuesta})..."))
        self._send({
            "accion": "buscar_partida",
            "juego": "blackjack",
            "apuesta": apuesta
        })
        self.refresh_ui()

    def on_play_again(self):
        self.in_game = False
        self._pedir_apuesta()

    # ---------------- UI ----------------
    def _build_ui(self):
        info_panel = self._panel(0.02, 0.02, 0.30, 0.10)
        self._themed_label(info_panel, text="Rol: Jugador", anchor="w").pack(
            anchor="w", padx=12, pady=(10, 2))
        self.status_label = self._themed_label(
            info_panel, text="Conectando...", font=theme.FONT_SMALL,
            fg=theme.TEXT_GREEN_DIM, anchor="w")
        self.status_label.pack(anchor="w", padx=12)
        self.credits_label = self._themed_label(
            info_panel, text="", font=theme.FONT_SMALL,
            fg=theme.TEXT_WARN, anchor="w")
        self.credits_label.pack(anchor="w", padx=12)

        turn_panel = self._panel(0.35, 0.02, 0.30, 0.08)
        self.turn_label = self._themed_label(turn_panel, text="")
        self.turn_label.pack(expand=True)
        self.bet_label = self._themed_label(
            turn_panel, text="", font=theme.FONT_SMALL, fg=theme.TEXT_WARN)
        self.bet_label.pack(expand=True)

        self._themed_label(
            self.root, text="Esc: salir de pantalla completa · F11: alternar",
            font=theme.FONT_SMALL, fg=theme.TEXT_GREEN_DIM, bg=theme.PANEL_BG,
        ).place(relx=0.98, rely=0.02, anchor="ne")

        # Rival - mano parcialmente oculta mientras la partida esté en curso
        self._themed_label(self.root, text="RIVAL", font=theme.FONT_SCORE,
                            bg=theme.PANEL_BG).place(relx=0.04, rely=0.16)
        self.dealer_cards_frame = tk.Frame(self.root, bg=theme.BG_DARK)
        self.dealer_cards_frame.place(relx=0.04, rely=0.20, relwidth=0.92, relheight=0.22)
        self.dealer_score_label = self._themed_label(
            self.root, text="Puntos: ?", font=theme.FONT_SCORE, fg=theme.TEXT_WARN)
        self.dealer_score_label.place(relx=0.04, rely=0.43)

        # Jugador (tú)
        self._themed_label(self.root, text="JUGADOR (Tú)", font=theme.FONT_SCORE,
                            bg=theme.PANEL_BG).place(relx=0.04, rely=0.50)
        self.player_cards_frame = tk.Frame(self.root, bg=theme.BG_DARK)
        self.player_cards_frame.place(relx=0.04, rely=0.54, relwidth=0.92, relheight=0.22)
        self.player_score_label = self._themed_label(
            self.root, text="Puntos: 0", font=theme.FONT_SCORE, fg=theme.TEXT_WARN)
        self.player_score_label.place(relx=0.04, rely=0.77)

        # Botones
        btn_panel = self._panel(0.30, 0.85, 0.40, 0.08)
        self.hit_btn = self._themed_button(btn_panel, "Pedir carta", self.on_hit)
        self.hit_btn.pack(side="left", expand=True, padx=10, pady=8)
        self.hit_btn.config(state="disabled")

        self.stand_btn = self._themed_button(btn_panel, "Plantarse", self.on_stand)
        self.stand_btn.pack(side="left", expand=True, padx=10, pady=8)
        self.stand_btn.config(state="disabled")

        self.again_btn = self._themed_button(
            btn_panel, "Jugar de nuevo", self.on_play_again)
        # Se muestra/oculta dinámicamente en refresh_ui(); no se empaqueta aquí.

        self.result_label = self._themed_label(
            self.root, text="", font=theme.FONT_RESULT, fg=theme.TEXT_WARN, bg=theme.RESULT_BG)
        self.result_label.place(relx=0.25, rely=0.94, relwidth=0.50, relheight=0.05)

    # ---------------- Red ----------------


    def _listen_server(self):
        buffer = ""
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        msg = json.loads(line)
                        self.msg_queue.put(("server_msg", msg))
            except (ConnectionResetError, OSError):
                break
        self.msg_queue.put(("status", "Desconectado del servidor."))

    def _send(self, msg):
        if self.sock:
            try:
                self.sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))
            except OSError:
                pass

    def _process_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "status":
                    self.status_label.config(text=payload)
                elif kind == "server_msg":
                    self._handle_server_msg(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._process_queue)

    # ---------------- Mensajes del servidor ----------------
    # El servidor identifica cada mensaje con la clave "accion", no "type".
    def _handle_server_msg(self, msg):
        accion = msg.get("accion")

        if accion == "apuesta_error":
            self.msg_queue.put(("status", msg.get("mensaje", "Apuesta inválida.")))
            self.waiting_for_match = False
            self.refresh_ui()
            self._pedir_apuesta(error_text=msg.get("mensaje"))

        elif accion == "creditos_actualizados":
            self.creditos = msg.get("creditos", self.creditos)
            self.credits_label.config(text=f"Créditos: {self.creditos}")

        elif accion == "esperando":
            self.waiting_for_match = True
            self.msg_queue.put(("status", "Esperando un rival..."))
            self.refresh_ui()

        elif accion in ("iniciar_partida", "estado_partida"):
            self.waiting_for_match = False
            self.in_game = True
            if accion == "iniciar_partida":
                self.apuesta_actual = msg.get("apuesta", self.apuesta_actual)
                if "tus_creditos" in msg:
                    self.creditos = msg["tus_creditos"]
                    self.credits_label.config(text=f"Créditos: {self.creditos}")
                self.bet_label.config(text=f"Apuesta: {self.apuesta_actual}")
            self._apply_estado(msg["estado"])
            self.refresh_ui()

        elif accion == "rival_desconectado":
            self.in_game = False
            self.finished = True
            self.result_text = msg.get("mensaje", "Tu rival se desconectó. Ganaste la partida.")
            self.refresh_ui()

        elif accion == "error":
            self.msg_queue.put(("status", msg.get("mensaje", "Error del servidor.")))

        # cualquier otra "accion" desconocida se ignora en el cliente

    def _apply_estado(self, estado):
        """Traduce el estado compartido (player1/player2) a 'yo' vs 'rival'
        según cuál de los dos client_id soy."""
        soy_player1 = estado["player1"] == self.player_id

        if soy_player1:
            self.player_hand = estado["player1_hand"]
            self.dealer_hand = estado["player2_hand"]
            self.player_score = estado["player1_score"]
            self.dealer_score = estado["player2_score"]
        else:
            self.player_hand = estado["player2_hand"]
            self.dealer_hand = estado["player1_hand"]
            self.player_score = estado["player2_score"]
            self.dealer_score = estado["player1_score"]

        self.is_my_turn = estado["turn"] == self.player_id
        self.finished = estado["finished"]

        resultado = estado.get("result")
        if resultado:
            if resultado["winner"] is None:
                self.result_text = f"Empate. {resultado.get('message', '')}".strip()
            elif resultado["winner"] == self.player_id:
                self.result_text = f"¡Ganaste! {resultado.get('message', '')}".strip()
            else:
                self.result_text = f"Perdiste. {resultado.get('message', '')}".strip()
        else:
            self.result_text = None

    # ---------------- Acciones del jugador ----------------
    def on_hit(self):
        self._send({"accion": "hit"})

    def on_stand(self):
        self._send({"accion": "stand"})

    # ---------------- Render ----------------
    def refresh_ui(self):
        if not self.in_game:
            # Todavía no hay partida: no dibujamos manos.
            self.turn_label.config(text="Esperando rival..." if self.waiting_for_match else "")
            self.bet_label.config(text=f"Apuesta: {self.apuesta_actual}" if self.apuesta_actual else "")
            self.player_score_label.config(text="Puntos: 0")
            self.dealer_score_label.config(text="Puntos: ?")
            self._render_hand(self.player_cards_frame, [])
            self._render_hand(self.dealer_cards_frame, [])
            self.hit_btn.config(state="disabled")
            self.stand_btn.config(state="disabled")
            self.hit_btn.pack_forget()
            self.stand_btn.pack_forget()
            if self.finished:
                self.again_btn.pack(side="left", expand=True, padx=10, pady=8)
            else:
                self.again_btn.pack_forget()
            self.result_label.config(text=self.result_text or "")
            return

        self._render_hand(self.player_cards_frame, self.player_hand)

        # Mientras la partida no termine, solo se ve la primera carta del rival
        if self.finished:
            self._render_hand(self.dealer_cards_frame, self.dealer_hand)
            self.dealer_score_label.config(text=f"Puntos: {calculate_score(self.dealer_hand)}")
        else:
            hidden = set(range(1, len(self.dealer_hand)))  # todas menos la primera
            self._render_hand(self.dealer_cards_frame, self.dealer_hand, hidden_indices=hidden)
            self.dealer_score_label.config(text="Puntos: ?")

        self.player_score_label.config(text=f"Puntos: {calculate_score(self.player_hand)}")
        self.bet_label.config(text=f"Apuesta: {self.apuesta_actual}" if self.apuesta_actual else "")

        if self.finished:
            self.turn_label.config(text="Partida terminada")
            self.hit_btn.config(state="disabled")
            self.stand_btn.config(state="disabled")
            self.hit_btn.pack_forget()
            self.stand_btn.pack_forget()
            self.again_btn.pack(side="left", expand=True, padx=10, pady=8)
            self.result_label.config(text=self.result_text or "")
        else:
            self.turn_label.config(text="Tu turno" if self.is_my_turn else "Turno del rival...")
            can_act = self.is_my_turn
            self.again_btn.pack_forget()
            self.hit_btn.pack(side="left", expand=True, padx=10, pady=8)
            self.stand_btn.pack(side="left", expand=True, padx=10, pady=8)
            self.hit_btn.config(state="normal" if can_act else "disabled")
            self.stand_btn.config(state="normal" if can_act else "disabled")
            self.result_label.config(text="")

    # ---------------- Cierre ----------------
    def _on_close(self):
        try:
            if self.sock:
                self._send({"accion": "logout"})
                self.sock.close()
        except OSError:
            pass
        self.root.destroy()
