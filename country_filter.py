import os
import re
import sys
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

from config import LEADS_FILE, TIER1_LEADS_FILE, DEFAULT_TIER1_LOCATIONS
from utils import console, load_leads
from browser import FacebookBrowser, CheckpointDetectedError

class CountryLeadFilter:
    """
    صائد القراء حسب الدولة (Tier-1 Country & Location Filter)
    يقوم بفحص حسابات القراء وتحديد موقعهم الجغرافي (USA, UK, Canada, Australia...)
    لاستخراج القراء ذوي القدرة الشرائية العالية.
    """
    def __init__(self, browser: FacebookBrowser, target_locations: list[str] = None):
        self.fb = browser
        self.page: Page = browser.page
        self.target_locations = [loc.lower().strip() for loc in (target_locations or DEFAULT_TIER1_LOCATIONS)]

    def check_profile_location(self, profile_url: str) -> tuple[bool, str]:
        """
        فحص بروفايل فيسبوك ومعرفة مكان السكن والمدينة/الدولة
        Returns: (is_target_country: bool, detected_location_string: str)
        """
        self.fb.check_checkpoint()

        # Clean URL
        clean_url = profile_url.split("?")[0].rstrip("/")
        # We can visit the profile directly or /about
        about_url = f"{clean_url}/about_overview" if "/profile.php" not in clean_url else f"{clean_url}&sk=about_overview"

        try:
            self.page.goto(about_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2.5, 4.0))
        except Exception:
            try:
                self.page.goto(clean_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(random.uniform(2.5, 4.0))
            except Exception:
                return False, "Failed to load"

        self.fb.check_checkpoint()

        # Extract text from intro/about section
        # Facebook places location in span with "Lives in", "From", "Habite à", "De", etc.
        page_text = ""
        detected_loc = ""

        try:
            # Look for explicit location items in the About / Intro section
            loc_elements = self.page.locator('span:has-text("Lives in"), span:has-text("From"), span:has-text("Habite à"), span:has-text("De"), span:has-text("يقيم في"), span:has-text("من")').all()
            for elem in loc_elements:
                try:
                    txt = elem.inner_text().strip()
                    if txt and len(txt) < 120:
                        detected_loc = txt
                        break
                except Exception:
                    pass

            # If not found directly, get general Intro container text
            if not detected_loc:
                intro_box = self.page.locator('div[data-pagelet="ProfileTilesFeed_0"], div[data-pagelet="ProfileIntro"]').first
                if intro_box and intro_box.is_visible():
                    detected_loc = intro_box.inner_text().replace("\n", " | ")
        except Exception:
            pass

        # If still empty, grab visible text of main column
        if not detected_loc:
            try:
                main_col = self.page.locator('div[role="main"]').first
                if main_col:
                    page_text = main_col.inner_text()[:1500].lower()
            except Exception:
                page_text = ""
        else:
            page_text = detected_loc.lower()

        # Match with target locations
        is_target = False
        matched_keyword = ""
        for loc in self.target_locations:
            pattern = r"\b" + re.escape(loc) + r"\b"
            if re.search(pattern, page_text):
                is_target = True
                matched_keyword = loc.title()
                break

        full_desc = detected_loc if detected_loc else (matched_keyword if is_target else "Unknown / Private")
        return is_target, full_desc

    def filter_existing_leads(self, max_leads: int = 50, progress_callback=None) -> list[dict]:
        """
        فحص القائمة الحالية في leads.csv واستخراج الأشخاص المقيمين في دول Tier-1
        """
        leads = load_leads()
        if not leads:
            console.print("[yellow]⚠️ No leads found in leads.csv to filter.[/yellow]")
            return []

        console.print(f"[bold cyan]🌍 Starting Country Filter on {min(len(leads), max_leads)} leads...[/bold cyan]")
        filtered_results = []
        checked_count = 0

        for lead in leads:
            if checked_count >= max_leads:
                break

            name = lead.get("name", "Unknown")
            profile_url = lead.get("profile_url", "")
            if not profile_url or profile_url == "N/A":
                continue

            checked_count += 1
            if progress_callback:
                progress_callback(f"Checking #{checked_count}/{min(len(leads), max_leads)}: {name}...")

            console.print(f"[cyan]Inspecting location for:[/cyan] {name} ({profile_url})")
            is_tier1, loc_desc = self.check_profile_location(profile_url)

            record = {
                "name": name,
                "profile_url": profile_url,
                "post_url": lead.get("post_url", ""),
                "location": loc_desc,
                "is_tier1": is_tier1,
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            if is_tier1:
                console.print(f"[bold green]🎯 MATCH TIER-1:[/bold green] {name} 📍 {loc_desc}")
                filtered_results.append(record)
            else:
                console.print(f"[gray]⏩ Skipped: {name} (Location: {loc_desc})[/gray]")

            # Safe human delay between profiles
            delay = random.uniform(3.5, 7.0)
            time.sleep(delay)

        # Save to tier1_leads.csv
        if filtered_results:
            self._save_tier1_leads(filtered_results)

        console.print(f"[bold green]✨ Filtering Completed! Found {len(filtered_results)} Tier-1 high-intent readers.[/bold green]")
        return filtered_results

    def scrape_group_members_by_country(self, group_url: str, max_members: int = 30, progress_callback=None) -> list[dict]:
        """
        استخراج وفلترة أعضاء مجموعة معينة حسب الدولة
        """
        members_url = group_url.rstrip("/") + "/members"
        console.print(f"[bold cyan]👥 Scanning group members at:[/bold cyan] {members_url}")
        if progress_callback:
            progress_callback(f"Opening {members_url}...")

        self.fb.check_checkpoint()
        self.page.goto(members_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(4, 6))

        self.fb.check_checkpoint()

        member_links = []
        scrolls = 0
        while len(member_links) < max_members * 3 and scrolls < 15:
            scrolls += 1
            anchors = self.page.locator('a[role="link"][href*="/user/"], a[role="link"][href*="profile.php"]').all()
            for a in anchors:
                try:
                    href = a.get_attribute("href")
                    txt = a.inner_text().strip()
                    if href and txt and len(txt) > 2 and not any(x in txt.lower() for x in ["admin", "moderator", "member"]):
                        clean_href = href.split("?")[0]
                        if clean_href.startswith("/"):
                            clean_href = "https://www.facebook.com" + clean_href
                        if not any(m["url"] == clean_href for m in member_links):
                            member_links.append({"name": txt, "url": clean_href})
                except Exception:
                    pass

            self.page.mouse.wheel(0, 800)
            time.sleep(2.0)

        console.print(f"[cyan]Found {len(member_links)} potential members. Now verifying country locations...[/cyan]")

        tier1_members = []
        for i, m in enumerate(member_links[:max_members]):
            if progress_callback:
                progress_callback(f"Verifying member {i+1}/{min(len(member_links), max_members)}: {m['name']}...")

            is_tier1, loc = self.check_profile_location(m["url"])
            if is_tier1:
                console.print(f"[bold green]🎯 MATCH TIER-1 Member:[/bold green] {m['name']} 📍 {loc}")
                tier1_members.append({
                    "name": m["name"],
                    "profile_url": m["url"],
                    "post_url": group_url,
                    "location": loc,
                    "is_tier1": True,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
            time.sleep(random.uniform(3.5, 6.0))

        if tier1_members:
            self._save_tier1_leads(tier1_members)

        return tier1_members

    def _save_tier1_leads(self, leads: list[dict]):
        """حفظ النتائج في data/tier1_leads.csv وتجنب التكرار"""
        df_new = pd.DataFrame(leads)
        if TIER1_LEADS_FILE.exists():
            try:
                df_old = pd.read_csv(TIER1_LEADS_FILE, encoding='utf-8')
                combined = pd.concat([df_new, df_old], ignore_index=True)
                combined.drop_duplicates(subset=["profile_url"], keep="first", inplace=True)
                combined.to_csv(TIER1_LEADS_FILE, index=False, encoding='utf-8')
                return
            except Exception:
                pass
        df_new.to_csv(TIER1_LEADS_FILE, index=False, encoding='utf-8')

if __name__ == "__main__":
    fb = FacebookBrowser(headless=False)
    try:
        fb.start()
        clf = CountryLeadFilter(fb)
        clf.filter_existing_leads(max_leads=10)
    finally:
        fb.stop()
