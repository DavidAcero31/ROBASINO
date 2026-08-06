"""
Ventana de inicio de sesión / registro del casino (ROBASINO).

Layout de dos columnas, responsive:
- Panel izquierdo (40% del ancho, proporcional): imagen de bienvenida,
  que se reescala en vivo al redimensionar la ventana, manteniendo
  proporciones. Solo cambia de tamaño cuando el USUARIO redimensiona
  la ventana; los campos de registro nunca lo afectan.
- Panel derecho (60% del ancho, proporcional): formulario de
  login / registro, dentro de un canvas con scroll, así que los
  campos extra de registro simplemente hacen crecer el contenido
  desplazable en vez de mover u obligar a redimensionar nada más.

La lógica de red y autenticación es la misma que en la versión
anterior: protocolo JSON con "accion" (login / registro / login_ok /
login_error / registro_ok / registro_error), el mismo socket se
reutiliza y se guarda en self.conexion al autenticar.
"""

import os
import socket
import json
import tkinter as tk

from PIL import Image, ImageTk

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

# ------------------------------------------------------------
# Paleta compartida con menu_principal.py (mesa de casino: verde
# oscuro de fieltro + acentos verde neón).
# ------------------------------------------------------------
BG = "#001a00"
PANEL_BG = "#002b00"
BORDER = "#33cc33"
NEON = "#66ff66"
NEON_DIM = "#339933"
FIELD_BG = "#0d2b0d"
ERROR = "#ff5c5c"
BTN_BG = "#0d4d0d"
BTN_BG_HOVER = "#136613"

# ------------------------------------------------------------
# Geometría de la ventana
# ------------------------------------------------------------
ANCHO_INICIAL = 950
ALTO_INICIAL = 660
ANCHO_MINIMO = 700
ALTO_MINIMO = 480

PROP_IZQUIERDO = 0.4  # 40% del ancho para el panel de imagen
PROP_DERECHO = 1.0 - PROP_IZQUIERDO


class Login:

    def __init__(self, root):

        self.ventana = tk.Toplevel(root)

        self.ventana.title("Iniciar Sesión")
        self.ventana.geometry(f"{ANCHO_INICIAL}x{ALTO_INICIAL}")
        self.ventana.minsize(ANCHO_MINIMO, ALTO_MINIMO)
        self.ventana.resizable(True, True)
        self.ventana.configure(bg=BG)

        # Resultado que main.py consulta después de que se cierre la ventana
        self.autenticado = False
        self.client_id = None  # id de ESTA conexión, asignado por el servidor
        self.id_jugador = None
        self.usuario = None
        self.nombre = None
        self.apellido = None
        self.pais = None
        self.nivel = None
        self.creditos = None
        self.conexion = None  # Socket ya conectado y autenticado, para reutilizar

        self.modo_registro = tk.BooleanVar(value=False)

        # Ruta base: cliente/ (igual que en menu_principal.py)
        self.ruta_base = os.path.dirname(os.path.dirname(__file__))

        self._construir_ui()

        # Cerrar con la X equivale a cancelar, no a un fallo silencioso
        self.ventana.protocol("WM_DELETE_WINDOW", self.cancelar)

    # ======================================================
    # CONSTRUCCIÓN DE LA INTERFAZ
    # ======================================================

    def _construir_ui(self):
        self._construir_panel_imagen()
        self._construir_panel_formulario()

    # ------------------------------------------------------
    # PANEL IZQUIERDO: IMAGEN
    # Proporcional al ancho/alto de la ventana (responsive), pero
    # SOLO cambia por redimensionamiento real de la ventana por
    # parte del usuario: los campos de registro nunca lo tocan.
    # ------------------------------------------------------

    def _construir_panel_imagen(self):

        self.panel_izquierdo = tk.Frame(
            self.ventana,
            bg=PANEL_BG,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER
        )

        self.panel_izquierdo.place(
            relx=0,
            rely=0,
            relwidth=PROP_IZQUIERDO,
            relheight=1.0
        )

        self._imagen_original = None
        self._filtro_resize = None
        self._resize_job = None
        self.etiqueta_imagen = None

        self._cargar_imagen_login()

    def _cargar_imagen_login(self):

        ruta_imagen = os.path.join(
            self.ruta_base,
            "recursos",
            "logo.png"
        )

        try:
            self._imagen_original = Image.open(ruta_imagen)

            try:
                self._filtro_resize = Image.Resampling.LANCZOS
            except AttributeError:
                # Compatibilidad con versiones antiguas de Pillow
                self._filtro_resize = Image.ANTIALIAS

            self.etiqueta_imagen = tk.Label(
                self.panel_izquierdo,
                bg=PANEL_BG,
                bd=0
            )
            self.etiqueta_imagen.place(relx=0.5, rely=0.5, anchor="center")

            # Cada vez que el panel cambia de tamaño (porque el usuario
            # redimensiona la ventana), se vuelve a escalar la imagen
            # a partir de la original, con debounce para no recalcular
            # en cada píxel mientras se arrastra el borde.
            self.panel_izquierdo.bind("<Configure>", self._on_configure_panel_izquierdo)

        except Exception as e:
            # No se pudo cargar la imagen: placeholder verde oscuro
            # en lugar de crashear.
            print(f"No se pudo cargar la imagen de login ({ruta_imagen}): {e}")
            self._mostrar_placeholder_imagen()

    def _on_configure_panel_izquierdo(self, event):
        ancho = event.width
        alto = event.height

        if ancho < 10 or alto < 10:
            return

        if self._resize_job is not None:
            self.ventana.after_cancel(self._resize_job)

        self._resize_job = self.ventana.after(
            80,
            lambda: self._renderizar_imagen(ancho, alto)
        )

    def _renderizar_imagen(self, ancho, alto):
        if self._imagen_original is None or self.etiqueta_imagen is None:
            return

        margen = 24
        max_ancho = max(1, ancho - margen * 2)
        max_alto = max(1, alto - margen * 2)

        escala = min(
            max_ancho / self._imagen_original.width,
            max_alto / self._imagen_original.height
        )
        nuevo_ancho = max(1, int(self._imagen_original.width * escala))
        nuevo_alto = max(1, int(self._imagen_original.height * escala))

        imagen_escalada = self._imagen_original.resize(
            (nuevo_ancho, nuevo_alto),
            self._filtro_resize
        )

        self.img_login = ImageTk.PhotoImage(imagen_escalada)
        self.etiqueta_imagen.configure(image=self.img_login)

    def _mostrar_placeholder_imagen(self):

        contenedor = tk.Frame(self.panel_izquierdo, bg=PANEL_BG)
        contenedor.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            contenedor,
            text="🎰",
            font=("Arial", 64),
            bg=PANEL_BG,
            fg=NEON
        ).pack()

        tk.Label(
            contenedor,
            text="ROBASINO",
            font=("Arial", 20, "bold"),
            bg=PANEL_BG,
            fg=NEON
        ).pack(pady=(8, 0))

    # ------------------------------------------------------
    # PANEL DERECHO: FORMULARIO
    # Proporcional al ancho/alto de la ventana. El contenido vive
    # dentro de un Canvas con scroll vertical, así que activar el
    # registro nunca necesita redimensionar la ventana ni afecta
    # al panel de la imagen: si no cabe, simplemente se desplaza.
    # ------------------------------------------------------

    def _construir_panel_formulario(self):

        self.panel_derecho = tk.Frame(self.ventana, bg=BG)

        self.panel_derecho.place(
            relx=PROP_IZQUIERDO,
            rely=0,
            relwidth=PROP_DERECHO,
            relheight=1.0
        )

        self.canvas = tk.Canvas(
            self.panel_derecho,
            bg=BG,
            highlightthickness=0,
            bd=0
        )
        self.scrollbar = tk.Scrollbar(
            self.panel_derecho,
            orient="vertical",
            command=self.canvas.yview,
            bg=FIELD_BG,
            troughcolor=PANEL_BG,
            activebackground=BORDER,
            highlightthickness=0,
            relief="flat"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Frame interno desplazable: aquí va todo el contenido real.
        self.contenido = tk.Frame(self.canvas, bg=BG)
        self._ventana_canvas = self.canvas.create_window(
            (0, 0),
            window=self.contenido,
            anchor="nw"
        )

        self.contenido.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        # El contenido interno debe tener siempre el mismo ancho que
        # el canvas visible, para que los campos "fill=x" se expandan
        # de verdad con la ventana.
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self._ventana_canvas, width=e.width)
        )

        # Scroll con la rueda del mouse, solo mientras el cursor esté
        # sobre el formulario (para no interferir con otras ventanas).
        self.canvas.bind("<Enter>", self._activar_scroll_mouse)
        self.canvas.bind("<Leave>", self._desactivar_scroll_mouse)

        self._construir_contenido_formulario()

    def _activar_scroll_mouse(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _desactivar_scroll_mouse(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _construir_contenido_formulario(self):

        tk.Frame(self.contenido, bg=BORDER, height=4).pack(fill="x")

        self.titulo_label = tk.Label(
            self.contenido,
            text="🎰 NovaTic Royal",
            font=("Arial", 24, "bold"),
            bg=BG,
            fg=NEON
        )
        self.titulo_label.pack(pady=(22, 0))

        self.subtitulo_label = tk.Label(
            self.contenido,
            text="INICIAR SESIÓN",
            font=("Arial", 12, "bold"),
            bg=BG,
            fg=NEON_DIM
        )
        self.subtitulo_label.pack(pady=(4, 14))

        # Panel tipo "carta" que agrupa el formulario, igual que los
        # paneles con borde ridge de menu_principal.py
        self.panel_form = tk.Frame(
            self.contenido,
            bg=PANEL_BG,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER
        )
        self.panel_form.pack(padx=28, pady=0, fill="x")

        self._campo(self.panel_form, "Usuario")
        self.usuario_entry = self._entry(self.panel_form)

        self._campo(self.panel_form, "Contraseña")
        self.password = self._entry(self.panel_form, show="*")

        # Enter en cualquiera de los dos campos también envía el formulario
        self.usuario_entry.bind("<Return>", lambda e: self.ingresar())
        self.password.bind("<Return>", lambda e: self.ingresar())

        tk.Checkbutton(
            self.panel_form,
            text="Crear cuenta nueva",
            variable=self.modo_registro,
            command=self._alternar_modo,
            font=("Arial", 10),
            bg=PANEL_BG,
            fg=NEON_DIM,
            selectcolor=FIELD_BG,
            activebackground=PANEL_BG,
            activeforeground=NEON,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            anchor="w"
        ).pack(fill="x", padx=22, pady=(14, 4))

        # Campos extra, solo visibles cuando se marca "Crear cuenta nueva".
        # Al mostrarse, el frame de contenido crece y el canvas
        # simplemente permite hacer scroll: la ventana no cambia de
        # tamaño y el panel de la imagen no se ve afectado.
        self._extra_frame = tk.Frame(self.panel_form, bg=PANEL_BG)

        self._campo(self._extra_frame, "Nombre")
        self.e_nombre = self._entry(self._extra_frame)

        self._campo(self._extra_frame, "Apellido")
        self.e_apellido = self._entry(self._extra_frame)

        self._campo(self._extra_frame, "Correo")
        self.e_correo = self._entry(self._extra_frame)

        self._campo(self._extra_frame, "País")
        self.e_pais = self._entry(self._extra_frame)

        tk.Frame(self.panel_form, bg=PANEL_BG, height=10).pack()

        self.mensaje_error = tk.Label(
            self.contenido,
            text="",
            font=("Arial", 10, "bold"),
            fg=ERROR,
            bg=BG,
            wraplength=380,
            justify="center"
        )
        self.mensaje_error.pack(pady=(14, 4))

        self.boton_ingresar = tk.Button(
            self.contenido,
            text="INGRESAR",
            width=22,
            font=("Arial", 12, "bold"),
            bg=BTN_BG,
            fg=NEON,
            activebackground=BTN_BG_HOVER,
            activeforeground=NEON,
            relief="flat",
            bd=0,
            cursor="hand2",
            command=self.ingresar
        )
        self.boton_ingresar.pack(pady=(10, 24), ipady=6)
        self.boton_ingresar.bind(
            "<Enter>", lambda e: self.boton_ingresar.config(bg=BTN_BG_HOVER)
        )
        self.boton_ingresar.bind(
            "<Leave>", lambda e: self.boton_ingresar.config(bg=BTN_BG)
        )

        self.usuario_entry.focus_set()

    def _campo(self, parent, texto):
        tk.Label(
            parent,
            text=texto,
            font=("Arial", 10, "bold"),
            bg=PANEL_BG,
            fg=NEON_DIM,
            anchor="w"
        ).pack(fill="x", padx=22, pady=(16, 4))

    def _entry(self, parent, show=None):
        entry = tk.Entry(
            parent,
            width=30,
            font=("Arial", 12),
            bg=FIELD_BG,
            fg=NEON,
            insertbackground=NEON,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=NEON,
            show=show if show else ""
        )
        entry.pack(
            fill="x",
            padx=24,
            pady=(0, 12),
            ipady=6
        )
        return entry

    def _alternar_modo(self):
        if self.modo_registro.get():
            self._extra_frame.pack(fill="x")
            self.subtitulo_label.config(text="CREAR CUENTA")
            self.boton_ingresar.config(text="REGISTRARSE")
        else:
            self._extra_frame.pack_forget()
            self.subtitulo_label.config(text="INICIAR SESIÓN")
            self.boton_ingresar.config(text="INGRESAR")
        self.mensaje_error.config(text="")
        # El contenido cambió de alto: refrescar el área de scroll.
        self.contenido.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # ======================================================
    # LÓGICA DE RED / AUTENTICACIÓN (sin cambios de protocolo)
    # ======================================================

    def ingresar(self):
        usuario = self.usuario_entry.get().strip()
        password = self.password.get()
        es_registro = self.modo_registro.get()

        if not usuario or not password:
            self.mensaje_error.config(text="Usuario y contraseña son obligatorios.", fg=ERROR)
            return

        if es_registro and not self.e_correo.get().strip():
            self.mensaje_error.config(text="El correo es obligatorio para registrarse.", fg=ERROR)
            return

        self.mensaje_error.config(
            text="Registrando..." if es_registro else "Conectando...",
            fg=NEON_DIM
        )
        self.ventana.update_idletasks()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((SERVER_HOST, SERVER_PORT))
        except OSError as e:
            self.mensaje_error.config(text=f"No se pudo conectar al servidor: {e}", fg=ERROR)
            return

        if es_registro:
            mensaje = {
                "accion": "registro",
                "usuario": usuario,
                "contrasena": password,
                "nombre": self.e_nombre.get().strip(),
                "apellido": self.e_apellido.get().strip(),
                "correo": self.e_correo.get().strip(),
                "pais": self.e_pais.get().strip(),
            }
        else:
            mensaje = {
                "accion": "login",
                "usuario": usuario,
                "contrasena": password
            }

        try:
            self._enviar(sock, mensaje)
            respuesta = self._recibir(sock)
        except OSError as e:
            self.mensaje_error.config(text=f"Error de conexión: {e}", fg=ERROR)
            sock.close()
            return

        if respuesta is None:
            self.mensaje_error.config(text="El servidor cerró la conexión.", fg=ERROR)
            sock.close()
            return

        accion_resp = respuesta.get("accion")

        # login_ok y registro_ok se tratan igual: el registro deja al
        # jugador autenticado de inmediato, sin pedirle iniciar sesión
        # de nuevo. El servidor debe devolver el mismo perfil en ambos
        # casos (client_id, id_jugador, usuario, nombre, apellido,
        # pais, nivel, creditos).
        if accion_resp in ("login_ok", "registro_ok"):
            self.autenticado = True
            self.client_id = respuesta.get("client_id")
            self.id_jugador = respuesta.get("id_jugador")
            self.usuario = respuesta.get("usuario", usuario)
            self.nombre = respuesta.get("nombre")
            self.apellido = respuesta.get("apellido")
            self.pais = respuesta.get("pais")
            self.nivel = respuesta.get("nivel")
            self.creditos = respuesta.get("creditos")
            self.conexion = sock  # NO se cierra: el resto de la aplicación lo reutiliza
            self.ventana.destroy()

        elif accion_resp in ("login_error", "registro_error"):
            self.mensaje_error.config(
                text=respuesta.get(
                    "mensaje",
                    "Usuario o contraseña incorrectos."
                    if accion_resp == "login_error"
                    else "No se pudo completar el registro."
                ),
                fg=ERROR
            )
            sock.close()

        else:
            self.mensaje_error.config(text="Respuesta inesperada del servidor.", fg=ERROR)
            sock.close()

    def cancelar(self):
        self.autenticado = False
        self.ventana.destroy()

    # ---------------- Ayudantes de red ----------------

    @staticmethod
    def _enviar(sock, mensaje):
        sock.sendall((json.dumps(mensaje) + "\n").encode("utf-8"))

    @staticmethod
    def _recibir(sock):
        """Lee UNA línea (un mensaje JSON), bloqueando.
        Es suficiente para el intercambio síncrono del login/registro.
        """
        buffer = ""

        while "\n" not in buffer:
            datos = sock.recv(4096)

            if not datos:
                return None

            buffer += datos.decode("utf-8")

        linea, _, _ = buffer.partition("\n")
        return json.loads(linea)
