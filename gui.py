import os
import sys
import json
import threading
import time
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

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
    FRIEND_REQUESTS_FILE, DEFAULT_TIER1_LOCATIONS
)
from utils import (
    load_leads, load_history, get_message_template,
    parse_spintax, console, get_reply_templates, save_reply_templates
)
from browser import FacebookBrowser, CheckpointDetectedError
from scraper import PostScraper
from messenger import SafeMessenger
from auto_poster import AutoPoster, get_story_template, get_groups_list, GROUPS_FILE, POSTS_FILE
from hybrid_engine import HybridCampaignEngine
from account_warmer import AccountWarmer
from competitor_spy import ViralSpyEngine
from country_filter import CountryLeadFilter
from friend_connector import FriendConnector, load_friend_history

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

        # Show default view (Auto-Poster)
        self.show_view("poster")

    def setup_sidebar(self):
        """القائمة الجانبية مع نظام إدارة الحسابات المتعددة"""
        self.sidebar_frame = ctk.CTkFrame(self, width=230, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(13, weight=1)

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
        self.btn_poster = ctk.CTkButton(
            self.sidebar_frame, text="📢 Auto-Poster", 
            command=lambda: self.show_view("poster"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_poster.grid(row=3, column=0, padx=12, pady=3, sticky="ew")

        self.btn_scraper = ctk.CTkButton(
            self.sidebar_frame, text="🔍 Comment Scraper", 
            command=lambda: self.show_view("scraper"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_scraper.grid(row=4, column=0, padx=12, pady=3, sticky="ew")

        self.btn_messenger = ctk.CTkButton(
            self.sidebar_frame, text="💬 Direct Messenger", 
            command=lambda: self.show_view("messenger"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_messenger.grid(row=5, column=0, padx=12, pady=3, sticky="ew")

        self.btn_templates = ctk.CTkButton(
            self.sidebar_frame, text="📝 Templates & Copy", 
            command=lambda: self.show_view("templates"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_templates.grid(row=6, column=0, padx=12, pady=3, sticky="ew")

        self.btn_leads = ctk.CTkButton(
            self.sidebar_frame, text="📊 Leads Database", 
            command=lambda: self.show_view("leads"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_leads.grid(row=7, column=0, padx=12, pady=3, sticky="ew")

        self.btn_warmer = ctk.CTkButton(
            self.sidebar_frame, text="🔥 Account Warmer", 
            command=lambda: self.show_view("warmer"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#e8590c", hover_color="#d9480f"
        )
        self.btn_warmer.grid(row=8, column=0, padx=12, pady=3, sticky="ew")

        self.btn_spy = ctk.CTkButton(
            self.sidebar_frame, text="🔎 Viral Post Spy", 
            command=lambda: self.show_view("spy"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#9c36b5", hover_color="#862e9c"
        )
        self.btn_spy.grid(row=9, column=0, padx=12, pady=3, sticky="ew")

        self.btn_country = ctk.CTkButton(
            self.sidebar_frame, text="🌍 Tier-1 Lead Filter", 
            command=lambda: self.show_view("country"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0ca678", hover_color="#099268"
        )
        self.btn_country.grid(row=10, column=0, padx=12, pady=3, sticky="ew")

        self.btn_friends = ctk.CTkButton(
            self.sidebar_frame, text="🤝 Friend Connector", 
            command=lambda: self.show_view("friends"),
            height=33, anchor="w", font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#22b8cf", hover_color="#15aabf"
        )
        self.btn_friends.grid(row=11, column=0, padx=12, pady=3, sticky="ew")

        # Bottom Login Button for the selected account
        self.btn_login = ctk.CTkButton(
            self.sidebar_frame, text="🔐 Login This Account", 
            command=self.open_login_browser,
            fg_color="#2b8a3e", hover_color="#237032",
            height=36, font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_login.grid(row=14, column=0, padx=12, pady=(10, 15), sticky="ew")

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
            "warmer": "#e8590c",
            "spy": "#9c36b5",
            "country": "#0ca678",
            "friends": "#22b8cf"
        }
        btns = {
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
                if name in special_colors:
                    btn.configure(fg_color=special_colors[name])
                else:
                    btn.configure(fg_color=["#3B8ED0", "#1F6AA5"])
            else:
                if name in special_colors:
                    btn.configure(fg_color="#343a40")
                else:
                    btn.configure(fg_color="transparent")

    # ---------------- 1. AUTO-POSTER VIEW ----------------
    def create_poster_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(frame, text="Automatically post high-converting story teasers to your target English groups with anti-ban delays.", text_color="gray")
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # Controls & URLs
        groups_label = ctk.CTkLabel(frame, text="Target Group URLs (One link per line):", font=ctk.CTkFont(weight="bold"))
        groups_label.pack(anchor="w", padx=10, pady=(5, 2))

        self.txt_groups = ctk.CTkTextbox(frame, height=110)
        self.txt_groups.pack(fill="x", padx=10, pady=(0, 10))
        groups_list = get_groups_list()
        self.txt_groups.insert("1.0", "\n".join(groups_list) if groups_list else "https://www.facebook.com/groups/your_group_here/\n")

        # Action Buttons + Delay
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

        delay_lbl = ctk.CTkLabel(btn_box, text="Delay: 4-6 minutes (Auto-Protected)", text_color="#74c0fc")
        delay_lbl.pack(side="left", padx=(0, 15))

        # Human Warming Toggle Checkbox
        self.chk_post_warming = ctk.CTkCheckBox(
            btn_box, 
            text="🌱 Human Warming (Scroll feed & like naturally during 4-6 min delay)"
        )
        self.chk_post_warming.select() # مفعّل افتراضياً
        self.chk_post_warming.pack(side="left")

        # Live Log Console
        log_label = ctk.CTkLabel(frame, text="Live Activity Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(10, 2))

        self.log_poster = ctk.CTkTextbox(frame, height=240, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_poster.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    # ---------------- 2. COMMENT SCRAPER VIEW ----------------
    def create_scraper_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(frame, text="Extract the clean profiles of real readers who commented on any story post.", text_color="gray")
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # Inputs
        url_label = ctk.CTkLabel(frame, text="Facebook Post URL (from Group or Page):", font=ctk.CTkFont(weight="bold"))
        url_label.pack(anchor="w", padx=10, pady=(5, 2))

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
        self.chk_rotate_accounts.pack(side="left", padx=(0, 15))

        # Human Warming Toggle Checkbox
        self.chk_msg_warming = ctk.CTkCheckBox(
            batch_frame, 
            text="🌱 Human Warming (Scroll & like naturally during delay)"
        )
        self.chk_msg_warming.select() # مفعّل افتراضياً
        self.chk_msg_warming.pack(side="left")

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

        h_title = ctk.CTkLabel(hybrid_box, text="⚡ Master Hybrid Campaign (Multi-Account DMs + Comment Replies + Inbound Flip)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#f06595")
        h_title.pack(anchor="w", padx=12, pady=(6, 2))

        h_url_frame = ctk.CTkFrame(hybrid_box, fg_color="transparent")
        h_url_frame.pack(fill="x", padx=12, pady=(0, 4))

        h_lbl = ctk.CTkLabel(h_url_frame, text="Post URL:", font=ctk.CTkFont(size=11, weight="bold"))
        h_lbl.pack(side="left", padx=(0, 8))

        self.entry_hybrid_post_url = ctk.CTkEntry(h_url_frame, placeholder_text="Paste Facebook Post URL here for comment replies...", height=30)
        self.entry_hybrid_post_url.pack(side="left", fill="x", expand=True, padx=(0, 10))

        h_opts_frame = ctk.CTkFrame(hybrid_box, fg_color="transparent")
        h_opts_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.chk_hybrid_reply = ctk.CTkCheckBox(h_opts_frame, text="🔔 Reply 'Sent DM!' on comments", font=ctk.CTkFont(size=11))
        self.chk_hybrid_reply.select()
        self.chk_hybrid_reply.pack(side="left", padx=(0, 15))

        self.chk_hybrid_inbound = ctk.CTkCheckBox(h_opts_frame, text="🧲 Inbound Flip (Invite rest to DM me)", font=ctk.CTkFont(size=11))
        self.chk_hybrid_inbound.select()
        self.chk_hybrid_inbound.pack(side="left", padx=(0, 15))

        self.btn_launch_hybrid = ctk.CTkButton(
            h_opts_frame, text="🚀 Launch Master Hybrid Campaign", 
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

        # 2. Reply Template A
        rep_a_lbl = ctk.CTkLabel(scroll_frame, text="2. Notification Reply A (Posted on comment: 'I sent you a DM'):", font=ctk.CTkFont(weight="bold"), text_color="#4dabf7")
        rep_a_lbl.pack(anchor="w", padx=10, pady=(4, 2))

        self.txt_reply_a = ctk.CTkTextbox(scroll_frame, height=85)
        self.txt_reply_a.pack(fill="x", padx=10, pady=(0, 8))
        self.txt_reply_a.insert("1.0", reply_tmps.get("reply_sent_dm", ""))

        # 3. Reply Template B
        rep_b_lbl = ctk.CTkLabel(scroll_frame, text="3. Inbound Reply B (Posted on remaining comments: 'Send me a DM!'):", font=ctk.CTkFont(weight="bold"), text_color="#f06595")
        rep_b_lbl.pack(anchor="w", padx=10, pady=(4, 2))

        self.txt_reply_b = ctk.CTkTextbox(scroll_frame, height=85)
        self.txt_reply_b.pack(fill="x", padx=10, pady=(0, 8))
        self.txt_reply_b.insert("1.0", reply_tmps.get("reply_inbound_invite", ""))

        # 4. Story Post Template
        post_lbl = ctk.CTkLabel(scroll_frame, text="4. Story Post Template (for Auto-Posting to Groups):", font=ctk.CTkFont(weight="bold"))
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

    # ---------------- 5. LEADS VIEW ----------------
    def create_leads_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(frame, text="View the readers you've gathered and your messaging status.", text_color="gray")
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=5)

        btn_refresh = ctk.CTkButton(btn_box, text="🔄 Refresh Data", command=self.refresh_leads_view, width=120)
        btn_refresh.pack(side="left", padx=(0, 10))

        btn_open_csv = ctk.CTkButton(btn_box, text="📂 Open leads.csv", fg_color="#339af0", hover_color="#1c7ed6", command=self.open_leads_file, width=140)
        btn_open_csv.pack(side="left")

        self.txt_leads_display = ctk.CTkTextbox(frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_leads_display.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh_leads_view()

        return frame

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
        """بدء النشر في المجموعات مع الرصد الذكي للكابتشا"""
        groups_text = self.txt_groups.get("1.0", "end").strip()
        groups = [g.strip() for g in groups_text.splitlines() if g.strip() and not g.strip().startswith('#')]

        if not groups:
            messagebox.showwarning("No Groups", "Please add at least one Facebook Group URL!")
            return

        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            f.write(groups_text)

        self.btn_start_post.configure(state="disabled")
        self.btn_stop_post.configure(state="normal")
        self.is_running = True
        account = self.current_account
        enable_warming = bool(self.chk_post_warming.get())

        def _worker():
            self.update_status("RUNNING", f"Posting via {account}")
            browser = FacebookBrowser(account_name=account, headless=False)
            self.active_browser = browser
            page = browser.start()
            try:
                poster = AutoPoster(page, browser=browser, log_callback=lambda msg: self.log_to(self.log_poster, msg))
                self.active_bot = poster
                poster.run_poster_campaign(groups, min_delay_min=4, max_delay_min=6, enable_warming=enable_warming)
                self.update_status("READY")
            except CheckpointDetectedError as cde:
                self.handle_checkpoint_alert(account, cde.reason)
            finally:
                browser.close()
                self.after(0, lambda: self.btn_start_post.configure(state="normal"))
                self.after(0, lambda: self.btn_stop_post.configure(state="disabled"))
                self.is_running = False

        self.worker_thread = threading.Thread(target=_worker, daemon=True)
        self.worker_thread.start()

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
        """بدء مراسلة المعلقين مع دعم تدوير الحسابات (Rotation) ورصد الكابتشا"""
        try:
            batch_size = int(self.entry_batch_size.get().strip())
        except ValueError:
            batch_size = 10

        self.btn_start_msg.configure(state="disabled")
        self.btn_stop_msg.configure(state="normal")
        self.is_running = True
        rotate_accounts = bool(self.chk_rotate_accounts.get())
        enable_warming = bool(self.chk_msg_warming.get())
        accounts_to_use = self.accounts if rotate_accounts else [self.current_account]

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

            self.update_status("RUNNING", f"DMs on {current_acc}")
            browser = FacebookBrowser(account_name=current_acc, headless=False)
            self.active_browser = browser
            page = browser.start()

            try:
                messenger = SafeMessenger(page, browser=browser)
                template = get_message_template()

                for idx, lead in enumerate(pending, start=1):
                    if not self.is_running:
                        break

                    # تدوير الحسابات كل 5 رسائل إذا كان الخيار مفعل
                    if rotate_accounts and idx > 1 and (idx - 1) % 5 == 0 and len(accounts_to_use) > 1:
                        self.log_to(self.log_messenger, "🔄 Switching to next account for rotation...")
                        browser.close()
                        acc_idx = (acc_idx + 1) % len(accounts_to_use)
                        current_acc = accounts_to_use[acc_idx]
                        self.update_status("RUNNING", f"Switched to {current_acc}")
                        browser = FacebookBrowser(account_name=current_acc, headless=False)
                        self.active_browser = browser
                        page = browser.start()
                        messenger = SafeMessenger(page, browser=browser)

                    self.log_to(self.log_messenger, f"[{idx}/{len(pending)}] Sending DM on {current_acc} to: {lead.get('name')}")
                    messenger.send_direct_message(lead, template)

                    if idx < len(pending) and self.is_running:
                        wait_sec = 90
                        if enable_warming:
                            self.update_status("COOLDOWN", f"Warming {wait_sec}s")
                            browser.human_warmup_session(
                                wait_sec,
                                log_callback=lambda msg: self.log_to(self.log_messenger, msg),
                                stop_check=lambda: not self.is_running
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
                browser.close()
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
        enable_inbound_flip = bool(self.chk_hybrid_inbound.get())
        enable_warming = bool(self.chk_msg_warming.get())
        accounts = list(self.accounts)

        self.btn_launch_hybrid.configure(state="disabled")
        self.btn_start_msg.configure(state="disabled")
        self.btn_stop_msg.configure(state="normal")
        self.is_running = True

        def _worker():
            use_tier1 = hasattr(self, 'chk_msg_tier1_only') and bool(self.chk_msg_tier1_only.get())
            target_file = TIER1_LEADS_FILE if (use_tier1 and TIER1_LEADS_FILE.exists()) else LEADS_FILE
            source_txt = "Tier-1 Leads" if target_file == TIER1_LEADS_FILE else "All Leads"
            self.update_status("RUNNING", "Hybrid Campaign Active")
            self.log_to(self.log_messenger, f"🚀 Launching Hybrid Campaign using [{source_txt}]...")
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
                    enable_inbound_flip=enable_inbound_flip,
                    enable_warming=enable_warming,
                    leads_file=target_file
                )
                self.update_status("READY", "Hybrid Done")
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
        rep_b_text = self.txt_reply_b.get("1.0", "end").strip()

        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            f.write(dm_text)
        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            f.write(story_text)

        save_reply_templates({
            "reply_sent_dm": rep_a_text,
            "reply_inbound_invite": rep_b_text
        })

        messagebox.showinfo("Saved", "All 4 templates saved successfully!")

    def preview_template_action(self):
        dm_text = self.txt_dm_template.get("1.0", "end").strip()
        rep_a_text = self.txt_reply_a.get("1.0", "end").strip()
        rep_b_text = self.txt_reply_b.get("1.0", "end").strip()

        sample_dm = parse_spintax(dm_text).replace("{name}", "Sarah")
        sample_rep_a = parse_spintax(rep_a_text).replace("{name}", "Sarah")
        sample_rep_b = parse_spintax(rep_b_text).replace("{name}", "Sarah")

        msg = (
            f"1. Direct Message (Sample):\n{sample_dm}\n\n"
            f"-----------------------------------------\n"
            f"2. Notification Reply A (Sample):\n{sample_rep_a}\n\n"
            f"-----------------------------------------\n"
            f"3. Inbound Invite Reply B (Sample):\n{sample_rep_b}"
        )
        messagebox.showinfo("Spintax Variations Preview", msg)

    def refresh_leads_view(self):
        leads = load_leads()
        history = load_history()

        self.txt_leads_display.delete("1.0", "end")
        header = f"{'#':<4} | {'Name':<25} | {'Status':<12} | {'Profile URL'}\n"
        header += "-" * 90 + "\n"
        self.txt_leads_display.insert("end", header)

        for idx, lead in enumerate(leads, start=1):
            status = "SENT" if lead['id'] in history else "PENDING"
            row = f"{idx:<4} | {lead.get('name', 'N/A')[:23]:<25} | {status:<12} | {lead.get('profile_url', '')}\n"
            self.txt_leads_display.insert("end", row)

    # ---------------- 6. ACCOUNT WARMER VIEW ----------------
    def create_warmer_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        desc = ctk.CTkLabel(frame, text="Warm up fresh or dormant Facebook accounts by scrolling the feed, watching reels, and placing natural likes/comments.", text_color="gray")
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # Settings Card
        settings_box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        settings_box.pack(fill="x", padx=10, pady=5)

        s_title = ctk.CTkLabel(settings_box, text="⚙️ Warming Session Configuration", font=ctk.CTkFont(size=13, weight="bold"), text_color="#ffa94d")
        s_title.pack(anchor="w", padx=12, pady=(8, 4))

        row1 = ctk.CTkFrame(settings_box, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(0, 6))

        lbl_dur = ctk.CTkLabel(row1, text="Session Duration:", font=ctk.CTkFont(weight="bold"))
        lbl_dur.pack(side="left", padx=(0, 8))

        self.combo_warm_duration = ctk.CTkOptionMenu(row1, values=["10 Minutes", "15 Minutes", "20 Minutes", "30 Minutes", "45 Minutes"], width=130)
        self.combo_warm_duration.set("15 Minutes")
        self.combo_warm_duration.pack(side="left", padx=(0, 20))

        # Toggles row
        row2 = ctk.CTkFrame(settings_box, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(0, 8))

        self.chk_warm_likes = ctk.CTkCheckBox(row2, text="👍 Random Likes (2-4 per session)")
        self.chk_warm_likes.select()
        self.chk_warm_likes.pack(side="left", padx=(0, 15))

        self.chk_warm_comments = ctk.CTkCheckBox(row2, text="💬 Friendly Comments (1-2 per session)")
        self.chk_warm_comments.select()
        self.chk_warm_comments.pack(side="left", padx=(0, 15))

        self.chk_warm_videos = ctk.CTkCheckBox(row2, text="🎥 Watch Videos & Reels")
        self.chk_warm_videos.select()
        self.chk_warm_videos.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=10)

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
        log_label = ctk.CTkLabel(frame, text="Warming Activity Log:", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10, pady=(10, 2))

        self.log_warmer = ctk.CTkTextbox(frame, height=270, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_warmer.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

    def start_warming_action(self, all_accounts: bool = False):
        """بدء جلسة تسخين الحساب أو الحسابات"""
        dur_str = self.combo_warm_duration.get().split()[0]
        try:
            duration_min = int(dur_str)
        except ValueError:
            duration_min = 15

        enable_likes = bool(self.chk_warm_likes.get())
        enable_comments = bool(self.chk_warm_comments.get())
        enable_videos = bool(self.chk_warm_videos.get())

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
                self.log_to(self.log_warmer, f"\n[bold orange]🔥 بدء تسخين وتدفئة الحساب: [{acc}][/bold orange]")
                browser = FacebookBrowser(account_name=acc, headless=False)
                self.active_browser = browser
                page = browser.start()

                try:
                    warmer = AccountWarmer(
                        page, browser=browser,
                        log_callback=lambda msg: self.log_to(self.log_warmer, msg),
                        stop_check_callback=lambda: not self.is_running
                    )
                    self.active_bot = warmer
                    warmer.run_warming_session(
                        duration_minutes=duration_min,
                        enable_likes=enable_likes,
                        enable_comments=enable_comments,
                        enable_video_watch=enable_videos
                    )
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
            text="Analyze top story posts in target groups/pages to extract viral hooks, engagement numbers, and story inspiration.", 
            text_color="gray"
        )
        desc.pack(anchor="w", padx=10, pady=(0, 10))

        # Inputs box
        box = ctk.CTkFrame(frame, fg_color="#18181b", corner_radius=8)
        box.pack(fill="x", padx=10, pady=5)

        # Row 1: Target URL
        r1 = ctk.CTkFrame(box, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(10, 6))
        lbl_url = ctk.CTkLabel(r1, text="Target Group / Page URL:", font=ctk.CTkFont(weight="bold"))
        lbl_url.pack(side="left", padx=(0, 10))
        self.entry_spy_url = ctk.CTkEntry(r1, placeholder_text="https://www.facebook.com/groups/fictionwriters...", width=500)
        self.entry_spy_url.pack(side="left", fill="x", expand=True)

        # Row 2: Settings
        r2 = ctk.CTkFrame(box, fg_color="transparent")
        r2.pack(fill="x", padx=12, pady=(0, 10))

        lbl_max = ctk.CTkLabel(r2, text="Max Posts to Scan:")
        lbl_max.pack(side="left", padx=(0, 8))
        self.entry_spy_max = ctk.CTkEntry(r2, width=70)
        self.entry_spy_max.insert(0, "15")
        self.entry_spy_max.pack(side="left", padx=(0, 20))

        lbl_min_c = ctk.CTkLabel(r2, text="Min Comments Filter:")
        lbl_min_c.pack(side="left", padx=(0, 8))
        self.entry_spy_min_c = ctk.CTkEntry(r2, width=70)
        self.entry_spy_min_c.insert(0, "5")
        self.entry_spy_min_c.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=8)

        self.btn_start_spy = ctk.CTkButton(
            btn_box, text="🚀 Start Viral Content Spy", 
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
        log_label.pack(anchor="w", padx=10, pady=(10, 2))

        self.log_spy = ctk.CTkTextbox(frame, height=270, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_spy.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return frame

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
        """بدء عملية التجسس على المنشورات الفيروسية"""
        url = self.entry_spy_url.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Please enter a valid Facebook Group or Page URL!")
            return

        try:
            max_posts = int(self.entry_spy_max.get().strip())
        except ValueError:
            max_posts = 15

        try:
            min_c = int(self.entry_spy_min_c.get().strip())
        except ValueError:
            min_c = 0

        self.btn_start_spy.configure(state="disabled")
        self.btn_stop_spy.configure(state="normal")
        self.is_running = True
        account = self.current_account

        def _worker():
            self.update_status("RUNNING", f"Spying via {account}")
            self.log_to(self.log_spy, f"🔍 Launching Viral Spy on: {url} using [{account}]")
            browser = FacebookBrowser(account_name=account, headless=False)
            self.active_browser = browser
            page = browser.start()

            try:
                spy = ViralSpyEngine(browser)
                self.active_bot = spy
                posts = spy.scan_posts(
                    target_url=url, 
                    max_posts=max_posts, 
                    min_comments=min_c, 
                    progress_callback=lambda msg: self.log_to(self.log_spy, msg)
                )
                self.log_to(self.log_spy, f"\n🎉 Successfully found {len(posts)} viral posts! Saved to data/viral_posts.csv")
                self.update_status("READY", "Spy Done")
            except CheckpointDetectedError as cde:
                self.handle_checkpoint_alert(account, cde.reason)
            except Exception as e:
                self.log_to(self.log_spy, f"[red]❌ Spy error: {str(e)[:100]}[/red]")
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

if __name__ == "__main__":
    app = FacebookBotGUI()
    app.mainloop()
