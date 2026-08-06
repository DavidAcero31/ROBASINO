"""
Capa de acceso a datos (MariaDB) del Casino Server.

Este módulo es el ÚNICO punto de contacto con la base de datos.
Ni client.py ni blackjack_game.py deben importarlo jamás — eso
rompería la arquitectura (los clientes nunca tocan la BD).

Requiere:
        pip install mysql-connector-python bcrypt

Antes de usar, ajustar DB_CONFIG y crear un usuario de MariaDB con
privilegios sobre la base `casino` (ver base_casino.sql para el esquema).
"""

import bcrypt
import mysql.connector
from mysql.connector import pooling

# ----------------------------------------------------------------
# CONFIGURACIÓN — ajustar a tu entorno
# ----------------------------------------------------------------
DB_CONFIG = {
    "host": "10.56.131.94",
    "port": 3306,
    "user": "baseC",
    "password": "Flialfonsoperez",
    "database": "casino",
    "autocommit": True,
}

_pool = None


# ----------------------------------------------------------------
# ERRORES DE DOMINIO
# ----------------------------------------------------------------
class UsuarioExistente(Exception):
    """El nombre de usuario ya está registrado."""


class CorreoExistente(Exception):
    """El correo ya está registrado."""


class CreditosInsuficientes(Exception):
    """La operación dejaría el saldo de créditos en negativo."""


# ----------------------------------------------------------------
# CONEXIÓN
# ----------------------------------------------------------------
def init_pool(pool_size=5):
    """Crea el pool de conexiones. Se debe llamar una vez al
    iniciar el servidor. Lanza mysql.connector.Error si no puede
    conectar (host caído, credenciales incorrectas, etc.)."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="casino_pool",
            pool_size=pool_size,
            **DB_CONFIG
        )
    return _pool


def _get_conn():
    if _pool is None:
        init_pool()
    return _pool.get_connection()


# ----------------------------------------------------------------
# JUGADORES
# ----------------------------------------------------------------
def registrar_jugador(nombre, apellido, correo, usuario, password,
                        pais="", creditos_iniciales=1000):
    """Crea una cuenta nueva. Devuelve el dict del jugador (sin hash)."""

    hash_pw = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    conn = _get_conn()
    try:
        cur = conn.cursor(dictionary=True)

        cur.execute("SELECT id_jugador FROM jugador WHERE usuario = %s", (usuario,))
        if cur.fetchone():
            raise UsuarioExistente(f"El usuario '{usuario}' ya existe.")

        cur.execute("SELECT id_jugador FROM jugador WHERE correo = %s", (correo,))
        if cur.fetchone():
            raise CorreoExistente(f"El correo '{correo}' ya está registrado.")

        cur.execute(
            """INSERT INTO jugador
                (nombre, apellido, correo, usuario, password,
                creditos, nivel, pais)
                VALUES (%s, %s, %s, %s, %s, %s, 1, %s)""",
            (nombre, apellido, correo, usuario, hash_pw,
                creditos_iniciales, pais)
        )
        id_jugador = cur.lastrowid
        cur.close()
        return obtener_jugador(id_jugador)
    finally:
        conn.close()


def autenticar_jugador(usuario, contrasena_plana):
    """Devuelve el dict del jugador (sin hash) si las credenciales son
    correctas, o None si el usuario no existe o la contraseña no coincide."""

    conn = _get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM jugador WHERE usuario = %s", (usuario,))
        fila = cur.fetchone()
        cur.close()

        if fila is None:
            return None
        if not bcrypt.checkpw(
            contrasena_plana.encode("utf-8"),
            fila["password"].encode("utf-8")
        ):
            return None

        fila.pop("password", None)
        return fila
    finally:
        conn.close()


def obtener_jugador(id_jugador):
    conn = _get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM jugador WHERE id_jugador = %s", (id_jugador,))
        fila = cur.fetchone()
        cur.close()
        if fila:
            fila.pop("password", None)
        return fila
    finally:
        conn.close()


def actualizar_creditos(id_jugador, delta):
    """Suma (delta positivo) o resta (delta negativo) créditos de forma
    atómica. Devuelve el nuevo saldo. Lanza CreditosInsuficientes si el
    resultado sería negativo."""

    conn = _get_conn()
    try:
        cur = conn.cursor()
        conn.start_transaction()
        cur.execute(
            "SELECT creditos FROM jugador WHERE id_jugador = %s FOR UPDATE",
            (id_jugador,)
        )
        fila = cur.fetchone()
        if fila is None:
            conn.rollback()
            cur.close()
            raise ValueError(f"Jugador {id_jugador} no existe.")

        nuevo_saldo = fila[0] + delta
        if nuevo_saldo < 0:
            conn.rollback()
            cur.close()
            raise CreditosInsuficientes(
                f"Saldo insuficiente: {fila[0]} + ({delta})"
            )

        cur.execute(
            "UPDATE jugador SET creditos = %s WHERE id_jugador = %s",
            (nuevo_saldo, id_jugador)
        )
        conn.commit()
        cur.close()
        return nuevo_saldo
    finally:
        conn.close()


# ----------------------------------------------------------------
# JUEGOS
# ----------------------------------------------------------------
def obtener_id_juego(nombre_juego):
    """Devuelve el id_juego correspondiente a un nombre (p. ej. 'blackjack'),
    o None si no está en el catálogo."""

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id_juego FROM juego WHERE nombre = %s", (nombre_juego,))
        fila = cur.fetchone()
        cur.close()
        return fila[0] if fila else None
    finally:
        conn.close()


# ----------------------------------------------------------------
# PARTIDAS / HISTORIAL
# ----------------------------------------------------------------
def registrar_partida(id_ronda, id_jugador, id_juego, valor_apuesta,
                        resultado, premio):
    """Guarda el resultado de UN jugador en UNA ronda. `resultado` debe ser
    uno de: 'gano', 'perdio', 'empate', 'abandono'. Devuelve id_partida."""

    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO partida
                (id_ronda, valor_apuesta, resultado, premio,
                id_jugador, id_juego, fecha)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
            (id_ronda, valor_apuesta, resultado, premio, id_jugador, id_juego)
        )
        id_partida = cur.lastrowid
        cur.close()
        return id_partida
    finally:
        conn.close()


def registrar_historial(id_partida, estado_anterior, estado_nuevo):
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO historial
                (id_partida, fecha_evento, estado_anterior, estado_nuevo)
                VALUES (%s, NOW(), %s, %s)""",
            (id_partida, estado_anterior, estado_nuevo)
        )
        cur.close()
    finally:
        conn.close()


def obtener_historial_jugador(id_jugador, limite=20):
    """Últimas partidas jugadas por un jugador, más recientes primero."""

    conn = _get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """SELECT p.id_partida, p.id_ronda, p.resultado, p.premio,
                    p.valor_apuesta, p.fecha, j.nombre AS juego
                FROM partida p
                JOIN juego j ON j.id_juego = p.id_juego
                WHERE p.id_jugador = %s
                ORDER BY p.fecha DESC
                LIMIT %s""",
            (id_jugador, limite)
        )
        filas = cur.fetchall()
        cur.close()
        return filas
    finally:
        conn.close()
