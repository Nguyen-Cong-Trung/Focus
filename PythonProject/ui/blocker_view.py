from ui.dropdown import FocusDropdown
from ui.design import MaterialFrame
from ui.panels import fit_wrap
from ui.design import MaterialButton
from utils.constants import SEPARATOR_COLOR
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from utils.constants import BG_PRIMARY, BG_CARD, ACCENT_FOCUS, ACCENT_DANGER, HOVER_BG, INPUT_BG, INPUT_BTN_COLOR, INPUT_BTN_HOVER, TEXT_SECONDARY, TEXT_PRIMARY, ACCENT_HOVER_DARK
from core.site_blocker import SiteBlocker
from core.app_blocker import AppBlocker
from data.database import DatabaseManager
from data.models import BlockedItem

class BlockerView(ctk.CTkFrame):
    def __init__(self, parent, site_blocker: SiteBlocker, app_blocker: AppBlocker, db: DatabaseManager):
        super().__init__(parent, fg_color=BG_PRIMARY)
        self.site_blocker = site_blocker
        self.app_blocker = app_blocker
        self.db = db

        from ui.panels import PageHeader, surface, label, rule
        from ui.design import nav_icon
        from utils.constants import ICE
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        header = PageHeader(self, "ATTENTION CONTROL", "Distraction Blocker",
                            "Build a quieter workspace. Keep distractions outside your focus sessions.")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 22))

        context = surface(self)
        context.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 18))
        context.grid_columnconfigure(1, weight=1)
        label(context, "", image=nav_icon('blocker')).grid(row=0, column=0, rowspan=2, padx=(22, 16), pady=20)
        label(context, "EDITING BLOCKLIST", 10, TEXT_SECONDARY, True).grid(row=0, column=1, sticky="w", pady=(16, 0))
        self.mode_var = ctk.StringVar(value="Default")
        self.mode_dropdown = FocusDropdown(context, values=["Default"], variable=self.mode_var,
            command=self._on_mode_changed, width=190, height=32, fg_color=BG_CARD,
            button_color=BG_CARD, button_hover_color=HOVER_BG, text_color=TEXT_PRIMARY,
            font=("Inter", 15, "bold"), corner_radius=6, dynamic_resizing=False)
        self.mode_dropdown.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 16))
        admin = self.site_blocker.is_admin()
        status = ctk.CTkFrame(context, fg_color="transparent")
        status.grid(row=0, column=2, rowspan=2, sticky="e", padx=22, pady=16)
        label(status, "Website access ready" if admin else "Website access limited", 12, ICE, True).pack(anchor="e")
        label(status, "Administrator permissions enabled" if admin else "Run as administrator to block sites", 11, TEXT_SECONDARY).pack(anchor="e", pady=(3, 0))
        self._context_narrow = None
        def layout_context(event):
            narrow = event.width < 680
            if self._context_narrow == narrow:
                return
            self._context_narrow = narrow
            status.grid_configure(row=2 if narrow else 0, column=0 if narrow else 2,
                                  columnspan=3 if narrow else 1, rowspan=1 if narrow else 2,
                                  sticky="w" if narrow else "e", pady=(0, 16) if narrow else 16)
        context.bind("<Configure>", layout_context)

        library = surface(self)
        library.grid(row=2, column=0, sticky="nsew", padx=28, pady=(0, 16))
        library.grid_columnconfigure(0, weight=1)
        library.grid_rowconfigure(2, weight=1)
        self.tabs_frame = ctk.CTkFrame(library, fg_color="transparent")
        self.tabs_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 14))
        self.btn_tab_web = ctk.CTkButton(self.tabs_frame, text="Websites", width=135, height=36,
            font=("Inter", 13, "bold"), corner_radius=8, command=lambda: self._switch_tab("web"))
        self.btn_tab_web.pack(side="left", padx=(0, 6))
        self.btn_tab_app = ctk.CTkButton(self.tabs_frame, text="Applications", width=145, height=36,
            font=("Inter", 13, "bold"), corner_radius=8, command=lambda: self._switch_tab("app"))
        self.btn_tab_app.pack(side="left")
        self.list_count = label(self.tabs_frame, "", 11, TEXT_SECONDARY)
        self.list_count.pack(side="right")
        rule(library).grid(row=1, column=0, sticky="ew", padx=20)
        self.content_frame = ctk.CTkFrame(library, fg_color="transparent")
        self.content_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(16, 12))
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.tab_web = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_app = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self._setup_websites_tab(self.tab_web)
        self._setup_apps_tab(self.tab_app)
        self._active_tab = "web"
        self._switch_tab("web")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)
        label(footer, "Need to regain access?", 12, TEXT_SECONDARY).grid(row=0, column=0, sticky="w")
        self.unblock_btn = ctk.CTkButton(footer, text="Unblock everything", width=164, height=34,
            fg_color="transparent", border_width=1, border_color=SEPARATOR_COLOR,
            text_color=TEXT_SECONDARY, hover_color=HOVER_BG, font=("Inter", 12),
            command=self._emergency_unblock)
        self.unblock_btn.grid(row=0, column=1, sticky="e")
        self._refresh_list()

    def _switch_tab(self, tab_name: str):
        self._active_tab = tab_name
        if hasattr(self, "list_count"):
            items = self.db.get_blocked_items("website" if tab_name == "web" else "app")
            self.list_count.configure(text=f"{sum(item.enabled for item in items)} enabled  /  {len(items)} total")
        if tab_name == "web":
            self.btn_tab_web.configure(fg_color=ACCENT_FOCUS, text_color="#ffffff")
            self.btn_tab_app.configure(fg_color="transparent", text_color=TEXT_SECONDARY)
            self.tab_app.grid_forget()
            self.tab_web.grid(row=0, column=0, sticky="nsew")
        else:
            self.btn_tab_app.configure(fg_color=ACCENT_FOCUS, text_color="#ffffff")
            self.btn_tab_web.configure(fg_color="transparent", text_color=TEXT_SECONDARY)
            self.tab_web.grid_forget()
            self.tab_app.grid(row=0, column=0, sticky="nsew")

    def _on_mode_changed(self, new_mode: str):
        if hasattr(self, 'on_mode_selected') and self.on_mode_selected:
            self.on_mode_selected(new_mode)
            
    def _setup_websites_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # Add entry
        add_frame = ctk.CTkFrame(tab, fg_color="transparent")
        add_frame.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        add_frame.grid_columnconfigure(0, weight=1)
        
        self.web_entry = ctk.CTkEntry(
            add_frame, placeholder_text="Enter a domain, e.g. youtube.com",
            fg_color=INPUT_BG, border_color=SEPARATOR_COLOR, border_width=1, 
            height=45, corner_radius=8, font=("Inter", 13)
        )
        self.web_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        add_btn = MaterialButton(
            add_frame, text="Add website", command=self._add_website, 
            width=120, height=45, corner_radius=12, font=("Inter", 15, "bold"),
            fg_color=ACCENT_FOCUS, hover_color=ACCENT_HOVER_DARK
        )
        add_btn.grid(row=0, column=1)

        # List
        self.web_list_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.web_list_frame.grid(row=1, column=0, sticky="nsew")

    def _setup_apps_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        # Add entry
        add_frame = ctk.CTkFrame(tab, fg_color="transparent")
        add_frame.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        add_frame.grid_columnconfigure(0, weight=1)
        
        self.app_entry = ctk.CTkEntry(
            add_frame, placeholder_text="Enter an application, e.g. Discord.exe",
            fg_color=INPUT_BG, border_color=SEPARATOR_COLOR, border_width=1, 
            height=45, corner_radius=8, font=("Inter", 13)
        )
        self.app_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        add_btn = MaterialButton(
            add_frame, text="Add app", command=self._add_app, 
            width=120, height=45, corner_radius=12, font=("Inter", 15, "bold"),
            fg_color=ACCENT_FOCUS, hover_color=ACCENT_HOVER_DARK
        )
        add_btn.grid(row=0, column=1)

        # List
        self.app_list_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.app_list_frame.grid(row=1, column=0, sticky="nsew")

    def _refresh_list(self):
        # Clear existing
        for widget in self.web_list_frame.winfo_children():
            widget.destroy()
        for widget in self.app_list_frame.winfo_children():
            widget.destroy()

        from ui.panels import label
        for kind, frame in (("website", self.web_list_frame), ("app", self.app_list_frame)):
            items = self.db.get_blocked_items(kind)
            if not items:
                empty = ctk.CTkFrame(frame, fg_color="transparent")
                empty.pack(fill="both", expand=True, pady=35)
                label(empty, "A clean slate.", 20, bold=True).pack()
                label(empty, "Add a website above." if kind == "website" else "Add an application above.",
                      13, TEXT_SECONDARY).pack(pady=(6, 0))
            for item in items:
                self._create_item_row(frame, item)
        self._update_count()

    def _update_count(self):
        kind = "website" if self._active_tab == "web" else "app"
        items = self.db.get_blocked_items(kind)
        self.list_count.configure(text=f"{sum(item.enabled for item in items)} enabled  /  {len(items)} total")

    def _create_item_row(self, parent_frame, item: BlockedItem):
        from ui.panels import label, rule
        from ui.design import nav_icon
        row = ctk.CTkFrame(parent_frame, fg_color="transparent", corner_radius=0)
        row.pack(fill="x")
        row.grid_columnconfigure(1, weight=1)
        icon = ctk.CTkFrame(row, width=38, height=38, fg_color=INPUT_BG, corner_radius=9)
        icon.grid(row=0, column=0, rowspan=2, padx=(2, 14), pady=13)
        icon.grid_propagate(False)
        label(icon, "", image=nav_icon('blocker' if item.item_type == 'website' else 'customizer')).place(relx=.5, rely=.5, anchor="center")
        name = label(row, item.value, 13, bold=True)
        name.grid(row=0, column=1, sticky="w", pady=(13, 0))
        label(row, "WEBSITE" if item.item_type == "website" else "APPLICATION", 9, TEXT_SECONDARY).grid(row=1, column=1, sticky="w", pady=(0, 13))
        switch_var = ctk.StringVar(value="on" if item.enabled else "off")
        ctk.CTkSwitch(row, text="", width=38, switch_width=34, switch_height=18,
            variable=switch_var, onvalue="on", offvalue="off", progress_color=ACCENT_FOCUS,
            command=lambda i=item.id, v=switch_var: self._toggle_item(i, v.get() == "on")).grid(row=0, column=2, rowspan=2, padx=(12, 20))
        ctk.CTkButton(row, text="Remove", width=68, height=30, fg_color="transparent",
            hover_color=HOVER_BG, text_color=TEXT_SECONDARY, font=("Inter", 11),
            command=lambda i=item.id: self._delete_item(i)).grid(row=0, column=3, rowspan=2, padx=(0, 2))
        rule(row).grid(row=2, column=0, columnspan=4, sticky="ew")
        row.bind("<Configure>", lambda e: fit_wrap(name,max(100,e.width-220)))

    def _add_website(self):
        self._add_item(self.web_entry, 'website')

    def _add_app(self):
        self._add_item(self.app_entry, 'app')

    def _add_item(self, entry, kind):
        app = self.winfo_toplevel()
        if not app.allow_blocklist_edit(): return
        try:
            self.db.add_blocked_item(BlockedItem(item_type=kind,value=entry.get().strip()))
        except (ValueError, OSError) as exc:
            CTkMessagebox(title='Could not add item',message=str(exc),icon='cancel')
            return
        entry.delete(0,'end')
        self._refresh_list()
        app.blocklist_changed()

    def _delete_item(self, item_id):
        app = self.winfo_toplevel()
        if not app.allow_blocklist_edit(): return
        self.db.delete_blocked_item(item_id)
        self._refresh_list()
        app.blocklist_changed()

    def _toggle_item(self, item_id, enabled):
        app = self.winfo_toplevel()
        if not app.allow_blocklist_edit():
            self._refresh_list()
            return
        self.db.toggle_blocked_item(item_id,enabled)
        self._update_count()
        app.blocklist_changed()

    def _apply_blocking(self):
        self.winfo_toplevel().apply_blocking()

    def _emergency_unblock(self):
        self.winfo_toplevel().emergency_unblock()

    def get_enabled_sites(self) -> list[str]:
        items = self.db.get_blocked_items("website")
        return [item.value for item in items if item.enabled]

    def get_enabled_apps(self) -> list[str]:
        items = self.db.get_blocked_items("app")
        return [item.value for item in items if item.enabled]
