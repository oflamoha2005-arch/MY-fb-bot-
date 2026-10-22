import time
import random
from playwright.sync_api import Page
from utils import console, parse_spintax
from browser import CheckpointDetectedError

WARMUP_COMMENTS_SPINTAX = "{Nice post!|Great one|Love this|So true!|Haha nice|Interesting post|Thanks for sharing|Awesome!|Very cool!}"

class AccountWarmer:
    def __init__(self, page: Page, browser=None, log_callback=None, stop_check_callback=None):
        self.page = page
        self.browser = browser
        self.log = log_callback if log_callback else console.print
        self.stop_check = stop_check_callback if stop_check_callback else (lambda: False)
        self.is_running = True

    def run_warming_session(
        self,
        duration_minutes: int = 15,
        enable_likes: bool = True,
        enable_comments: bool = True,
        enable_video_watch: bool = True
    ):
        """
        تشغيل جلسة تسخين وتدفئة حساب فيسبوك مستقلة (Standalone Account Warmer)
        لبناء Trust Score عالي للحسابات الجديدة أو الخاملة قبل البدء في الحملات.
        """
        self.log(f"\n[bold yellow]🔥 بدء جلسة تسخين الحساب لمدة {duration_minutes} دقيقة...[/bold yellow]")
        
        # التوجه للصفحة الرئيسية
        self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=45000)
        self.page.wait_for_timeout(3500)

        total_seconds = duration_minutes * 60
        end_time = time.time() + total_seconds

        likes_count = 0
        comments_count = 0
        max_likes = random.randint(2, 4) if enable_likes else 0
        max_comments = random.randint(1, 2) if enable_comments else 0

        self.log(f"• المستهدف: حتى {max_likes} إعجابات و {max_comments} تعليقات عفوية هادئة.")

        while time.time() < end_time and self.is_running and not self.stop_check():
            # فحص الأمان والكابتشا
            if self.browser:
                self.browser.verify_safety_or_raise()

            activity_choice = random.choices(["scroll", "watch_video", "like", "comment"], weights=[65, 15, 12, 8])[0]

            # 1. التمرير الطبيعي والقراءة في الـ Feed
            if activity_choice == "scroll":
                scroll_amount = random.randint(300, 650)
                self.page.evaluate(f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}});")
                pause = random.uniform(3.5, 7.0)
                time.sleep(pause)

                # احتمال الصعود قليلاً للأعلى
                if random.random() < 0.2:
                    scroll_up = random.randint(100, 200)
                    self.page.evaluate(f"window.scrollBy({{top: -{scroll_up}, behavior: 'smooth'}});")
                    time.sleep(random.uniform(2.0, 3.5))

            # 2. مشاهدة فيديو / Reel قصير
            elif activity_choice == "watch_video" and enable_video_watch:
                try:
                    video_elements = self.page.locator('video, div[data-video-id], div[aria-label*="video"]')
                    if video_elements.count() > 0 and video_elements.first.is_visible():
                        watch_time = random.randint(12, 25)
                        self.log(f"[dim]🎥 التوقف لمشاهدة مقطع فيديو لمدة {watch_time} ثانية...[/dim]")
                        time.sleep(watch_time)
                except Exception:
                    pass

            # 3. وضع إعجاب عفوي (Like)
            elif activity_choice == "like" and enable_likes and likes_count < max_likes:
                try:
                    like_btns = self.page.locator('div[aria-label="Like"], div[aria-label="أعجبني"], div[role="button"]:has-text("Like")')
                    for b_idx in range(min(like_btns.count(), 3)):
                        btn = like_btns.nth(b_idx)
                        if btn.is_visible():
                            btn.click(timeout=2000)
                            likes_count += 1
                            self.log(f"[green]👍 وضع إعجاب عفوي رقم ({likes_count}/{max_likes}) على بوست في الـ Feed.[/green]")
                            time.sleep(random.uniform(4.0, 6.0))
                            break
                except Exception:
                    pass

            # 4. وضع تعليق خفيف وعفوي (Comment)
            elif activity_choice == "comment" and enable_comments and comments_count < max_comments:
                try:
                    comment_inputs = self.page.locator('div[role="textbox"][aria-label*="Write a comment"], div[role="textbox"][aria-label*="اكتب تعليقاً"]')
                    if comment_inputs.count() > 0 and comment_inputs.first.is_visible():
                        c_box = comment_inputs.first
                        c_box.click()
                        self.page.wait_for_timeout(800)
                        friendly_comment = parse_spintax(WARMUP_COMMENTS_SPINTAX)
                        c_box.fill(friendly_comment)
                        self.page.wait_for_timeout(1500)
                        c_box.press("Enter")
                        comments_count += 1
                        self.log(f"[cyan]💬 وضع تعليق خفيف رقم ({comments_count}/{max_comments}): \"{friendly_comment}\"[/cyan]")
                        time.sleep(random.uniform(6.0, 10.0))
                except Exception:
                    pass

            # تقرير التوقيت المتبقي كل دقيقة
            remaining = int(end_time - time.time())
            if remaining > 0 and remaining % 60 == 0:
                self.log(f"[dim]⏳ متبقي في جلسة تسخين الحساب: {remaining // 60} دقيقة...[/dim]")

        self.log(f"\n[bold green]🏁 اكتملت جلسة تسخين الحساب بنجاح![/bold green]")
        self.log(f"• إجمالي الإعجابات: {likes_count}")
        self.log(f"• إجمالي التعليقات العفوية: {comments_count}")
        self.log(f"• الحساب الآن أصبح دافئاً وأكثر أماناً للاستخدام.")
