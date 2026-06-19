import tkinter as tk
from vistas.menu_principal import MenuPrincipal


def main():

    root = tk.Tk()

    app = MenuPrincipal(root)

    root.mainloop()


if __name__ == "__main__":
    main()