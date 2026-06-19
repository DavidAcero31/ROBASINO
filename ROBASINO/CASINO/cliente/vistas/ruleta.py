import tkinter as tk
import threading, queue, random, math, os

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

    @classmethod
    def number_at_angle(cls,wheel_angle,ball_angle):
        arc=360/len(cls.ORDER)
        idx=math.floor(((ball_angle-wheel_angle+arc/2)%360)/arc)%len(cls.ORDER)
        return cls.ORDER[idx]

# ── Apuestas ─────────────────────────────────────────────────────
class BetManager:
    TYPES={
        "Rojo":   (lambda n:n!=0 and n in Wheel.REDS,2),
        "Negro":  (lambda n:n!=0 and n not in Wheel.REDS,2),
        "Par":    (lambda n:n!=0 and n%2==0,2),
        "Impar":  (lambda n:n!=0 and n%2==1,2),
        "1–18":   (lambda n:1<=n<=18,2),
        "19–36":  (lambda n:19<=n<=36,2),
        "1ª Doc.":(lambda n:1<=n<=12,3),
        "2ª Doc.":(lambda n:13<=n<=24,3),
        "3ª Doc.":(lambda n:25<=n<=36,3),
        "Col. 1": (lambda n:n!=0 and n%3==1,3),
        "Col. 2": (lambda n:n!=0 and n%3==2,3),
        "Col. 3": (lambda n:n!=0 and n%3==0,3),
    }
    def __init__(self): self.bets={}
    def place(self,k,v): self.bets[k]=self.bets.get(k,0)+v
    def total(self): return sum(self.bets.values())
    def clear(self):
        r=self.total(); self.bets.clear(); return r
    def settle(self,num):
        w=0
        for k,v in self.bets.items():
            if isinstance(k,int): w+=v*36 if k==num else 0
            else:
                cond,mult=self.TYPES[k]
                if cond(num): w+=v*mult
        self.bets.clear(); return w

# ── Hilo de física ───────────────────────────────────────────────
class SpinWorker(threading.Thread):
    def __init__(self,q,fps=60):
        super().__init__(daemon=True)
        self.q=q; self.dt=1/fps; self._stop=threading.Event()
    def stop(self): self._stop.set()
    def run(self):
        angle=ball=0.0
        sw=random.uniform(8,12)*60*self.dt
        bw=random.uniform(-18,-14)*60*self.dt
        frames=random.randint(180,300); phase="spinning"
        while not self._stop.is_set():
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
            self._stop.wait(self.dt)

# ── UI ───────────────────────────────────────────────────────────
class Ruleta:
    W,H=1100,780
    CHIPS={5:"#1a6b1a",10:"#1a2b6b",25:"#6b1a1a",50:"#5a1a6b",100:"#6b4d00"}
    OUTER=[("1–18",T.RELIEF_LO,"1–18"),("Par",T.RELIEF_LO,"Par"),
        ("■ ROJO",T.RED,"Rojo"),("■ NEGRO","#1e1e1e","Negro"),
        ("Impar",T.RELIEF_LO,"Impar"),("19–36",T.RELIEF_LO,"19–36")]
    DOZENS=["1ª Doc.","2ª Doc.","3ª Doc."]
    DOZ_LABELS=["1ª Docena  (1–12)","2ª Docena  (13–24)","3ª Docena  (25–36)"]
    COLS=["Col. 3","Col. 2","Col. 1"]

    def __init__(self,root):
        self.root=root; self.bets=BetManager()
        self.balance=1000; self.chip_val=10; self.spinning=False
        self._angle=self._ball_angle=0.0
        self._frame_q=self._worker=None
        self._chip_btns={}; self._history=[]

        root.title("Robasino — Ruleta")
        root.configure(bg=T.DEEP); root.resizable(False,False)

        self._build_bg()
        self._build_header(); self._build_body(); self._build_history()
        self._draw_wheel(); self._draw_ball()

    # ── Fondo ────────────────────────────────────────────────────
    def _build_bg(self):
        self.cv=tk.Canvas(self.root,width=self.W,height=self.H,
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
        self.spinning=True
        self.spin_btn.config(state="disabled",bg=T.DIM)
        self.result_lbl.config(text="…",fg=T.PARCH)
        self.result_sub.config(text="Girando…",fg=T.PARCH)
        self._frame_q=queue.Queue()
        self._worker=SpinWorker(self._frame_q)
        self._worker.start()
        self.root.after(16,self._poll)

    def _poll(self):
        try:
            while True:
                kind,angle,ball=self._frame_q.get_nowait()
                self._angle,self._ball_angle=angle,ball
                self._draw_wheel(self._angle); self._draw_ball()
                if kind=="done":
                    self._worker.join(timeout=0.1); self._resolve(); return
        except queue.Empty: pass
        self.root.after(16,self._poll)

    def _resolve(self):
        num=Wheel.number_at_angle(self._angle,self._ball_angle)
        self.result_lbl.config(text=str(num),fg=T.LEAF_HI)
        self.result_sub.config(text=Wheel.color_name(num),fg=Wheel.color_of(num))
        w=self.bets.settle(num)
        if w>0: self.result_sub.config(text=f"¡GANASTE  ${w}!",fg=T.LEAF_HI)
        else:   self.result_sub.config(text="Sin suerte — ¡inténtalo de nuevo!",fg="#ff6666")
        lbl=tk.Label(self.hist_frame,text=str(num),width=3,bg=Wheel.color_of(num),
                    fg="white",font=("Courier",9,"bold"),relief="flat",pady=2)
        lbl.pack(side="left",padx=1); self._history.append(lbl)
        if len(self._history)>20: self._history.pop(0).destroy()
        self.spinning=False; self.spin_btn.config(state="normal",bg=T.LEAF)
        self.balance+=w
        if self.balance<=0:
            self.balance=1000
            self.result_sub.config(text="Sin saldo — se recargaron $1,000",fg=T.LEAF_HI)
        self._refresh()

# if __name__=="__main__":
#     os.chdir(os.path.dirname(os.path.abspath(__file__)))
#     root=tk.Tk()
#     Ruleta(root)
#     root.mainloop()