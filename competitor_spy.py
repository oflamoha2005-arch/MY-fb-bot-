import os
import re
import sys
import time
import random
import json
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

from config import VIRAL_POSTS_FILE, KEYWORDS_FILE, SPY_HISTORY_FILE, SCRAPED_POSTS_FILE
from utils import console
from browser import FacebookBrowser, CheckpointDetectedError

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

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

def load_keywords(file_path: Path = KEYWORDS_FILE) -> list[str]:
    """تحميل الكلمات المفتاحية الخاصة بالنيتش من الملف"""
    if not file_path.exists():
        default_keywords = [
            "story", "stories", "novel", "novels", "book", "books",
            "fiction", "mystery", "suspense", "thriller", "horror",
            "chapter", "twist", "author", "reader", "reading", "tale"
        ]
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(default_keywords))
        except Exception:
            pass
        return default_keywords

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]
            return lines if lines else ["story", "fiction", "book"]
    except Exception:
        return ["story", "fiction", "book"]

def is_niche_relevant(text: str, keywords: list[str]) -> bool:
    """التحقق من أن المنشور يتحدث عن نيتش الروايات/القصص ويحتوي على الكلمات المفتاحية"""
    if not keywords:
        return True
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)

def is_recent_post(time_str: str, max_months: int = 3) -> bool:
    """
    التحقق من حداثة المنشور (ألا يتجاوز 3 أشهر)
    يدعم التنسيقات الإنجليزية والفرنسية والعربية والتواريخ المطلقة
    """
    if not time_str:
        return True # إذا تعذر استخراج الوقت نعتبره صالحاً احتياطياً
    s = time_str.lower().strip()

    # 1. فحص السنوات النسبية (إذا كان المنشور قديم بسنة أو أكثر يُستبعد مباشرة)
    if re.search(r'\b([1-9]\d*)\s*(?:y|yr|yrs|year|years|an|ans|سنة|سنوات)\b', s):
        return False

    # 2. فحص الأشهر النسبية (مثلاً 4 mos أو 5 mois أو 4 أشهر)
    m_match = re.search(r'\b([1-9]\d*)\s*(?:mo|mos|month|months|mois|شهر|أشهر|اشهر)\b', s)
    if m_match:
        months = int(m_match.group(1))
        return months <= max_months

    # 3. فحص التواريخ المطلقة التي تحتوي على سنة (مثل October 12, 2024)
    year_match = re.search(r'\b(20\d{2})\b', s)
    if year_match:
        post_year = int(year_match.group(1))
        now = datetime.now()
        post_month = 1
        for m_name, m_num in MONTH_MAP.items():
            if m_name in s:
                post_month = m_num
                break
        months_ago = (now.year - post_year) * 12 + (now.month - post_month)
        if months_ago > max_months:
            return False

    return True

def load_spy_history(file_path: Path = SPY_HISTORY_FILE) -> dict:
    """تحميل سجل المجموعات التي تم فحصها لتجنب التكرار"""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_spy_history(history: dict, file_path: Path = SPY_HISTORY_FILE):
    """حفظ سجل المجموعات المفحوصة"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def clean_url_key(url: str) -> str:
    """تنظيف وتوحيد شكل الرابط لاستخدامه كمفتاح في قواعد البيانات والسجلات"""
    if not url:
        return ""
    return str(url).split("?")[0].strip().rstrip("/").lower()

def load_scraped_posts_history(file_path: Path = SCRAPED_POSTS_FILE) -> dict:
    """تحميل سجل المنشورات التي تم سحب تعليقاتها مسبقاً لمنع التكرار نهائياً"""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_scraped_posts_history(history: dict, file_path: Path = SCRAPED_POSTS_FILE):
    """حفظ سجل المنشورات المسحوبة في JSON"""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def is_post_scraped(post_url: str, history: dict = None) -> bool:
    """التحقق مما إذا كان المنشور قد تم سحب معلقيه مسبقاً لتخطيه (Skip)"""
    if history is None:
        history = load_scraped_posts_history()
    return clean_url_key(post_url) in history

def mark_post_as_scraped(post_url: str, leads_count: int = 0, tier1_count: int = 0, group_url: str = ""):
    """تسجيل منشور كرابط مكتمل السحب في قاعدة البيانات والسجل"""
    history = load_scraped_posts_history()
    key = clean_url_key(post_url)
    history[key] = {
        "post_url": post_url,
        "group_url": group_url,
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "leads_extracted": leads_count,
        "tier1_leads_found": tier1_count,
        "status": "scraped"
    }
    save_scraped_posts_history(history)

def get_unscraped_viral_posts(viral_posts_file: Path = VIRAL_POSTS_FILE) -> list[dict]:
    """استخراج قائمة روابط المنشورات الفيروسية المسجلة في Database 2 والتي لم تُسحب تعليقاتها بعد (Links Only)"""
    if not viral_posts_file.exists():
        return []
    try:
        df = pd.read_csv(viral_posts_file, encoding='utf-8')
        if df.empty:
            return []
        history = load_scraped_posts_history()
        unscraped = []
        for _, row in df.iterrows():
            if "post_url" in row:
                p_url = str(row.get("post_url", "")).strip()
            elif "url" in row:
                p_url = str(row.get("url", "")).strip()
            else:
                p_url = str(row.iloc[0]).strip()
            if p_url and p_url.startswith("http") and not is_post_scraped(p_url, history):
                unscraped.append({"post_url": p_url})
        return unscraped
    except Exception:
        return []

def is_group_processed(group_url: str, history: dict = None) -> bool:
    """التحقق مما إذا كانت المجموعة قد تم فحصها واستخراج منشوراتها مسبقاً"""
    if history is None:
        history = load_spy_history()
    clean_url = group_url.strip().rstrip("/").lower()
    item = history.get(clean_url)
    if not item:
        return False
    if isinstance(item, dict):
        return item.get("status") == "completed" or item.get("posts_found", 0) > 0
    return bool(item)

def is_group_on_cooldown(group_url: str, cooldown_hours: int = 24, history: dict = None) -> bool:
    """التحقق مما إذا كانت المجموعة قد فُحصت خلال آخر 24 ساعة"""
    if history is None:
        history = load_spy_history()
    clean_url = group_url.strip().rstrip("/").lower()
    item = history.get(clean_url)
    if not item:
        return False
    try:
        last_scanned = item.get("scanned_at") if isinstance(item, dict) else item
        if not last_scanned:
            return False
        last_dt = datetime.fromisoformat(last_scanned)
        diff_hours = (datetime.now() - last_dt).total_seconds() / 3600.0
        return diff_hours < cooldown_hours
    except Exception:
        return False

class ViralSpyEngine:
    """
    محرّك التجسس واصطياد المنشورات الفيروسية (Scout & Competitor Spy Engine)
    - يعمل بحساب واحد مخصص (Scout Account)
    - يتحقق من الكلمات المفتاحية لمطابقة النيتش
    - يستبعد المنشورات الأقدم من 3 أشهر
    - يفتح نصوص المنشورات الطويلة بالكامل (See More / عرض المزيد)
    - يحسب مؤشر القوة والانتشار (Engagement Score)
    - تمرير بشري بطيء وقراءة تدريجية (Human Micro-Scrolling)
    - يدعم الروتين اليومي: مجموعة واحدة فقط يومياً، استخراج أفضل 3 منشورات وإنهاء الجلسة
    - يتذكر المجموعات المفحوصة لتفادي التكرار نهائياً
    """
    def __init__(self, browser: FacebookBrowser):
        self.fb = browser
        self.page: Page = browser.page
        self.keywords = load_keywords()

    def set_keywords(self, keywords: list[str]):
        """تحديث الكلمات المفتاحية ديناميكياً"""
        if keywords:
            self.keywords = [k.strip().lower() for k in keywords if k.strip()]

    def _human_scroll_and_read(self):
        """
        محاكاة تمرير وتصفح بشري طبيعي:
        - تمرير تدريجي عبر دفعات صغيرة (Micro-steps)
        - وقفات قراءة عشوائية لمحاكاة حركة العين
        - تراجع طفيف لأعلى أحياناً كما يفعل القارئ البشري
        """
        steps = random.randint(3, 5)
        for _ in range(steps):
            delta = random.randint(180, 320)
            self.page.mouse.wheel(0, delta)
            time.sleep(random.uniform(0.2, 0.45))

        # 25% فرصة لتمرير خفيف للأعلى لمحاكاة إعادة قراءة عنوان
        if random.random() < 0.25:
            self.page.mouse.wheel(0, -random.randint(60, 130))
            time.sleep(random.uniform(0.3, 0.7))

        # وقفة قراءة واقعية
        time.sleep(random.uniform(2.5, 4.5))

    def scan_posts(
        self, 
        target_url: str, 
        max_posts: int = 3, 
        min_comments: int = 0, 
        max_months: int = 3,
        progress_callback=None
    ) -> list[dict]:
        """
        فحص مجموعة واستخراج أفضل المنشورات المطابقة للنيتش
        مرتبة حسب مؤشر القوة والانتشار (Engagement Score)
        """
        clean_url = target_url.strip()
        console.print(f"[bold cyan]🔍 Starting Viral Content Spy on:[/bold cyan] {clean_url}")
        if progress_callback:
            progress_callback(f"Opening {clean_url}...")

        self.fb.verify_safety_or_raise()
        self.page.goto(clean_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(random.uniform(4, 7))
        self.fb.verify_safety_or_raise()

        candidate_posts = []
        seen_texts = set()

        scroll_attempts = 0
        max_scrolls = max(20, max_posts * 5)

        while scroll_attempts < max_scrolls:
            scroll_attempts += 1
            if progress_callback:
                progress_callback(f"Evaluating posts in {clean_url} (Found {len(candidate_posts)} relevant candidates, Scroll #{scroll_attempts})...")

            # فتح النصوص الطويلة العامة المرئية
            try:
                general_see_mores = self.page.locator('div[role="button"]:has-text("See more"), div[role="button"]:has-text("Afficher la suite"), div[role="button"]:has-text("عرض المزيد")').all()
                for btn in general_see_mores[:3]:
                    try:
                        if btn.is_visible():
                            btn.click(timeout=800)
                            time.sleep(0.3)
                    except Exception:
                        pass
            except Exception:
                pass

            # استخراج حاويات المنشورات
            articles = self.page.locator('div[role="feed"] > div, div[role="article"]').all()
            if not articles:
                articles = self.page.locator('div[data-ad-preview="message"]').all()

            for art in articles:
                try:
                    # فتح زر "See more" الخاص بهذا المنشور بعينه لضمان قراءة النص كاملاً
                    try:
                        art_see_more = art.locator('div[role="button"]:has-text("See more"), div[role="button"]:has-text("Afficher la suite"), div[role="button"]:has-text("عرض المزيد")').first
                        if art_see_more and art_see_more.is_visible():
                            art_see_more.click(timeout=600)
                            time.sleep(random.uniform(0.3, 0.5))
                    except Exception:
                        pass

                    # 1. استخراج نص المنشور
                    msg_elem = art.locator('div[data-ad-preview="message"], div[dir="auto"]').first
                    if not msg_elem or not msg_elem.is_visible():
                        continue

                    raw_text = msg_elem.inner_text().strip()
                    if not raw_text or len(raw_text) < 3:
                        continue

                    # تجنب تكرار المنشور
                    text_preview = raw_text[:80].lower()
                    if text_preview in seen_texts:
                        continue
                    seen_texts.add(text_preview)

                    # 2. التحقق من مطابقة النيتش بواسطة الكلمات المفتاحية
                    if not is_niche_relevant(raw_text, self.keywords):
                        # المنشور لا يتعلق بالروايات أو القصص المستهدفة
                        continue

                    # 3. استخراج التوقيت والتحقق من حداثة المنشور (<= 3 أشهر)
                    time_text = ""
                    try:
                        time_elem = art.locator('a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"], abbr, span[id] a').first
                        if time_elem:
                            time_text = (time_elem.get_attribute("aria-label") or time_elem.inner_text() or "").strip()
                    except Exception:
                        pass

                    if time_text and not is_recent_post(time_text, max_months=max_months):
                        # المنشور قديم تجاوز 3 أشهر
                        continue

                    # 4. استخراج اسم الكاتب / الناشر
                    author_name = "Unknown"
                    try:
                        author_elem = art.locator('h2 a, h3 a, h4 a, strong a, a[role="link"]:has(span)').first
                        if author_elem and author_elem.is_visible():
                            author_name = author_elem.inner_text().strip()
                    except Exception:
                        pass

                    # 5. استخراج رابط المنشور
                    post_url = clean_url
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

                    # 6. استخراج التفاعلات (Reactions / Likes)
                    reactions_count = 0
                    try:
                        rx_text = art.locator('span[aria-label*="reaction"], span[aria-label*="like"], span[aria-label*="J\'aime"], span[aria-label*="إعجاب"]').first
                        if rx_text and rx_text.is_visible():
                            aria = rx_text.get_attribute("aria-label") or rx_text.inner_text()
                            reactions_count = parse_counter(aria)
                        else:
                            spans = art.locator('span').all()
                            for s in spans:
                                txt = s.inner_text() or ""
                                if any(x in txt.lower() for x in ["like", "reaction", "j'aime", "others"]):
                                    reactions_count = parse_counter(txt)
                                    if reactions_count > 0:
                                        break
                    except Exception:
                        pass

                    # 7. استخراج عدد التعليقات (Comments Count)
                    comments_count = 0
                    try:
                        c_elem = art.locator('span:has-text("comment"), span:has-text("Commentaire"), span:has-text("تعليق")').first
                        if c_elem and c_elem.is_visible():
                            comments_count = parse_counter(c_elem.inner_text())
                    except Exception:
                        pass

                    if min_comments > 0 and comments_count < min_comments:
                        continue

                    # 8. استخراج عدد المشاركات (Shares Count)
                    shares_count = 0
                    try:
                        s_elem = art.locator('span:has-text("share"), span:has-text("partage"), span:has-text("مشاركة")').first
                        if s_elem and s_elem.is_visible():
                            shares_count = parse_counter(s_elem.inner_text())
                    except Exception:
                        pass

                    # 9. حساب مؤشر القوة والانتشار (Engagement Score)
                    viral_score = (reactions_count * 1) + (comments_count * 2.5) + (shares_count * 3)

                    # استخراج الهوك (Hook) كأول فقرات
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
                        "timestamp_raw": time_text,
                        "post_url": post_url,
                        "source": clean_url,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }

                    candidate_posts.append(post_obj)
                    console.print(f"[green]✔ Matched Post:[/green] [bold]{author_name}[/bold] | 💬 {comments_count} | 👍 {reactions_count} | 🚀 Score: {int(viral_score)}")

                except Exception:
                    continue

            # التمرير البشري التدريجي وقراءة المحتوى
            self._human_scroll_and_read()

            # الاكتفاء إذا وجدنا عدداً وفيراً لفرز الأفضل
            if len(candidate_posts) >= max_posts * 3:
                break

        # ترتيب المنشورات تنازلياً حسب مؤشر القوة والانتشار
        candidate_posts.sort(key=lambda x: x["viral_score"], reverse=True)
        top_posts = candidate_posts[:max_posts]

        # حفظ المنشورات المتصدرة في CSV
        if top_posts:
            self._save_results(top_posts)

        # تحديث ذاكرة المجموعات المفحوصة
        history = load_spy_history()
        history[clean_url.rstrip("/").lower()] = {
            "status": "completed" if len(top_posts) > 0 else "empty",
            "scanned_at": datetime.now().isoformat(),
            "posts_found": len(top_posts)
        }
        save_spy_history(history)

        console.print(f"[bold green]✨ Selected top {len(top_posts)} viral posts for {clean_url}[/bold green]")
        return top_posts

    def scout_daily_routine(
        self,
        group_urls: list[str],
        target_posts: int = 3,
        min_comments: int = 0,
        max_months: int = 3,
        progress_callback=None
    ) -> tuple[str, list[dict]]:
        """
        تنفيذ وضع الروتين اليومي الذكي (Daily Routine):
        - يبحث في قائمة المجموعات عن أول مجموعة لم تُفحص مسبقاً.
        - يدخل لها ويفحصها بهدوء لاستخراج أفضل 3 منشورات فيروسية (target_posts).
        - إذا وجد المنشورات المطابقة، يحفظها في قاعدة البيانات وينهي الجلسة فوراً.
        - إذا لم يجد أي منشور يطابق شروط النيتش، ينتقل للمجموعة التالية كاستثناء.
        """
        history = load_spy_history()
        
        # تصفية المجموعات للبحث عن غير المفحوصة
        pending_groups = [g for g in group_urls if not is_group_processed(g, history)]
        if not pending_groups:
            if progress_callback:
                progress_callback("ℹ All groups in the list have already been processed!")
            return "", []

        for idx, group_url in enumerate(pending_groups, 1):
            if progress_callback:
                progress_callback(f"📅 Daily Routine: Visiting Group {idx}/{len(pending_groups)}: {group_url}")
            
            posts = self.scan_posts(
                target_url=group_url,
                max_posts=target_posts,
                min_comments=min_comments,
                max_months=max_months,
                progress_callback=progress_callback
            )

            if len(posts) > 0:
                if progress_callback:
                    progress_callback(f"🎯 Success! Found {len(posts)} viral posts from {group_url}. Finished today's mission!")
                return group_url, posts
            else:
                if progress_callback:
                    progress_callback(f"⚠️ No qualifying niche posts found in {group_url}. Moving to next group...")
                time.sleep(random.uniform(5, 10))

        return "", []

    def _save_results(self, posts: list[dict]):
        """حفظ روابط المنشورات الفيروسية فقط في viral_posts.csv (قائمة روابط مباشرة Links Only بدون أي متغيرات زائدة)"""
        clean_rows = [{"post_url": p["post_url"]} for p in posts if p.get("post_url")]
        if not clean_rows:
            return
        df_new = pd.DataFrame(clean_rows)
        if VIRAL_POSTS_FILE.exists():
            try:
                df_old = pd.read_csv(VIRAL_POSTS_FILE, encoding='utf-8')
                if "post_url" in df_old.columns:
                    df_old = df_old[["post_url"]]
                combined = pd.concat([df_new, df_old], ignore_index=True)
                combined.drop_duplicates(subset=["post_url"], keep="first", inplace=True)
                combined.to_csv(VIRAL_POSTS_FILE, index=False, encoding='utf-8')
                return
            except Exception:
                pass
        df_new.to_csv(VIRAL_POSTS_FILE, index=False, encoding='utf-8')

if __name__ == "__main__":
    url = input("Enter Facebook Group URL to scout: ").strip()
    if url:
        fb = FacebookBrowser(headless=False)
        try:
            fb.start()
            spy = ViralSpyEngine(fb)
            results = spy.scan_posts(url, max_posts=3)
            print(f"\nExtracted {len(results)} top viral posts successfully!")
        finally:
            fb.stop()
