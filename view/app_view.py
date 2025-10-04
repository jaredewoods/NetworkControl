import tkinter as tk
from tkinter import ttk, messagebox
from typing import List
from model.types import Interface
from .widgets import NICRow

HDR_BG = "#f6f8fa"

class AppView(tk.Tk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.title("NIC Control Panel (Windows)")
        self.geometry("1360x520")
        self.configure(bg="white")

        top = tk.Frame(self, bg="white"); top.pack(fill="x", padx=8, pady=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(top, text="Apply Changes", command=self.apply_all).pack(side="left", padx=6)

        hdr = tk.Frame(self, bg="white"); hdr.pack(fill="x", padx=8)
        headers = ["Connection","Description","IP Address","Subnet Mask","Default Gateway","DNS Server","Mode","Physical Address"]
        for i, h in enumerate(headers):
            f = tk.Frame(hdr, bd=1, relief="solid", bg=HDR_BG)
            tk.Label(f, text=h, font=("Segoe UI", 10, "bold"), bg=HDR_BG, anchor="center").pack(padx=8, pady=6, fill="x")
            f.grid(row=0, column=i, sticky="nsew", padx=(0,1), pady=(0,1))
            hdr.grid_columnconfigure(i, weight=0)  # stop header auto-grow/shrink

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg="white")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(8,0), pady=(2,8))
        self.scroll.pack(side="right", fill="y", padx=(0,8), pady=(2,8))

        self.rows: List[NICRow] = []
        self.refresh()

    def refresh(self):
        for w in self.body.winfo_children(): w.destroy()
        self.rows.clear()
        try:
            interfs: List[Interface] = self.controller.list_interfaces()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list adapters:\n{e}"); return

        for r, it in enumerate(interfs):
            rt = self.controller.read_runtime(it.name)
            color = self.controller.connectivity_color(it.link_status)
            row = NICRow(self.body, it, rt, on_apply=self.controller.apply, connectivity_color=color)
            row.grid(row=r, column=0, sticky="nsew")
            self.body.grid_rowconfigure(r, weight=1, uniform="rows")
            self.rows.append(row)

    def apply_all(self):
        if not messagebox.askokcancel("Apply", "Applying changes may drop your network connection. Continue?"):
            return
        for row in self.rows:
            try:
                row.apply()
            except Exception as e:
                messagebox.showerror("Apply failed", str(e))
        self.refresh()
