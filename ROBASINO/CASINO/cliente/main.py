# import tkinter as tk
# from vistas.pantalla_inicio import PantallaInicio


# def main():

#     root = tk.Tk()

#     PantallaInicio(root)

#     root.mainloop()


# if __name__ == "__main__":
#     main()

import tkinter as tk
from vistas.menu_principal import MenuPrincipal
from modelos.jugador import Jugador


def main():

    root = tk.Tk()
    jugador = Jugador()
    app = MenuPrincipal(
        root,
        jugador,
        )

    root.mainloop()


if __name__ == "__main__":
    main()