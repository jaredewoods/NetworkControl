import tkinter as tk
from tkinter import ttk
from model.types import NICRuntime, NICStaged
from model.network import ipv4

FONT = ("Segoe UI", 10)
FONT_ITALIC = ("Segoe UI", 10, "italic")
FONT_MONO = ("Consolas", 10)
COLOR_EDIT = "#0b57d0"   # blue
COLOR_LOCK = "#5f6b7a"   # grey
COLOR_ERR  = "#c62828"   # red

class TableCell(tk.Frame):
    def __init__(self, master, width_chars=18, justify="center"):
        super().__init__(master, bd=1, relief="solid", bg="white", highlightthickness=0)
        self.var = tk.StringVar()
        self.label = tk.Label(self, textvariable=self.var, bg="white", font=FONT, anchor="center", justify=justify)
        self.entry = None
        self.width_chars = width_chars
        self.justify = justify
        self.label.pack(fill="both", expand=True, padx=8, pady=6)
        self.validator = None

    def set_text(self, text): self.var.set("" if text is None else str(text))

    def set_label_style(self, color, italic=False):
        self.label.config(fg=color, font=(FONT_ITALIC if italic else FONT))

    def make_editable(self, validator=None, color=COLOR_EDIT):
        if self.entry:
            self.validator = validator
            self.entry.config(fg=color)
            return
        self.label.pack_forget()
        self.entry = tk.Entry(self, textvariable=self.var, width=self.width_chars, justify=self.justify,
                              font=FONT_MONO, fg=color, relief="flat")
        self.entry.pack(fill="both", expand=True, padx=8, pady=6)
        self.entry.icursor(tk.END)
        self.validator = validator
        self.entry.bind("<FocusOut>", self._validate)
        self.entry.bind("<Return>", self._validate)

    def make_readonly(self, color=COLOR_LOCK, italic=True):
        if self.entry:
            self.entry.destroy(); self.entry = None
        self.label.pack(fill="both", expand=True, padx=8, pady=6)
        self.set_label_style(color, italic=italic)

    def set_error(self):
        if self.entry: self.entry.config(fg=COLOR_ERR)
        else: self.set_label_style(COLOR_ERR, italic=False)

    def _validate(self, *_):
        if self.validator is None: return
        v = self.var.get().strip()
        if not self.validator(v):
            self.set_error()
        else:
            if self.entry: self.entry.config(fg=COLOR_EDIT)

class LED(tk.Canvas):
    def __init__(self, master, size=12):
        super().__init__(master, width=size, height=size, bg="white", highlightthickness=0)
        self.oval = self.create_oval(1,1,size-1,size-1, fill="#cccccc", outline="#999")
    def set(self, color):
        self.itemconfig(self.oval, fill=color, outline=color)

class NICRow(tk.Frame):
    def __init__(self, master, iface, runtime: NICRuntime, on_apply, connectivity_color: str):
        super().__init__(master, bg="white")
        self.iface = iface
        self.runtime = runtime
        self.on_apply = on_apply

        # Column 0: Connection (LED + name)
        conn = tk.Frame(self, bg="white")
        self.led = LED(conn, 12); self.led.pack(side="left", padx=(6,8))
        tk.Label(conn, text=self.iface.name, bg="white", font=FONT, anchor="w").pack(side="left", fill="x", expand=True)
        self._place(conn, 0)

        # Column 1: Description (read-only)
        self.c_desc = TableCell(self, width_chars=24, justify="center"); self.c_desc.set_text(self.iface.description); self.c_desc.make_readonly()
        self._place(self.c_desc, 1)

        # Columns 2-5: IP fields
        self.c_ip   = TableCell(self, width_chars=18); self._place(self.c_ip, 2)
        self.c_mask = TableCell(self, width_chars=18); self._place(self.c_mask, 3)
        self.c_gw   = TableCell(self, width_chars=18); self._place(self.c_gw, 4)
        self.c_dns  = TableCell(self, width_chars=30); self._place(self.c_dns, 5)

        # Column 6: Mode combobox
        self.mode_var = tk.StringVar()
        self.mode = ttk.Combobox(self, textvariable=self.mode_var, values=["DHCP","Static"], state="readonly", width=10, justify="center")
        self._place(self.mode, 6)

        # Column 7: MAC (read-only)
        self.c_mac = TableCell(self, width_chars=20); self.c_mac.set_text(self.iface.mac); self.c_mac.make_readonly()
        self._place(self.c_mac, 7)

        for i in range(8): self.grid_columnconfigure(i, weight=0)  # stop row auto-grow/shrink
        self.refresh(runtime, connectivity_color)

    def _place(self, widget, col):
        widget.grid(row=0, column=col, sticky="nsew", padx=(0,1), pady=(0,1))

    def refresh(self, runtime: NICRuntime, connectivity_color: str):
        self.runtime = runtime
        dhcp = bool(runtime.dhcp)
        self.mode_var.set("DHCP" if dhcp else "Static")

        dns_text = ", ".join(runtime.dns) if runtime.dns else ("DHCP not Assigned" if dhcp else "")
        self.c_ip.set_text(runtime.ip or ("DHCP not Assigned" if dhcp else ""))
        self.c_mask.set_text(runtime.mask or ("DHCP not Assigned" if dhcp else ""))
        self.c_gw.set_text(runtime.gw or ("DHCP not Assigned" if dhcp else ""))
        self.c_dns.set_text(dns_text)

        if dhcp:
            for c in (self.c_ip, self.c_mask, self.c_gw, self.c_dns): c.make_readonly()
        else:
            self.c_ip.make_editable(validator=ipv4)
            self.c_mask.make_editable(validator=ipv4)
            self.c_gw.make_editable(validator=lambda s:(not s) or ipv4(s))
            self.c_dns.make_editable(validator=lambda s: all((p.strip()=="" or ipv4(p.strip())) for p in s.split(",")))

        # LED
        self.led.set(connectivity_color)

    def staged(self) -> NICStaged:
        mode = self.mode_var.get()
        if mode == "Static":
            dns_list = [p.strip() for p in self.c_dns.var.get().split(",") if p.strip() and ipv4(p.strip())]
        else:
            dns_list = []  # prevent silent static DNS override in DHCP
        return NICStaged(
            name=self.iface.name,
            mode=mode,
            ip=self.c_ip.var.get().strip() if mode=="Static" else None,
            mask=self.c_mask.var.get().strip() if mode=="Static" else None,
            gw=self.c_gw.var.get().strip() if mode=="Static" else None,
            dns=dns_list,
        )

    def apply(self):
        self.on_apply(self.staged())
