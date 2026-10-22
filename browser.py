import sys
import re
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, BrowserContext, Page
from playwright_stealth import stealth
from config import PROFILES_DIR, PROFILE_DIR
from utils import console

class CheckpointDetectedError(Exception):
    """استثناء يتم إطلاقه عند رصد كابتشا أو طلب تأكيد هوية من فيسبوك"""
    def __init__(self, reason: str, url: str):
        self.reason = reason
        self.url = url
        super().__init__(f"Checkpoint Detected: {reason} at {url}")

class FacebookBrowser:
    def __init__(self, account_name: str = "account_1", headless: bool = False, cdp_url: str = None, executable_path: str = None):
        self.account_name = account_name
        self.account_dir = PROFILES_DIR / account_name
        self.account_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.cdp_url = cdp_url
        self.executable_path = executable_path
        self.playwright = None
        self.context: BrowserContext = None
        self.page: Page = None

    def start(self) -> Page:
        """بدء تشغيل المتصفح (يدعم Chrome العادي أو الربط بمتصفحات Anti-Detect عبر CDP)"""
        console.print(f"[yellow]⏳ جاري فتح المتصفح للحساب: [bold]{self.account_name}[/bold]...[/yellow]")
        self.playwright = sync_playwright().start()

        # إذا كان هناك رابط ربط بمتصفح Anti-Detect Browser (Dolphin / AdsPower / GoLogin)
        if self.cdp_url:
            console.print(f"[cyan]🔗 الاتصال بمتصفح Anti-Detect عبر CDP: {self.cdp_url}...[/cyan]")
            browser_instance = self.playwright.chromium.connect_over_cdp(self.cdp_url)
            self.context = browser_instance.contexts[0] if browser_instance.contexts else browser_instance.new_context()
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            stealth(self.page)
            return self.page

        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--no-sandbox',
            '--start-maximized',
            '--disable-extensions'
        ]

        # اختيار مسار المتصفح (مخصص أو Chrome العادي)
        chrome_channel = None
        if not self.executable_path:
            if Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe").exists():
                chrome_channel = "chrome"

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.account_dir),
            headless=self.headless,
            executable_path=self.executable_path,
            channel=chrome_channel,
            args=args,
            no_viewport=True,
            locale="en-US,en",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )

        if len(self.context.pages) > 0:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()

        stealth(self.page)
        console.print(f"[green]✔ تم تشغيل متصفح الحساب [{self.account_name}] بنجاح![/green]")
        return self.page

    def check_checkpoint(self) -> tuple[bool, str]:
        """
        الرصد الذكي لطلبات الكابتشا أو تأكيد الهوية أو الحظر المؤقت
        يرجع (True, reason) في حالة وجود كابتشا أو حظر
        """
        if not self.page:
            return False, ""

        try:
            current_url = self.page.url.lower()

            # 1. فحص روابط الـ Checkpoint المعروفة
            suspicious_urls = [
                ('/checkpoint/', "صفحة تأكيد الهوية (Facebook Checkpoint)"),
                ('/login/device-based/', "تم تسجيل الخروج ويطلب كلمة السر مجدداً"),
                ('/two_step_verification/', "طلب كود التحقق بخطوتين (2FA)"),
                ('/recover/initiate/', "طلب استعادة الحساب"),
                ('temporary-block', "حظر مؤقت على الحساب")
            ]
            for s_url, reason in suspicious_urls:
                if s_url in current_url:
                    return True, reason

            # 2. فحص نصوص الحظر والـ Captcha داخل الصفحة
            page_content = self.page.content().lower()
            suspicious_texts = [
                ("your account has been locked", "تم قفل الحساب من فيسبوك"),
                ("help us confirm that this is you", "طلب تأكيد هويتك لحماية الحساب"),
                ("security check", "طلب فحص الأمان (Security Check / Captcha)"),
                ("upload your id", "طلب صورة بطاقة الهوية"),
                ("you're temporarily blocked", "حظر مؤقت من فيسبوك على هذا الإجراء"),
                ("action blocked", "تم حظر هذا الإجراء مؤقتاً للاشتباه في السبام")
            ]
            for text, reason in suspicious_texts:
                if text in page_content:
                    return True, reason

            return False, ""
        except Exception:
            return False, ""

    def verify_safety_or_raise(self):
        """فحص الأمان، وإذا تم رصد مشكلة يطلق استثناء CheckpointDetectedError فوراً"""
        is_checkpoint, reason = self.check_checkpoint()
        if is_checkpoint:
            console.print(f"\n[bold red]🛑 تنبيه أمني عاجل للحساب [{self.account_name}]: {reason}![/bold red]")
            raise CheckpointDetectedError(reason, self.page.url)

    def human_warmup_session(self, duration_seconds: int, log_callback=None, stop_check=None):
        """
        محاكاة التصفح البشري العفوي (Human Session Warming):
        التمرير في الـ Feed وقراءة البوستات ووضع لايك نادر وعفوي أثناء فترة الانتظار
        لرفع درجة أمان وثقة الحساب ومنع كشف الروبوت.
        """
        log = log_callback if log_callback else console.print
        log(f"[cyan]🌱 بدء التصفح الطبيعي في الـ Feed لتدفئة الحساب ({duration_seconds // 60} دقيقة و {duration_seconds % 60} ثانية)...[/cyan]")

        try:
            # التوجه للصفحة الرئيسية للـ Feed
            self.page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=30000)
            self.page.wait_for_timeout(3000)

            end_time = time.time() + duration_seconds
            max_likes = random.randint(1, 2) # لايك أو اثنين فقط كحد أقصى للحماية من السبام
            likes_given = 0

            while time.time() < end_time:
                if stop_check and stop_check():
                    log("[yellow]تم إيقاف جلسة التصفح بطلب من المستخدم.[/yellow]")
                    break

                # فحص الأمان ورصد الكابتشا
                self.verify_safety_or_raise()

                # تمرير سلس للأسفل بمسافة عشوائية
                scroll_amount = random.randint(350, 650)
                self.page.evaluate(f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}});")
                
                # وقفة طبيعية لمحاكاة قراءة المنشور
                read_pause = random.uniform(4.0, 7.5)
                time.sleep(read_pause)

                # احتمال 20% للصعود قليلاً للأعلى (كأنه يعيد قراءة سطر)
                if random.random() < 0.20:
                    scroll_up = random.randint(120, 220)
                    self.page.evaluate(f"window.scrollBy({{top: -{scroll_up}, behavior: 'smooth'}});")
                    time.sleep(random.uniform(2.0, 3.5))

                # احتمال 15% لوضع لايك عفوي على بوست في الصفحة
                if likes_given < max_likes and random.random() < 0.15:
                    try:
                        like_buttons = self.page.locator('div[aria-label="Like"], div[aria-label="أعجبني"], div[role="button"]:has-text("Like")')
                        for i in range(min(like_buttons.count(), 3)):
                            btn = like_buttons.nth(i)
                            if btn.is_visible():
                                btn.click(timeout=2000)
                                likes_given += 1
                                log("[dim]👍 وضع إعجاب عفوي على منشور في الـ Feed أثناء التصفح.[/dim]")
                                time.sleep(random.uniform(3.0, 5.0))
                                break
                    except Exception:
                        pass

                remaining = int(end_time - time.time())
                if remaining > 0 and remaining % 30 == 0:
                    log(f"[dim]متبقي في التصفح الطبيعي: {remaining} ثانية...[/dim]")

            log("[green]✔ انتهت فترة التصفح الطبيعي! التوجه فوراً لتنفيذ الخطوة التالية...[/green]")

        except CheckpointDetectedError:
            raise
        except Exception as e:
            log(f"[dim]ملاحظة أثناء التصفح: {str(e)[:60]}[/dim]")

    def close(self):
        """إغلاق المتصفح بأمان"""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
