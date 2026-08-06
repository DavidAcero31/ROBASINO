from .game_logic import create_deck, draw_card, calculate_score


class BlackjackGame:

    def __init__(self, game_id, player1_id, player2_id):

        self.game_id = game_id

        self.player1 = player1_id
        self.player2 = player2_id

        self.restart()


    # =====================================================
    # INICIAR / REINICIAR PARTIDA
    # =====================================================

    def restart(self):

        self.deck = create_deck()

        self.player1_hand = [
            draw_card(self.deck),
            draw_card(self.deck)
        ]

        self.player2_hand = [
            draw_card(self.deck),
            draw_card(self.deck)
        ]

        self.player1_stood = False
        self.player2_stood = False

        self.turn = self.player1

        self.finished = False

        self.result = None


    # =====================================================
    # PEDIR CARTA
    # =====================================================

    def hit(self, player_id):

        if self.finished:
            return

        if self.turn != player_id:
            return

        card = draw_card(self.deck)

        if card is None:
            return

        if player_id == self.player1:

            self.player1_hand.append(card)

            if calculate_score(self.player1_hand) > 21:

                self.player1_stood = True

                self.turn = self.player2

        else:

            self.player2_hand.append(card)

            if calculate_score(self.player2_hand) > 21:

                self.player2_stood = True

        self.check_end()


    # =====================================================
    # PLANTARSE
    # =====================================================

    def stand(self, player_id):

        if self.finished:
            return

        if self.turn != player_id:
            return

        if player_id == self.player1:

            self.player1_stood = True

            self.turn = self.player2

        else:

            self.player2_stood = True

        self.check_end()


    # =====================================================
    # PUNTAJES
    # =====================================================

    def player1_score(self):

        return calculate_score(
            self.player1_hand
        )


    def player2_score(self):

        return calculate_score(
            self.player2_hand
        )


    # =====================================================
    # CAMBIO DE TURNO
    # =====================================================

    def next_turn(self):

        if self.turn == self.player1:

            self.turn = self.player2

        else:

            self.turn = self.player1


    # =====================================================
    # VALIDAR TURNO
    # =====================================================

    def is_player_turn(self, player_id):

        return self.turn == player_id

        # =====================================================
    # VERIFICAR SI LA PARTIDA TERMINÓ
    # =====================================================

    def check_end(self):

        p1_score = self.player1_score()
        p2_score = self.player2_score()

        # -----------------------------
        # Jugador 1 se pasó
        # -----------------------------

        if p1_score > 21:

            self.finished = True

            self.result = {
                "winner": self.player2,
                "loser": self.player1,
                "message": "El jugador 1 se pasó de 21."
            }

            return

        # -----------------------------
        # Jugador 2 se pasó
        # -----------------------------

        if p2_score > 21:

            self.finished = True

            self.result = {
                "winner": self.player1,
                "loser": self.player2,
                "message": "El jugador 2 se pasó de 21."
            }

            return

        # -----------------------------
        # Ambos se plantaron
        # -----------------------------

        if self.player1_stood and self.player2_stood:

            self.finished = True

            if p1_score > p2_score:

                self.result = {
                    "winner": self.player1,
                    "loser": self.player2,
                    "message": "Jugador 1 gana."
                }

            elif p2_score > p1_score:

                self.result = {
                    "winner": self.player2,
                    "loser": self.player1,
                    "message": "Jugador 2 gana."
                }

            else:

                self.result = {
                    "winner": None,
                    "loser": None,
                    "message": "Empate."
                }

            return


    # =====================================================
    # OBTENER ESTADO COMPLETO
    # =====================================================

    def get_state(self):

        return {

            "game_id": self.game_id,

            "player1": self.player1,

            "player2": self.player2,

            "player1_hand": self.player1_hand,

            "player2_hand": self.player2_hand,

            "player1_score": self.player1_score(),

            "player2_score": self.player2_score(),

            "player1_stood": self.player1_stood,

            "player2_stood": self.player2_stood,

            "turn": self.turn,

            "finished": self.finished,

            "result": self.result

        }


    # =====================================================
    # ESTADO PARA UN JUGADOR
    # =====================================================

    def get_player_state(self, player_id):

        if player_id == self.player1:

            return {

                "your_hand": self.player1_hand,

                "opponent_hand": self.player2_hand,

                "your_score": self.player1_score(),

                "opponent_score": self.player2_score(),

                "your_turn": self.turn == self.player1,

                "finished": self.finished,

                "result": self.result

            }

        elif player_id == self.player2:

            return {

                "your_hand": self.player2_hand,

                "opponent_hand": self.player1_hand,

                "your_score": self.player2_score(),

                "opponent_score": self.player1_score(),

                "your_turn": self.turn == self.player2,

                "finished": self.finished,

                "result": self.result

            }

        return None


    # =====================================================
    # INFORMACIÓN DE LA PARTIDA
    # =====================================================

    def get_winner(self):

        if self.result is None:
            return None

        return self.result["winner"]


    def get_result(self):

        return self.result


    def is_finished(self):

        return self.finished


    def has_player(self, player_id):

        return player_id == self.player1 or player_id == self.player2


    # =====================================================
    # CONVERTIR A DICCIONARIO
    # =====================================================

    def to_dict(self):

        return {

            "game_id": self.game_id,

            "player1": self.player1,

            "player2": self.player2,

            "player1_score": self.player1_score(),

            "player2_score": self.player2_score(),

            "finished": self.finished,

            "turn": self.turn

        }
