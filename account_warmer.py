import os
import sys
import time
import random
import urllib.parse
from pathlib import Path
from playwright.sync_api import Page
from utils import console, parse_spintax
from browser import FacebookBrowser, CheckpointDetectedError
from competitor_spy import load_keywords, is_niche_relevant

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

WARMUP_COMMENTS_SPINTAX = "{Great story!|Loved reading this|Such a gripping story!|Interesting read, thanks for sharing|So well written!|Really enjoyed this post!|Fascinating plot|Nice post!|Awesome story!|Great recommendation}"

class AccountWarmer:
    """
    محرّك تدفئة الحسابات الذكي المتخصص في النيتش (Niche-Targeted Account Warmer)
    - يركز فقط على المنشورات المتعلقة بنيتش الروايات والقصص (keywords.txt).
    - يتجاهل المنشورات العشوائية ولا يعلق أو يعجب بها.
    - إذا لم يجد منشورات نيتش في الـ Feed، يبحث بذكاء عن كلمات مفتاحية في Facebook Search لتدريب الخوارزميات.
    - يشاهد Stories عشوائية للأصدقاء والصفحات لمدة ~11 ثانية لمحاكاة إنسان حقيقي 100%.
    - تمرير بشري طبيعي بطيء (Micro-scrolling) مع قراءة وتصفح.
    """
    def __init__(self, page: Page, browser=None, log_callback=None, stop_check_callback=None):
        self.page = page
        self.browser = browser
        self.log = log_callback if log_callback else console.print
        self.stop_check = stop_check_callback if stop_check_callback else (lambda: False)
        self.is_running = True
        self.keywords = load_keywords()

    def set_keywords(self, keywords: list[str]):
        """تحديث الكلمات المفتاحية ديناميكياً"""
        if keywords:
            self.keywords = [k.strip().lower() for k in keywords if k.strip()]

    def _human_micro_scroll(self, steps_min: int = 2, steps_max: int = 4):
        """تمرير بشري تدريجي بطيء"""
        steps = random.randint(steps_min, steps_max)
        for _ in range(steps):
            delta = random.randint(150, 300)
            self.page.mouse.wheel(0, delta)
            time.sleep(random.uniform(0.2, 0.45))

        # فرصة خفيفة للتمرير لأعلى لمحاكاة إعادة القراءة
        if random.random() < 0.2:
            self.page.mouse.wheel(0, -random.randint(60, 120))
            time.sleep(random.uniform(0.3, 0.6))

        time.sleep(random.uniform(2.5, 4.5))

    def _watch_facebook_story(self) -> bool:
        """
        مشاهدة ستوري (Story) طبيعية لمدة حوالي 11 ثانية
        """
        try:
            story_selectors = [
                'div[data-pagelet="Stories"] div[role="button"]',
                'div[aria-label*="Stories"] div[role="button"]',
                'div[aria-label*="قصص"] div[role="button"]',
                'div[aria-label*="story by"]',
                'div[role="button"]:has(span:has-text("Story"))'
            ]
            story_btn = None
            for sel in story_selectors:
                loc = self.page.locator(sel)
                for idx in range(min(loc.count(), 4)):
                    candidate = loc.nth(idx)
                    if candidate.is_visible():
                        story_btn = candidate
                        break
                if story_btn:
                    break

            if story_btn:
                self.log("[dim]👀 النقر على ستوري (Story) لمشاهدتها...[/dim]")
                story_btn.click(timeout=3000)
                
                # مشاهدة لمدة تقارب 11 ثانية (بين 9 و 13 ثانية)
                watch_time = random.uniform(9.5, 12.5)
                self.log(f"[magenta]👁️ مشاهدة الستوري لمدة {watch_time:.1f} ثانية كقارئ بشري طبيعي...[/magenta]")
                time.sleep(watch_time)

                # إغلاق الستوري بالضغط على Escape أو زر الإغلاق
                self.page.keyboard.press("Escape")
                time.sleep(1.0)
                try:
                    close_btn = self.page.locator('div[aria-label="Close"], div[aria-label="إغلاق"]').first
                    if close_btn and close_btn.is_visible():
                        close_btn.click(timeout=1000)
                except Exception:
                    pass
                time.sleep(1.5)
                return True
        except Exception:
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
        return False

    def _search_niche_posts(self, query: str):
        """
        البحث عن كلمات النيتش في Facebook Search لتدريب خوارزميات فيسبوك
        على تصنيف الحساب كمهتم بالروايات والقصص
        """
        encoded = urllib.parse.quote(query)
        search_url = f"https://www.facebook.com/search/posts/?q={encoded}"
        self.log(f"[cyan]🔎 توجيه البحث إلى منشورات النيتش: \"{query}\" لتدريب الخوارزميات...[/cyan]")
        try:
            self.page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(random.uniform(4.0, 6.0))
        except Exception:
            pass

    def run_warming_session(
        self,
        duration_minutes: int = 15,
        enable_likes: bool = True,
        enable_comments: bool = True,
        enable_video_watch: bool = True,
        enable_stories: bool = True
    ):
        """
        تشغيل جلسة تسخين وتدفئة ذكية تركز على نيتش الروايات/القصص:
        - يفلتر منشورات الـ Feed بموجب keywords.txt
        - يتجاهل المنشورات العشوائية
        - ينتقل للبحث (Search) عن كلمات النيتش إذا كان الـ Feed فقيراً
        - يشاهد ستوريات لمدة ~11 ثانية
        - لايكات وتعليقات خفيفة هادفة فقط على منشورات النيتش
        """
        self.log(f"\n[bold yellow]🔥 بدء جلسة تدفئة الحساب الذكية المتخصصة في النيتش ({duration_minutes} دقيقة)...[/bold yellow]")
        self.log(f"🎯 الكلمات المفتاحية المستهدفة: {', '.join(self.keywords[:5])}...")

        # التوجه للصفحة الرئيسية
        self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=45000)
        time.sleep(random.uniform(3.5, 6.0))

        total_seconds = duration_minutes * 60
        end_time = time.time() + total_seconds

        likes_count = 0
        comments_count = 0
        stories_watched = 0
        max_likes = random.randint(2, 4) if enable_likes else 0
        max_comments = random.randint(1, 2) if enable_comments else 0
        max_stories = random.randint(1, 2) if enable_stories else 0

        self.log(f"• المستهدف: حتى {max_likes} إعجابات و {max_comments} تعليقات عفوية على منشورات النيتش فقط، و {max_stories} ستوري.")

        consecutive_irrelevant_scrolls = 0
        is_in_search_mode = False

        while time.time() < end_time and self.is_running and not self.stop_check():
            if self.browser:
                self.browser.verify_safety_or_raise()

            # 1. مشاهدة ستوري (مرة أو مرتين خلال الجلسة)
            if enable_stories and stories_watched < max_stories and random.random() < 0.25 and not is_in_search_mode:
                if self._watch_facebook_story():
                    stories_watched += 1
                    time.sleep(random.uniform(2.0, 4.0))

            # 2. فحص المنشورات المرئية الحالية
            articles = self.page.locator('div[role="feed"] > div, div[role="article"]').all()
            if not articles:
                articles = self.page.locator('div[data-ad-preview="message"]').all()

            found_niche_post_in_view = False

            for art in articles[:4]:
                if time.time() >= end_time or not self.is_running or self.stop_check():
                    break

                try:
                    msg_elem = art.locator('div[data-ad-preview="message"], div[dir="auto"]').first
                    if not msg_elem or not msg_elem.is_visible():
                        continue

                    raw_text = msg_elem.inner_text().strip()
                    if not raw_text or len(raw_text) < 3:
                        continue

                    # فحص مطابقة النيتش (Keywords Match)
                    if not is_niche_relevant(raw_text, self.keywords):
                        # منشور عشوائي لا علاقة له بالروايات -> تجاهله فوراً
                        continue

                    found_niche_post_in_view = True
                    consecutive_irrelevant_scrolls = 0
                    preview = raw_text[:70].replace("\n", " ")
                    self.log(f"[bold green]📖 منشور نيتش مطابق:[/bold green] \"{preview}...\"")

                    # محاكاة القراءة البشرية المتأنية للمنشور
                    reading_time = random.uniform(4.5, 8.5)
                    self.log(f"[dim]تصفح وقراءة المنشور لمدة {reading_time:.1f} ثوانٍ...[/dim]")
                    time.sleep(reading_time)

                    # هل يتضمن فيديو أو ريلز؟
                    if enable_video_watch and random.random() < 0.35:
                        try:
                            vid = art.locator('video, div[data-video-id]').first
                            if vid and vid.is_visible():
                                v_time = random.randint(12, 22)
                                self.log(f"[dim]🎥 مشاهدة مقطع فيديو متعلق بالنيتش لمدة {v_time} ثانية...[/dim]")
                                time.sleep(v_time)
                        except Exception:
                            pass

                    # إعجاب بالمنشور المطابق للنيتش
                    if enable_likes and likes_count < max_likes and random.random() < 0.5:
                        try:
                            like_btn = art.locator('div[aria-label="Like"], div[aria-label="أعجبني"], div[role="button"]:has-text("Like")').first
                            if like_btn and like_btn.is_visible():
                                like_btn.click(timeout=2000)
                                likes_count += 1
                                self.log(f"[green]👍 وضع إعجاب ({likes_count}/{max_likes}) على منشور الروايات/القصص.[/green]")
                                time.sleep(random.uniform(3.5, 6.0))
                        except Exception:
                            pass

                    # تعليق لطيف على منشور النيتش
                    if enable_comments and comments_count < max_comments and random.random() < 0.3:
                        try:
                            c_box = art.locator('div[role="textbox"][aria-label*="Write a comment"], div[role="textbox"][aria-label*="اكتب تعليقاً"]').first
                            if c_box and c_box.is_visible():
                                c_box.click()
                                time.sleep(0.8)
                                friendly_comment = parse_spintax(WARMUP_COMMENTS_SPINTAX)
                                c_box.fill(friendly_comment)
                                time.sleep(1.2)
                                c_box.press("Enter")
                                comments_count += 1
                                self.log(f"[cyan]💬 وضع تعليق خفيف ({comments_count}/{max_comments}): \"{friendly_comment}\"[/cyan]")
                                time.sleep(random.uniform(6.0, 10.0))
                        except Exception:
                            pass

                except Exception:
                    continue

            # إذا لم نجد أي منشور متعلق بالنيتش لعدة تمريرات متتالية، ننتقل للبحث الذكي
            if not found_niche_post_in_view:
                consecutive_irrelevant_scrolls += 1

            if consecutive_irrelevant_scrolls >= 5 and not is_in_search_mode:
                # التحول إلى صفحة نتائج البحث عن النيتش
                query = random.choice([
                    "fiction story", "suspense novel", "mystery story",
                    "short story books", "dark thriller story", "book reading"
                ])
                self._search_niche_posts(query)
                is_in_search_mode = True
                consecutive_irrelevant_scrolls = 0
                time.sleep(3)

            # التمرير البشري
            self._human_micro_scroll()

            # تقرير التوقيت المتبقي كل دقيقة
            remaining = int(end_time - time.time())
            if remaining > 0 and remaining % 60 == 0:
                self.log(f"[dim]⏳ متبقي في جلسة تدفئة الحساب: {remaining // 60} دقيقة...[/dim]")

        self.log(f"\n[bold green]🏁 اكتملت جلسة تدفئة الحساب الذكية بنجاح![/bold green]")
        self.log(f"• إجمالي الإعجابات بالنيتش: {likes_count}")
        self.log(f"• إجمالي التعليقات بالنيتش: {comments_count}")
        self.log(f"• ستوريات تمت مشاهدتها: {stories_watched}")
        self.log(f"• تم توجيه وتدريب خوارزميات الحساب نحو نيتش الروايات بنجاح.")

if __name__ == "__main__":
    fb = FacebookBrowser(headless=False)
    try:
        fb.start()
        warmer = AccountWarmer(fb.page, browser=fb)
        warmer.run_warming_session(duration_minutes=5)
    finally:
        fb.stop()
