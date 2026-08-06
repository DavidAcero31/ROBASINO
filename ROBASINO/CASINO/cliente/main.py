import tkinter as tk

from vistas.login import Login
from vistas.menu_principal import MenuPrincipal
from modelos.jugador import Jugador


def main():

    root = tk.Tk()

    # Ocultamos la ventana principal mientras aparece el login
    root.withdraw()

    login = Login(root)

    # Espera hasta que el usuario cierre el login
    root.wait_window(login.ventana)

    # Si nunca inició sesión, cerrar la aplicación
    if not login.autenticado:
        root.destroy()
        return

    print("id:", login.id_jugador)
    print("usuario:", login.usuario)
    print("nombre:", login.nombre)
    print("apellido:", login.apellido)
    print("nivel:", login.nivel)
    print("pais:", login.pais)
    print("creditos:", login.creditos)

    # Mostrar la ventana principal
    root.deiconify()

    jugador = Jugador()
    jugador.client_id = login.client_id 

    jugador.id = login.id_jugador
    jugador.usuario = login.usuario
    jugador.nombre = login.nombre
    jugador.apellido = login.apellido
    jugador.pais = login.pais
    jugador.nivel = login.nivel
    jugador.creditos = login.creditos

    MenuPrincipal(root, jugador, login.conexion)

    root.mainloop()


if __name__ == "__main__":
    main()
