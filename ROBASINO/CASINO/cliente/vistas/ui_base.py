"""
Mixin con la lógica de ventana compartida por BlackjackServer y BlackjackClient:
- Arranca en pantalla completa (Esc para salir, F11 para alternar).
- Reescala el fondo y las cartas cada vez que cambia el tamaño de la ventana,
  usando coordenadas relativas (relx/rely/relwidth/relheight) para que el
  diseño sea responsive.
"""

import os

CONTROLADORES_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "controladores"
)


import tkinter as tk

import vistas.theme as theme
from .image_loader import get_card_image, get_background_image


class BaseGameUI:
    # ---------------- Ventana / pantalla completa ----------------
    def _init_window(self, title):
        self.root = tk.Toplevel(self.parent)
        self.root.title(title)
        self.root.configure(bg=theme.BG_DARK)
        self.root.minsize(*theme.MIN_WINDOW_SIZE)

        self._is_fullscreen = True
        self.root.attributes("-fullscreen", True)

        self.root.bind("<Escape>", self._exit_fullscreen)
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._bg_photo = None
        self._card_refs = []
        self._resize_job = None
        self._current_size = None

        self._create_background_label()
        self.root.bind("<Configure>", self._on_configure)

    def _toggle_fullscreen(self, event=None):
        self._is_fullscreen = not self._is_fullscreen
        self.root.attributes("-fullscreen", self._is_fullscreen)
        if not self._is_fullscreen:
            self.root.geometry(theme.DEFAULT_WINDOWED_SIZE)

    def _exit_fullscreen(self, event=None):
        self._is_fullscreen = False
        self.root.attributes("-fullscreen", False)
        self.root.geometry(theme.DEFAULT_WINDOWED_SIZE)

    def _on_close(self):
        """Las subclases pueden sobreescribir esto para cerrar sockets antes de salir."""
        self.root.destroy()

    # ---------------- Responsive: redimensionado con debounce ----------------
    def _on_configure(self, event):
        # Solo reaccionar a cambios de tamaño de la ventana raíz (no de sub-widgets)
        if event.widget is not self.root:
            return
        new_size = (event.width, event.height)
        if new_size == self._current_size:
            return
        self._current_size = new_size
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(theme.RESIZE_DEBOUNCE_MS, self._rebuild_on_resize)

    def _rebuild_on_resize(self):
        self._resize_job = None
        self._apply_background()
        self.refresh_ui()  # cada subclase implementa refresh_ui()

    # ---------------- Fondo ----------------
    def _create_background_label(self):
        self._bg_label = tk.Label(self.root, bd=0, bg=theme.BG_DARK)
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_label.lower()

    def _apply_background(self):
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        if w < 10 or h < 10:
            return
        img = get_background_image((w, h))
        self._bg_photo = img
        if img:
            self._bg_label.config(image=img)
            self._bg_label.image = img
        self._bg_label.place(x=0, y=0, width=w, height=h)
        self._bg_label.lower()

    # ---------------- Helpers de widgets temáticos ----------------
    def _panel(self, relx, rely, relwidth, relheight):
        frame = tk.Frame(
            self.root,
            bg=theme.PANEL_BG,
            highlightbackground=theme.PANEL_BORDER,
            highlightthickness=2,
            bd=0,
        )
        frame.place(relx=relx, rely=rely, relwidth=relwidth, relheight=relheight)
        return frame

    def _themed_label(self, parent, **kwargs):
        defaults = dict(bg=theme.PANEL_BG, fg=theme.TEXT_GREEN, font=theme.FONT_LABEL)
        defaults.update(kwargs)
        return tk.Label(parent, **defaults)

    def _themed_button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=theme.FONT_LABEL,
            bg=theme.BUTTON_BG,
            fg=theme.BUTTON_TEXT,
            activebackground=theme.BUTTON_ACTIVE_BG,
            activeforeground=theme.BUTTON_TEXT,
            disabledforeground=theme.BUTTON_DISABLED_FG,
            relief="flat",
            bd=0,
            highlightbackground=theme.PANEL_BORDER,
            highlightthickness=1,
            padx=14,
            pady=8,
            cursor="hand2",
        )

    # ---------------- Cartas responsive ----------------
    def _card_size(self):
        """Tamaño de carta proporcional a la altura actual de la ventana."""
        h = max(self.root.winfo_height(), 400)
        card_h = int(h * theme.CARD_HEIGHT_RATIO)
        card_w = int(card_h * theme.CARD_ASPECT)
        return (card_w, card_h)

    def _render_hand(self, container, hand, hidden_indices=()):
        for child in container.winfo_children():
            child.destroy()
        size = self._card_size()
        kept_refs = []
        for i, card in enumerate(hand):
            hidden = i in hidden_indices
            img = get_card_image(card, size=size, hidden=hidden)
            lbl = tk.Label(container, image=img, bg=theme.BG_DARK, bd=0)
            lbl.image = img
            lbl.pack(side="left", padx=6)
            kept_refs.append(img)
        self._card_refs.extend(kept_refs)
        # limitar crecimiento indefinido de la lista de referencias
        if len(self._card_refs) > 200:
            self._card_refs = kept_refs
