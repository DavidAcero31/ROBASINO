class Jugador:

    def __init__(self):

        self.nombre = "Invitado"
        self.creditos = 100000
        self.nivel = 1
        self.partidas_jugadas = 0

    def agregar_creditos(self, cantidad):

        self.creditos += cantidad

    def retirar_creditos(self, cantidad):

        self.creditos -= cantidad

    def incrementar_partidas(self):

        self.partidas_jugadas += 1