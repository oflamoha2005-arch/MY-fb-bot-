import os
import sys
import json
import csv
import threading
import time
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox, filedialog

# Support UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    BASE_DIR, LEADS_FILE, HISTORY_FILE, TEMPLATES_FILE, PROFILES_DIR, 
    ACCOUNTS_FILE, REPLY_TEMPLATES_FILE, VIRAL_POSTS_FILE, TIER1_LEADS_FILE, 
    FRIEND_REQUESTS_FILE, DEFAULT_TIER1_LOCATIONS, KEYWORDS_FILE, SPY_HISTORY_FILE,
    SCRAPED_POSTS_FILE, ACCOUNTS_HEALTH_FILE
)
from utils import (
    load_leads, load_history, get_message_template,
    parse_spintax, console, get_reply_templates, save_reply_templates,
    load_accounts_health, get_account_health
)
from browser import FacebookBrowser, CheckpointDetectedError
from scraper import PostScraper
from messenger import SafeMessenger
from auto_poster import (
    AutoPoster, get_story_template, get_groups_list, GROUPS_FILE, POSTS_FILE,
    run_multi_account_poster, clear_poster_history, is_already_posted
)
from hybrid_engine import HybridCampaignEngine
from account_warmer import AccountWarmer
from competitor_spy import (
    ViralSpyEngine, load_keywords, is_group_on_cooldown, is_group_processed,
    load_scraped_posts_history, is_post_scraped
)
from country_filter import CountryLeadFilter
from friend_connector import FriendConnector, load_friend_history
from daily_orchestrator import DailyMasterOrchestrator
from telegram_notifier import (
    load_telegram_config, save_telegram_config,
    test_telegram_connection, is_telegram_configured
)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def get_saved_accounts() -> list[str]:
    """قراءة قائمة أسماء الحسابات المسجلة"""
    default_accounts = ["account_1", "account_2", "account_3"]
    if not ACCOUNTS_FILE.exists():
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_accounts, f, indent=2)
        return default_accounts
    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            accs = json.load(f)
            return accs if accs else default_accounts
    except Exception:
        return default_accounts

def save_accounts(accounts: list[str]):
    """حفظ قائمة الحسابات"""
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=2)

class FacebookBotGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Group Facebook Bot - Multi-Account & Control Dashboard")
        self.geometry("1150x740")
        self.minsize(1000, 650)

        # Multi-Account list
        self.accounts = get_saved_accounts()
        self.current_account = self.accounts[0] if self.accounts else "account_1"

        # Worker thread & Bot reference
        self.worker_thread = None
        self.active_bot = None
        self.active_browser = None
        self.is_running = False

        # Grid layout (1x2)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.setup_sidebar()
        self.setup_views()

        # Show default view (Daily Master Task)
        self.show_view("daily")

    def setup_sidebar(self):
        """القائمة الجانبية مع نظام إدارة الحسابات المتعددة"""
        self.sidebar_frame = ctk.CTkFrame(self, width=230, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(14, weight=1)

        # Logo & App Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="🤖 Group Bot", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 2))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Multi-Account Marketing", 
            font=ctk.CTkFont(size=12), 
            text_color="#339af0"
        )
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15))

        # --- MULTI-ACCOUNT SELECTOR SECTION ---
        acc_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="#18181b", corner_radius=8)
        acc_frame.grid(row=2, column=0, padx=12, pady=(0, 15), sticky="ew")

        lbl_acc = ctk.CTkLabel(acc_frame, text="Active Account:", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray")
        lbl_acc.pack(anchor="w", padx=10, pady=(6, 2))

        self.combo_accounts = ctk.CTkOptionMenu(
            acc_frame, 
            values=self.accounts,
            command=self.on_account_changed,
            height=30
        )
        self.combo_accounts.set(self.current_account)
        self.combo_accounts.pack(fill="x", padx=10, pady=(0, 6))

        # Add Account button
        btn_add_acc = ctk.CTkButton(
            acc_frame, text="+ Add New Account", 
            command=self.add_new_account, 
            height=24, fg_color="#343a40", hover_color="#495057", font=ctk.CTkFont(size=11)
        )
        btn_add_acc.pack(fill="x", padx=10, pady=(0, 8))

        # Navigation Buttons
        self.btn_daily = ctk.CTkButton(
            self.sidebar_frame, text="⚡ Daily Master Task", 
            command=lambda: self.show_view("daily"),
            height=35, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#f59f00", hover_color="#d97706", text_color="#1a1500"
        )
        self.btn_daily.grid(row=3, column=0, padx=12, pady=(0, 6), sticky="ew")

        self.btn_poster = ctk.CTkButton(
            self.sidebar_frame, text="📢 Auto-Poster", 
            command=lambda: self.show_view("poster"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_poster.grid(row=4, column=0, padx=12, pady=3, sticky="ew")

        self.btn_scraper = ctk.CTkButton(
            self.sidebar_frame, text="🔍 Comment Scraper", 
            command=lambda: self.show_view("scraper"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_scraper.grid(row=5, column=0, padx=12, pady=3, sticky="ew")

        self.btn_messenger = ctk.CTkButton(
            self.sidebar_frame, text="💬 Direct Messenger", 
            command=lambda: self.show_view("messenger"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_messenger.grid(row=6, column=0, padx=12, pady=3, sticky="ew")

        self.btn_templates = ctk.CTkButton(
            self.sidebar_frame, text="📝 Templates & Copy", 
            command=lambda: self.show_view("templates"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_templates.grid(row=7, column=0, padx=12, pady=3, sticky="ew")

        self.btn_leads = ctk.CTkButton(
            self.sidebar_frame, text="📊 Leads Database", 
            command=lambda: self.show_view("leads"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_leads.grid(row=8, column=0, padx=12, pady=3, sticky="ew")

        self.btn_warmer = ctk.CTkButton(
            self.sidebar_frame, text="🔥 Account Warmer", 
            command=lambda: self.show_view("warmer"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#e8590c", hover_color="#d9480f"
        )
        self.btn_warmer.grid(row=9, column=0, padx=12, pady=3, sticky="ew")

        self.btn_spy = ctk.CTkButton(
            self.sidebar_frame, text="🔎 Viral Post Spy", 
            command=lambda: self.show_view("spy"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#9c36b5", hover_color="#862e9c"
        )
        self.btn_spy.grid(row=10, column=0, padx=12, pady=3, sticky="ew")

        self.btn_country = ctk.CTkButton(
            self.sidebar_frame, text="🌍 Tier-1 Lead Filter", 
            command=lambda: self.show_view("country"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0ca678", hover_color="#099268"
        )
        self.btn_country.grid(row=11, column=0, padx=12, pady=3, sticky="ew")

        self.btn_friends = ctk.CTkButton(
            self.sidebar_frame, text="🤝 Friend Connector", 
            command=lambda: self.show_view("friends"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#22b8cf", hover_color="#15aabf"
        )
        self.btn_friends.grid(row=12, column=0, padx=12, pady=3, sticky="ew")

        self.btn_telegram = ctk.CTkButton(
            self.sidebar_frame, text="📱 Telegram Alerts (Active)", 
            command=self.open_telegram_settings_dialog,
            fg_color="#1098ad", hover_color="#0c8599",
            height=33, font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_telegram.grid(row=14, column=0, padx=12, pady=(15, 3), sticky="ew")

        # Bottom Login Button for the selected account
        self.btn_login = ctk.CTkButton(
            self.sidebar_frame, text="🔐 Login This Account", 
            command=self.open_login_browser,
            fg_color="#2b8a3e", hover_color="#237032",
            height=36, font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_login.grid(row=15, column=0, padx=12, pady=(3, 15), sticky="ew")

    def on_account_changed(self, choice: str):
        """تغيير الحساب النشط"""
        self.current_account = choice
        self.update_status("READY", f"Switched to {self.current_account}")

    def add_new_account(self):
        """إضافة حساب جديد"""
        dialog = ctk.CTkInputDialog(text="Enter new account identifier (e.g. account_4):", title="Add Account")
        new_name = dialog.get_input()
        if new_name and new_name.strip():
            clean_name = new_name.strip().replace(" ", "_")
            if clean_name not in self.accounts:
                self.accounts.append(clean_name)
                save_accounts(self.accounts)
                self.combo_accounts.configure(values=self.accounts)
                self.combo_accounts.set(clean_name)
                self.current_account = clean_name
                messagebox.showinfo("Account Added", f"Account '{clean_name}' created successfully.\nNow click 'Login This Account' to authenticate it once!")

    def setup_views(self):
        """إنشاء شاشات العمل لكل قسم مع شريط الحالة العلوي"""
        self.main_container = ctk.CTkFrame(self, corner_radius=10)
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # --- TOP HEADER BAR WITH LIVE STATUS BADGE ---
        self.header_bar = ctk.CTkFrame(self.main_container, height=45, fg_color="transparent")
        self.header_bar.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        self.lbl_view_title = ctk.CTkLabel(
            self.header_bar, text="Dashboard", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.lbl_view_title.pack(side="left")

        # Live Status Badge (Pill)
        self.status_pill = ctk.CTkLabel(
            self.header_bar, 
            text="🟢 READY", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2b2b36", 
            corner_radius=12,
            padx=14, pady=4
        )
        self.status_pill.pack(side="right")

        # Views Container
        self.views_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.views_container.grid_rowconfigure(0, weight=1)
        self.views_container.grid_columnconfigure(0, weight=1)

        self.views = {
            "daily": self.create_daily_view(),
            "poster": self.create_poster_view(),
            "scraper": self.create_scraper_view(),
            "messenger": self.create_messenger_view(),
            "templates": self.create_templates_view(),
            "leads": self.create_leads_view(),
            "warmer": self.create_warmer_view(),
            "spy": self.create_spy_view(),
            "country": self.create_country_view(),
            "friends": self.create_friends_view()
        }

    def update_status(self, state: str, text: str = ""):
        """تحديث شارة الحالة الحية (Ready, Running, Checkpoint)"""
        def _set():
            if state == "READY":
                self.status_pill.configure(text=f"🟢 {text or 'READY'}", fg_color="#183424", text_color="#51cf66")
            elif state == "RUNNING":
                self.status_pill.configure(text=f"🔵 {text or 'RUNNING'}", fg_color="#19324d", text_color="#4dabf7")
            elif state == "CHECKPOINT":
                self.status_pill.configure(text=f"🔴 {text or 'CHECKPOINT ALERT'}", fg_color="#4d1b1b", text_color="#ff8787")
            elif state == "COOLDOWN":
                self.status_pill.configure(text=f"🟡 {text or 'COOLDOWN'}", fg_color="#4d411b", text_color="#ffd43b")
        self.after(0, _set)

    def show_view(self, view_name: str):
        """التبديل بين الشاشات"""
        titles = {
            "daily": "⚡ Daily Master Orchestrator (الروتين اليومي الشامل)",
            "poster": "📢 Facebook Groups Auto-Poster",
            "scraper": "🔍 Facebook Post Comment Scraper",
            "messenger": "💬 Direct Messenger Outreach",
            "templates": "📝 Message & Story Templates",
            "leads": "📊 Leads Database & Activity",
            "warmer": "🔥 Standalone Account Warmer",
            "spy": "🔎 Viral Content & Competitor Spy",
            "country": "🌍 Tier-1 Country & Location Lead Filter",
            "friends": "🤝 Targeted International Friend Connector"
        }
        self.lbl_view_title.configure(text=titles.get(view_name, "Dashboard"))

        for name, frame in self.views.items():
            if name == view_name:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

        # Highlight sidebar button
        special_colors = {
            "daily": "#f59f00",
            "warmer": "#e8590c",
            "spy": "#9c36b5",
            "country": "#0ca678",
            "friends": "#22b8cf"
        }
        btns = {
            "daily": self.btn_daily,
            "poster": self.btn_poster,
            "scraper": self.btn_scraper,
            "messenger": self.btn_messenger,
            "templates": self.btn_templates,
            "leads": self.btn_leads,
            "warmer": self.btn_warmer,
            "spy": self.btn_spy,
            "country": self.btn_country,
            "friends": self.btn_friends
        }
        for name, btn in btns.items():
            if name == view_name:
                if name == "daily":
                    btn.configure(fg_color="#f59f00", text_color="#1a1500")
                elif name in special_colors:
                    btn.configure(fg_color=special_colors[name], text_color="#ffffff")
                else:
                    btn.configure(fg_color=["#3B8ED0", "#1F6AA5"], text_color="#ffffff")
            else:
                if name == "daily":
                    btn.configure(fg_color="#343a40", text_color="#ffd43b")
                elif name in special_colors:
                    btn.configure(fg_color="#343a40", text_color="#ffffff")
                else:
                    btn.configure(fg_color="transparent", text_color="#ffffff")

    # ---------------- 0. DAILY MASTER VIEW ----------------
    def create_daily_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(
            frame, 
            text="⚡ Full Funnel Automation: 10m Niche Warmer ➔ Daily Scout (1 Group) ➔ Scrape & Tier-1 Filter ➔ Multi-Account Outreach (DM + Notification) & Friend Connector ➔ Group Story Posting.", 
            text_color="#fcc419", font=ctk.CTkFont(size=12, weight="bold")
        )
        desc.pack(anchor="w", padx=10, pady=(0, 6))

        # Main settings card
        box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        box.pack(fill="x", padx=10, pady=4)

        # Row 1: Scout Account & Warmer
        r1 = ctk.CTkFrame(box, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(8, 4))

        lbl_scout = ctk.CTkLabel(r1, text="Scout Account:", font=ctk.CTkFont(weight="bold"))
        lbl_scout.pack(side="left", padx=(0, 6))
        self.combo_daily_scout = ctk.CTkOptionMenu(r1, values=self.accounts, width=120)
        self.combo_daily_scout.set(self.current_account)
        self.combo_daily_scout.pack(side="left", padx=(0, 16))

        lbl_warm = ctk.CTkLabel(r1, text="Initial Warmer (min):", font=ctk.CTkFont(weight="bold"))
        lbl_warm.pack(side="left", padx=(0, 6))
        self.entry_daily_warmup = ctk.CTkEntry(r1, width=50)
        self.entry_daily_warmup.insert(0, "10")
        self.entry_daily_warmup.pack(side="left", padx=(0, 14))

        self.chk_daily_warm_all = ctk.CTkCheckBox(
            r1, text="🔥 Warm ALL Accounts", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f59f00"
        )
        self.chk_daily_warm_all.pack(side="left", padx=(0, 14))

        self.chk_daily_sandwich = ctk.CTkCheckBox(
            r1, text="🛡️ Session Sandwich (90s/60s)", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#69db7c"
        )
        self.chk_daily_sandwich.select()
        self.chk_daily_sandwich.pack(side="left")

        # Row 2: 3-Databases Engine: Target Quota & Scrape/Filter Settings
        r2 = ctk.CTkFrame(box, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(4, 4))

        lbl_quota = ctk.CTkLabel(r2, text="🎯 Target Tier-1 Quota:", font=ctk.CTkFont(weight="bold"), text_color="#51cf66")
        lbl_quota.pack(side="left", padx=(0, 4))
        self.entry_daily_quota = ctk.CTkEntry(r2, width=45)
        self.entry_daily_quota.insert(0, "15")
        self.entry_daily_quota.pack(side="left", padx=(0, 14))

        lbl_scrape = ctk.CTkLabel(r2, text="Scrape/Post:")
        lbl_scrape.pack(side="left", padx=(0, 4))
        self.entry_daily_scrape_max = ctk.CTkEntry(r2, width=45)
        self.entry_daily_scrape_max.insert(0, "25")
        self.entry_daily_scrape_max.pack(side="left", padx=(0, 14))

        lbl_filt = ctk.CTkLabel(r2, text="Filter/Post:")
        lbl_filt.pack(side="left", padx=(0, 4))
        self.entry_daily_filter_max = ctk.CTkEntry(r2, width=45)
        self.entry_daily_filter_max.insert(0, "20")
        self.entry_daily_filter_max.pack(side="left", padx=(0, 14))

        lbl_max_groups = ctk.CTkLabel(r2, text="Max Groups/Run:")
        lbl_max_groups.pack(side="left", padx=(0, 4))
        self.entry_daily_max_groups = ctk.CTkEntry(r2, width=40)
        self.entry_daily_max_groups.insert(0, "5")
        self.entry_daily_max_groups.pack(side="left")

        # Row 3: Multi-Account Outreach & Friend Requests
        r3 = ctk.CTkFrame(box, fg_color="transparent")
        r3.pack(fill="x", padx=12, pady=(4, 4))

        lbl_dms = ctk.CTkLabel(r3, text="DMs / Account:", font=ctk.CTkFont(weight="bold"))
        lbl_dms.pack(side="left", padx=(0, 6))
        self.entry_daily_dms = ctk.CTkEntry(r3, width=45)
        self.entry_daily_dms.insert(0, "4")
        self.entry_daily_dms.pack(side="left", padx=(0, 14))

        self.chk_daily_reply = ctk.CTkCheckBox(
            r3, text="❤️ Like Comment + 🔔 Notification Reply", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ff8787"
        )
        self.chk_daily_reply.select()
        self.chk_daily_reply.pack(side="left", padx=(0, 16))

        lbl_friends = ctk.CTkLabel(r3, text="Friend Requests / Account:", font=ctk.CTkFont(weight="bold"))
        lbl_friends.pack(side="left", padx=(0, 6))
        self.entry_daily_friends = ctk.CTkEntry(r3, width=45)
        self.entry_daily_friends.insert(0, "3")
        self.entry_daily_friends.pack(side="left")

        # Row 4: Group Posting Options
        r4 = ctk.CTkFrame(box, fg_color="transparent")
        r4.pack(fill="x", padx=12, pady=(4, 8))

        self.chk_daily_posting = ctk.CTkCheckBox(
            r4, text="📢 Run Group Story Posting", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffa94d"
        )
        self.chk_daily_posting.select()
        self.chk_daily_posting.pack(side="left", padx=(0, 10))

        lbl_p_acc = ctk.CTkLabel(r4, text="Groups / Account:")
        lbl_p_acc.pack(side="left", padx=(0, 4))
        self.entry_daily_posts_per_acc = ctk.CTkEntry(r4, width=45)
        self.entry_daily_posts_per_acc.insert(0, "2")
        self.entry_daily_posts_per_acc.pack(side="left", padx=(0, 16))

        lbl_img = ctk.CTkLabel(r4, text="Cover Image (Optional):")
        lbl_img.pack(side="left", padx=(0, 6))
        self.entry_daily_image = ctk.CTkEntry(r4, placeholder_text="Leave blank or select image...", width=200)
        self.entry_daily_image.pack(side="left", padx=(0, 6))

        # استعادة مسار الصورة المحفوظة مسبقاً لمزامنتها مع Auto-Poster
        cfg_img_path = DATA_DIR / "poster_config.json"
        if cfg_img_path.exists():
            try:
                with open(cfg_img_path, 'r', encoding='utf-8') as f:
                    saved_img = json.load(f).get("image_path", "")
                    if saved_img and os.path.exists(saved_img):
                        self.entry_daily_image.insert(0, saved_img)
            except Exception:
                pass

        btn_browse_daily_img = ctk.CTkButton(
            r4, text="🖼️", width=36, height=28,
            fg_color="#3b5bdb", hover_color="#364fc7",
            command=self.browse_daily_image
        )
        btn_browse_daily_img.pack(side="left", padx=(0, 4))

        def _clear_daily_image():
            self.entry_daily_image.delete(0, 'end')
            if hasattr(self, 'entry_post_image'):
                self.entry_post_image.delete(0, 'end')
            if cfg_img_path.exists():
                try:
                    with open(cfg_img_path, 'w', encoding='utf-8') as f:
                        json.dump({"image_path": ""}, f)
                except Exception:
                    pass

        btn_clear_daily_img = ctk.CTkButton(
            r4, text="❌", width=36, height=28,
            fg_color="#495057", hover_color="#343a40",
            command=_clear_daily_image
        )
        btn_clear_daily_img.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=8)

        self.btn_start_daily = ctk.CTkButton(
            btn_box, text="⚡ Start Daily Master Routine", 
            fg_color="#f59f00", hover_color="#d97706", text_color="#1a1500",
            command=self.start_daily_action, height=38, font=ctk.CTkFont(size=13, weight="bold")
        )
        self.btn_start_daily.pack(side="left", padx=(0, 12))

        self.btn_stop_daily = ctk.CTkButton(
            btn_box, text="⏹ Stop Routine", 
            fg_color="#c92a2a", hover_color="#a61e1e", 
            command=self.stop_any_action, height=38, state="disabled"
        )
        self.btn_stop_daily.pack(side="left", padx=(0, 12))

        btn_open_data = ctk.CTkButton(
            btn_box, text="📂 Open Data Folder", 
            fg_color="#343a40", hover_color="#495057", 
            command=self.open_data_folder_action, height=38
        )
        btn_open_data.pack(side="left")

        # Live Activity Log Console
        log_label = ctk.CTkLabel(frame, text="Daily Master Execution Console:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(6, 2))

        self.log_daily = ctk.CTkTextbox(frame, height=220, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_daily.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    def browse_daily_image(self):
        """اختيار صورة للبوست في الروتين اليومي وحفظها ومزامنتها مع Auto-Poster"""
        file_path = filedialog.askopenfilename(
            title="Select Book Cover or Teaser Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All files", "*.*")]
        )
        if file_path:
            self.entry_daily_image.delete(0, 'end')
            self.entry_daily_image.insert(0, file_path)
            try:
                cfg_img_path = DATA_DIR / "poster_config.json"
                with open(cfg_img_path, 'w', encoding='utf-8') as f:
                    json.dump({"image_path": file_path}, f)
                if hasattr(self, 'entry_post_image'):
                    self.entry_post_image.delete(0, 'end')
                    self.entry_post_image.insert(0, file_path)
            except Exception:
                pass

    def open_data_folder_action(self):
        """فتح مجلد البيانات في مستكشف ويندوز"""
        data_dir = BASE_DIR / "data"
        if data_dir.exists():
            os.startfile(str(data_dir))
        else:
            os.startfile(str(BASE_DIR))

    def start_daily_action(self):
        """بدء تنفيذ الروتين اليومي الشامل في مسار خلفي مستقل وبدون أي تعارض"""
        try:
            warmup_min = int(self.entry_daily_warmup.get().strip())
        except ValueError:
            warmup_min = 10

        try:
            tier1_quota = int(self.entry_daily_quota.get().strip())
        except ValueError:
            tier1_quota = 15

        try:
            max_groups = int(self.entry_daily_max_groups.get().strip())
        except ValueError:
            max_groups = 5

        try:
            scrape_max = int(self.entry_daily_scrape_max.get().strip())
        except ValueError:
            scrape_max = 25

        try:
            filter_max = int(self.entry_daily_filter_max.get().strip())
        except ValueError:
            filter_max = 20

        try:
            dms_per_acc = int(self.entry_daily_dms.get().strip())
        except ValueError:
            dms_per_acc = 4

        try:
            friends_per_acc = int(self.entry_daily_friends.get().strip())
        except ValueError:
            friends_per_acc = 3

        try:
            posts_per_acc = int(self.entry_daily_posts_per_acc.get().strip())
        except ValueError:
            posts_per_acc = 2

        scout_acc = self.combo_daily_scout.get()
        use_sandwich = bool(self.chk_daily_sandwich.get())
        warm_all = bool(self.chk_daily_warm_all.get())
        enable_reply = bool(self.chk_daily_reply.get())
        enable_posting = bool(self.chk_daily_posting.get())
        img_path = self.entry_daily_image.get().strip() or None

        self.btn_start_daily.configure(state="disabled")
        self.btn_stop_daily.configure(state="normal")
        self.is_running = True

        def _worker():
            self.update_status("RUNNING", "Daily Routine Active")
            self.log_to(self.log_daily, "⚡ Launching Daily Master Routine...")

            orchestrator = DailyMasterOrchestrator(
                log_callback=lambda msg: self.log_to(self.log_daily, msg),
                status_callback=lambda state, text: self.update_status(state, text),
                checkpoint_callback=lambda acc, r: self.handle_checkpoint_alert(acc, r),
                stop_check=lambda: not self.is_running
            )
            self.active_bot = orchestrator

            try:
                orchestrator.run_daily_funnel(
                    accounts=self.accounts,
                    scout_account=scout_acc,
                    warmup_minutes=warmup_min,
                    warm_all_accounts=warm_all,
                    target_posts=2,
                    target_tier1_quota=tier1_quota,
                    max_leads_to_scrape=scrape_max,
                    max_leads_to_filter=filter_max,
                    max_groups_to_scout=max_groups,
                    dms_per_account=dms_per_acc,
                    enable_comment_reply=enable_reply,
                    friend_requests_per_account=friends_per_acc,
                    enable_group_posting=enable_posting,
                    posts_per_account=posts_per_acc,
                    image_path=img_path,
                    enable_sandwich=use_sandwich
                )
            except Exception as e:
                self.log_to(self.log_daily, f"[red]❌ Unexpected error in Daily Routine: {str(e)[:120]}[/red]")
            finally:
                self.after(0, lambda: self.btn_start_daily.configure(state="normal"))
                self.after(0, lambda: self.btn_stop_daily.configure(state="disabled"))
                self.update_status("READY", "Daily Routine Done")
                self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    # ---------------- 1. AUTO-POSTER VIEW ----------------
    def create_poster_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(
            frame, 
            text="Automatically post story teasers across Facebook groups with Multi-Account Rotation, image attachment, and permanent memory.", 
            text_color="gray"
        )
        desc.pack(anchor="w", padx=10, pady=(0, 6))

        # Main box
        box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        box.pack(fill="x", padx=10, pady=4)

        # Row 1: Groups URLs
        r1 = ctk.CTkFrame(box, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(6, 4))
        lbl_groups = ctk.CTkLabel(r1, text="Target Group URLs (one per line):", font=ctk.CTkFont(weight="bold"))
        lbl_groups.pack(anchor="w", pady=(0, 2))

        self.txt_groups = ctk.CTkTextbox(r1, height=85, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_groups.pack(fill="x", expand=True)
        groups_list = get_groups_list()
        self.txt_groups.insert("1.0", "\n".join(groups_list) if groups_list else "https://www.facebook.com/groups/fictionwriters/\nhttps://www.facebook.com/groups/shortstorywriters/\n")

        # Row 1.5: Story Post Content (Permanent until 100% finished across all groups)
        r_post = ctk.CTkFrame(box, fg_color="transparent")
        r_post.pack(fill="x", padx=12, pady=(4, 4))
        lbl_post_content = ctk.CTkLabel(
            r_post, 
            text="Active Story Post Content (محفوظ دائماً حتى يكتمل النشر في جميع المجموعات 100%):", 
            font=ctk.CTkFont(weight="bold")
        )
        lbl_post_content.pack(anchor="w", pady=(0, 2))

        self.txt_story_post = ctk.CTkTextbox(r_post, height=90, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_story_post.pack(fill="x", expand=True)
        current_story = get_story_template()
        if current_story:
            self.txt_story_post.insert("1.0", current_story)

        def _on_story_change(event=None):
            content = self.txt_story_post.get("1.0", "end").strip()
            with open(POSTS_FILE, 'w', encoding='utf-8') as f:
                f.write(content)
            self.update_poster_stats()
        self.txt_story_post.bind("<KeyRelease>", _on_story_change)

        # Row 2: Image / Book Cover Attachment (Optional)
        r2 = ctk.CTkFrame(box, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(4, 4))
        lbl_img = ctk.CTkLabel(r2, text="Optional Image / Book Cover:", font=ctk.CTkFont(weight="bold"))
        lbl_img.pack(side="left", padx=(0, 8))
        self.entry_post_image = ctk.CTkEntry(r2, placeholder_text="Leave blank for text-only, or browse image...", width=420)
        self.entry_post_image.pack(side="left", fill="x", expand=True, padx=(0, 8))

        # Restore saved image path if exists
        cfg_img_path = DATA_DIR / "poster_config.json"
        if cfg_img_path.exists():
            try:
                with open(cfg_img_path, 'r', encoding='utf-8') as f:
                    saved_img = json.load(f).get("image_path", "")
                    if saved_img and os.path.exists(saved_img):
                        self.entry_post_image.insert(0, saved_img)
            except Exception:
                pass

        btn_browse_img = ctk.CTkButton(
            r2, text="🖼️ Browse Image", width=110, height=28,
            fg_color="#3b5bdb", hover_color="#364fc7",
            command=self.browse_post_image
        )
        btn_browse_img.pack(side="left", padx=(0, 6))

        def _clear_image():
            self.entry_post_image.delete(0, 'end')
            if hasattr(self, 'entry_daily_image'):
                self.entry_daily_image.delete(0, 'end')
            if cfg_img_path.exists():
                try:
                    with open(cfg_img_path, 'w', encoding='utf-8') as f:
                        json.dump({"image_path": ""}, f)
                except Exception:
                    pass

        btn_clear_img = ctk.CTkButton(
            r2, text="❌", width=36, height=28,
            fg_color="#495057", hover_color="#343a40",
            command=_clear_image
        )
        btn_clear_img.pack(side="left")

        # Row 3: Rotation & Sandwich Settings
        r3 = ctk.CTkFrame(box, fg_color="transparent")
        r3.pack(fill="x", padx=12, pady=(4, 8))

        self.chk_rotate_poster = ctk.CTkCheckBox(
            r3, text="🔄 Multi-Account Rotation", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#4dabf7"
        )
        self.chk_rotate_poster.select()
        self.chk_rotate_poster.pack(side="left", padx=(0, 12))

        lbl_limit = ctk.CTkLabel(r3, text="Posts/Profile:")
        lbl_limit.pack(side="left", padx=(0, 4))
        self.entry_posts_per_acc = ctk.CTkEntry(r3, width=45)
        self.entry_posts_per_acc.insert(0, "3")
        self.entry_posts_per_acc.pack(side="left", padx=(0, 14))

        self.chk_post_sandwich = ctk.CTkCheckBox(
            r3, text="🛡️ Session Sandwich (90s/60s)", font=ctk.CTkFont(size=11)
        )
        self.chk_post_sandwich.select()
        self.chk_post_sandwich.pack(side="left", padx=(0, 12))

        self.chk_post_warming = ctk.CTkCheckBox(
            r3, text="🌱 Inter-Post Warming (4-6m)", font=ctk.CTkFont(size=11)
        )
        self.chk_post_warming.select()
        self.chk_post_warming.pack(side="left", padx=(0, 14))

        btn_reset_history = ctk.CTkButton(
            r3, text="🗑️ Reset Memory", width=100, height=26,
            fg_color="#862e9c", hover_color="#702484",
            command=self.reset_poster_history_action
        )
        btn_reset_history.pack(side="right")

        # Action Buttons row
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=5)

        self.btn_start_post = ctk.CTkButton(
            btn_box, text="🚀 Start Auto-Posting", 
            fg_color="#1971c2", hover_color="#1864ab", 
            command=self.start_poster_action, height=36, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start_post.pack(side="left", padx=(0, 10))

        self.btn_stop_post = ctk.CTkButton(
            btn_box, text="⏹ Stop", 
            fg_color="#c92a2a", hover_color="#a61e1e", 
            command=self.stop_any_action, height=36, state="disabled"
        )
        self.btn_stop_post.pack(side="left", padx=(0, 15))

        self.lbl_poster_stats = ctk.CTkLabel(
            btn_box, text="📊 Ready to post with memory continuity", 
            text_color="#74c0fc", font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_poster_stats.pack(side="left", padx=(0, 10))

        # Live Log Console
        log_label = ctk.CTkLabel(frame, text="Live Activity Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(6, 2))

        self.log_poster = ctk.CTkTextbox(frame, height=220, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_poster.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Initial stats
        self.after(500, self.update_poster_stats)

        return frame

    def browse_post_image(self):
        """اختيار صورة للبوست من الحاسوب وحفظ مسارها الدائم ومزامنتها"""
        file_path = filedialog.askopenfilename(
            title="Select Book Cover or Teaser Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp"), ("All files", "*.*")]
        )
        if file_path:
            self.entry_post_image.delete(0, 'end')
            self.entry_post_image.insert(0, file_path)
            try:
                cfg_img_path = DATA_DIR / "poster_config.json"
                with open(cfg_img_path, 'w', encoding='utf-8') as f:
                    json.dump({"image_path": file_path}, f)
                if hasattr(self, 'entry_daily_image'):
                    self.entry_daily_image.delete(0, 'end')
                    self.entry_daily_image.insert(0, file_path)
            except Exception:
                pass

    def reset_poster_history_action(self):
        """إعادة تعيين سجل المجموعات المنشورة"""
        if messagebox.askyesno("Reset Poster Memory", "Are you sure you want to clear the posting memory?\nThis will allow the bot to post to all groups again."):
            clear_poster_history()
            messagebox.showinfo("Memory Reset", "Posting history has been reset successfully.")
            self.update_poster_stats()

    def update_poster_stats(self):
        """تحديث عداد المجموعات وحالة نص المنشور المحفوظ"""
        try:
            groups_text = self.txt_groups.get("1.0", "end").strip()
            groups = [g.strip() for g in groups_text.splitlines() if g.strip() and not g.strip().startswith('#')]
            pending = [g for g in groups if not is_already_posted(g)]
            done = len(groups) - len(pending)
            post_content = get_story_template()

            # تفريغ خانة المنشور بالواجهة إذا تم تفريغه تلقائياً بعد اكتمال النشر في جميع المجموعات
            if hasattr(self, 'txt_story_post'):
                current_ui_text = self.txt_story_post.get("1.0", "end").strip()
                if not post_content and current_ui_text:
                    self.txt_story_post.delete("1.0", "end")

            if not post_content:
                self.lbl_poster_stats.configure(
                    text="🟢 Campaign Completed! Box is empty & ready for next post.",
                    text_color="#51cf66"
                )
            else:
                self.lbl_poster_stats.configure(
                    text=f"📊 Total Groups: {len(groups)}  |  Posted: {done}  |  Remaining: {len(pending)}",
                    text_color="#74c0fc"
                )
        except Exception:
            pass

    # ---------------- 2. COMMENT SCRAPER VIEW ----------------
    def create_scraper_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(frame, text="Extract the clean profiles of real readers who commented on any story post.", text_color="gray")
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # Inputs
        r_url = ctk.CTkFrame(frame, fg_color="transparent")
        r_url.pack(fill="x", padx=10, pady=(5, 2))

        url_label = ctk.CTkLabel(r_url, text="Facebook Post URL (from Group or Page):", font=ctk.CTkFont(weight="bold"))
        url_label.pack(side="left")

        btn_load_viral = ctk.CTkButton(
            r_url, text="📥 Use Top Viral Post", width=140, height=24,
            fg_color="#9c36b5", hover_color="#862e9c", font=ctk.CTkFont(size=11, weight="bold"),
            command=self.load_top_viral_post_action
        )
        btn_load_viral.pack(side="right")

        self.entry_post_url = ctk.CTkEntry(frame, placeholder_text="https://www.facebook.com/groups/123/posts/456/", height=36)
        self.entry_post_url.pack(fill="x", padx=10, pady=(0, 10))

        count_frame = ctk.CTkFrame(frame, fg_color="transparent")
        count_frame.pack(fill="x", padx=10, pady=5)
        
        c_label = ctk.CTkLabel(count_frame, text="Max Commenters to Extract:")
        c_label.pack(side="left", padx=(0, 10))

        self.entry_max_leads = ctk.CTkEntry(count_frame, width=80)
        self.entry_max_leads.insert(0, "30")
        self.entry_max_leads.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=10)

        self.btn_start_scrape = ctk.CTkButton(
            btn_box, text="🎯 Extract Leads", 
            fg_color="#099268", hover_color="#087f5b", 
            command=self.start_scraper_action, height=36, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start_scrape.pack(side="left", padx=(0, 10))

        # Live Log Console
        log_label = ctk.CTkLabel(frame, text="Scraping Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(10, 2))

        self.log_scraper = ctk.CTkTextbox(frame, height=290, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_scraper.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    # ---------------- 3. AUTO-MESSENGER VIEW ----------------
    def create_messenger_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(frame, text="Deliver personalized sample links to interested leads with human typing & safe delays.", text_color="gray")
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # Stats row
        stats_box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        stats_box.pack(fill="x", padx=10, pady=5)

        self.lbl_stats = ctk.CTkLabel(stats_box, text="Loading leads data...", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_stats.pack(padx=15, pady=10)
        self.update_messenger_stats()

        # Batch size input & Account rotation
        batch_frame = ctk.CTkFrame(frame, fg_color="transparent")
        batch_frame.pack(fill="x", padx=10, pady=5)

        b_label = ctk.CTkLabel(batch_frame, text="Batch size (Messages to send):")
        b_label.pack(side="left", padx=(0, 10))

        self.entry_batch_size = ctk.CTkEntry(batch_frame, width=80)
        self.entry_batch_size.insert(0, "10")
        self.entry_batch_size.pack(side="left", padx=(0, 20))

        # Tier-1 Only toggle
        self.chk_msg_tier1_only = ctk.CTkCheckBox(
            batch_frame, 
            text="🎯 Tier-1 Filtered Only",
            command=self.update_messenger_stats
        )
        self.chk_msg_tier1_only.pack(side="left", padx=(0, 15))

        # Rotation checkbox
        self.chk_rotate_accounts = ctk.CTkCheckBox(batch_frame, text="Auto-Rotate Accounts (Every 5 DMs)")
        self.chk_rotate_accounts.select()
        self.chk_rotate_accounts.pack(side="left", padx=(0, 15))

        # Options Row 2 (Warming & Safety Controls)
        opts_row2 = ctk.CTkFrame(frame, fg_color="transparent")
        opts_row2.pack(fill="x", padx=10, pady=(2, 6))

        # Human Warming Toggle Checkbox
        self.chk_msg_warming = ctk.CTkCheckBox(
            opts_row2, 
            text="🌱 Inter-DM Warming (Scroll during delay)"
        )
        self.chk_msg_warming.select() # مفعّل افتراضياً
        self.chk_msg_warming.pack(side="left", padx=(0, 20))

        # Pre & Post Session Warming (The Session Sandwich)
        self.chk_msg_sandwich_warming = ctk.CTkCheckBox(
            opts_row2, 
            text="🛡️ Pre & Post Warming (Natural Session: 90s Entry / 60s Exit)",
            text_color="#69db7c"
        )
        self.chk_msg_sandwich_warming.select() # مفعّل افتراضياً
        self.chk_msg_sandwich_warming.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=(5, 5))

        self.btn_start_msg = ctk.CTkButton(
            btn_box, text="🚀 Standard DM Campaign", 
            fg_color="#7048e8", hover_color="#5f3dc4", 
            command=self.start_messenger_action, height=36, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start_msg.pack(side="left", padx=(0, 10))

        self.btn_stop_msg = ctk.CTkButton(
            btn_box, text="⏹ Stop All", 
            fg_color="#c92a2a", hover_color="#a61e1e", 
            command=self.stop_any_action, height=36, state="disabled"
        )
        self.btn_stop_msg.pack(side="left")

        # --- HYBRID MASTER CAMPAIGN SECTION ---
        hybrid_box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        hybrid_box.pack(fill="x", padx=10, pady=(5, 8))

        h_title = ctk.CTkLabel(hybrid_box, text="⚡ Master Targeted Campaign (Multi-Account DMs + Comment Notification Replies)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f06595")
        h_title.pack(anchor="w", padx=12, pady=(6, 2))

        h_url_frame = ctk.CTkFrame(hybrid_box, fg_color="transparent")
        h_url_frame.pack(fill="x", padx=12, pady=(0, 4))

        h_lbl = ctk.CTkLabel(h_url_frame, text="Post URL:", font=ctk.CTkFont(size=11, weight="bold"))
        h_lbl.pack(side="left", padx=(0, 8))

        self.entry_hybrid_post_url = ctk.CTkEntry(h_url_frame, placeholder_text="Paste Facebook Post URL here for comment replies...", height=30)
        self.entry_hybrid_post_url.pack(side="left", fill="x", expand=True, padx=(0, 10))

        h_opts_frame = ctk.CTkFrame(hybrid_box, fg_color="transparent")
        h_opts_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.chk_hybrid_reply = ctk.CTkCheckBox(h_opts_frame, text="❤️ Like Comment + 🔔 Reply 'Sent DM!'", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ff8787")
        self.chk_hybrid_reply.select()
        self.chk_hybrid_reply.pack(side="left", padx=(0, 15))

        self.btn_launch_hybrid = ctk.CTkButton(
            h_opts_frame, text="🚀 Launch Targeted Campaign", 
            fg_color="#d6336c", hover_color="#c2255c", 
            command=self.start_hybrid_action, height=32, font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_launch_hybrid.pack(side="right")

        # Live Log Console
        log_label = ctk.CTkLabel(frame, text="Outreach Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(6, 2))

        self.log_messenger = ctk.CTkTextbox(frame, height=210, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_messenger.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    # ---------------- 4. TEMPLATES VIEW ----------------
    def create_templates_view(self):
        scroll_frame = ctk.CTkScrollableFrame(self.views_container, fg_color="transparent")
        scroll_frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(scroll_frame, text="Customize your outreach copy with {option1|option2} Spintax for 100% unique variations.", text_color="gray")
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # 1. DM Template
        dm_lbl = ctk.CTkLabel(scroll_frame, text="1. Direct Message Template (Sent to Inbox with Book Link):", font=ctk.CTkFont(weight="bold"))
        dm_lbl.pack(anchor="w", padx=10, pady=(4, 2))

        self.txt_dm_template = ctk.CTkTextbox(scroll_frame, height=110)
        self.txt_dm_template.pack(fill="x", padx=10, pady=(0, 8))
        self.txt_dm_template.insert("1.0", get_message_template())

        # Reply templates
        reply_tmps = get_reply_templates()

        # 2. Notification Reply
        rep_a_lbl = ctk.CTkLabel(scroll_frame, text="2. Notification Reply (Posted on comment: 'I sent you a DM'):", font=ctk.CTkFont(weight="bold"), text_color="#4dabf7")
        rep_a_lbl.pack(anchor="w", padx=10, pady=(4, 2))

        self.txt_reply_a = ctk.CTkTextbox(scroll_frame, height=85)
        self.txt_reply_a.pack(fill="x", padx=10, pady=(0, 8))
        self.txt_reply_a.insert("1.0", reply_tmps.get("reply_sent_dm", ""))

        # 3. Story Post Template
        post_lbl = ctk.CTkLabel(scroll_frame, text="3. Story Post Template (for Auto-Posting to Groups):", font=ctk.CTkFont(weight="bold"))
        post_lbl.pack(anchor="w", padx=10, pady=(4, 2))

        self.txt_story_template = ctk.CTkTextbox(scroll_frame, height=100)
        self.txt_story_template.pack(fill="x", padx=10, pady=(0, 8))
        self.txt_story_template.insert("1.0", get_story_template())

        # Save & Preview Buttons
        btn_box = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=10)

        btn_save = ctk.CTkButton(btn_box, text="💾 Save All Templates", command=self.save_templates_action, height=36, font=ctk.CTkFont(weight="bold"))
        btn_save.pack(side="left", padx=(0, 10))

        btn_preview = ctk.CTkButton(btn_box, text="🧪 Preview Random Variations", fg_color="#495057", hover_color="#343a40", command=self.preview_template_action, height=36)
        btn_preview.pack(side="left")

        return scroll_frame

    # ---------------- 5. LEADS VIEW & 8-DATABASES DASHBOARD ----------------
    def create_leads_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(
            frame, 
            text="Central 8-Databases Dashboard: View readers, viral posts, outreach status, and live account health.", 
            text_color="gray"
        )
        desc.pack(anchor="w", padx=10, pady=(0, 6))

        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=5)

        lbl_db = ctk.CTkLabel(btn_box, text="Select Database:", font=ctk.CTkFont(weight="bold"))
        lbl_db.pack(side="left", padx=(0, 6))

        self.combo_db_selector = ctk.CTkOptionMenu(
            btn_box,
            values=[
                "Tier-1 Qualified Readers (DB 4)",
                "Accounts Health & Quotas (DB 8)",
                "Viral Posts & Queue (DB 2)",
                "Raw Commenters (DB 3)",
                "Outreach History (DB 5)"
            ],
            command=lambda _: self.refresh_leads_view(),
            width=230
        )
        self.combo_db_selector.set("Tier-1 Qualified Readers (DB 4)")
        self.combo_db_selector.pack(side="left", padx=(0, 10))

        btn_refresh = ctk.CTkButton(btn_box, text="🔄 Refresh", command=self.refresh_leads_view, width=90)
        btn_refresh.pack(side="left", padx=(0, 8))

        btn_open_t1 = ctk.CTkButton(
            btn_box, text="📂 Tier-1 CSV", 
            fg_color="#0ca678", hover_color="#099268", 
            command=self.open_tier1_leads_file, width=110
        )
        btn_open_t1.pack(side="left", padx=(0, 8))

        btn_open_csv = ctk.CTkButton(
            btn_box, text="📂 Raw Leads CSV", 
            fg_color="#339af0", hover_color="#1c7ed6", 
            command=self.open_leads_file, width=120
        )
        btn_open_csv.pack(side="left", padx=(0, 8))

        btn_open_health = ctk.CTkButton(
            btn_box, text="📂 Health JSON", 
            fg_color="#495057", hover_color="#343a40", 
            command=self.open_health_file, width=110
        )
        btn_open_health.pack(side="left")

        self.txt_leads_display = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_leads_display.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        self.refresh_leads_view()

        return frame

    def open_tier1_leads_file(self):
        if TIER1_LEADS_FILE.exists():
            os.startfile(str(TIER1_LEADS_FILE))
        else:
            messagebox.showinfo("Not Found", "tier1_leads.csv has not been created yet.")

    def open_health_file(self):
        if ACCOUNTS_HEALTH_FILE.exists():
            os.startfile(str(ACCOUNTS_HEALTH_FILE))
        else:
            messagebox.showinfo("Not Found", "accounts_health.json has not been created yet.")

    # ---------------- HELPER ACTIONS & THREADING ----------------
    def log_to(self, text_widget, message: str):
        """إضافة سطر للـ Log بشكل آمن عبر الـ Threads"""
        def _append():
            clean_msg = message
            for tag in ["[cyan]", "[/cyan]", "[green]", "[/green]", "[bold green]", "[/bold green]",
                        "[bold]", "[/bold]", "[yellow]", "[/yellow]", "[dim]", "[/dim]",
                        "[red]", "[/red]", "[bold cyan]", "[/bold cyan]", "[bold yellow]", "[/bold yellow]",
                        "[italic]", "[/italic]"]:
                clean_msg = clean_msg.replace(tag, "")
            
            text_widget.insert("end", clean_msg + "\n")
            text_widget.see("end")
        self.after(0, _append)

    def handle_checkpoint_alert(self, account_name: str, reason: str):
        """التعامل الفوري مع كشف الكابتشا أو تأكيد الهوية لحماية الحساب"""
        self.update_status("CHECKPOINT", f"ALERT: {account_name}")
        messagebox.showerror(
            "🛑 Security Alert (Checkpoint Detected)",
            f"Account: [{account_name}]\n\n"
            f"Facebook detected a security checkpoint:\n'{reason}'\n\n"
            "The bot has been PAUSED IMMEDIATELY to protect your account.\n"
            "Please click 'Login This Account' to check and solve it manually in Chrome."
        )

    def update_messenger_stats(self):
        use_tier1 = hasattr(self, 'chk_msg_tier1_only') and bool(self.chk_msg_tier1_only.get())
        target_file = TIER1_LEADS_FILE if (use_tier1 and TIER1_LEADS_FILE.exists()) else LEADS_FILE
        file_label = "Tier-1 Leads (Filtered)" if target_file == TIER1_LEADS_FILE else "All Leads (leads.csv)"
        leads = load_leads(target_file)
        history = load_history()
        pending = len([l for l in leads if l['id'] not in history])
        self.lbl_stats.configure(
            text=f"📂 Source: {file_label}  |  Total: {len(leads)}  |  Messaged: {len(history)}  |  Ready: {pending}"
        )

    def open_login_browser(self):
        """فتح المتصفح لحساب محدد لتسجيل الدخول"""
        account = self.current_account
        def _task():
            self.update_status("RUNNING", f"Logging into {account}")
            b = FacebookBrowser(account_name=account, headless=False)
            page = b.start()
            page.goto("https://www.facebook.com/")
            messagebox.showinfo("Facebook Login", f"Chrome is now open for: [{account}]\n\n1. Log into this account.\n2. Join target story groups.\n3. Click OK when done to save this account's session.")
            b.close()
            self.update_status("READY", f"{account} saved")
        threading.Thread(target=_task, daemon=True).start()

    def start_poster_action(self):
        """بدء النشر في المجموعات مع دعم تدوير الحسابات والذاكرة الدائمة وساندويتش الجلسة"""
        groups_text = self.txt_groups.get("1.0", "end").strip()
        groups = [g.strip() for g in groups_text.splitlines() if g.strip() and not g.strip().startswith('#')]

        if not groups:
            messagebox.showwarning("No Groups", "Please add at least one Facebook Group URL!")
            return

        story_content = self.txt_story_post.get("1.0", "end").strip() if hasattr(self, 'txt_story_post') else get_story_template()
        if not story_content:
            messagebox.showwarning(
                "Empty Post", 
                "The story post text is empty!\n(خانة المنشور فارغة حالياً، يرجى كتابة أو لصق نص القصة قبل النشر)"
            )
            return

        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            f.write(groups_text)

        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            f.write(story_content)

        img_path = self.entry_post_image.get().strip()
        if img_path and not os.path.exists(img_path):
            messagebox.showwarning("Image Not Found", f"Specified image does not exist:\n{img_path}")
            return

        try:
            posts_per_acc = int(self.entry_posts_per_acc.get().strip())
        except ValueError:
            posts_per_acc = 3

        rotate_accounts = bool(self.chk_rotate_poster.get())
        enable_sandwich = bool(self.chk_post_sandwich.get())
        enable_warming = bool(self.chk_post_warming.get())
        accounts_to_use = list(self.accounts) if rotate_accounts else [self.current_account]

        self.btn_start_post.configure(state="disabled")
        self.btn_stop_post.configure(state="normal")
        self.is_running = True

        def _worker():
            self.log_to(self.log_poster, f"📢 Launching Auto-Poster Campaign across {len(accounts_to_use)} account(s)...")
            if img_path:
                self.log_to(self.log_poster, f"🖼️ Attached Image: {Path(img_path).name}")

            res = run_multi_account_poster(
                accounts=accounts_to_use,
                groups=groups,
                posts_per_account=posts_per_acc,
                image_path=img_path if img_path else None,
                min_delay_min=4,
                max_delay_min=6,
                enable_warming=enable_warming,
                enable_sandwich=enable_sandwich,
                log_callback=lambda msg: self.log_to(self.log_poster, msg),
                status_callback=lambda st, txt: self.update_status(st, txt),
                checkpoint_callback=lambda acc, r: self.handle_checkpoint_alert(acc, r),
                stop_check=lambda: not self.is_running
            )
            self.after(0, self.update_poster_stats)
            self.update_status("READY", "Posting Done")
            self.after(0, lambda: self.btn_start_post.configure(state="normal"))
            self.after(0, lambda: self.btn_stop_post.configure(state="disabled"))
            self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def load_top_viral_post_action(self):
        """جلب رابط أعلى منشور فيروسي تفاعلاً من ملف viral_posts.csv وتعبئته مباشرة"""
        if not VIRAL_POSTS_FILE.exists():
            messagebox.showinfo("No Viral Posts", "No viral posts found in data/viral_posts.csv yet.\nRun the 'Viral Post Spy' first!")
            return
        try:
            with open(VIRAL_POSTS_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get("post_url", "").strip()
                    if url:
                        self.entry_post_url.delete(0, 'end')
                        self.entry_post_url.insert(0, url)
                        messagebox.showinfo("Loaded", f"Loaded top viral post URL:\n{url}")
                        return
            messagebox.showinfo("Empty", "No valid post URLs found in viral_posts.csv.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read viral posts: {e}")

    def start_scraper_action(self):
        """بدء سحب المعلقين"""
        post_url = self.entry_post_url.get().strip()
        if not post_url:
            messagebox.showwarning("Missing URL", "Please enter a valid Facebook Post URL!")
            return

        try:
            max_leads = int(self.entry_max_leads.get().strip())
        except ValueError:
            max_leads = 30

        self.btn_start_scrape.configure(state="disabled")
        account = self.current_account

        def _worker():
            self.update_status("RUNNING", f"Scraping via {account}")
            browser = FacebookBrowser(account_name=account, headless=False)
            self.active_browser = browser
            page = browser.start()
            try:
                self.log_to(self.log_scraper, f"🔍 Starting extraction from: {post_url} using [{account}]")
                scraper = PostScraper(page)
                leads = scraper.scrape_comments(post_url=post_url, max_leads=max_leads)
                self.log_to(self.log_scraper, f"🎉 Done! Gathered {len(leads)} fresh leads.")
                self.after(0, self.update_messenger_stats)
                self.update_status("READY")
            except CheckpointDetectedError as cde:
                self.handle_checkpoint_alert(account, cde.reason)
            finally:
                browser.close()
                self.after(0, lambda: self.btn_start_scrape.configure(state="normal"))

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def start_messenger_action(self):
        """بدء مراسلة المعلقين مع دعم تدوير الحسابات (Rotation) والتسخين القبلي والبعدي ورصد الكابتشا"""
        try:
            batch_size = int(self.entry_batch_size.get().strip())
        except ValueError:
            batch_size = 10

        self.btn_start_msg.configure(state="disabled")
        self.btn_stop_msg.configure(state="normal")
        self.is_running = True
        rotate_accounts = bool(self.chk_rotate_accounts.get())
        enable_warming = bool(self.chk_msg_warming.get())
        enable_sandwich = hasattr(self, 'chk_msg_sandwich_warming') and bool(self.chk_msg_sandwich_warming.get())
        accounts_to_use = list(self.accounts) if rotate_accounts else [self.current_account]

        def _worker():
            use_tier1 = hasattr(self, 'chk_msg_tier1_only') and bool(self.chk_msg_tier1_only.get())
            target_file = TIER1_LEADS_FILE if (use_tier1 and TIER1_LEADS_FILE.exists()) else LEADS_FILE
            leads = load_leads(target_file)
            history = load_history()
            pending = [l for l in leads if l['id'] not in history][:batch_size]

            if not pending:
                source_txt = "Tier-1 Leads" if target_file == TIER1_LEADS_FILE else "Leads"
                self.log_to(self.log_messenger, f"🎉 No pending {source_txt} to message.")
                self.after(0, lambda: self.btn_start_msg.configure(state="normal"))
                self.after(0, lambda: self.btn_stop_msg.configure(state="disabled"))
                return

            acc_idx = 0
            current_acc = accounts_to_use[acc_idx]
            browser = None

            def open_account(acc_name):
                nonlocal browser
                self.update_status("RUNNING", f"DMs on {acc_name}")
                b = FacebookBrowser(account_name=acc_name, headless=False)
                self.active_browser = b
                page = b.start()
                if enable_sandwich and self.is_running:
                    self.update_status("WARMING", f"Pre-Warm {acc_name} 90s")
                    self.log_to(self.log_messenger, f"🌱 [Pre-Warming] بدء تصفح طبيعي في Feed للحساب [{acc_name}] (90 ثانية)...")
                    b.human_warmup_session(
                        90,
                        log_callback=lambda msg: self.log_to(self.log_messenger, msg),
                        stop_check=lambda: not self.is_running,
                        label="Pre-Warming"
                    )
                return b, page

            def close_account(b, acc_name):
                if not b:
                    return
                try:
                    if enable_sandwich and self.is_running:
                        self.update_status("WARMING", f"Post-Cool {acc_name} 60s")
                        self.log_to(self.log_messenger, f"🧊 [Post-Cooling] تصفح هادئ قبل إغلاق الحساب [{acc_name}] (60 ثانية)...")
                        b.human_warmup_session(
                            60,
                            log_callback=lambda msg: self.log_to(self.log_messenger, msg),
                            stop_check=lambda: not self.is_running,
                            label="Post-Cooling"
                        )
                except Exception:
                    pass
                finally:
                    b.close()

            try:
                browser, page = open_account(current_acc)
                messenger = SafeMessenger(page, browser=browser)
                template = get_message_template()

                idx = 0
                while idx < len(pending) and self.is_running:
                    lead = pending[idx]

                    # تدوير الحسابات كل 5 رسائل إذا كان الخيار مفعل
                    if rotate_accounts and idx > 0 and idx % 5 == 0 and len(accounts_to_use) > 1:
                        self.log_to(self.log_messenger, "🔄 Switching to next account for rotation...")
                        close_account(browser, current_acc)
                        acc_idx = (acc_idx + 1) % len(accounts_to_use)
                        current_acc = accounts_to_use[acc_idx]
                        self.update_status("RUNNING", f"Switched to {current_acc}")
                        browser, page = open_account(current_acc)
                        messenger = SafeMessenger(page, browser=browser)

                    self.log_to(self.log_messenger, f"[{idx + 1}/{len(pending)}] Sending DM on {current_acc} to: {lead.get('name')}")
                    try:
                        messenger.send_direct_message(lead, template)
                    except CheckpointDetectedError as cde:
                        self.log_to(self.log_messenger, f"[bold red]🛑 تنبيه أمني للحساب [{current_acc}]: {cde.reason}![/bold red]")
                        self.handle_checkpoint_alert(current_acc, cde.reason)
                        if browser:
                            browser.close()
                            browser = None
                        if rotate_accounts and len(accounts_to_use) > 1:
                            self.log_to(self.log_messenger, f"[yellow]⚠️ سيتم إيقاف [{current_acc}] والتحول فوراً للحساب التالي...[/yellow]")
                            accounts_to_use.remove(current_acc)
                            if not accounts_to_use:
                                self.log_to(self.log_messenger, "[red]❌ استنفدت جميع الحسابات المتاحة.[/red]")
                                break
                            acc_idx = acc_idx % len(accounts_to_use)
                            current_acc = accounts_to_use[acc_idx]
                            browser, page = open_account(current_acc)
                            messenger = SafeMessenger(page, browser=browser)
                            continue
                        else:
                            break

                    idx += 1

                    if idx < len(pending) and self.is_running:
                        wait_sec = 90
                        if enable_warming:
                            self.update_status("COOLDOWN", f"Warming {wait_sec}s")
                            browser.human_warmup_session(
                                wait_sec,
                                log_callback=lambda msg: self.log_to(self.log_messenger, msg),
                                stop_check=lambda: not self.is_running,
                                label="Inter-DM Warm"
                            )
                        else:
                            self.update_status("COOLDOWN", f"Wait {wait_sec}s")
                            self.log_to(self.log_messenger, f"⏳ Waiting {wait_sec}s safe delay...")
                            time.sleep(wait_sec)
                        self.update_status("RUNNING", f"DMs on {current_acc}")

                self.update_status("READY")
            except CheckpointDetectedError as cde:
                self.handle_checkpoint_alert(current_acc, cde.reason)
            finally:
                if browser:
                    close_account(browser, current_acc)
                self.after(0, lambda: self.btn_start_msg.configure(state="normal"))
                self.after(0, lambda: self.btn_stop_msg.configure(state="disabled"))
                self.after(0, self.update_messenger_stats)
                self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def stop_any_action(self):
        if self.active_bot:
            self.active_bot.is_running = False
        self.is_running = False
        self.update_status("READY", "Stopped")
        messagebox.showinfo("Stopped", "Campaign stopped safely.")

    def start_hybrid_action(self):
        """بدء الحملة الهجينة الشاملة بتدوير الحسابات والرد على التعليقات"""
        post_url = self.entry_hybrid_post_url.get().strip()
        if not post_url:
            messagebox.showwarning("Missing URL", "Please enter the Facebook Post URL for comment replies!")
            return

        try:
            dms_per_acc = int(self.entry_batch_size.get().strip())
        except ValueError:
            dms_per_acc = 5

        enable_comment_reply = bool(self.chk_hybrid_reply.get())
        enable_warming = bool(self.chk_msg_warming.get())
        enable_sandwich = hasattr(self, 'chk_msg_sandwich_warming') and bool(self.chk_msg_sandwich_warming.get())
        accounts = list(self.accounts)

        self.btn_launch_hybrid.configure(state="disabled")
        self.btn_start_msg.configure(state="disabled")
        self.btn_stop_msg.configure(state="normal")
        self.is_running = True

        def _worker():
            use_tier1 = hasattr(self, 'chk_msg_tier1_only') and bool(self.chk_msg_tier1_only.get())
            target_file = TIER1_LEADS_FILE if (use_tier1 and TIER1_LEADS_FILE.exists()) else LEADS_FILE
            source_txt = "Tier-1 Leads" if target_file == TIER1_LEADS_FILE else "All Leads"
            self.update_status("RUNNING", "Direct Campaign Active")
            self.log_to(self.log_messenger, f"🚀 Launching Targeted Campaign using [{source_txt}]...")
            engine = HybridCampaignEngine(
                log_callback=lambda msg: self.log_to(self.log_messenger, msg),
                stop_check_callback=lambda: not self.is_running
            )
            self.active_bot = engine
            try:
                engine.run_hybrid_campaign(
                    post_url=post_url,
                    accounts=accounts,
                    dms_per_account=dms_per_acc,
                    enable_comment_reply=enable_comment_reply,
                    enable_warming=enable_warming,
                    enable_sandwich_warming=enable_sandwich,
                    leads_file=target_file
                )
                self.update_status("READY", "Campaign Done")
            except Exception as e:
                self.log_to(self.log_messenger, f"[red]❌ خطأ في الحملة: {str(e)[:100]}[/red]")
            finally:
                self.after(0, lambda: self.btn_launch_hybrid.configure(state="normal"))
                self.after(0, lambda: self.btn_start_msg.configure(state="normal"))
                self.after(0, lambda: self.btn_stop_msg.configure(state="disabled"))
                self.after(0, self.update_messenger_stats)
                self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def save_templates_action(self):
        dm_text = self.txt_dm_template.get("1.0", "end").strip()
        story_text = self.txt_story_template.get("1.0", "end").strip()
        rep_a_text = self.txt_reply_a.get("1.0", "end").strip()

        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            f.write(dm_text)
        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            f.write(story_text)

        save_reply_templates({
            "reply_sent_dm": rep_a_text
        })

        messagebox.showinfo("Saved", "All templates saved successfully!")

    def preview_template_action(self):
        dm_text = self.txt_dm_template.get("1.0", "end").strip()
        rep_a_text = self.txt_reply_a.get("1.0", "end").strip()

        sample_dm = parse_spintax(dm_text).replace("{name}", "Sarah")
        sample_rep_a = parse_spintax(rep_a_text).replace("{name}", "Sarah")

        msg = (
            f"1. Direct Message (Sample):\n{sample_dm}\n\n"
            f"-----------------------------------------\n"
            f"2. Notification Reply (Sample):\n{sample_rep_a}"
        )
        messagebox.showinfo("Spintax Variations Preview", msg)

    def refresh_leads_view(self):
        choice = getattr(self, "combo_db_selector", None)
        selected_db = choice.get() if choice else "Tier-1 Qualified Readers (DB 4)"
        self.txt_leads_display.delete("1.0", "end")

        if "Accounts Health" in selected_db:
            health = load_accounts_health()
            header = f"{'Account':<12} | {'Status':<12} | {'DMs Today':<10} | {'Friends Today':<14} | {'Posts Today':<12} | {'Warmup':<8} | {'Last Active'}\n"
            header += "=" * 95 + "\n"
            self.txt_leads_display.insert("end", header)
            if not health:
                self.txt_leads_display.insert("end", "ℹ No account health data recorded yet. Run a session to see live stats!\n")
            for acc in self.accounts:
                info = get_account_health(acc)
                status = info.get("status", "HEALTHY")
                dms = f"{info.get('dms_today', 0)}/15"
                friends = f"{info.get('friend_requests_today', 0)}/15"
                posts = f"{info.get('posts_today', 0)}/10"
                warm = f"{info.get('warmup_minutes_today', 0)}m"
                active = str(info.get("last_active", "N/A"))[:19]
                row = f"{acc:<12} | {status:<12} | {dms:<10} | {friends:<14} | {posts:<12} | {warm:<8} | {active}\n"
                self.txt_leads_display.insert("end", row)

        elif "Viral Posts" in selected_db:
            if not VIRAL_POSTS_FILE.exists():
                self.txt_leads_display.insert("end", "ℹ No viral posts saved in viral_posts.csv yet.\n")
                return
            try:
                import pandas as pd
                df = pd.read_csv(VIRAL_POSTS_FILE, encoding='utf-8')
                scraped_hist = load_scraped_posts_history()
                header = f"{'#':<4} | {'Status':<10} | {'Post URL'}\n"
                header += "=" * 95 + "\n"
                self.txt_leads_display.insert("end", header)
                for idx, row in df.iterrows():
                    p_url = str(row.get("post_url", row.iloc[0] if len(row) > 0 else "")).strip()
                    status = "SCRAPED" if is_post_scraped(p_url, scraped_hist) else "PENDING"
                    line = f"{idx+1:<4} | {status:<10} | {p_url}\n"
                    self.txt_leads_display.insert("end", line)
            except Exception as e:
                self.txt_leads_display.insert("end", f"Error reading viral_posts.csv: {str(e)}\n")

        elif "Outreach History" in selected_db:
            history = load_history()
            header = f"{'#':<4} | {'Profile ID / URL':<35} | {'Account':<12} | {'Action':<15} | {'Date'}\n"
            header += "=" * 95 + "\n"
            self.txt_leads_display.insert("end", header)
            if not history:
                self.txt_leads_display.insert("end", "ℹ No outreach messages recorded yet in history.json.\n")
            for idx, (p_id, info) in enumerate(history.items(), start=1):
                acc = str(info.get("account", "N/A"))
                act = str(info.get("action", "dm"))
                dt = str(info.get("date", "N/A"))
                line = f"{idx:<4} | {p_id[:33]:<35} | {acc:<12} | {act:<15} | {dt}\n"
                self.txt_leads_display.insert("end", line)

        else: # Tier-1 Leads (DB 4) or Raw Commenters (DB 3)
            target = TIER1_LEADS_FILE if "Tier-1" in selected_db else LEADS_FILE
            leads = load_leads(target)
            history = load_history()
            header = f"{'#':<4} | {'Name':<22} | {'Status':<10} | {'Location':<18} | {'Profile URL'}\n"
            header += "=" * 95 + "\n"
            self.txt_leads_display.insert("end", header)
            if not leads:
                self.txt_leads_display.insert("end", f"ℹ No leads found in {target.name} yet.\n")
            for idx, lead in enumerate(leads, start=1):
                status = "SENT" if lead['id'] in history else "PENDING"
                loc = str(lead.get("location", "N/A"))[:16]
                row = f"{idx:<4} | {lead.get('name', 'N/A')[:20]:<22} | {status:<10} | {loc:<18} | {lead.get('profile_url', '')}\n"
                self.txt_leads_display.insert("end", row)

    # ---------------- 6. ACCOUNT WARMER VIEW ----------------
    def create_warmer_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(
            frame, 
            text="Niche-Targeted Account Warmer: trains Facebook's algorithms around fiction/story posts, watches stories (~11s), and builds aged trust score.", 
            text_color="gray"
        )
        desc.pack(anchor="w", padx=10, pady=(0, 6))

        # Settings Card
        settings_box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        settings_box.pack(fill="x", padx=10, pady=4)

        s_title = ctk.CTkLabel(settings_box, text="⚙️ Niche Warming Configuration", font=ctk.CTkFont(size=13, weight="bold"), text_color="#ffa94d")
        s_title.pack(anchor="w", padx=12, pady=(6, 4))

        row1 = ctk.CTkFrame(settings_box, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(0, 4))

        lbl_dur = ctk.CTkLabel(row1, text="Session Duration per Account:", font=ctk.CTkFont(weight="bold"))
        lbl_dur.pack(side="left", padx=(0, 8))

        self.combo_warm_duration = ctk.CTkOptionMenu(
            row1, 
            values=["10 Minutes", "15 Minutes", "20 Minutes", "30 Minutes", "45 Minutes", "60 Minutes"], 
            width=140
        )
        self.combo_warm_duration.set("20 Minutes")
        self.combo_warm_duration.pack(side="left", padx=(0, 20))

        # Toggles row
        row2 = ctk.CTkFrame(settings_box, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 8))

        self.chk_warm_likes = ctk.CTkCheckBox(row2, text="👍 Niche Likes (2-4)", font=ctk.CTkFont(size=11))
        self.chk_warm_likes.select()
        self.chk_warm_likes.pack(side="left", padx=(0, 12))

        self.chk_warm_comments = ctk.CTkCheckBox(row2, text="💬 Story Comments (1-2)", font=ctk.CTkFont(size=11))
        self.chk_warm_comments.select()
        self.chk_warm_comments.pack(side="left", padx=(0, 12))

        self.chk_warm_videos = ctk.CTkCheckBox(row2, text="🎥 Videos & Reels", font=ctk.CTkFont(size=11))
        self.chk_warm_videos.select()
        self.chk_warm_videos.pack(side="left", padx=(0, 12))

        self.chk_warm_stories = ctk.CTkCheckBox(row2, text="👁️ Watch Stories (~11s)", font=ctk.CTkFont(size=11))
        self.chk_warm_stories.select()
        self.chk_warm_stories.pack(side="left", padx=(0, 12))

        self.chk_warm_sandwich = ctk.CTkCheckBox(row2, text="🛡️ Session Sandwich", font=ctk.CTkFont(size=11))
        self.chk_warm_sandwich.select()
        self.chk_warm_sandwich.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=8)

        self.btn_start_warm = ctk.CTkButton(
            btn_box, text="🔥 Warm Active Account", 
            fg_color="#e8590c", hover_color="#d9480f", 
            command=lambda: self.start_warming_action(all_accounts=False), height=36, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start_warm.pack(side="left", padx=(0, 10))

        self.btn_start_warm_all = ctk.CTkButton(
            btn_box, text="🔄 Warm ALL Accounts in Rotation", 
            fg_color="#1971c2", hover_color="#1864ab", 
            command=lambda: self.start_warming_action(all_accounts=True), height=36, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start_warm_all.pack(side="left", padx=(0, 10))

        self.btn_stop_warm = ctk.CTkButton(
            btn_box, text="⏹ Stop", 
            fg_color="#c92a2a", hover_color="#a61e1e", 
            command=self.stop_any_action, height=36, state="disabled"
        )
        self.btn_stop_warm.pack(side="left")

        # Live Log Console
        log_label = ctk.CTkLabel(frame, text="Niche Warming Activity Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(6, 2))

        self.log_warmer = ctk.CTkTextbox(frame, height=250, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_warmer.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    def start_warming_action(self, all_accounts: bool = False):
        """بدء جلسة تسخين الحساب أو الحسابات مع النيتش والستوريات وساندويتش الجلسة"""
        dur_str = self.combo_warm_duration.get().split()[0]
        try:
            duration_min = int(dur_str)
        except ValueError:
            duration_min = 20

        enable_likes = bool(self.chk_warm_likes.get())
        enable_comments = bool(self.chk_warm_comments.get())
        enable_videos = bool(self.chk_warm_videos.get())
        enable_stories = bool(self.chk_warm_stories.get())
        enable_sandwich = bool(self.chk_warm_sandwich.get())

        accounts_to_warm = self.accounts if all_accounts else [self.current_account]

        self.btn_start_warm.configure(state="disabled")
        self.btn_start_warm_all.configure(state="disabled")
        self.btn_stop_warm.configure(state="normal")
        self.is_running = True

        def _worker():
            for acc in accounts_to_warm:
                if not self.is_running:
                    break

                self.update_status("RUNNING", f"Warming {acc}")
                self.log_to(self.log_warmer, f"\n[bold orange]🔥 بدء تسخين وتوجيه الحساب [{acc}] نحو نيتش الروايات ({duration_min} دقيقة)...[/bold orange]")
                browser = FacebookBrowser(account_name=acc, headless=False)
                self.active_browser = browser

                try:
                    browser.start()

                    # Phase 1: Pre-Warming
                    if enable_sandwich and self.is_running:
                        self.log_to(self.log_warmer, f"🛡️ [Sandwich] تشغيل تسخين تمهيدي 90 ثانية على {acc}...")
                        browser.human_warmup_session(duration_seconds=90, label="Warmer Pre-Warming", log_callback=lambda msg: self.log_to(self.log_warmer, msg))

                    warmer = AccountWarmer(
                        browser.page, browser=browser,
                        log_callback=lambda msg: self.log_to(self.log_warmer, msg),
                        stop_check_callback=lambda: not self.is_running
                    )
                    self.active_bot = warmer
                    warmer.run_warming_session(
                        duration_minutes=duration_min,
                        enable_likes=enable_likes,
                        enable_comments=enable_comments,
                        enable_video_watch=enable_videos,
                        enable_stories=enable_stories
                    )

                    # Phase 3: Post-Cooling
                    if enable_sandwich and self.is_running:
                        self.log_to(self.log_warmer, f"🛡️ [Sandwich] تشغيل تبريد ختامي 60 ثانية على {acc}...")
                        browser.human_warmup_session(duration_seconds=60, label="Warmer Post-Cooling", log_callback=lambda msg: self.log_to(self.log_warmer, msg))

                except CheckpointDetectedError as cde:
                    self.handle_checkpoint_alert(acc, cde.reason)
                except Exception as e:
                    self.log_to(self.log_warmer, f"[red]خطأ أثناء التسخين: {str(e)[:80]}[/red]")
                finally:
                    browser.close()

            self.update_status("READY", "Warming Complete")
            self.after(0, lambda: self.btn_start_warm.configure(state="normal"))
            self.after(0, lambda: self.btn_start_warm_all.configure(state="normal"))
            self.after(0, lambda: self.btn_stop_warm.configure(state="disabled"))
            self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    # ---------------- 7. VIRAL CONTENT & COMPETITOR SPY VIEW ----------------
    def create_spy_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(
            frame, 
            text="Scout and extract viral niche posts from target groups using a dedicated Scout Account. Filters by recency (<= 3 months), engagement score, and keywords.", 
            text_color="gray"
        )
        desc.pack(anchor="w", padx=10, pady=(0, 6))

        # Inputs box
        box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        box.pack(fill="x", padx=10, pady=4)

        # Row 1: Target Groups
        r1 = ctk.CTkFrame(box, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(8, 4))
        lbl_url = ctk.CTkLabel(r1, text="Target Group URLs (one per line or comma-separated):", font=ctk.CTkFont(weight="bold"))
        lbl_url.pack(anchor="w", pady=(0, 3))
        self.txt_spy_urls = ctk.CTkTextbox(r1, height=65, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_spy_urls.pack(fill="x", expand=True)
        self.txt_spy_urls.insert("1.0", "https://www.facebook.com/groups/fictionwriters\nhttps://www.facebook.com/groups/shortstorywriters")

        # Row 2: Niche Keywords
        r2 = ctk.CTkFrame(box, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(4, 4))
        lbl_kw = ctk.CTkLabel(r2, text="Niche Keywords:", font=ctk.CTkFont(weight="bold"))
        lbl_kw.pack(side="left", padx=(0, 10))
        
        kw_list = load_keywords()
        self.entry_spy_keywords = ctk.CTkEntry(r2, width=420)
        self.entry_spy_keywords.insert(0, ", ".join(kw_list))
        self.entry_spy_keywords.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        btn_save_kw = ctk.CTkButton(
            r2, text="💾 Save Keywords", width=120, height=28,
            fg_color="#2b8a3e", hover_color="#237032",
            command=self.save_keywords_from_gui
        )
        btn_save_kw.pack(side="right")

        # Row 3: Numeric settings and Checkboxes
        r3 = ctk.CTkFrame(box, fg_color="transparent")
        r3.pack(fill="x", padx=12, pady=(4, 8))

        lbl_max = ctk.CTkLabel(r3, text="Top Posts/Group:")
        lbl_max.pack(side="left", padx=(0, 6))
        self.entry_spy_max = ctk.CTkEntry(r3, width=50)
        self.entry_spy_max.insert(0, "6")
        self.entry_spy_max.pack(side="left", padx=(0, 14))

        lbl_months = ctk.CTkLabel(r3, text="Max Age (Months):")
        lbl_months.pack(side="left", padx=(0, 6))
        self.entry_spy_months = ctk.CTkEntry(r3, width=50)
        self.entry_spy_months.insert(0, "3")
        self.entry_spy_months.pack(side="left", padx=(0, 14))

        lbl_min_c = ctk.CTkLabel(r3, text="Min Comments:")
        lbl_min_c.pack(side="left", padx=(0, 6))
        self.entry_spy_min_c = ctk.CTkEntry(r3, width=50)
        self.entry_spy_min_c.insert(0, "5")
        self.entry_spy_min_c.pack(side="left", padx=(0, 18))

        self.chk_spy_daily_mode = ctk.CTkCheckBox(
            r3, text="📅 Daily Mode (1 Group/Day - Top 3 Posts)", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f59f00"
        )
        self.chk_spy_daily_mode.select()
        self.chk_spy_daily_mode.pack(side="left", padx=(0, 14))

        self.chk_spy_sandwich = ctk.CTkCheckBox(
            r3, text="🛡️ Session Sandwich", font=ctk.CTkFont(size=11)
        )
        self.chk_spy_sandwich.select()
        self.chk_spy_sandwich.pack(side="left", padx=(0, 14))

        self.chk_spy_cooldown = ctk.CTkCheckBox(
            r3, text="⏳ Skip If Processed", font=ctk.CTkFont(size=11)
        )
        self.chk_spy_cooldown.select()
        self.chk_spy_cooldown.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=6)

        self.btn_start_spy = ctk.CTkButton(
            btn_box, text="🚀 Scout Viral Posts", 
            fg_color="#9c36b5", hover_color="#862e9c", 
            command=self.start_spy_action, height=36, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start_spy.pack(side="left", padx=(0, 10))

        self.btn_stop_spy = ctk.CTkButton(
            btn_box, text="⏹ Stop", 
            fg_color="#c92a2a", hover_color="#a61e1e", 
            command=self.stop_any_action, height=36, state="disabled"
        )
        self.btn_stop_spy.pack(side="left", padx=(0, 10))

        self.btn_open_viral = ctk.CTkButton(
            btn_box, text="📂 Open viral_posts.csv", 
            fg_color="#343a40", hover_color="#495057", 
            command=self.open_viral_posts_file, height=36
        )
        self.btn_open_viral.pack(side="left")

        # Live Log Console
        log_label = ctk.CTkLabel(frame, text="Viral Spy Activity Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(6, 2))

        self.log_spy = ctk.CTkTextbox(frame, height=220, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_spy.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    def save_keywords_from_gui(self):
        """حفظ الكلمات المفتاحية من الواجهة إلى keywords.txt"""
        raw = self.entry_spy_keywords.get().strip()
        kws = [k.strip().lower() for k in raw.split(",") if k.strip()]
        if not kws:
            messagebox.showwarning("Empty Keywords", "Please enter at least one keyword!")
            return
        try:
            with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(kws))
            messagebox.showinfo("Saved", f"Saved {len(kws)} niche keywords to keywords.txt!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save keywords: {e}")

    # ---------------- 8. TIER-1 COUNTRY & LOCATION FILTER VIEW ----------------
    def create_country_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(
            frame, 
            text="Filter readers by location (USA, UK, Canada, Australia...) to focus outreach solely on high-purchasing international readers.", 
            text_color="gray"
        )
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # Controls box
        box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        box.pack(fill="x", padx=10, pady=5)

        # Source mode
        r_mode = ctk.CTkFrame(box, fg_color="transparent")
        r_mode.pack(fill="x", padx=12, pady=(10, 6))

        lbl_src = ctk.CTkLabel(r_mode, text="Filter Source:", font=ctk.CTkFont(weight="bold"))
        lbl_src.pack(side="left", padx=(0, 15))

        self.country_source_var = ctk.StringVar(value="leads")
        self.radio_src_leads = ctk.CTkRadioButton(r_mode, text="Existing Commenters (leads.csv)", variable=self.country_source_var, value="leads")
        self.radio_src_leads.pack(side="left", padx=(0, 20))

        self.radio_src_group = ctk.CTkRadioButton(r_mode, text="Scrape Group Members Tab", variable=self.country_source_var, value="group")
        self.radio_src_group.pack(side="left")

        # Group URL (if group mode)
        r_grp = ctk.CTkFrame(box, fg_color="transparent")
        r_grp.pack(fill="x", padx=12, pady=(0, 6))
        lbl_grp = ctk.CTkLabel(r_grp, text="Group URL (if members mode):")
        lbl_grp.pack(side="left", padx=(0, 10))
        self.entry_country_group_url = ctk.CTkEntry(r_grp, placeholder_text="https://www.facebook.com/groups/fictionreaders...", width=450)
        self.entry_country_group_url.pack(side="left", fill="x", expand=True)

        # Target Keywords
        r_keys = ctk.CTkFrame(box, fg_color="transparent")
        r_keys.pack(fill="x", padx=12, pady=(0, 6))
        lbl_keys = ctk.CTkLabel(r_keys, text="Target Locations/Keywords:")
        lbl_keys.pack(side="left", padx=(0, 10))
        self.entry_target_locations = ctk.CTkEntry(r_keys, width=450)
        self.entry_target_locations.insert(0, ", ".join(["United States", "USA", "United Kingdom", "UK", "Canada", "Australia", "New Zealand", "Ireland"]))
        self.entry_target_locations.pack(side="left", fill="x", expand=True)

        # Max to check
        r_max = ctk.CTkFrame(box, fg_color="transparent")
        r_max.pack(fill="x", padx=12, pady=(0, 10))
        lbl_m = ctk.CTkLabel(r_max, text="Max Profiles to Verify:")
        lbl_m.pack(side="left", padx=(0, 10))
        self.entry_country_max = ctk.CTkEntry(r_max, width=70)
        self.entry_country_max.insert(0, "30")
        self.entry_country_max.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=8)

        self.btn_start_country = ctk.CTkButton(
            btn_box, text="🎯 Start Country Filter", 
            fg_color="#0ca678", hover_color="#099268", 
            command=self.start_country_filter_action, height=36, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start_country.pack(side="left", padx=(0, 10))

        self.btn_stop_country = ctk.CTkButton(
            btn_box, text="⏹ Stop", 
            fg_color="#c92a2a", hover_color="#a61e1e", 
            command=self.stop_any_action, height=36, state="disabled"
        )
        self.btn_stop_country.pack(side="left", padx=(0, 10))

        self.btn_open_tier1 = ctk.CTkButton(
            btn_box, text="📂 Open tier1_leads.csv", 
            fg_color="#343a40", hover_color="#495057", 
            command=self.open_tier1_leads_file, height=36
        )
        self.btn_open_tier1.pack(side="left")

        # Live Log Console
        log_label = ctk.CTkLabel(frame, text="Country Filter Activity Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(10, 2))

        self.log_country = ctk.CTkTextbox(frame, height=270, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_country.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    # ---------------- 9. FRIEND CONNECTOR VIEW ----------------
    def create_friends_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(
            frame, 
            text="Send safe, human-paced friend requests to verified book readers to build a 5,000-friend profile full of real buyers.", 
            text_color="gray"
        )
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # Controls box
        box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        box.pack(fill="x", padx=10, pady=5)

        # Row 1: Source
        r1 = ctk.CTkFrame(box, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(10, 6))

        lbl_f_src = ctk.CTkLabel(r1, text="Reader Leads Source:", font=ctk.CTkFont(weight="bold"))
        lbl_f_src.pack(side="left", padx=(0, 15))

        self.friend_source_var = ctk.StringVar(value="tier1")
        self.radio_f_tier1 = ctk.CTkRadioButton(r1, text="Tier-1 Leads (tier1_leads.csv)", variable=self.friend_source_var, value="tier1")
        self.radio_f_tier1.pack(side="left", padx=(0, 20))

        self.radio_f_all = ctk.CTkRadioButton(r1, text="All Commenters (leads.csv)", variable=self.friend_source_var, value="all")
        self.radio_f_all.pack(side="left")

        # Row 2: Daily Limit
        r2 = ctk.CTkFrame(box, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(0, 10))

        lbl_lim = ctk.CTkLabel(r2, text="Daily Requests Limit (Safe anti-ban: 10-15):")
        lbl_lim.pack(side="left", padx=(0, 10))

        self.entry_friend_limit = ctk.CTkEntry(r2, width=70)
        self.entry_friend_limit.insert(0, "10")
        self.entry_friend_limit.pack(side="left", padx=(0, 20))

        lbl_delay = ctk.CTkLabel(r2, text="⏱ Interval: 40-85s random human delays", text_color="gray")
        lbl_delay.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=8)

        self.btn_start_friends = ctk.CTkButton(
            btn_box, text="🤝 Start Sending Friend Requests", 
            fg_color="#22b8cf", hover_color="#15aabf", 
            command=self.start_friend_connector_action, height=36, font=ctk.CTkFont(weight="bold")
        )
        self.btn_start_friends.pack(side="left", padx=(0, 10))

        self.btn_stop_friends = ctk.CTkButton(
            btn_box, text="⏹ Stop", 
            fg_color="#c92a2a", hover_color="#a61e1e", 
            command=self.stop_any_action, height=36, state="disabled"
        )
        self.btn_stop_friends.pack(side="left", padx=(0, 10))

        self.btn_view_history = ctk.CTkButton(
            btn_box, text="📊 View History", 
            fg_color="#343a40", hover_color="#495057", 
            command=self.view_friend_history_action, height=36
        )
        self.btn_view_history.pack(side="left")

        # Live Log Console
        log_label = ctk.CTkLabel(frame, text="Friend Connector Activity Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(10, 2))

        self.log_friends = ctk.CTkTextbox(frame, height=270, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_friends.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    # ---------------- ACTIONS FOR THE NEW VIEWS ----------------
    def start_spy_action(self):
        """بدء عملية اصطياد المنشورات الفيروسية لحساب Scout"""
        raw_urls = self.txt_spy_urls.get("1.0", "end").strip()
        urls = [u.strip() for u in raw_urls.split("\n") if u.strip()]
        if not urls:
            urls = [u.strip() for u in raw_urls.split(",") if u.strip()]

        if not urls:
            messagebox.showwarning("Missing URLs", "Please enter at least one target Facebook Group URL!")
            return

        # Keywords
        raw_kws = self.entry_spy_keywords.get().strip()
        custom_kws = [k.strip().lower() for k in raw_kws.split(",") if k.strip()]

        try:
            max_posts = int(self.entry_spy_max.get().strip())
        except ValueError:
            max_posts = 6

        try:
            max_months = int(self.entry_spy_months.get().strip())
        except ValueError:
            max_months = 3

        try:
            min_c = int(self.entry_spy_min_c.get().strip())
        except ValueError:
            min_c = 0

        use_daily_mode = bool(self.chk_spy_daily_mode.get())
        use_sandwich = bool(self.chk_spy_sandwich.get())
        use_cooldown = bool(self.chk_spy_cooldown.get())

        self.btn_start_spy.configure(state="disabled")
        self.btn_stop_spy.configure(state="normal")
        self.is_running = True
        account = self.current_account

        def _worker():
            self.update_status("RUNNING", f"Scout via {account}")
            mode_lbl = "DAILY 1-GROUP" if use_daily_mode else f"BATCH ({len(urls)} groups)"
            self.log_to(self.log_spy, f"🕵️ Launching Scout Spy [{mode_lbl}] using [{account}]")
            self.log_to(self.log_spy, f"🎯 Niche Keywords: {', '.join(custom_kws[:6])}...")
            self.log_to(self.log_spy, f"📅 Max Post Age: <= {max_months} months | Target Posts: {max_posts}")

            browser = FacebookBrowser(account_name=account, headless=False)
            self.active_browser = browser

            try:
                browser.start()

                # Phase 1: Pre-Warming
                if use_sandwich and self.is_running:
                    self.update_status("WARMING", f"Pre-Warming {account}")
                    self.log_to(self.log_spy, f"🛡️ [Sandwich] Running 90s Pre-Warming on {account}...")
                    browser.human_warmup_session(duration_seconds=90, label="Scout Pre-Warming")

                spy = ViralSpyEngine(browser)
                spy.set_keywords(custom_kws)
                self.active_bot = spy

                total_extracted = 0

                if use_daily_mode:
                    self.log_to(self.log_spy, f"📅 Executing Daily Mission: visiting next unprocessed group for {max_posts} top posts...")
                    scanned_group, group_posts = spy.scout_daily_routine(
                        group_urls=urls,
                        target_posts=max_posts,
                        min_comments=min_c,
                        max_months=max_months,
                        progress_callback=lambda msg: self.log_to(self.log_spy, msg)
                    )
                    total_extracted = len(group_posts)
                    if scanned_group:
                        self.log_to(self.log_spy, f"\n🎯 Daily Mission Done! Finished group: {scanned_group}")
                    else:
                        self.log_to(self.log_spy, "\nℹ No pending unprocessed groups found or no matching posts.")
                else:
                    for idx, group_url in enumerate(urls, 1):
                        if not self.is_running:
                            break

                        # Check 24h cooldown / processed
                        if use_cooldown and is_group_on_cooldown(group_url, cooldown_hours=24):
                            self.log_to(self.log_spy, f"⏳ Skipping {group_url} (Scanned within last 24h)")
                            continue

                        self.log_to(self.log_spy, f"\n[{idx}/{len(urls)}] 🚀 Scanning Group: {group_url}")
                        group_posts = spy.scan_posts(
                            target_url=group_url,
                            max_posts=max_posts,
                            min_comments=min_c,
                            max_months=max_months,
                            progress_callback=lambda msg: self.log_to(self.log_spy, msg)
                        )
                        total_extracted += len(group_posts)
                        self.log_to(self.log_spy, f"✔ Extracted {len(group_posts)} top viral posts from this group.")

                        # Sleep between groups if there are more
                        if idx < len(urls) and self.is_running:
                            pause_sec = random.randint(15, 30)
                            self.log_to(self.log_spy, f"⏸ Cooling down for {pause_sec}s before next group...")
                            time.sleep(pause_sec)

                # Phase 3: Post-Cooling
                if use_sandwich and self.is_running:
                    self.update_status("COOLING", f"Post-Cooling {account}")
                    self.log_to(self.log_spy, f"🛡️ [Sandwich] Running 60s Post-Cooling on {account}...")
                    browser.human_warmup_session(duration_seconds=60, label="Scout Post-Cooling")

                self.log_to(self.log_spy, f"\n🎉 Scouting completed! Total viral posts collected: {total_extracted}")
                self.update_status("READY", "Scout Done")

            except CheckpointDetectedError as cde:
                self.handle_checkpoint_alert(account, cde.reason)
            except Exception as e:
                self.log_to(self.log_spy, f"❌ Scout error: {str(e)[:120]}")
            finally:
                browser.close()
                self.after(0, lambda: self.btn_start_spy.configure(state="normal"))
                self.after(0, lambda: self.btn_stop_spy.configure(state="disabled"))
                self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def start_country_filter_action(self):
        """بدء عملية فلترة القراء حسب الدولة"""
        mode = self.country_source_var.get()
        target_keys = [k.strip() for k in self.entry_target_locations.get().split(",") if k.strip()]
        
        try:
            max_profiles = int(self.entry_country_max.get().strip())
        except ValueError:
            max_profiles = 30

        group_url = self.entry_country_group_url.get().strip()
        if mode == "group" and not group_url:
            messagebox.showwarning("Missing Group URL", "Please enter the Group URL to scrape members from!")
            return

        self.btn_start_country.configure(state="disabled")
        self.btn_stop_country.configure(state="normal")
        self.is_running = True
        account = self.current_account

        def _worker():
            self.update_status("RUNNING", f"Filtering on {account}")
            self.log_to(self.log_country, f"🌍 Starting Country Filter ({mode} mode) using [{account}]")
            browser = FacebookBrowser(account_name=account, headless=False)
            self.active_browser = browser
            page = browser.start()

            try:
                clf = CountryLeadFilter(browser, target_locations=target_keys)
                self.active_bot = clf

                if mode == "leads":
                    results = clf.filter_existing_leads(
                        max_leads=max_profiles,
                        progress_callback=lambda msg: self.log_to(self.log_country, msg)
                    )
                else:
                    results = clf.scrape_group_members_by_country(
                        group_url=group_url,
                        max_members=max_profiles,
                        progress_callback=lambda msg: self.log_to(self.log_country, msg)
                    )

                self.log_to(self.log_country, f"\n✨ Filtering completed! Identified {len(results)} Tier-1 high-intent readers.")
                self.update_status("READY", "Filter Done")
            except CheckpointDetectedError as cde:
                self.handle_checkpoint_alert(account, cde.reason)
            except Exception as e:
                self.log_to(self.log_country, f"[red]❌ Country Filter error: {str(e)[:100]}[/red]")
            finally:
                browser.close()
                self.after(0, lambda: self.btn_start_country.configure(state="normal"))
                self.after(0, lambda: self.btn_stop_country.configure(state="disabled"))
                self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def start_friend_connector_action(self):
        """بدء إرسال طلبات الصداقة للقراء المستهدفين"""
        source = self.friend_source_var.get()
        try:
            limit = int(self.entry_friend_limit.get().strip())
        except ValueError:
            limit = 10

        self.btn_start_friends.configure(state="disabled")
        self.btn_stop_friends.configure(state="normal")
        self.is_running = True
        account = self.current_account

        def _worker():
            self.update_status("RUNNING", f"Connecting via {account}")
            self.log_to(self.log_friends, f"🤝 Starting Friend Connector using [{account}] (Daily limit: {limit})...")
            browser = FacebookBrowser(account_name=account, headless=False)
            self.active_browser = browser
            page = browser.start()

            try:
                connector = FriendConnector(browser, account_name=account)
                self.active_bot = connector
                res = connector.run_connector_campaign(
                    source=source,
                    max_requests=limit,
                    progress_callback=lambda msg: self.log_to(self.log_friends, msg)
                )
                self.update_status("READY", "Friend Connector Done")
            except CheckpointDetectedError as cde:
                self.handle_checkpoint_alert(account, cde.reason)
            except Exception as e:
                self.log_to(self.log_friends, f"[red]❌ Error in Friend Connector: {str(e)[:100]}[/red]")
            finally:
                browser.close()
                self.after(0, lambda: self.btn_start_friends.configure(state="normal"))
                self.after(0, lambda: self.btn_stop_friends.configure(state="disabled"))
                self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

    def open_viral_posts_file(self):
        if VIRAL_POSTS_FILE.exists():
            os.startfile(str(VIRAL_POSTS_FILE))
        else:
            messagebox.showinfo("File Not Found", "No viral_posts.csv found yet. Run the Viral Spy first!")

    def open_tier1_leads_file(self):
        if TIER1_LEADS_FILE.exists():
            os.startfile(str(TIER1_LEADS_FILE))
        else:
            messagebox.showinfo("File Not Found", "No tier1_leads.csv found yet. Run the Country Filter first!")

    def view_friend_history_action(self):
        hist = load_friend_history()
        count = len(hist)
        msg = f"Total friend requests tracked: {count}\n\n"
        items = list(hist.items())[-5:]
        for url, details in items:
            msg += f"• {details.get('name', 'User')}: {details.get('status')} via {details.get('account')} ({details.get('requested_at')})\n"
        messagebox.showinfo("Friend Requests History", msg if count > 0 else "No friend requests recorded yet.")

    def open_leads_file(self):
        if LEADS_FILE.exists():
            os.startfile(str(LEADS_FILE))
        else:
            messagebox.showinfo("File Not Found", "No leads.csv file found yet. Scrape some comments first!")

    def open_telegram_settings_dialog(self):
        """نافذة إدارة وإعدادات بوت تليجرام للتنبيهات الفورية"""
        cfg = load_telegram_config()

        dialog = ctk.CTkToplevel(self)
        dialog.title("📱 Telegram Emergency & Report Settings")
        dialog.geometry("520x430")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        lbl_header = ctk.CTkLabel(
            dialog, text="📱 Telegram Alerts & Notification Engine",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#22b8cf"
        )
        lbl_header.pack(pady=(16, 4))

        lbl_desc = ctk.CTkLabel(
            dialog, 
            text="يتم إرسال لقطات الشاشة وتنبيهات الطوارئ وتقارير الحملات مباشرة لهاتفك.",
            font=ctk.CTkFont(size=11), text_color="#adb5bd"
        )
        lbl_desc.pack(pady=(0, 15))

        f_inputs = ctk.CTkFrame(dialog, fg_color="#18181b", corner_radius=8)
        f_inputs.pack(fill="x", padx=20, pady=5)

        # Bot Token
        lbl_token = ctk.CTkLabel(f_inputs, text="Telegram Bot Token:", font=ctk.CTkFont(weight="bold"))
        lbl_token.pack(anchor="w", padx=15, pady=(10, 2))
        entry_token = ctk.CTkEntry(f_inputs, width=460, font=ctk.CTkFont(family="Consolas", size=11))
        entry_token.insert(0, cfg.get("bot_token", ""))
        entry_token.pack(padx=15, pady=(0, 10))

        # Chat ID
        lbl_chat = ctk.CTkLabel(f_inputs, text="Your Telegram Chat ID:", font=ctk.CTkFont(weight="bold"))
        lbl_chat.pack(anchor="w", padx=15, pady=(0, 2))
        entry_chat = ctk.CTkEntry(f_inputs, width=460, font=ctk.CTkFont(family="Consolas", size=11))
        entry_chat.insert(0, cfg.get("chat_id", ""))
        entry_chat.pack(padx=15, pady=(0, 10))

        # Enable switch
        chk_enable = ctk.CTkCheckBox(f_inputs, text="Enable Telegram Instant Alerts", font=ctk.CTkFont(weight="bold"))
        if cfg.get("enabled", True):
            chk_enable.select()
        else:
            chk_enable.deselect()
        chk_enable.pack(anchor="w", padx=15, pady=(0, 12))

        # Action Buttons
        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=15)

        def _save():
            token_val = entry_token.get().strip()
            chat_val = entry_chat.get().strip()
            en_val = bool(chk_enable.get())
            save_telegram_config(token_val, chat_val, en_val)
            messagebox.showinfo("Saved", "Telegram settings saved successfully!")
            dialog.destroy()

        def _test():
            token_val = entry_token.get().strip()
            chat_val = entry_chat.get().strip()
            en_val = bool(chk_enable.get())
            save_telegram_config(token_val, chat_val, en_val)
            ok, msg = test_telegram_connection()
            if ok:
                messagebox.showinfo("Success", f"🎉 {msg}")
            else:
                messagebox.showerror("Error", f"❌ {msg}")

        btn_test = ctk.CTkButton(
            btn_box, text="🧪 Send Test Ping", 
            fg_color="#0ca678", hover_color="#099268", 
            command=_test, width=150, height=36, font=ctk.CTkFont(weight="bold")
        )
        btn_test.pack(side="left", padx=(0, 10))

        btn_save = ctk.CTkButton(
            btn_box, text="💾 Save Settings", 
            fg_color="#1971c2", hover_color="#1864ab", 
            command=_save, width=150, height=36, font=ctk.CTkFont(weight="bold")
        )
        btn_save.pack(side="left")

if __name__ == "__main__":
    app = FacebookBotGUI()
    app.mainloop()
