"""Paleta y estilos compartidos por server.py y client.py."""

# --- Colores (inspirados en el mockup: mesa verde oscuro, texto neón) ---
BG_DARK = "#03110a"          # respaldo si no carga la imagen de fondo
PANEL_BG = "#0c2413"         # fondo de los paneles de información
PANEL_BORDER = "#4a8f57"     # borde claro de los paneles
TEXT_GREEN = "#6dffa0"       # texto principal (verde neón)
TEXT_GREEN_DIM = "#4fae72"   # texto secundario / apagado
TEXT_WARN = "#ffd166"        # resaltar resultados / avisos

BUTTON_BG = "#123a1e"
BUTTON_ACTIVE_BG = "#1f5c31"
BUTTON_DISABLED_FG = "#3a5a44"
BUTTON_TEXT = "#d9ffe8"

RESULT_BG = "#0c2413"

# --- Fuentes ---
FONT_TITLE = ("Georgia", 18, "bold")
FONT_LABEL = ("Arial", 12, "bold")
FONT_SMALL = ("Arial", 10)
FONT_SCORE = ("Arial", 13, "bold")
FONT_RESULT = ("Arial", 15, "bold")

# --- Tamaños ---
# Ya no hay ventana ni cartas de tamaño fijo: todo se calcula en tiempo real
# a partir del tamaño actual de la ventana (ver ui_base.py).
CARD_ASPECT = 90 / 130       # ancho/alto de una carta estándar
CARD_HEIGHT_RATIO = 0.20     # la carta ocupa ~20% de la altura de la ventana
MIN_WINDOW_SIZE = (800, 600)
DEFAULT_WINDOWED_SIZE = "1200x800"
RESIZE_DEBOUNCE_MS = 120     # espera antes de redibujar tras un resize