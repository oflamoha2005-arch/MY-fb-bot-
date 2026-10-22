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

from config import VIRAL_POSTS_FILE
from utils import console
from browser import FacebookBrowser, CheckpointDetectedError

def parse_counter(text: str) -> int:
    """تحويل أرقام الفيسبوك النصية مثل 1.2K أو 350 إلى أرقام صحيحة"""
    if not text:
        return 0
    text = text.strip().lower().replace(",", "")
    match = re.search(r"([\d\.]+)\s*([kmb]?)", text)
    if not match:
        return 0
    val_str, unit = match.groups()
    try:
        val = float(val_str)
        if unit == "k":
            return int(val * 1000)
        elif unit == "m":
            return int(val * 1000000)
        elif unit == "b":
            return int(val * 1000000000)
        return int(val)
    except Exception:
        return 0

class ViralSpyEngine:
    """
    محرّك التجسس على المحتوى الفيروسي والقصص الأكثر تفاعلاً
    Viral Content & Competitor Spy
    """
    def __init__(self, browser: FacebookBrowser):
        self.fb = browser
        self.page: Page = browser.page

    def scan_posts(self, target_url: str, max_posts: int = 15, min_comments: int = 0, progress_callback=None) -> list[dict]:
        """
        فحص المجموعة أو الصفحة واستخراج أنجح المنشورات مرتبة حسب التفاعل
        """
        console.print(f"[bold cyan]🔍 Starting Viral Content Spy on:[/bold cyan] {target_url}")
        if progress_callback:
            progress_callback(f"Opening {target_url}...")

        self.fb.check_checkpoint()
        self.page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(4, 7))

        self.fb.check_checkpoint()

        posts_data = []
        seen_texts = set()

        scroll_attempts = 0
        max_scrolls = max(25, max_posts * 3)

        while len(posts_data) < max_posts and scroll_attempts < max_scrolls:
            scroll_attempts += 1
            if progress_callback:
                progress_callback(f"Scanned {len(posts_data)}/{max_posts} viral posts (Scroll #{scroll_attempts})...")

            # Click all visible "See more" / "Afficher la suite" buttons to get full story hooks
            try:
                see_mores = self.page.locator('div[role="button"]:has-text("See more"), div[role="button"]:has-text("Afficher la suite"), div[role="button"]:has-text("عرض المزيد")').all()
                for btn in see_mores[:3]:
                    try:
                        if btn.is_visible():
                            btn.click(timeout=1000)
                            time.sleep(0.3)
                    except Exception:
                        pass
            except Exception:
                pass

            # Find post containers
            # Facebook post containers usually have role="feed" children or role="article"
            articles = self.page.locator('div[role="feed"] > div, div[role="article"]').all()
            if not articles:
                articles = self.page.locator('div[data-ad-preview="message"]').all()

            for art in articles:
                if len(posts_data) >= max_posts:
                    break

                try:
                    # 1. Post Text
                    # Find text container
                    msg_elem = art.locator('div[data-ad-preview="message"], div[dir="auto"]').first
                    if not msg_elem or not msg_elem.is_visible():
                        continue

                    raw_text = msg_elem.inner_text().strip()
                    if not raw_text or len(raw_text) < 30: # Ignore very short headers/status
                        continue

                    # Deduplicate by text preview
                    text_preview = raw_text[:80].lower()
                    if text_preview in seen_texts:
                        continue
                    seen_texts.add(text_preview)

                    # 2. Extract Author
                    author_name = "Unknown"
                    try:
                        author_elem = art.locator('h2 a, h3 a, h4 a, strong a, a[role="link"]:has(span)').first
                        if author_elem and author_elem.is_visible():
                            author_name = author_elem.inner_text().strip()
                    except Exception:
                        pass

                    # 3. Extract Post URL / Timestamp
                    post_url = target_url
                    try:
                        link_elem = art.locator('a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"]').first
                        if link_elem:
                            href = link_elem.get_attribute("href")
                            if href:
                                if href.startswith("/"):
                                    href = "https://www.facebook.com" + href
                                post_url = href.split("?")[0]
                    except Exception:
                        pass

                    # 4. Extract Reactions / Likes
                    reactions_count = 0
                    try:
                        rx_text = art.locator('span[aria-label*="reaction"], span[aria-label*="like"], span[aria-label*="J\'aime"], span[aria-label*="إعجاب"]').first
                        if rx_text and rx_text.is_visible():
                            aria = rx_text.get_attribute("aria-label") or rx_text.inner_text()
                            reactions_count = parse_counter(aria)
                        else:
                            # Try looking for reaction counter span
                            spans = art.locator('span').all()
                            for s in spans:
                                txt = s.inner_text() or ""
                                if any(x in txt.lower() for x in ["like", "reaction", "j'aime", "others"]):
                                    reactions_count = parse_counter(txt)
                                    if reactions_count > 0:
                                        break
                    except Exception:
                        pass

                    # 5. Extract Comments Count
                    comments_count = 0
                    try:
                        c_elem = art.locator('span:has-text("comment"), span:has-text("Commentaire"), span:has-text("تعليق")').first
                        if c_elem and c_elem.is_visible():
                            comments_count = parse_counter(c_elem.inner_text())
                    except Exception:
                        pass

                    # Filter by minimum comments if specified
                    if min_comments > 0 and comments_count < min_comments:
                        continue

                    # 6. Extract Shares Count
                    shares_count = 0
                    try:
                        s_elem = art.locator('span:has-text("share"), span:has-text("partage"), span:has-text("مشاركة")').first
                        if s_elem and s_elem.is_visible():
                            shares_count = parse_counter(s_elem.inner_text())
                    except Exception:
                        pass

                    # Calculate Viral Score
                    viral_score = (reactions_count * 1) + (comments_count * 2.5) + (shares_count * 3)

                    # Extract Hook (first 300 chars or first 2 paragraphs)
                    paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]
                    hook = "\n".join(paragraphs[:3]) if len(paragraphs) >= 3 else raw_text[:350]

                    post_obj = {
                        "author": author_name,
                        "hook": hook,
                        "full_text": raw_text,
                        "reactions": reactions_count,
                        "comments": comments_count,
                        "shares": shares_count,
                        "viral_score": int(viral_score),
                        "post_url": post_url,
                        "source": target_url,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }

                    posts_data.append(post_obj)
                    console.print(f"[green]✔ Found Post #[/green]{len(posts_data)}: [bold]{author_name}[/bold] | 💬 {comments_count} comments | 👍 {reactions_count} reactions | Score: {int(viral_score)}")

                except Exception as e:
                    continue

            # Human scroll down
            scroll_by = random.randint(700, 1200)
            self.page.mouse.wheel(0, scroll_by)
            time.sleep(random.uniform(2.5, 4.5))

        # Sort posts by Viral Score descending
        posts_data.sort(key=lambda x: x["viral_score"], reverse=True)

        # Save to CSV
        if posts_data:
            self._save_results(posts_data)

        console.print(f"[bold green]✨ Finished! Scraped {len(posts_data)} viral posts saved to {VIRAL_POSTS_FILE}[/bold green]")
        return posts_data

    def _save_results(self, posts: list[dict]):
        """حفظ أو تحديث ملف viral_posts.csv"""
        df_new = pd.DataFrame(posts)
        if VIRAL_POSTS_FILE.exists():
            try:
                df_old = pd.read_csv(VIRAL_POSTS_FILE, encoding='utf-8')
                combined = pd.concat([df_new, df_old], ignore_index=True)
                combined.drop_duplicates(subset=["hook"], keep="first", inplace=True)
                combined.sort_values(by="viral_score", ascending=False, inplace=True)
                combined.to_csv(VIRAL_POSTS_FILE, index=False, encoding='utf-8')
                return
            except Exception:
                pass
        df_new.to_csv(VIRAL_POSTS_FILE, index=False, encoding='utf-8')

if __name__ == "__main__":
    url = input("Enter Facebook Group or Page URL to spy on: ").strip()
    if url:
        fb = FacebookBrowser(headless=False)
        try:
            fb.start()
            spy = ViralSpyEngine(fb)
            results = spy.scan_posts(url, max_posts=10)
            print(f"\nExtracted {len(results)} viral posts successfully!")
        finally:
            fb.stop()
