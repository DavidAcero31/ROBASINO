import tkinter as tk
import threading, queue, random, math, os

from controladores.controlador_ruleta import ControladorRuleta

# ── Colores ──────────────────────────────────────────────────────
class T:
    # Base oscura — negro verdoso como la imagen
    DEEP      = "#060e08"   # fondo general, casi negro
    RELIEF    = "#0c1f10"   # paneles principales
    RELIEF_LO = "#081509"   # paneles hundidos / celdas
    BORDER    = "#1a4a22"   # bordes y líneas internas
    TABLE     = "#071208"   # mesa de apuestas

    # Verdes brillantes (filigrana y resaltes)
    GREEN     = "#1a7a2a"   # cero de la ruleta
    FELT      = "#0a2a10"

    # Dorados envejecidos (igual que los grabados de la imagen)
    LEAF      = "#7a6a2a"   # dorado apagado — bordes de panel
    LEAF_HI   = "#a8943c"   # dorado más brillante — títulos

    # Texto y fichas
    PARCH     = "#8aaa80"   # texto secundario (verde grisáceo)
    DIM       = "#2a3a2a"   # texto muy apagado

    # Rojo y negro de los sectores
    RED       = "#8b1a1a"   # rojo oscuro, casi vino
    BLACK     = "#0d0d0d"   # negro puro

    # Misc (se mantienen para compatibilidad)
    BG=DEEP; FELT=FELT; GOLD="#7a6a2a"; GOLD2="#a8943c"

# ── Rueda ────────────────────────────────────────────────────────
class Wheel:
    ORDER=[0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,
        24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
    REDS={1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

    @classmethod
    def color_of(cls,n):
        return T.GREEN if n==0 else (T.RED if n in cls.REDS else T.BLACK)

    @classmethod
    def color_name(cls,n):
        return "Verde" if n==0 else ("Rojo" if n in cls.REDS else "Negro")

# ── Apuestas ─────────────────────────────────────────────────────
# Los nombres de apuesta externa ("Rojo", "1ª Doc.", etc.) son solo
# etiquetas que la vista usa para armar botones y para mostrar lo que
# el jugador lleva apostado. La validación y el cálculo de qué apuesta
# gana y cuánto paga viven SOLO en el servidor (ruleta_logic.py,
# BET_TYPES) — este mismo conjunto de nombres, replicado ahí.
class BetManager:
    def __init__(self): self.bets={}
    def place(self,k,v): self.bets[k]=self.bets.get(k,0)+v
    def total(self): return sum(self.bets.values())
    def clear(self):
        r=self.total(); self.bets.clear(); return r

# ── Hilo de física ───────────────────────────────────────────────
class SpinWorker(threading.Thread):
    def __init__(self,q,fps=60):
        super().__init__(daemon=True)
        self.q=q; self.dt=1/fps; self._detener=threading.Event()
    def stop(self): self._detener.set()
    def run(self):
        angle=ball=0.0
        sw=random.uniform(8,12)*60*self.dt
        bw=random.uniform(-18,-14)*60*self.dt
        frames=random.randint(180,300); phase="spinning"
        while not self._detener.is_set():
            if phase=="spinning":
                angle+=sw; ball+=bw
                sw=min(sw*1.004,14*60*self.dt)
                bw=max(bw*1.004,-20*60*self.dt)
                frames-=1
                if frames<=0: phase="slowing"
            else:
                angle+=sw; ball+=bw; sw*=0.975; bw*=0.975
                if abs(sw)<0.3:
                    self.q.put(("done",angle%360,ball%360)); return
            self.q.put(("frame",angle%360,ball%360))
            self._detener.wait(self.dt)

# ── UI ───────────────────────────────────────────────────────────
class Ruleta(tk.Frame):
    """Se abre como un Frame que se apila sobre la ventana del menú,
    igual que Dados y Tragamonedas (ver vistas/dados.py,
    vistas/tragamonedas.py) — así el botón "← Menú" puede simplemente
    destruirse a sí mismo y dejar el menú principal visible debajo, en
    vez de reconfigurar la ventana raíz compartida como hacía antes."""

    W,H=1100,780
    CHIPS={5:"#1a6b1a",10:"#1a2b6b",25:"#6b1a1a",50:"#5a1a6b",100:"#6b4d00"}
    OUTER=[("1–18",T.RELIEF_LO,"1–18"),("Par",T.RELIEF_LO,"Par"),
        ("■ ROJO",T.RED,"Rojo"),("■ NEGRO","#1e1e1e","Negro"),
        ("Impar",T.RELIEF_LO,"Impar"),("19–36",T.RELIEF_LO,"19–36")]
    DOZENS=["1ª Doc.","2ª Doc.","3ª Doc."]
    DOZ_LABELS=["1ª Docena  (1–12)","2ª Docena  (13–24)","3ª Docena  (25–36)"]
    COLS=["Col. 3","Col. 2","Col. 1"]

    def __init__(self, root, jugador=None, conexion=None):
        super().__init__(root, bg=T.DEEP)
        self.root=root; self.bets=BetManager()
        # `jugador` / `conexion` (GestorConexion compartido) siguen el
        # mismo patrón que Dados/Tragamonedas: esta vista nunca toca el
        # socket directamente. Todo lo que necesite el servidor pasa
        # por self.controlador, que se suscribe a "resultado_ruleta" /
        # "ruleta_error" sobre la conexión compartida y desuscribe sus
        # handlers en _volver_menu() — nunca se abre un hilo propio.
        self.jugador = jugador
        self.conexion = conexion
        self.controlador = (
            ControladorRuleta(conexion, jugador, self)
            if conexion is not None else None
        )

        # El saldo mostrado arranca en los créditos reales del jugador
        # (autoritativos: los puso el servidor en el login/juego
        # anterior). A partir de aquí solo se ajusta de dos formas:
        # (a) localmente, como "reserva visual" al apostar/limpiar
        #     fichas, sin tocar la base de datos — igual que antes de
        #     confirmar el giro, y
        # (b) de forma autoritativa, sobrescrito por los créditos que
        #     devuelve el servidor en cada resultado_ruleta/ruleta_error
        #     (ver on_resultado_servidor / on_error_servidor).
        creditos_iniciales = getattr(jugador, "creditos", None) if jugador is not None else None
        self.balance = creditos_iniciales if creditos_iniciales is not None else 1000

        self.chip_val=10; self.spinning=False
        self._angle=self._ball_angle=0.0
        self._frame_q=self._worker=None
        self._chip_btns={}; self._history=[]
        # Resultado autoritativo pendiente del servidor (numero/color/
        # premio/creditos) mientras la animación de la rueda sigue
        # corriendo. _resolve() solo se ejecuta cuando AMBAS cosas están
        # listas: la animación terminó Y el servidor ya contestó.
        self._resultado_pendiente=None
        self._animacion_lista=False

        try:
            root.title("Robasino — Ruleta")
        except tk.TclError:
            pass

        self.pack(fill="both", expand=True)

        self._build_bg()
        self._build_header(); self._build_body(); self._build_history()
        self._draw_wheel(); self._draw_ball()

    # ── Fondo ────────────────────────────────────────────────────
    def _build_bg(self):
        # El Canvas cuelga de `self` (el Frame de Ruleta), no de
        # `self.root` (la ventana compartida con el menú): así, al
        # destruir este Frame en _volver_menu(), el canvas y todo lo
        # que dibuja se van con él, sin tocar nada del menú principal.
        self.cv=tk.Canvas(self,width=self.W,height=self.H,
                        bg=T.DEEP,highlightthickness=0)
        self.cv.pack(fill="both",expand=True)

        try:
            from PIL import Image, ImageTk
            
            # ruta_fondo = self.base_path / "recursos" / "fondo_principal.png"
            
            # img = Image.open(ruta_fondo)
            img = Image.open("recursos/fondo_principal.png").convert("RGB")
            # Recorte centrado para ajustar al tamaño de la ventana
            iw, ih = img.size
            tr = self.W / self.H
            if iw/ih > tr:
                nw=int(ih*tr); x0=(iw-nw)//2; img=img.crop((x0,0,x0+nw,ih))
            else:
                nh=int(iw/tr); y0=(ih-nh)//2; img=img.crop((0,y0,iw,y0+nh))
            img=img.resize((self.W,self.H),Image.LANCZOS)
            self._bg=ImageTk.PhotoImage(img)
            self.cv.create_image(0,0,image=self._bg,anchor="nw")
        except Exception:
            pass  # Si no hay imagen, usa el color T.DEEP de fondo

    def _place(self,w,x,y,anchor="nw"):
        self.cv.create_window(x,y,window=w,anchor=anchor)

    def _panel(self,x,y,w,h,fill=T.RELIEF):
        self.cv.create_rectangle(x,y,x+w,y+h,fill=fill,outline=T.LEAF,width=2)
        self.cv.create_rectangle(x+4,y+4,x+w-4,y+h-4,outline=T.BORDER,width=1)
        f=tk.Frame(self.cv,bg=fill); self._place(f,x+4,y+4)
        f.config(width=w-8,height=h-8); return f

    # ── Header ───────────────────────────────────────────────────
    def _build_header(self):
        self._panel(20,16,self.W-40,64)
        hdr=tk.Frame(self.cv,bg=T.RELIEF); self._place(hdr,36,24)

        # Mismo texto/estilo "← Menú" que usan Dados y Tragamonedas,
        # para que se vea consistente con el resto de la app.
        self.btn_volver=tk.Button(hdr,text="← Menú",bg=T.RELIEF_LO,fg=T.PARCH,
                font=("Georgia",11,"bold"),relief="flat",cursor="hand2",
                padx=10,pady=4,command=self._volver_menu)
        self.btn_volver.pack(side="left",padx=(0,16))
        self.btn_volver.bind("<Enter>",lambda e:self.btn_volver.config(bg=T.BORDER))
        self.btn_volver.bind("<Leave>",lambda e:self.btn_volver.config(bg=T.RELIEF_LO))

        tk.Label(hdr,text="♠  ROBASINO RULETA  ♠",bg=T.RELIEF,fg=T.LEAF_HI,
                font=("Georgia",24,"bold")).pack(side="left")
        bf=tk.Frame(self.cv,bg=T.RELIEF_LO,highlightbackground=T.LEAF,
                    highlightthickness=1,padx=16,pady=6)
        self._place(bf,self.W-40,24,anchor="ne")
        tk.Label(bf,text="SALDO",bg=T.RELIEF_LO,fg=T.PARCH,
                font=("Courier",8)).pack(side="left",padx=(0,8))
        self.bal_lbl=tk.Label(bf,text=f"$ {self.balance:,}",bg=T.RELIEF_LO,
                            fg=T.LEAF_HI,font=("Georgia",18,"bold"))
        self.bal_lbl.pack(side="left")
        rf=tk.Frame(self.cv,bg=T.RELIEF); self._place(rf,self.W-230,24,anchor="ne")
        self.result_lbl=tk.Label(rf,text="—",bg=T.RELIEF,fg=T.LEAF_HI,
                                font=("Georgia",26,"bold"),width=3)
        self.result_lbl.pack(side="right",padx=(0,16))
        self.result_sub=tk.Label(rf,text="Gira la rueda",bg=T.RELIEF,
                                fg=T.PARCH,font=("Courier",9))
        self.result_sub.pack(side="right")

    # ── Cuerpo ───────────────────────────────────────────────────
    def _build_body(self):
        col=self._panel(20,96,340,560)
        self.wc=tk.Canvas(col,width=300,height=300,bg=T.RELIEF,highlightthickness=0)
        self.wc.pack(pady=(6,0))
        tk.Label(col,text="FICHA",bg=T.RELIEF,fg=T.PARCH,
                font=("Georgia",10,"bold")).pack(pady=(10,2))
        cr=tk.Frame(col,bg=T.RELIEF); cr.pack()
        for v in [5,10,25,50,100]: self._chip_btn(cr,v)
        tk.Label(col,text="APUESTAS ACTIVAS",bg=T.RELIEF,fg=T.LEAF_HI,
                font=("Georgia",10,"bold")).pack(pady=(10,2))
        self.bets_lbl=tk.Label(col,text="(ninguna)",bg=T.RELIEF,fg=T.PARCH,
                                font=("Courier",8),justify="left",wraplength=290)
        self.bets_lbl.pack(anchor="w",padx=10)
        ac=tk.Frame(col,bg=T.RELIEF); ac.pack(fill="x",pady=(10,0),padx=10)
        self.spin_btn=tk.Button(ac,text="▶  GIRAR",bg=T.LEAF,fg=T.DEEP,
                                font=("Georgia",13,"bold"),relief="flat",pady=7,
                                cursor="hand2",command=self.spin)
        self.spin_btn.pack(side="left",padx=(0,6),fill="x",expand=True)
        tk.Button(ac,text="✖ LIMPIAR",bg=T.RELIEF_LO,fg=T.PARCH,
                font=("Courier",9),relief="flat",pady=7,cursor="hand2",
                command=self.clear_bets).pack(side="left",fill="x",expand=True)

        right=self._panel(380,96,700,360,fill="#0d2b1a")
        table=tk.Frame(right,bg="#0d2b1a",padx=10,pady=10); table.pack()
        self._grid(table); self._dozens(table); self._outer(table)

    def _btn(self,parent,text,bg,cmd,**kw):
        b=tk.Button(parent,text=text,bg=bg,fg="white",font=("Courier",9,"bold"),
                    relief="flat",cursor="hand2",command=cmd)
        b.grid(**kw)
        b.bind("<Enter>",lambda e:b.config(bg=T.BORDER))
        b.bind("<Leave>",lambda e:b.config(bg=bg))
        return b

    def _grid(self,table):
        f=tk.Frame(table,bg="#0d2b1a"); f.grid(row=0,column=0,sticky="n")
        self._btn(f,"0",T.GREEN,lambda:self.place_bet(0),
                row=0,column=0,rowspan=3,padx=(0,3),pady=1,sticky="nsew")
        for ci in range(12):
            for ri in range(3):
                n=ci*3+(3-ri)
                bg=T.RED if n in Wheel.REDS else "#1e1e1e"
                self._btn(f,str(n),bg,lambda x=n:self.place_bet(x),
                        row=ri,column=ci+1,padx=1,pady=1,sticky="nsew")
        for i,k in enumerate(self.COLS):
            self._btn(f,"2:1",T.RELIEF,lambda k=k:self.place_bet(k),
                    row=i,column=13,padx=(4,0),pady=1,sticky="nsew")

    def _dozens(self,table):
        f=tk.Frame(table,bg="#0d2b1a"); f.grid(row=1,column=0,sticky="ew",pady=(3,0))
        tk.Label(f,text="",bg="#0d2b1a",width=4).grid(row=0,column=0)
        for i,(lbl,k) in enumerate(zip(self.DOZ_LABELS,self.DOZENS)):
            self._btn(f,lbl,T.RELIEF,lambda k=k:self.place_bet(k),
                    row=0,column=i+1,padx=1,sticky="ew")
            f.grid_columnconfigure(i+1,minsize=140)
        tk.Label(f,text="",bg="#0d2b1a",width=5).grid(row=0,column=4)

    def _outer(self,table):
        f=tk.Frame(table,bg="#0d2b1a"); f.grid(row=2,column=0,sticky="ew",pady=(3,0))
        tk.Label(f,text="",bg="#0d2b1a",width=4).grid(row=0,column=0)
        for i,(lbl,bg,k) in enumerate(self.OUTER):
            self._btn(f,lbl,bg,lambda k=k:self.place_bet(k),
                    row=0,column=i+1,padx=1,sticky="ew")

    def _build_history(self):
        hp=self._panel(380,470,700,60)
        row=tk.Frame(hp,bg=T.RELIEF); row.pack(anchor="w",padx=8,pady=8)
        tk.Label(row,text="HISTORIAL",bg=T.RELIEF,fg=T.LEAF_HI,
                font=("Georgia",10,"bold")).pack(side="left",padx=(0,10))
        self.hist_frame=tk.Frame(row,bg=T.RELIEF); self.hist_frame.pack(side="left")

    # ── Volver al menú ──────────────────────────────────────────
    def _volver_menu(self):
        if self.spinning:
            return  # no se puede salir a mitad de un giro (mismo criterio que Dados/Tragamonedas)

        if self._worker is not None and self._worker.is_alive():
            self._worker.stop()

        # Desuscribe del GestorConexion compartido: sin esto, un
        # "resultado_ruleta" que llegue tarde (o de una apuesta que
        # quedó en vuelo) intentaría actualizar widgets de una vista
        # ya destruida. Mismo criterio que Dados/Tragamonedas.
        if self.controlador is not None:
            self.controlador.cerrar()

        self.destroy()

    # ── Chips ────────────────────────────────────────────────────
    def _chip_btn(self,parent,val):
        bg=self.CHIPS.get(val,T.RELIEF_LO)
        btn=tk.Button(parent,text=f"${val}",width=5,bg=bg,fg="white",
                    font=("Courier",9,"bold"),relief="flat",cursor="hand2",pady=4,
                    command=lambda:self._set_chip(val,btn))
        btn.pack(side="left",padx=2)
        self._chip_btns[val]=btn
        if val==self.chip_val: btn.config(relief="solid",bd=2)

    def _set_chip(self,val,btn):
        self.chip_val=val
        for b in self._chip_btns.values(): b.config(relief="flat",bd=0)
        btn.config(relief="solid",bd=2)

    # ── Rueda/bola ───────────────────────────────────────────────
    def _draw_wheel(self,off=0):
        c=self.wc; c.delete("wheel")
        cx,cy,R,ri=150,150,135,48; n=len(Wheel.ORDER); arc=360/n
        for i,num in enumerate(Wheel.ORDER):
            s=off+i*arc-arc/2
            c.create_arc(cx-R,cy-R,cx+R,cy+R,start=s,extent=arc,
                        fill=Wheel.color_of(num),outline=T.LEAF,width=1,tags="wheel")
            a=math.radians(-(s+arc/2)); rx=(R+ri)/2
            c.create_text(cx+rx*math.cos(a),cy+rx*math.sin(a),text=str(num),
                        fill="white",font=("Courier",6,"bold"),tags="wheel")
        c.create_oval(cx-R-4,cy-R-4,cx+R+4,cy+R+4,
                    outline=T.LEAF_HI,width=3,tags="wheel")
        c.create_oval(cx-ri,cy-ri,cx+ri,cy+ri,
                    fill=T.RELIEF_LO,outline=T.LEAF,width=2,tags="wheel")
        c.create_text(cx,cy,text="♦",fill=T.LEAF_HI,font=("Georgia",18,"bold"),tags="wheel")
        c.create_polygon(cx-6,cy-R-16,cx+6,cy-R-16,cx,cy-R+2,fill=T.LEAF_HI,tags="wheel")

    def _draw_ball(self):
        c=self.wc; c.delete("ball")
        cx,cy,R=150,150,120; a=math.radians(-self._ball_angle)
        bx,by=cx+R*math.cos(a),cy+R*math.sin(a)
        c.create_oval(bx-5,by-5,bx+5,by+5,fill="white",outline=T.PARCH,width=1,tags="ball")

    # ── Apuestas ─────────────────────────────────────────────────
    def place_bet(self,key):
        if self.spinning or self.balance<self.chip_val:
            self.result_sub.config(text="Sin saldo",fg="#ff4444"); return
        self.balance-=self.chip_val; self.bets.place(key,self.chip_val); self._refresh()

    def clear_bets(self):
        if not self.spinning: self.balance+=self.bets.clear(); self._refresh()

    def _refresh(self):
        self.bal_lbl.config(text=f"$ {self.balance:,}")
        if not self.bets.bets:
            self.bets_lbl.config(text="(ninguna)",fg=T.DIM)
        else:
            parts=[f"{k if isinstance(k,str) else f'Nº {k}'}: ${v}"
                for k,v in self.bets.bets.items()]
            self.bets_lbl.config(text="  ".join(parts),fg=T.PARCH)

    # ── Giro ─────────────────────────────────────────────────────
    def spin(self):
        if self.spinning: return
        if not self.bets.bets:
            self.result_sub.config(text="¡Haz una apuesta!",fg=T.LEAF_HI); return
        if self.controlador is None:
            self.result_sub.config(text="Sin conexión al servidor.",fg="#ff4444"); return

        self.spinning=True
        self._resultado_pendiente=None
        self._animacion_lista=False
        self.spin_btn.config(state="disabled",bg=T.DIM)
        self.result_lbl.config(text="…",fg=T.PARCH)
        self.result_sub.config(text="Girando…",fg=T.PARCH)

        # El servidor es quien decide número/color/premio; esto solo
        # dispara la petición. La respuesta llega de forma asíncrona a
        # on_resultado_servidor()/on_error_servidor() (callbacks del
        # ControladorRuleta, suscritos vía GestorConexion).
        self.controlador.girar(dict(self.bets.bets))

        # La física de la rueda es puramente decorativa: nunca decide
        # el número, solo entretiene mientras se espera al servidor.
        self._frame_q=queue.Queue()
        self._worker=SpinWorker(self._frame_q)
        self._worker.start()
        self.root.after(16,self._poll)

    def _poll(self):
        try:
            while True:
                kind,angle,ball=self._frame_q.get_nowait()
                self._angle=angle
                self._draw_wheel(self._angle)
                if kind=="frame":
                    self._ball_angle=ball; self._draw_ball()
                if kind=="done":
                    self._worker.join(timeout=0.1)
                    self._angle_final=angle
                    self._animacion_lista=True
                    self._intentar_resolver()
                    return
        except queue.Empty: pass
        self.root.after(16,self._poll)

    # ── Callbacks del ControladorRuleta (llegan desde el hilo único
    # de escucha del GestorConexion; solo tocan widgets Tk porque
    # Tk procesa este callback en el mismo ciclo de eventos que ya
    # dispara root.after — ver nota en gestor_conexion.py) ──────────
    def on_resultado_servidor(self, numero, color, premio, creditos):
        # Este callback corre en el hilo único de escucha de
        # GestorConexion (ver _despachar en gestor_conexion.py), NO en
        # el hilo principal de Tkinter — hay que reencolarlo con
        # root.after(0, ...) antes de tocar cualquier widget.
        self.root.after(0, self._aplicar_resultado_servidor,
                        numero, color, premio, creditos)

    def _aplicar_resultado_servidor(self, numero, color, premio, creditos):
        self._resultado_pendiente={
            "numero": numero, "color": color,
            "premio": premio, "creditos": creditos,
        }
        self._intentar_resolver()

    def on_error_servidor(self, mensaje):
        # Mismo motivo: reencolar en el hilo de Tk antes de tocar widgets.
        self.root.after(0, self._aplicar_error_servidor, mensaje)

    def _aplicar_error_servidor(self, mensaje):
        # p.ej. "No tienes suficientes créditos.": el servidor nunca
        # llegó a girar, así que se devuelven las fichas apostadas.
        self.spinning=False
        self._animacion_lista=False; self._resultado_pendiente=None
        if self._worker is not None and self._worker.is_alive():
            self._worker.stop()
        self.spin_btn.config(state="normal",bg=T.LEAF)
        self.result_lbl.config(text="—",fg=T.LEAF_HI)
        self.result_sub.config(text=mensaje,fg="#ff4444")
        self.balance+=self.bets.clear()
        self._refresh()

    def _intentar_resolver(self):
        if self._animacion_lista and self._resultado_pendiente is not None:
            self._resolve(self._resultado_pendiente)

    def _resolve(self, resultado):
        numero=resultado["numero"]
        color=resultado["color"]                  # "rojo"/"negro"/"verde", del servidor
        premio=resultado["premio"]
        creditos=resultado["creditos"]
        color_hex={"rojo":T.RED,"negro":T.BLACK,"verde":T.GREEN}.get(color,T.PARCH)

        # La bola "cae" exactamente sobre el número que mandó el
        # servidor: se usa el ángulo final que dejó la física (solo
        # estético) y se ubica la bola en el centro de la ranura de
        # `numero` sobre ESE ángulo de rueda — nunca al revés.
        idx=Wheel.ORDER.index(numero)
        arc=360/len(Wheel.ORDER)
        self._angle=self._angle_final
        self._ball_angle=(self._angle_final+idx*arc)%360
        self._draw_wheel(self._angle); self._draw_ball()

        self.result_lbl.config(text=str(numero),fg=T.LEAF_HI)
        if premio>0: self.result_sub.config(text=f"¡GANASTE  ${premio}!",fg=T.LEAF_HI)
        else:        self.result_sub.config(text="Sin suerte — ¡inténtalo de nuevo!",fg="#ff6666")

        lbl=tk.Label(self.hist_frame,text=str(numero),width=3,bg=color_hex,
                    fg="white",font=("Courier",9,"bold"),relief="flat",pady=2)
        lbl.pack(side="left",padx=1); self._history.append(lbl)
        if len(self._history)>20: self._history.pop(0).destroy()

        self.spinning=False; self.spin_btn.config(state="normal",bg=T.LEAF)
        self.bets.clear()
        # Saldo autoritativo: lo que diga el servidor, punto. Nunca se
        # deriva de una suma local ni se "recarga" saldo inventado.
        if creditos is not None:
            self.balance=creditos
        self._resultado_pendiente=None; self._animacion_lista=False
        self._refresh()

# if __name__=="__main__":
#     os.chdir(os.path.dirname(os.path.abspath(__file__)))
#     root=tk.Tk()
#     Ruleta(root)
#     root.mainloop()
