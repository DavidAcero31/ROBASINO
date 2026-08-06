"""
Carga imágenes desde la carpeta resources/ (hermana de vista/ y controladores/).
Requiere Pillow: pip install pillow --break-system-packages
"""

import os
import sys

from PIL import Image, ImageTk


sys.path.append(
    os.path.join(os.path.dirname(__file__), "..", "controladores")
)

RESOURCES_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "recursos",
    "blackjack"
)

from controladores.game_logic import card_filename

# Cache para que las PhotoImage no sean recolectadas por el garbage collector
_image_cache = {}

def _resolve_path(filename):
    path = os.path.join(RESOURCES_DIR, filename)
    if os.path.exists(path):
        return path
    # Si falta la imagen, usamos el reverso de carta como respaldo
    fallback = os.path.join(RESOURCES_DIR, "back.png")
    if os.path.exists(fallback):
        return fallback
    return None


_FALLBACK_SIZE = (90, 130)


def get_card_image(card, size=None, hidden=False):
    """
    Devuelve una ImageTk.PhotoImage para la carta dada, escalada a `size` (ancho, alto).
    Si hidden=True o card es None, devuelve el reverso (back.png).
    """
    size = size or _FALLBACK_SIZE

    filename = "back.png" if (hidden or card is None) else card_filename(card)
    print("Carta:", card)
    print("Archivo:", filename)
    cache_key = (filename, size)
    if cache_key in _image_cache:
        return _image_cache[cache_key]

    path = _resolve_path(filename)
    if path is None:
        _image_cache[cache_key] = None
        return None

    try:
        img = Image.open(path).convert("RGBA")
        img = img.resize(size, Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"⚠️ No se pudo cargar la imagen de carta '{filename}': {e}")
        tk_img = None

    _image_cache[cache_key] = tk_img
    return tk_img


def get_background_image(size):

    cache_key = ("background", size)

    if cache_key in _image_cache:
        return _image_cache[cache_key]

    path = os.path.join(
        RESOURCES_DIR,
        "fondo_principal.png"
    )

    if not os.path.exists(path):
        print("⚠️ No se encontró fondo_principal.png")
        return None

    try:
        img = Image.open(path).convert("RGB")
        img = img.resize(size, Image.LANCZOS)

        tk_img = ImageTk.PhotoImage(img)

        _image_cache[cache_key] = tk_img

        return tk_img

    except Exception as e:
        print(f"⚠️ Error cargando fondo: {e}")
        return None