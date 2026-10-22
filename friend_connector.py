import os
import sys
import json
import time
import random
import pandas as pd
from datetime import datetime
from pathlib import Path
from playwright.sync_api import Page

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    FRIEND_REQUESTS_FILE, TIER1_LEADS_FILE, LEADS_FILE,
    MAX_FRIEND_REQUESTS_PER_DAY, MIN_FRIEND_DELAY_SECONDS, MAX_FRIEND_DELAY_SECONDS
)
from utils import console, load_leads
from browser import FacebookBrowser, CheckpointDetectedError

def load_friend_history() -> dict:
    """قراءة سجل طلبات الصداقة السابقة"""
    if not FRIEND_REQUESTS_FILE.exists():
        return {}
    try:
        with open(FRIEND_REQUESTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_friend_history(history: dict):
    """حفظ سجل طلبات الصداقة"""
    with open(FRIEND_REQUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

class FriendConnector:
    """
    بناء شبكة الأصدقاء الأجانب (Targeted Friend Connector)
    يرسل طلبات صداقة مدروسة وبأمان كامل للقراء المستهدفين (Tier-1)
    لبناء حساب شخصي به آلاف القراء الحقيقيين.
    """
    def __init__(self, browser: FacebookBrowser, account_name: str = "account_1"):
        self.fb = browser
        self.page: Page = browser.page
        self.account_name = account_name
        self.history = load_friend_history()

    def get_requests_sent_today(self) -> int:
        """حساب عدد الطلبات المرسلة اليوم بهذا الحساب"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        count = 0
        for item in self.history.values():
            if item.get("account") == self.account_name and item.get("requested_at", "").startswith(today_str):
                count += 1
        return count

    def send_friend_request(self, profile_url: str, user_name: str = "") -> str:
        """
        زيارة بروفايل وإرسال طلب الصداقة إذا كان متاحاً
        Returns status: 'sent', 'already_sent', 'already_friends', 'no_add_button', 'error'
        """
        self.fb.check_checkpoint()
        clean_url = profile_url.split("?")[0].rstrip("/")

        # Check if requested previously
        if clean_url in self.history:
            return "already_sent"

        try:
            self.page.goto(clean_url, wait_until="domcontentloaded", timeout=35000)
            time.sleep(random.uniform(3.0, 5.0))
        except Exception as e:
            return "error"

        self.fb.check_checkpoint()

        # Human behavior: gentle scroll down then back up
        self.page.mouse.wheel(0, 300)
        time.sleep(random.uniform(1.0, 2.0))
        self.page.mouse.wheel(0, -200)
        time.sleep(1.0)

        # Look for "Add friend" buttons across multiple languages
        # English: "Add friend"
        # French: "Ajouter comme ami(e)"
        # Arabic: "إضافة صديق"
        add_selectors = [
            'div[role="button"]:has-text("Add friend")',
            'div[aria-label="Add friend"]',
            'div[aria-label="Add Friend"]',
            'div[role="button"]:has-text("Ajouter")',
            'div[role="button"]:has-text("إضافة صديق")',
            'span:has-text("Add friend")'
        ]

        # Check if already friends or pending
        pending_selectors = [
            'div[role="button"]:has-text("Cancel request")',
            'div[role="button"]:has-text("Friend request sent")',
            'div[role="button"]:has-text("Invitation envoyée")',
            'div[role="button"]:has-text("Friends")',
            'div[role="button"]:has-text("Amis")',
            'div[role="button"]:has-text("أصدقاء")'
        ]

        for p_sel in pending_selectors:
            try:
                elem = self.page.locator(p_sel).first
                if elem and elem.is_visible():
                    self.history[clean_url] = {
                        "name": user_name,
                        "account": self.account_name,
                        "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "status": "already_connected_or_pending"
                    }
                    save_friend_history(self.history)
                    return "already_sent"
            except Exception:
                pass

        # Try to click Add Friend
        clicked = False
        for a_sel in add_selectors:
            try:
                btn = self.page.locator(a_sel).first
                if btn and btn.is_visible():
                    # Move mouse to button for anti-bot realism
                    box = btn.bounding_box()
                    if box:
                        self.page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                        time.sleep(0.4)
                    btn.click()
                    clicked = True
                    time.sleep(2.0)
                    break
            except Exception:
                pass

        if clicked:
            self.history[clean_url] = {
                "name": user_name,
                "account": self.account_name,
                "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "status": "sent"
            }
            save_friend_history(self.history)
            return "sent"

        return "no_add_button"

    def run_connector_campaign(
        self, 
        source: str = "tier1", 
        max_requests: int = MAX_FRIEND_REQUESTS_PER_DAY,
        progress_callback=None
    ) -> dict:
        """
        تشغيل حملة إرسال طلبات الصداقة الآمنة
        source: 'tier1' (tier1_leads.csv) or 'all' (leads.csv)
        """
        sent_today = self.get_requests_sent_today()
        remaining_quota = max(0, max_requests - sent_today)

        if remaining_quota <= 0:
            msg = f"Daily limit reached ({sent_today}/{max_requests}) for {self.account_name}. Safe pause until tomorrow."
            console.print(f"[yellow]⚠️ {msg}[/yellow]")
            if progress_callback:
                progress_callback(msg)
            return {"sent": 0, "status": "daily_limit_reached"}

        # Load leads
        target_file = TIER1_LEADS_FILE if source == "tier1" and TIER1_LEADS_FILE.exists() else LEADS_FILE
        if not target_file.exists():
            msg = f"Source file {target_file.name} not found! Please scrape leads first."
            console.print(f"[red]❌ {msg}[/red]")
            return {"sent": 0, "status": "no_leads_file"}

        try:
            df = pd.read_csv(target_file, encoding='utf-8')
            leads = df.to_dict('records')
        except Exception as e:
            return {"sent": 0, "status": f"Error loading {target_file.name}: {e}"}

        console.print(f"[bold cyan]🤝 Starting Friend Connector for {self.account_name} (Target: {remaining_quota} requests)...[/bold cyan]")
        
        sent_count = 0
        for i, lead in enumerate(leads):
            if sent_count >= remaining_quota:
                break

            name = lead.get("name", "Reader")
            profile_url = lead.get("profile_url", "")
            if not profile_url or profile_url == "N/A":
                continue

            clean_url = profile_url.split("?")[0].rstrip("/")
            if clean_url in self.history:
                continue

            if progress_callback:
                progress_callback(f"Sending Friend Request #{sent_count + 1}/{remaining_quota} to {name}...")

            console.print(f"[cyan]Connecting with:[/cyan] {name} ({clean_url})")
            status = self.send_friend_request(profile_url, name)

            if status == "sent":
                sent_count += 1
                console.print(f"[bold green]✔ Friend Request SENT to:[/bold green] {name} ({sent_count}/{remaining_quota})")
                
                # Check safe daily limit
                if sent_count >= remaining_quota:
                    break

                # Safe Delay between requests (40 to 85 seconds)
                delay = random.randint(MIN_FRIEND_DELAY_SECONDS, MAX_FRIEND_DELAY_SECONDS)
                console.print(f"[gray]⏳ Human Pause: waiting {delay}s before next request...[/gray]")
                for sec in range(delay, 0, -5):
                    if progress_callback:
                        progress_callback(f"Pause: {sec}s remaining before next friend request...")
                    time.sleep(min(5, sec))

            elif status == "already_sent":
                console.print(f"[gray]⏩ Already requested/friends: {name}[/gray]")
                time.sleep(2)
            else:
                console.print(f"[yellow]⚠️ No 'Add Friend' button for {name} (Private/Follow-only)[/yellow]")
                time.sleep(2)

        summary = f"Friend Connector finished! Sent {sent_count} targeted requests."
        console.print(f"[bold green]✨ {summary}[/bold green]")
        if progress_callback:
            progress_callback(summary)

        return {"sent": sent_count, "status": "completed"}

if __name__ == "__main__":
    fb = FacebookBrowser(headless=False)
    try:
        fb.start()
        fc = FriendConnector(fb, "account_1")
        fc.run_connector_campaign(source="tier1", max_requests=5)
    finally:
        fb.stop()
