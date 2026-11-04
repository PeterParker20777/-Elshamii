"""Elshamii desktop management interface. Made By PeterParker 🕷️"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from api import APIError, StoreAPI
from i18n import shape_arabic, tr
from resources import asset_path


APP_NAME = "الشامي | Elshamii"
INK = "#172033"
MUTED = "#748094"
NAVY = "#17243A"
NAVY_LIGHT = "#223550"
GOLD = "#D9A441"
BG = "#F3F5F8"
WHITE = "#FFFFFF"
GREEN = "#16845B"
RED = "#C74747"
ORANGE = "#C17A21"


def data_dir() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home())) / "PPMarket"
    root.mkdir(parents=True, exist_ok=True)
    return root


class ElshamiiApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.title(APP_NAME)
        self.geometry("1440x900")
        self.minsize(1120, 720)
        self.configure(fg_color=BG)
        self.api = StoreAPI()
        self.token = None
        self.username = ""
        self.language = "ar"
        self.current_page = "dashboard"
        self.dashboard_data = {}
        self.orders_cache = []
        self.logo_image = None
        self.config_path = data_dir() / "desktop_config.json"
        self.config_data = self._load_config()
        self.language = self.config_data.get("language", "ar")
        # Asset root is centralized so icons/images can be bundled consistently later.
        self.assets_root = asset_path()
        self._show_login()

    def _load_config(self) -> dict:
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.config_path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.config_data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.config_path)

    def t(self, key: str) -> str:
        return shape_arabic(tr(self.language, key), self.language)

    def _clear(self):
        for child in self.winfo_children():
            child.destroy()

    def _show_login(self):
        # Never fall back to Login when the API cannot be reached. Doing so
        # hides the real first-run setup state and confuses a stopped server
        # with an already-created owner account.
        try:
            status = self.api.bootstrap_status()
            if not isinstance(status, dict) or "setup_required" not in status:
                raise APIError("The server returned an invalid bootstrap status.")
            self.bootstrap_required = bool(status["setup_required"])
        except APIError as exc:
            self._show_server_unavailable(exc)
            return
        if self.bootstrap_required:
            self._show_bootstrap()
            return
        self._clear()
        self.title(self.t("app_title"))
        outer = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        outer.pack(fill="both", expand=True)
        panel = ctk.CTkFrame(outer, fg_color=WHITE, corner_radius=24, width=470, height=590,
                             border_width=1, border_color="#E7EAF0")
        panel.place(relx=.5, rely=.5, anchor="center")
        panel.pack_propagate(False)

        ctk.CTkLabel(panel, text="✦", text_color=GOLD, font=ctk.CTkFont(size=34, weight="bold")).pack(pady=(42, 2))
        ctk.CTkLabel(panel, text="الشامي", text_color=INK, font=ctk.CTkFont(family="Segoe UI", size=34, weight="bold")).pack()
        ctk.CTkLabel(panel, text="ELSHAMII", text_color=GOLD, font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(0, 8))
        ctk.CTkLabel(panel, text=self.t("login_title"), text_color=INK,
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(22, 4))
        ctk.CTkLabel(panel, text=self.t("login_subtitle"), text_color=MUTED,
                     font=ctk.CTkFont(size=13)).pack(pady=(0, 22))

        form = ctk.CTkFrame(panel, fg_color="transparent", width=350)
        form.pack(fill="x", padx=58)
        ctk.CTkLabel(form, text=self.t("username"), text_color=INK, anchor="e" if self.language == "ar" else "w").pack(fill="x", pady=(0, 6))
        self.username_entry = ctk.CTkEntry(form, height=46, corner_radius=10, border_color="#DCE2EA",
                                           fg_color="#FAFBFC", text_color=INK, justify="right" if self.language == "ar" else "left")
        self.username_entry.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(form, text=self.t("password"), text_color=INK, anchor="e" if self.language == "ar" else "w").pack(fill="x", pady=(0, 6))
        self.password_entry = ctk.CTkEntry(form, height=46, corner_radius=10, border_color="#DCE2EA",
                                           fg_color="#FAFBFC", text_color=INK, show="•",
                                           justify="right" if self.language == "ar" else "left")
        self.password_entry.pack(fill="x", pady=(0, 18))
        self.login_error = ctk.CTkLabel(form, text="", text_color=RED, wraplength=340, font=ctk.CTkFont(size=12))
        self.login_error.pack(fill="x", pady=(0, 8))
        self.login_button = ctk.CTkButton(form, text=self.t("sign_in"), height=48, corner_radius=10,
                                          fg_color=NAVY, hover_color=NAVY_LIGHT, text_color=WHITE,
                                          font=ctk.CTkFont(size=15, weight="bold"), command=self._login)
        self.login_button.pack(fill="x")
        self.password_entry.bind("<Return>", lambda _e: self._login())
        self.username_entry.bind("<Return>", lambda _e: self.password_entry.focus_set())

        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=28, pady=22)
        ctk.CTkButton(footer, text="العربية" if self.language == "en" else "English", width=90, height=30,
                      fg_color="#F0F2F5", hover_color="#E5E9EF", text_color=INK,
                      command=self._toggle_language).pack(side="left")
        ctk.CTkLabel(footer, text=self.t("made_by"), text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="right")
        self.username_entry.focus_set()

    def _show_server_unavailable(self, error: APIError):
        self._clear()
        self.title(self.t("app_title"))
        outer = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        outer.pack(fill="both", expand=True)
        panel = ctk.CTkFrame(outer, fg_color=WHITE, corner_radius=22, width=560, height=390,
                             border_width=1, border_color="#E7EAF0")
        panel.place(relx=.5, rely=.5, anchor="center")
        panel.pack_propagate(False)
        ctk.CTkLabel(panel, text="الشامي", text_color=INK,
                     font=ctk.CTkFont(family="Segoe UI", size=34, weight="bold")).pack(pady=(42, 0))
        ctk.CTkLabel(panel, text="ELSHAMII", text_color=GOLD,
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(0, 22))
        ctk.CTkLabel(panel, text=("السيرفر المحلي غير متصل" if self.language == "ar" else "Local server is unavailable"),
                     text_color=INK, font=ctk.CTkFont(size=21, weight="bold")).pack(pady=(0, 10))
        detail = ("شغّل السيرفر باستخدام Start_Elshamii.bat ثم اضغط إعادة المحاولة."
                  if self.language == "ar" else
                  "Start the backend with Start_Elshamii.bat, then retry.")
        ctk.CTkLabel(panel, text=detail, text_color=MUTED, wraplength=440,
                     font=ctk.CTkFont(size=13)).pack(pady=(0, 8))
        reason = ("تعذر الاتصال بـ API المحلي." if error.status_code is None else
                  f"API response: HTTP {error.status_code}")
        ctk.CTkLabel(panel, text=reason, text_color=RED,
                     font=ctk.CTkFont(size=11)).pack(pady=(0, 18))
        ctk.CTkButton(panel, text=("إعادة المحاولة" if self.language == "ar" else "Retry"),
                      height=46, width=210, corner_radius=10, fg_color=NAVY,
                      hover_color=NAVY_LIGHT, text_color=WHITE, command=self._show_login).pack()
        ctk.CTkLabel(panel, text=self.t("made_by"), text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="bottom", pady=20)

    def _show_bootstrap(self):
        self._clear()
        self.title(self.t("app_title"))
        outer = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        outer.pack(fill="both", expand=True)
        panel = ctk.CTkFrame(outer, fg_color=WHITE, corner_radius=24, width=500, height=700,
                             border_width=1, border_color="#E7EAF0")
        panel.place(relx=.5, rely=.5, anchor="center")
        panel.pack_propagate(False)
        ctk.CTkLabel(panel, text="✦", text_color=GOLD, font=ctk.CTkFont(size=34, weight="bold")).pack(pady=(24, 0))
        ctk.CTkLabel(panel, text="الشامي", text_color=INK, font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold")).pack()
        ctk.CTkLabel(panel, text="ELSHAMII", text_color=GOLD, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(0, 8))
        ctk.CTkLabel(panel, text=self.t("bootstrap_title"), text_color=INK,
                     font=ctk.CTkFont(size=21, weight="bold")).pack(pady=(12, 4))
        ctk.CTkLabel(panel, text=self.t("bootstrap_subtitle"), text_color=MUTED,
                     font=ctk.CTkFont(size=12), wraplength=390).pack(pady=(0, 18))
        form = ctk.CTkFrame(panel, fg_color="transparent")
        form.pack(fill="x", padx=58)
        fields = [
            ("username", "bootstrap_username_entry", False),
            ("password", "bootstrap_password_entry", True),
            ("confirm_password", "bootstrap_confirm_entry", True),
            ("developer_code", "bootstrap_code_entry", True),
        ]
        for key, attr, secret in fields:
            ctk.CTkLabel(form, text=self.t(key), text_color=INK, anchor="e" if self.language == "ar" else "w").pack(fill="x", pady=(7, 4))
            entry = ctk.CTkEntry(form, height=43, corner_radius=9, fg_color="#FAFBFC",
                                 border_color="#DCE2EA", text_color=INK, show="•" if secret else "",
                                 justify="right" if self.language == "ar" else "left")
            entry.pack(fill="x", pady=(0, 4))
            setattr(self, attr, entry)
        self.bootstrap_error = ctk.CTkLabel(form, text="", text_color=RED, wraplength=370,
                                            font=ctk.CTkFont(size=11))
        self.bootstrap_error.pack(fill="x", pady=(7, 5))
        self.bootstrap_button = ctk.CTkButton(form, text=self.t("create_owner"), height=46,
            corner_radius=10, fg_color=NAVY, hover_color=NAVY_LIGHT, text_color=WHITE,
            font=ctk.CTkFont(size=14, weight="bold"), command=self._create_first_owner)
        self.bootstrap_button.pack(fill="x", pady=(5, 0))
        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=28, pady=18)
        ctk.CTkButton(footer, text="العربية" if self.language == "en" else "English", width=90, height=30,
            fg_color="#F0F2F5", hover_color="#E5E9EF", text_color=INK,
            command=self._toggle_language).pack(side="left")
        ctk.CTkLabel(footer, text=self.t("made_by"), text_color=MUTED,
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="right")
        self.bootstrap_username_entry.focus_set()

    def _create_first_owner(self):
        username = self.bootstrap_username_entry.get().strip()
        password = self.bootstrap_password_entry.get()
        confirm = self.bootstrap_confirm_entry.get()
        code = self.bootstrap_code_entry.get()
        if not username or not password or not confirm or not code:
            self.bootstrap_error.configure(text=self.t("complete_fields"))
            return
        if password != confirm:
            self.bootstrap_error.configure(text=self.t("password_mismatch"))
            return
        if len(password) < 8:
            self.bootstrap_error.configure(text=self.t("password_short"))
            return
        self.bootstrap_button.configure(state="disabled", text=self.t("loading"))
        self.update_idletasks()
        try:
            result = self.api.create_first_owner(code, username, password)
            self.token = result["token"]
            self.username = result.get("username", username)
            self.current_page = "dashboard"
            self._show_shell()
            self._load_dashboard()
        except APIError as exc:
            messages = {
                "invalid_code": self.t("invalid_developer_code"),
                "setup_completed": self.t("setup_already_done"),
                "bootstrap_not_configured": self.t("bootstrap_not_configured"),
                "username_taken": self.t("username_taken"),
                "invalid_input": self.t("invalid_input"),
            }
            self.bootstrap_error.configure(text=messages.get((exc.payload or {}).get("error"), self.t("bootstrap_failed")))
            self.bootstrap_button.configure(state="normal", text=self.t("create_owner"))

    def _toggle_language(self):
        self.language = "en" if self.language == "ar" else "ar"
        self.config_data["language"] = self.language
        self._save_config()
        self._show_login()

    def _login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            self.login_error.configure(text=self.t("login_error"))
            return
        self.login_button.configure(state="disabled", text=self.t("loading"))
        self.update_idletasks()
        try:
            result = self.api.login(username, password)
            self.token = result["token"]
            self.username = result.get("username", username)
            self._show_shell()
            self._load_dashboard()
        except APIError as exc:
            message = self.t("no_permission") if exc.status_code == 403 else self.t("login_error")
            self.login_error.configure(text=message)
            self.login_button.configure(state="normal", text=self.t("sign_in"))

    def _show_shell(self):
        self._clear()
        self.title(APP_NAME)
        shell = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        shell.pack(fill="both", expand=True)
        self.sidebar = ctk.CTkFrame(shell, width=246, fg_color=NAVY, corner_radius=0)
        self.sidebar.pack(side="right" if self.language == "ar" else "left", fill="y")
        self.sidebar.pack_propagate(False)
        self.content = ctk.CTkFrame(shell, fg_color=BG, corner_radius=0)
        self.content.pack(side="left" if self.language == "ar" else "right", fill="both", expand=True)
        self._build_sidebar()
        self._render_page(self.current_page)

    def _build_sidebar(self):
        s = self.sidebar
        ctk.CTkLabel(s, text="الشامي", text_color=WHITE, font=ctk.CTkFont(size=30, weight="bold")).pack(pady=(34, 0))
        ctk.CTkLabel(s, text="ELSHAMII", text_color=GOLD, font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0, 6))
        ctk.CTkLabel(s, text=self.t("subtitle"), text_color="#AAB6C8", font=ctk.CTkFont(size=10, weight="bold")).pack(pady=(0, 38))
        nav = [
            ("dashboard", "▦", "dashboard"), ("products", "▣", "products"),
            ("categories", "▤", "categories"), ("inventory", "◫", "inventory"),
            ("orders", "▤", "orders"), ("reports", "▥", "reports"),
            ("server", "◉", "server"), ("settings", "⚙", "settings"),
        ]
        self.nav_buttons = {}
        for page, glyph, key in nav:
            button = ctk.CTkButton(s, text=f"{glyph}     {self.t(key)}", height=48, corner_radius=10,
                                   anchor="e" if self.language == "ar" else "w",
                                   fg_color=NAVY_LIGHT if page == self.current_page else "transparent",
                                   hover_color=NAVY_LIGHT, text_color=WHITE,
                                   font=ctk.CTkFont(size=14, weight="bold" if page == self.current_page else "normal"),
                                   command=lambda p=page: self._render_page(p))
            button.pack(fill="x", padx=18, pady=5)
            self.nav_buttons[page] = button
        spacer = ctk.CTkFrame(s, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        ctk.CTkFrame(s, height=1, fg_color="#34445D").pack(fill="x", padx=20, pady=16)
        ctk.CTkLabel(s, text=self.username, text_color=WHITE, font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="e" if self.language == "ar" else "w", padx=22)
        ctk.CTkLabel(s, text="STAFF ACCOUNT", text_color="#91A0B5", font=ctk.CTkFont(size=9, weight="bold")).pack(anchor="e" if self.language == "ar" else "w", padx=22, pady=(2, 12))
        ctk.CTkButton(s, text=f"↪  {self.t('logout')}", height=40, corner_radius=9,
                      fg_color="#293B55", hover_color="#3B4F6B", text_color=WHITE,
                      command=self._logout).pack(fill="x", padx=18, pady=(0, 20))

    def _render_page(self, page: str):
        self.current_page = page
        if hasattr(self, "nav_buttons"):
            for key, button in self.nav_buttons.items():
                button.configure(fg_color=NAVY_LIGHT if key == page else "transparent",
                                 font=ctk.CTkFont(size=14, weight="bold" if key == page else "normal"))
        for child in self.content.winfo_children():
            child.destroy()
        if page == "dashboard":
            self._page_dashboard()
        elif page == "orders":
            self._page_orders()
        elif page == "products":
            self._page_products()
        elif page == "categories":
            self._page_categories()
        elif page == "inventory":
            self._page_inventory()
        elif page == "reports":
            self._page_reports()
        elif page == "server":
            self._page_server()
        elif page == "settings":
            self._page_settings()

    def _header(self, title: str, subtitle: str, action_text: str | None = None, action=None):
        header = ctk.CTkFrame(self.content, fg_color="transparent")
        header.pack(fill="x", padx=34, pady=(30, 22))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="right" if self.language == "ar" else "left", fill="x", expand=True)
        ctk.CTkLabel(left, text=title, text_color=INK, font=ctk.CTkFont(size=27, weight="bold"),
                     anchor="e" if self.language == "ar" else "w").pack(fill="x")
        ctk.CTkLabel(left, text=subtitle, text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="e" if self.language == "ar" else "w").pack(fill="x", pady=(5, 0))
        if action_text:
            ctk.CTkButton(header, text=action_text, width=118, height=38, corner_radius=9,
                          fg_color=NAVY, hover_color=NAVY_LIGHT, command=action).pack(side="left" if self.language == "ar" else "right")

    def _stat_card(self, parent, title, value, hint, accent=GOLD):
        card = ctk.CTkFrame(parent, fg_color=WHITE, corner_radius=14, border_width=1, border_color="#E7EAF0")
        card.grid_propagate(False)
        ctk.CTkFrame(card, width=4, fg_color=accent, corner_radius=3).pack(side="right" if self.language == "ar" else "left", fill="y", padx=(0, 12) if self.language == "ar" else (12, 0), pady=16)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=14)
        ctk.CTkLabel(body, text=title, text_color=MUTED, font=ctk.CTkFont(size=12),
                     anchor="e" if self.language == "ar" else "w").pack(fill="x")
        ctk.CTkLabel(body, text=str(value), text_color=INK, font=ctk.CTkFont(size=27, weight="bold"),
                     anchor="e" if self.language == "ar" else "w").pack(fill="x", pady=(5, 0))
        ctk.CTkLabel(body, text=hint, text_color=MUTED, font=ctk.CTkFont(size=10),
                     anchor="e" if self.language == "ar" else "w").pack(fill="x", pady=(2, 0))
        return card

    def _load_dashboard(self):
        try:
            self.dashboard_data = self.api.dashboard()
            if self.current_page == "dashboard":
                self._render_page("dashboard")
        except APIError:
            if self.current_page == "dashboard":
                self._render_page("dashboard")

    def _page_dashboard(self):
        self._header(self.t("overview"), self.t("overview_sub"), self.t("refresh"), self._load_dashboard)
        d = self.dashboard_data or {}
        products = d.get("products", {})
        orders = d.get("orders", {})
        today = d.get("today", {})
        grid = ctk.CTkFrame(self.content, fg_color="transparent")
        grid.pack(fill="x", padx=34)
        for col in range(4):
            grid.grid_columnconfigure(col, weight=1, uniform="stats")
        stats = [
            (self.t("today_sales"), f"{today.get('sales', '0.00')} EGP", self.t("today_orders") + f": {today.get('orders', 0)}", GOLD),
            (self.t("today_orders"), today.get("orders", 0), self.t("status_PENDING") + f": {orders.get('PENDING', 0)}", "#4B83C6"),
            (self.t("products"), products.get("total", 0), self.t("low_stock") + f": {products.get('low_stock', 0)}", GREEN),
            (self.t("out_stock"), products.get("out_of_stock", 0), self.t("low_stock") + f": {products.get('low_stock', 0)}", RED),
        ]
        for i, row in enumerate(stats):
            self._stat_card(grid, *row).grid(row=0, column=i, sticky="nsew", padx=7, ipady=5)

        section = ctk.CTkFrame(self.content, fg_color=WHITE, corner_radius=14, border_width=1, border_color="#E7EAF0")
        section.pack(fill="both", expand=True, padx=41, pady=26)
        top = ctk.CTkFrame(section, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=18)
        ctk.CTkLabel(top, text=self.t("order_queue"), text_color=INK,
                     font=ctk.CTkFont(size=17, weight="bold")).pack(side="right" if self.language == "ar" else "left")
        ctk.CTkButton(top, text=self.t("view_orders"), width=125, height=32, fg_color="#F0F3F7",
                      hover_color="#E4E9F0", text_color=INK, command=lambda: self._render_page("orders")).pack(side="left" if self.language == "ar" else "right")
        self._render_order_rows(section, self._safe_recent_orders())

    def _safe_recent_orders(self):
        try:
            return self.api.orders()[:6]
        except APIError:
            return []

    def _render_order_rows(self, parent, orders):
        if not orders:
            ctk.CTkLabel(parent, text=self.t("no_orders"), text_color=MUTED,
                         font=ctk.CTkFont(size=13)).pack(expand=True, pady=55)
            return
        for order in orders:
            row = ctk.CTkFrame(parent, fg_color="#FAFBFD", corner_radius=10)
            row.pack(fill="x", padx=18, pady=5)
            main = ctk.CTkFrame(row, fg_color="transparent")
            main.pack(fill="x", padx=14, pady=10)
            ctk.CTkLabel(main, text=order.get("reference", "—"), text_color=INK,
                         font=ctk.CTkFont(size=13, weight="bold")).pack(side="right" if self.language == "ar" else "left")
            ctk.CTkLabel(main, text=order.get("customer_name", "—"), text_color=MUTED,
                         font=ctk.CTkFont(size=12)).pack(side="right" if self.language == "ar" else "left", padx=18)
            ctk.CTkLabel(main, text=f"{order.get('total', '0.00')} EGP", text_color=INK,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left" if self.language == "ar" else "right")
            ctk.CTkLabel(main, text=self.t("status_" + order.get("status", "PENDING")), text_color=self._status_color(order.get("status")),
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="left" if self.language == "ar" else "right", padx=14)

    def _page_products(self):
        self._header(self.t("products"), self.t("products_sub"), self.t("add_product"), self._product_dialog)
        tools = ctk.CTkFrame(self.content, fg_color="transparent")
        tools.pack(fill="x", padx=34, pady=(0, 12))
        self.product_search = ctk.CTkEntry(tools, height=40, width=360, placeholder_text=self.t("product_search"))
        self.product_search.pack(side="right" if self.language == "ar" else "left")
        self.product_search.bind("<Return>", lambda _e: self._refresh_products())
        ctk.CTkButton(tools, text=self.t("search"), width=100, height=40, fg_color=NAVY,
                      command=self._refresh_products).pack(side="right" if self.language == "ar" else "left", padx=8)
        self.products_frame = ctk.CTkScrollableFrame(self.content, fg_color=BG, corner_radius=0)
        self.products_frame.pack(fill="both", expand=True, padx=28, pady=(0, 18))
        self._refresh_products()

    def _refresh_products(self):
        if not hasattr(self, "products_frame") or not self.products_frame.winfo_exists():
            return
        for child in self.products_frame.winfo_children():
            child.destroy()
        try:
            rows = self.api.products(query=self.product_search.get() if hasattr(self, "product_search") else "")
            active_rows = [row for row in rows if row.get("active", True)]
            if not active_rows:
                ctk.CTkLabel(self.products_frame, text=self.t("no_products"), text_color=MUTED).pack(pady=45)
            for product in active_rows:
                card = ctk.CTkFrame(self.products_frame, fg_color=WHITE, corner_radius=12,
                                    border_width=1, border_color="#E7EAF0")
                card.pack(fill="x", padx=5, pady=5)
                line = ctk.CTkFrame(card, fg_color="transparent")
                line.pack(fill="x", padx=15, pady=12)
                name = product.get("name_ar" if self.language == "ar" else "name_en") or product.get("name_en")
                ctk.CTkLabel(line, text=name, text_color=INK,
                             font=ctk.CTkFont(size=14, weight="bold")).pack(side="right" if self.language == "ar" else "left")
                ctk.CTkLabel(line, text=f"{product.get('price', '0.00')} EGP", text_color=NAVY,
                             font=ctk.CTkFont(size=13, weight="bold")).pack(side="right" if self.language == "ar" else "left", padx=20)
                stock = int(product.get("stock", 0))
                color = RED if stock == 0 else ORANGE if product.get("is_low_stock") else GREEN
                ctk.CTkLabel(line, text=f"{self.t('stock')}: {stock}", text_color=color,
                             font=ctk.CTkFont(size=12, weight="bold")).pack(side="right" if self.language == "ar" else "left", padx=12)
                ctk.CTkButton(line, text=self.t("edit"), width=76, height=30, fg_color=NAVY,
                              command=lambda p=product: self._product_dialog(p)).pack(side="left" if self.language == "ar" else "right", padx=4)
                ctk.CTkButton(line, text=self.t("deactivate"), width=90, height=30, fg_color=RED,
                              hover_color="#A93636", command=lambda pid=product["id"]: self._deactivate_product(pid)).pack(side="left" if self.language == "ar" else "right", padx=4)
        except APIError as exc:
            ctk.CTkLabel(self.products_frame, text=f"{self.t('api_error')}\n{exc}", text_color=RED).pack(pady=40)

    def _product_dialog(self, product=None):
        try:
            categories = self.api.categories()
        except APIError as exc:
            self._message(str(exc))
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.t("edit_product") if product else self.t("add_product"))
        dialog.geometry("520x690")
        dialog.minsize(480, 620)
        dialog.transient(self)
        dialog.grab_set()
        form = ctk.CTkScrollableFrame(dialog, fg_color=BG)
        form.pack(fill="both", expand=True, padx=14, pady=14)
        fields = {}
        specs = [("name_ar", "product_name_ar"), ("name_en", "product_name_en"),
                 ("sku", "sku"), ("barcode", "barcode"), ("price", "price"),
                 ("stock", "stock"), ("low_stock_threshold", "low_stock_threshold")]
        for key, label_key in specs:
            ctk.CTkLabel(form, text=self.t(label_key), text_color=INK).pack(anchor="e" if self.language == "ar" else "w", pady=(8, 3))
            entry = ctk.CTkEntry(form, height=38, justify="right" if self.language == "ar" else "left")
            entry.pack(fill="x")
            if product:
                entry.insert(0, str(product.get(key) if product.get(key) is not None else ""))
            elif key == "low_stock_threshold":
                entry.insert(0, "5")
            elif key == "stock":
                entry.insert(0, "0")
            fields[key] = entry
        category_labels = [self.t("no_category")] + [c.get("name_ar" if self.language == "ar" else "name_en") for c in categories if c.get("active", True)]
        category_rows = [None] + [c for c in categories if c.get("active", True)]
        ctk.CTkLabel(form, text=self.t("category"), text_color=INK).pack(anchor="e" if self.language == "ar" else "w", pady=(8, 3))
        category_menu = ctk.CTkOptionMenu(form, values=category_labels, fg_color=NAVY, button_color=NAVY_LIGHT)
        category_menu.pack(fill="x")
        selected = next((i for i, c in enumerate(category_rows) if product and c and c.get("id") == product.get("category")), 0)
        category_menu.set(category_labels[selected])
        feedback = ctk.CTkLabel(form, text="", text_color=RED, wraplength=420)
        feedback.pack(fill="x", pady=8)

        def save():
            try:
                payload = {key: fields[key].get().strip() for key, _ in specs}
                if not payload["name_ar"] or not payload["name_en"]:
                    raise ValueError(self.t("complete_fields"))
                payload["price"] = float(payload["price"])
                payload["low_stock_threshold"] = int(payload["low_stock_threshold"])
                category_id = category_rows[category_labels.index(category_menu.get())]
                payload["category"] = category_id.get("id") if category_id else None
                payload["sku"] = payload["sku"] or None
                payload["barcode"] = payload["barcode"] or None
                if product:
                    payload.pop("stock")
                    self.api.update_product(product["id"], payload)
                else:
                    payload["stock"] = int(payload["stock"])
                    self.api.create_product(payload)
                dialog.destroy()
                self._refresh_products()
                self._load_dashboard()
            except (ValueError, TypeError) as exc:
                feedback.configure(text=str(exc))
            except APIError as exc:
                feedback.configure(text=str(exc))

        ctk.CTkButton(form, text=self.t("save"), height=42, fg_color=NAVY, command=save).pack(fill="x", pady=(10, 16))

    def _deactivate_product(self, product_id):
        if not self._ask_yes_no(self.t("deactivate_confirm")):
            return
        try:
            self.api.deactivate_product(product_id)
            self._refresh_products()
            self._load_dashboard()
        except APIError as exc:
            self._message(str(exc))

    def _ask_yes_no(self, message):
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.t("confirm"))
        dialog.geometry("390x170")
        dialog.transient(self)
        dialog.grab_set()
        result = {"value": False}
        ctk.CTkLabel(dialog, text=message, text_color=INK, wraplength=330).pack(expand=True, padx=20, pady=15)
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(pady=(0, 18))
        ctk.CTkButton(buttons, text=self.t("confirm"), fg_color=RED,
                      command=lambda: (result.update(value=True), dialog.destroy())).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text=self.t("back"), fg_color=NAVY, command=dialog.destroy).pack(side="left", padx=6)
        self.wait_window(dialog)
        return result["value"]

    def _page_categories(self):
        self._header(self.t("categories"), self.t("categories_sub"), self.t("add_category"), self._category_dialog)
        self.categories_frame = ctk.CTkScrollableFrame(self.content, fg_color=BG, corner_radius=0)
        self.categories_frame.pack(fill="both", expand=True, padx=34, pady=(0, 20))
        try:
            rows = self.api.categories()
            for category in rows:
                card = ctk.CTkFrame(self.categories_frame, fg_color=WHITE, corner_radius=10)
                card.pack(fill="x", pady=5)
                label = category.get("name_ar" if self.language == "ar" else "name_en")
                ctk.CTkLabel(card, text=f"{label}   •   {category.get('product_count', 0)} {self.t('products')}",
                             text_color=INK, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="e" if self.language == "ar" else "w", padx=18, pady=14)
        except APIError as exc:
            ctk.CTkLabel(self.categories_frame, text=str(exc), text_color=RED).pack(pady=30)

    def _category_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.t("add_category"))
        dialog.geometry("420x310")
        dialog.transient(self)
        dialog.grab_set()
        panel = ctk.CTkFrame(dialog, fg_color=BG)
        panel.pack(fill="both", expand=True, padx=18, pady=18)
        entries = {}
        for key in ("category_name_ar", "category_name_en"):
            ctk.CTkLabel(panel, text=self.t(key), text_color=INK).pack(anchor="e" if self.language == "ar" else "w", pady=(8, 3))
            entry = ctk.CTkEntry(panel, height=38)
            entry.pack(fill="x")
            entries[key] = entry
        feedback = ctk.CTkLabel(panel, text="", text_color=RED)
        feedback.pack(pady=6)
        def save():
            ar, en = entries["category_name_ar"].get().strip(), entries["category_name_en"].get().strip()
            if not ar or not en:
                feedback.configure(text=self.t("complete_fields")); return
            try:
                self.api.create_category(ar, en)
                dialog.destroy()
                self._render_page("categories")
            except APIError as exc:
                feedback.configure(text=str(exc))
        ctk.CTkButton(panel, text=self.t("save"), fg_color=NAVY, command=save).pack(fill="x", pady=8)

    def _page_inventory(self):
        self._header(self.t("inventory"), self.t("inventory_sub"), self.t("refresh"), lambda: self._render_page("inventory"))
        frame = ctk.CTkScrollableFrame(self.content, fg_color=BG)
        frame.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        try:
            products = self.api.products()
            for product in products:
                if not product.get("active", True):
                    continue
                row = ctk.CTkFrame(frame, fg_color=WHITE, corner_radius=10)
                row.pack(fill="x", pady=5)
                name = product.get("name_ar" if self.language == "ar" else "name_en")
                ctk.CTkLabel(row, text=f"{name}   •   {self.t('stock')}: {product.get('stock', 0)}",
                             text_color=INK, font=ctk.CTkFont(size=13, weight="bold")).pack(side="right" if self.language == "ar" else "left", padx=14, pady=13)
                ctk.CTkButton(row, text=self.t("adjust_stock"), width=120, fg_color=NAVY,
                              command=lambda p=product: self._stock_dialog(p)).pack(side="left" if self.language == "ar" else "right", padx=12, pady=8)
        except APIError as exc:
            ctk.CTkLabel(frame, text=str(exc), text_color=RED).pack(pady=30)

    def _stock_dialog(self, product):
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.t("adjust_stock"))
        dialog.geometry("420x360")
        dialog.transient(self); dialog.grab_set()
        panel = ctk.CTkFrame(dialog, fg_color=BG); panel.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(panel, text=product.get("name_ar" if self.language == "ar" else "name_en"), text_color=INK,
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=8)
        ctk.CTkLabel(panel, text=f"{self.t('current_stock')}: {product.get('stock', 0)}", text_color=MUTED).pack()
        delta = ctk.CTkEntry(panel, placeholder_text=self.t("stock_delta"), height=40); delta.pack(fill="x", pady=8)
        reason = ctk.CTkOptionMenu(panel, values=["RESTOCK", "CORRECTION", "DAMAGE"], fg_color=NAVY, button_color=NAVY_LIGHT); reason.pack(fill="x", pady=6)
        note = ctk.CTkEntry(panel, placeholder_text=self.t("note"), height=40); note.pack(fill="x", pady=6)
        feedback = ctk.CTkLabel(panel, text="", text_color=RED); feedback.pack(pady=5)
        def save():
            try:
                value = int(delta.get())
                if value == 0: raise ValueError(self.t("stock_delta_error"))
                self.api.adjust_stock(product["id"], value, reason.get(), note.get().strip())
                dialog.destroy(); self._render_page("inventory"); self._load_dashboard()
            except (ValueError, APIError) as exc:
                feedback.configure(text=str(exc))
        ctk.CTkButton(panel, text=self.t("save"), fg_color=NAVY, command=save).pack(fill="x", pady=8)

    def _page_reports(self):
        self._header(self.t("reports"), self.t("reports_sub"), self.t("refresh"), self._refresh_reports)
        self.reports_frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self.reports_frame.pack(fill="both", expand=True, padx=30, pady=12)
        self._refresh_reports()

    def _refresh_reports(self):
        if not hasattr(self, "reports_frame") or not self.reports_frame.winfo_exists(): return
        for child in self.reports_frame.winfo_children(): child.destroy()
        try:
            data = self.api.dashboard(); today = data.get("today", {}); products = data.get("products", {}); orders = data.get("orders", {})
            cards = [(self.t("today_sales"), f"{today.get('sales', '0.00')} EGP"),
                     (self.t("today_orders"), today.get("orders", 0)),
                     (self.t("active_products"), products.get("available", 0)),
                     (self.t("low_stock"), products.get("low_stock", 0)),
                     (self.t("completed_orders"), orders.get("COMPLETED", 0)),
                     (self.t("pending_orders"), orders.get("PENDING", 0))]
            for index, (label, value) in enumerate(cards):
                self.reports_frame.grid_columnconfigure(index % 3, weight=1)
                self._stat_card(self.reports_frame, label, value, self.t("report_live_hint")).grid(row=index // 3, column=index % 3, sticky="nsew", padx=7, pady=7, ipady=8)
        except APIError as exc:
            ctk.CTkLabel(self.reports_frame, text=str(exc), text_color=RED).pack(pady=30)

    def _page_orders(self):
        self._header(self.t("orders"), self.t("overview_sub"), self.t("refresh"), self._refresh_orders)
        tools = ctk.CTkFrame(self.content, fg_color="transparent")
        tools.pack(fill="x", padx=34, pady=(0, 14))
        self.order_search = ctk.CTkEntry(tools, width=340, height=40, placeholder_text=self.t("search"),
                                         justify="right" if self.language == "ar" else "left")
        self.order_search.pack(side="right" if self.language == "ar" else "left")
        self.order_search.bind("<Return>", lambda _e: self._refresh_orders())
        self.status_filter = ctk.CTkOptionMenu(tools, width=170, height=40,
            values=[self.t("all_statuses"), "PENDING", "ACCEPTED", "PREPARING", "READY", "COMPLETED", "REJECTED", "CANCELLED"],
            command=lambda _v: self._refresh_orders(), fg_color=NAVY, button_color=NAVY_LIGHT)
        self.status_filter.set(self.t("all_statuses"))
        self.status_filter.pack(side="right" if self.language == "ar" else "left", padx=10)
        self.orders_frame = ctk.CTkScrollableFrame(self.content, fg_color=BG, corner_radius=0)
        self.orders_frame.pack(fill="both", expand=True, padx=28, pady=(0, 20))
        self._refresh_orders()

    def _refresh_orders(self):
        if not hasattr(self, "orders_frame") or not self.orders_frame.winfo_exists():
            return
        for child in self.orders_frame.winfo_children():
            child.destroy()
        status = self.status_filter.get() if hasattr(self, "status_filter") else ""
        if status == self.t("all_statuses"):
            status = ""
        try:
            rows = self.api.orders(status=status, query=self.order_search.get() if hasattr(self, "order_search") else "")
            self.orders_cache = rows
            if not rows:
                ctk.CTkLabel(self.orders_frame, text=self.t("no_orders"), text_color=MUTED).pack(pady=50)
            for order in rows:
                self._order_card(order)
        except APIError:
            ctk.CTkLabel(self.orders_frame, text=self.t("api_error"), text_color=RED).pack(pady=50)

    def _order_card(self, order):
        card = ctk.CTkFrame(self.orders_frame, fg_color=WHITE, corner_radius=13,
                            border_width=1, border_color="#E7EAF0")
        card.pack(fill="x", padx=6, pady=6)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=17, pady=(13, 7))
        ctk.CTkLabel(top, text=order.get("reference", "—"), text_color=INK,
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="right" if self.language == "ar" else "left")
        ctk.CTkLabel(top, text=self.t("status_" + order.get("status", "PENDING")),
                     text_color=self._status_color(order.get("status")),
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left" if self.language == "ar" else "right")
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(fill="x", padx=17, pady=3)
        customer = f"{order.get('customer_name', '—')}   •   {order.get('customer_phone', '')}"
        ctk.CTkLabel(info, text=customer, text_color=INK, font=ctk.CTkFont(size=12)).pack(side="right" if self.language == "ar" else "left")
        ctk.CTkLabel(info, text=f"{order.get('total', '0.00')} EGP", text_color=INK,
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left" if self.language == "ar" else "right")
        items = order.get("items", [])
        item_summary = "  |  ".join(f"{x.get('product_name_ar' if self.language == 'ar' else 'product_name_en', '')} × {x.get('quantity', 0)}" for x in items[:5])
        ctk.CTkLabel(card, text=item_summary or "—", text_color=MUTED, anchor="e" if self.language == "ar" else "w",
                     font=ctk.CTkFont(size=11)).pack(fill="x", padx=17, pady=(5, 8))
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 12))
        self._order_actions(actions, order)

    def _order_actions(self, parent, order):
        status = order.get("status")
        order_id = order.get("id")
        actions = []
        if status == "PENDING":
            actions = [("accept", "ACCEPTED", GREEN), ("reject", "REJECTED", RED)]
        elif status == "ACCEPTED":
            actions = [("prepare", "PREPARING", NAVY)]
        elif status == "PREPARING":
            actions = [("ready", "READY", GREEN)]
        elif status == "READY":
            actions = [("complete", "COMPLETED", GREEN)]
        if status in ("PENDING", "ACCEPTED", "PREPARING", "READY"):
            actions.append(("cancel", "CANCELLED", RED))
        for label, new_status, color in actions:
            ctk.CTkButton(parent, text=self.t(label), height=32, width=112, corner_radius=8,
                          fg_color=color, hover_color=color, command=lambda oid=order_id, st=new_status: self._change_status(oid, st)).pack(side="right" if self.language == "ar" else "left", padx=4)
        if order.get("payment_status") == "AWAITING_VERIFICATION":
            ctk.CTkButton(parent, text=self.t("confirm_payment"), height=32, width=145, corner_radius=8,
                          fg_color="#EAF1FA", hover_color="#DDE8F5", text_color=NAVY,
                          command=lambda oid=order_id: self._confirm_payment(oid)).pack(side="left" if self.language == "ar" else "right", padx=4)

    def _change_status(self, order_id, status):
        reason = ""
        if status in ("REJECTED", "CANCELLED"):
            reason = self._ask_reason()
            if reason is None:
                return
        try:
            self.api.change_order_status(order_id, status, reason)
            self._refresh_orders()
            self._load_dashboard()
        except APIError as exc:
            self._message(str(exc))

    def _confirm_payment(self, order_id):
        try:
            self.api.confirm_payment(order_id)
            self._refresh_orders()
        except APIError as exc:
            self._message(str(exc))

    def _ask_reason(self):
        dialog = ctk.CTkInputDialog(text=self.t("reason_hint"), title=self.t("reason_title"))
        value = dialog.get_input()
        if value is None:
            return None
        if not value.strip():
            self._message(self.t("reason_title"))
            return None
        return value.strip()

    def _message(self, message):
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.t("app_title"))
        dialog.geometry("390x170")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=message, wraplength=330, text_color=INK).pack(expand=True, padx=24, pady=20)
        ctk.CTkButton(dialog, text=self.t("confirm"), command=dialog.destroy, fg_color=NAVY).pack(pady=(0, 18))

    def _page_server(self):
        self._header(self.t("server_title"), self.t("server_sub"), self.t("refresh"), self._refresh_server)
        wrap = ctk.CTkFrame(self.content, fg_color=WHITE, corner_radius=14, border_width=1, border_color="#E7EAF0")
        wrap.pack(fill="x", padx=40, pady=5)
        self.server_status = ctk.CTkLabel(wrap, text=self.t("loading"), text_color=MUTED, font=ctk.CTkFont(size=16))
        self.server_status.pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(24, 16))
        ctk.CTkLabel(wrap, text=self.t("api_address") + ":  http://127.0.0.1:8000", text_color=INK,
                     font=ctk.CTkFont(size=13)).pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(0, 24))
        self._refresh_server()

    def _refresh_server(self):
        if not hasattr(self, "server_status") or not self.server_status.winfo_exists():
            return
        try:
            result = self.api.health()
            good = result.get("status") == "ok" and result.get("database") == "ok"
            label = self.t("connected") if good else self.t("disconnected")
            self.server_status.configure(text=f"●  {self.t('api_status')}: {label}     |     {self.t('database')}: {label}",
                                         text_color=GREEN if good else RED)
        except APIError:
            self.server_status.configure(text=f"●  {self.t('api_status')}: {self.t('disconnected')}", text_color=RED)

    def _page_settings(self):
        self._header(self.t("settings_title"), self.t("settings_sub"))
        panel = ctk.CTkFrame(self.content, fg_color=WHITE, corner_radius=14, border_width=1, border_color="#E7EAF0")
        panel.pack(fill="x", padx=40, pady=5)
        ctk.CTkLabel(panel, text=self.t("brand_note"), text_color=MUTED, font=ctk.CTkFont(size=12)).pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(22, 3))
        ctk.CTkLabel(panel, text="الشامي  |  Elshamii", text_color=INK, font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(0, 18))
        ctk.CTkFrame(panel, height=1, fg_color="#E9EDF2").pack(fill="x", padx=24, pady=5)
        ctk.CTkLabel(panel, text=self.t("logo"), text_color=INK, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(18, 7))
        logo_row = ctk.CTkFrame(panel, fg_color="transparent")
        logo_row.pack(fill="x", padx=24)
        self.logo_path_label = ctk.CTkLabel(logo_row, text=self.config_data.get("logo_path", self.t("logo_hint")), text_color=MUTED)
        self.logo_path_label.pack(side="right" if self.language == "ar" else "left", padx=8)
        ctk.CTkButton(logo_row, text=self.t("choose_logo"), width=130, fg_color=NAVY,
                      command=self._choose_logo).pack(side="left" if self.language == "ar" else "right")
        ctk.CTkLabel(panel, text=self.t("instagram"), text_color=INK, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(24, 7))
        self.instagram_entry = ctk.CTkEntry(panel, height=42, placeholder_text="https://instagram.com/yourstore",
                                             justify="left")
        self.instagram_entry.pack(fill="x", padx=24)
        self.instagram_entry.insert(0, self.config_data.get("instagram_url", ""))
        ctk.CTkLabel(panel, text=self.t("language"), text_color=INK, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(22, 7))
        lang = ctk.CTkSegmentedButton(panel, values=["العربية", "English"], command=self._save_language)
        lang.set("العربية" if self.language == "ar" else "English")
        lang.pack(anchor="e" if self.language == "ar" else "w", padx=24)
        self.settings_feedback = ctk.CTkLabel(panel, text="", text_color=GREEN, font=ctk.CTkFont(size=12))
        self.settings_feedback.pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(18, 0))
        ctk.CTkButton(panel, text=self.t("save"), height=42, width=170, fg_color=NAVY,
                      hover_color=NAVY_LIGHT, command=self._save_settings).pack(anchor="e" if self.language == "ar" else "w", padx=24, pady=(10, 20))
        ctk.CTkLabel(self.content, text=self.t("made_by"), text_color=MUTED,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(pady=24)

    def _choose_logo(self):
        path = filedialog.askopenfilename(title=self.t("choose_logo"),
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")])
        if not path:
            return
        source = Path(path)
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp") or source.stat().st_size > 5 * 1024 * 1024:
            self._message("Choose a PNG, JPG or WEBP image under 5 MB.")
            return
        destination_dir = data_dir() / "branding"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / ("store_logo" + source.suffix.lower())
        shutil.copy2(source, destination)
        self.config_data["logo_path"] = str(destination)
        self.logo_path_label.configure(text=destination.name)

    def _save_language(self, value):
        self.language = "ar" if value == "العربية" else "en"
        self.config_data["language"] = self.language
        self._save_config()
        page = self.current_page
        self._show_shell()
        self._render_page(page)

    def _save_settings(self):
        url = self.instagram_entry.get().strip()
        if url and not (url.startswith("https://www.instagram.com/") or url.startswith("https://instagram.com/")):
            self.settings_feedback.configure(text="Enter a valid Instagram profile URL.", text_color=RED)
            return
        self.config_data["instagram_url"] = url
        self.config_data["language"] = self.language
        self._save_config()
        self.settings_feedback.configure(text=self.t("saved"), text_color=GREEN)

    @staticmethod
    def _status_color(status):
        return {"PENDING": ORANGE, "ACCEPTED": "#3975B8", "PREPARING": "#3975B8",
                "READY": GREEN, "COMPLETED": GREEN, "REJECTED": RED, "CANCELLED": MUTED}.get(status, MUTED)

    def _logout(self):
        try:
            self.api.logout()
        except APIError:
            self.api.set_token(None)
        self.token = None
        self.username = ""
        self.current_page = "dashboard"
        self._show_login()
