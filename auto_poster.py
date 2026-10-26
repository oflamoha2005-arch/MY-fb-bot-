import os
import sys
import time
import random
import json
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import Page
from utils import console, parse_spintax, record_account_action, update_account_status, get_account_health
from config import BASE_DIR, POSTER_HISTORY_FILE
from browser import FacebookBrowser, CheckpointDetectedError

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

GROUPS_FILE = BASE_DIR / "groups.txt"
POSTS_FILE = BASE_DIR / "posts.txt"

DEFAULT_STORY_POST = """{Late last night, something strange happened in my house|I wasn't going to share this story, but I need some answers|A chilling incident occurred in my quiet neighborhood recently}.

{I was working late downstairs when I heard what sounded like scratching from behind the locked pantry door|I heard faint footsteps coming from the attic, even though nobody else was home|My dog suddenly stared at the empty corner of the hallway and began growling like crazy}.

{I slowly walked toward the door, my heart pounding, and turned the handle... What was inside left me speechless|I grabbed a flashlight and approached cautiously... What I found gave me chills to the bone}.

{What do you think happened next? Drop your theory in the comments, and I'll send you the full chapter for free to see if you guessed right|If anyone enjoys dark mystery stories and wants to read the rest, let me know below and I'd love to share the link with you}!"""

DEFAULT_GROUPS = """# ضع هنا روابط مجموعات فيسبوك التي تريد النشر فيها (رابط في كل سطر)
# مثال:
# https://www.facebook.com/groups/fictionwriters/
# https://www.facebook.com/groups/shortstorywriters/
"""

def load_poster_history() -> dict:
    """تحميل سجل المجموعات التي تم النشر فيها لتذكر التقدم وعدم النسيان"""
    if not POSTER_HISTORY_FILE.exists():
        return {}
    try:
        with open(POSTER_HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_poster_history(group_url: str, status: str = "posted", account: str = "unknown"):
    """حفظ المجموعة في سجل الذاكرة مباشرة بعد النشر"""
    history = load_poster_history()
    clean_url = group_url.strip().rstrip("/").lower()
    history[clean_url] = {
        "url": group_url.strip(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "account": account
    }
    try:
        with open(POSTER_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def is_already_posted(group_url: str, history: dict = None) -> bool:
    """
    فحص هل تم النشر في هذه المجموعة لحملة المنشور الحالي.
    تبقى المجموعة مستبعدة ومسجلة طيلة فترة الحملة حتى يتم النشر في جميع المجموعات 100%،
    وعند اكتمال آخر مجموعة يتم تفريغ المنشور وإعادة ضبط الذاكرة تلقائياً للمنشور الجديد.
    """
    if history is None:
        history = load_poster_history()
    clean_url = group_url.strip().rstrip("/").lower()
    entry = history.get(clean_url)
    if not entry:
        return False
    if isinstance(entry, dict):
        status = entry.get("status", "")
        return status in ["posted", "pending_approval"]
    return False

def clear_poster_history():
    """مسح سجل النشر لإعادة البدء من جديد إذا أراد المستخدم أو عند اكتمال النشر في كافة المجموعات"""
    if POSTER_HISTORY_FILE.exists():
        try:
            with open(POSTER_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)
        except Exception:
            pass

def clear_story_template():
    """تفريغ نص المنشور بعد اكتمال النشر في جميع المجموعات 100%"""
    try:
        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            f.write("")
    except Exception:
        pass

def get_story_template() -> str:
    """قراءة نص المنشور من ملف posts.txt. إذا تم إفراغه يرجع نص فارغ للإشارة إلى اكتمال الحملة"""
    if not POSTS_FILE.exists():
        return ""
    try:
        with open(POSTS_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return ""

def get_groups_list() -> list[str]:
    """قراءة قائمة المجموعات من ملف groups.txt"""
    if not GROUPS_FILE.exists():
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_GROUPS)
        return []
    groups = []
    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    groups.append(line)
    except Exception:
        pass
    return groups

class AutoPoster:
    """
    محرّك النشر التلقائي في مجموعات فيسبوك
    - يدعم Spintax لتوليد نصوص فريدة
    - يدعم إرفاق غلاف الرواية أو الصور (اختياري)
    - يتعرف على موافقة الأدمن (Pending Admin Approval)
    - فواصل أمان مع تسخين طبيعي وتصفح للـ Feed بين كل مجموعة
    """
    def __init__(self, page: Page, browser=None, log_callback=None, account_name: str = "unknown"):
        self.page = page
        self.browser = browser
        self.log = log_callback if log_callback else console.print
        self.account_name = account_name
        self.is_running = True

    def post_to_group(self, group_url: str, story_template: str, image_path: str = None) -> tuple[bool, str]:
        """
        نشر قصة في مجموعة فيسبوك محددة
        ترجع (نجاح/فشل, الحالة: posted / pending_approval / no_box / error)
        """
        if self.browser:
            self.browser.verify_safety_or_raise()

        clean_url = group_url.strip()
        self.log(f"[cyan]🌐 التوجه إلى المجموعة:[/cyan] {clean_url}")
        try:
            self.page.goto(clean_url, wait_until="domcontentloaded", timeout=50000)
            time.sleep(random.uniform(3.5, 6.0))

            if self.browser:
                self.browser.verify_safety_or_raise()

            # البحث عن زر إنشاء منشور (Write something... / Create a public post)
            post_triggers = [
                'div[role="button"]:has-text("Write something...")',
                'div[role="button"]:has-text("Create a public post")',
                'div[role="button"]:has-text("اكتب شيئاً...")',
                'div[role="button"]:has-text("إنشاء منشور عام")',
                'span:has-text("Write something...")',
                'span:has-text("Create a public post")',
                'div[aria-label*="Create a post"]',
                'div[role="button"]:has-text("Express yourself")'
            ]

            trigger_btn = None
            for sel in post_triggers:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    trigger_btn = loc.first
                    break

            if not trigger_btn:
                self.log(f"[yellow]⚠️ تعذر العثور على خانة النشر في هذه المجموعة (قد تتطلب إذناً خاصاً أو تكون مغلقة).[/yellow]")
                save_poster_history(clean_url, status="no_post_box", account=self.account_name)
                return False, "no_post_box"

            self.log("[dim]الضغط على خانة إنشاء منشور...[/dim]")
            trigger_btn.click()
            time.sleep(random.uniform(2.5, 4.0))

            unique_post = parse_spintax(story_template)

            text_boxes = [
                'div[role="textbox"][contenteditable="true"]',
                'div[data-lexical-editor="true"]',
                'div[aria-label*="What\'s on your mind"]',
                'div[aria-label*="Create a public post"]',
                'div[aria-label*="اكتب شيئاً"]',
                'div[aria-label*="بم تفكر"]',
                'div[role="combobox"][contenteditable="true"]'
            ]

            textbox = None
            for sel in text_boxes:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    textbox = loc.first
                    break

            if not textbox:
                self.log(f"[yellow]⚠️ لم يتم العثور على مربع كتابة المنشور داخل النافذة.[/yellow]")
                return False, "no_textbox"

            self.log("[dim]كتابة القصة المشوقة ومحاكاة الكتابة الإنسانية...[/dim]")
            textbox.click()
            time.sleep(0.5)
            textbox.fill(unique_post)
            time.sleep(random.uniform(1.5, 3.0))

            # خيار إرفاق الصورة إن وُجدت
            if image_path and os.path.isfile(image_path):
                self.log(f"[dim]📸 محاولة إرفاق الصورة: {Path(image_path).name}...[/dim]")
                try:
                    file_input = self.page.locator('input[type="file"][accept*="image"]').first
                    if not file_input or file_input.count() == 0:
                        photo_btn = self.page.locator('div[aria-label*="Photo/video"], div[aria-label*="صورة/فيديو"], div[aria-label*="Photo/vidéo"], div[role="button"]:has-text("Photo/video")').first
                        if photo_btn and photo_btn.is_visible():
                            photo_btn.click()
                            time.sleep(1.2)
                        file_input = self.page.locator('input[type="file"][accept*="image"]').first

                    if file_input and file_input.count() > 0:
                        file_input.set_input_files(image_path)
                        self.log(f"[green]✔ تم إرفاق الصورة بنجاح.[/green]")
                        time.sleep(random.uniform(3.0, 5.0)) # مهلة لتوليد المعاينة
                    else:
                        self.log(f"[yellow]⚠️ لم تظهر خانة رفع الصورة، سيتم الاستمرار كنص فقط.[/yellow]")
                except Exception as ie:
                    self.log(f"[yellow]⚠️ تعذر إرفاق الصورة ({str(ie)[:50]}), سيتم النشر كنص.[/yellow]")

            # البحث عن زر النشر Post
            post_buttons = [
                'div[aria-label="Post"]',
                'div[role="button"]:has-text("Post")',
                'div[aria-label="نشر"]',
                'div[role="button"]:has-text("نشر")',
                'div[aria-label="Publier"]',
                'div[role="button"]:has-text("Publier")',
                'span:has-text("Post")',
                'span:has-text("Publier")',
                'span:has-text("نشر")'
            ]

            post_btn = None
            for sel in post_buttons:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    post_btn = loc.first
                    break

            if not post_btn:
                self.log("[yellow]⚠️ تعذر العثور على زر Post.[/yellow]")
                return False, "no_post_btn"

            self.log("[dim]الضغط على زر النشر (Post)...[/dim]")
            post_btn.click()
            time.sleep(random.uniform(4.0, 7.0))

            # فحص إشعار موافقة المشرف (Pending Admin Approval)
            approval_selectors = [
                'span:has-text("pending approval")',
                'div:has-text("pending approval")',
                'span:has-text("submitted to admins")',
                'div:has-text("submitted to admins")',
                'span:has-text("en attente d\'approbation")',
                'span:has-text("في انتظار موافقة")',
                'span:has-text("قيد المراجعة")',
                'div:has-text("قيد المراجعة")'
            ]
            is_pending = False
            for sel in approval_selectors:
                try:
                    loc = self.page.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible():
                        is_pending = True
                        break
                except Exception:
                    pass

            if is_pending:
                save_poster_history(clean_url, status="pending_approval", account=self.account_name)
                self.log(f"[cyan]⏳ تم تقديم المنشور وهو في انتظار موافقة المسؤول (Pending Admin Approval).[/cyan]")
                return True, "pending_approval"
            else:
                save_poster_history(clean_url, status="posted", account=self.account_name)
                self.log(f"[bold green]✔ تم نشر القصة مباشرة بنجاح في المجموعة![/bold green]")
                return True, "posted"

        except CheckpointDetectedError:
            raise
        except Exception as e:
            self.log(f"[red]❌ خطأ أثناء النشر: {str(e)[:100]}[/red]")
            return False, "error"

    def run_poster_campaign(
        self, 
        groups: list[str], 
        image_path: str = None,
        min_delay_min: int = 4, 
        max_delay_min: int = 6, 
        enable_warming: bool = True
    ):
        """
        تشغيل حملة النشر لحساب واحد مع تخطي المجموعات المنشورة مسبقاً
        والتسخين الطبيعي أثناء فترات الانتظار
        """
        if not groups:
            self.log("[red]❌ لم يتم تحديد أي مجموعات. يرجى إضافة روابط المجموعات أولاً.[/red]")
            return

        pending_groups = [g for g in groups if not is_already_posted(g)]
        already_done = len(groups) - len(pending_groups)

        if already_done > 0:
            self.log(f"[cyan]🧠 الذاكرة الدائمة: تم تخطي {already_done} مجموعة تم النشر فيها مسبقاً.[/cyan]")

        if not pending_groups:
            self.log("[bold green]🎉 تم النشر في جميع المجموعات المحددة مسبقاً! لا توجد مجموعات جديدة.[/bold green]")
            return

        story_template = get_story_template()
        self.log(f"[bold yellow]🚀 سيبدأ النشر في {len(pending_groups)} مجموعة مع فواصل أمان ({min_delay_min}-{max_delay_min} دقيقة)...[/bold yellow]")

        for idx, group_url in enumerate(pending_groups, start=1):
            if not self.is_running:
                self.log("[yellow]تم إيقاف عملية النشر يدوياً.[/yellow]")
                break

            self.log(f"\n[cyan]━━━━━━━━━━━━━ [المجموعة {idx} من {len(pending_groups)}] ━━━━━━━━━━━━━[/cyan]")
            success, status = self.post_to_group(group_url, story_template, image_path=image_path)

            if idx < len(pending_groups) and self.is_running:
                wait_sec = random.randint(min_delay_min * 60, max_delay_min * 60)
                if enable_warming and self.browser:
                    self.browser.human_warmup_session(
                        wait_sec, 
                        label="Inter-Post Warming",
                        log_callback=self.log, 
                        stop_check=lambda: not self.is_running
                    )
                else:
                    self.log(f"[yellow]⏳ فاصل أمان طبيعي: الانتظار {wait_sec // 60} دقيقة و {wait_sec % 60} ثانية...[/yellow]")
                    for remaining in range(wait_sec, 0, -10):
                        if not self.is_running:
                            break
                        time.sleep(min(10, remaining))

def run_multi_account_poster(
    accounts: list[str],
    groups: list[str],
    posts_per_account: int = 3,
    image_path: str = None,
    min_delay_min: int = 4,
    max_delay_min: int = 6,
    enable_warming: bool = True,
    enable_sandwich: bool = True,
    log_callback=None,
    status_callback=None,
    checkpoint_callback=None,
    stop_check=None
) -> dict:
    """
    محرّك النشر التلقائي المتقدم متعدد الحسابات (Multi-Account Group Poster):
    - يوزع المجموعات بالتساوي (مثلاً 3 مجموعات لكل حساب).
    - يتذكر المجموعات المنشورة بشكل دائم ويكمل تلقائياً المجموعات المتبقية في اليوم التالي.
    - يطبق ساندويتش الجلسة (90 ثانية تسخين + 60 ثانية تبريد) لكل حساب.
    - فاصل 4-6 دقائق وتصفح للـ Feed بين كل منشور.
    - انتقال تلقائي للحساب الموالي إذا واجه أي حساب مشكلة أمان (Failover).
    """
    log = log_callback if log_callback else console.print
    history = load_poster_history()

    # استبعاد المجموعات المنشورة مسبقاً
    pending = [g for g in groups if not is_already_posted(g, history)]
    already_done = len(groups) - len(pending)

    if already_done > 0:
        log(f"[cyan]🧠 الذاكرة النشطة: تم تخطي {already_done} مجموعة منشورة سابقاً.[/cyan]")

    story_template = get_story_template()
    if not story_template or not story_template.strip():
        log("[bold yellow]⚠️ خانة المنشور فارغة حالياً (أو تم تفريغها بعد اكتمال نشر المنشور السابق).[/bold yellow]")
        log("[cyan]👉 يرجى كتابة أو وضع منشور جديد في التطبيق للبدء في النشر![/cyan]")
        return {"total_posted": 0, "completed": False, "empty_post": True}

    if not pending:
        log("[bold green]🎉 مبروك! تم النشر في جميع المجموعات المحددة في القائمة 100%! لا توجد أي مجموعة متبقية.[/bold green]")
        log("[cyan]✨ تم تفريغ مكان المنشور بنجاح، التطبيق جاهز لمنشورك القادم![/cyan]")
        clear_story_template()
        clear_poster_history()
        try:
            from telegram_notifier import send_telegram_message
            t_msg = (
                "🎉 <b>اكتمل نشر المنشور في جميع المجموعات بالكامل!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📢 تم النشر في جميع الـ {len(groups)} مجموعة المحددة 100% بنجاح.\n\n"
                "✨ <b>تم تفريغ خانة المنشور الآن</b>، مكان المنشور فارغ وجاهز لتضع فيه المنشور الجديد!"
            )
            send_telegram_message(t_msg)
        except Exception:
            pass
        return {"total_posted": 0, "completed": True, "remaining": 0}

    log(f"[bold yellow]📢 جاري توزيع {len(pending)} مجموعة متبقية على {len(accounts)} حساب بمعدل {posts_per_account} مجموعات لكل حساب...[/bold yellow]")

    total_posted = 0
    group_idx = 0

    for acc_idx, account in enumerate(accounts, start=1):
        if stop_check and stop_check():
            log("[yellow]تم إيقاف حملة النشر بواسطة المستخدم.[/yellow]")
            break

        # فحص صحة الحساب وتخطي أي حساب في وضع Checkpoint لحمايته
        acc_health = get_account_health(account)
        if acc_health.get("status") == "CHECKPOINT":
            log(f"\n[bold yellow]⚠️ تخطي الحساب [{account}] لوجوده في وضع مراجعة أمنية (CHECKPOINT) لحمايته، والتحول للحساب الموالي...[/bold yellow]")
            continue

        if group_idx >= len(pending):
            break

        # تحديد حصة هذا الحساب من المجموعات
        assigned_groups = pending[group_idx : group_idx + posts_per_account]
        group_idx += len(assigned_groups)

        log(f"\n[bold magenta]══════════════ [الحساب {acc_idx}/{len(accounts)}: {account}] ══════════════[/bold magenta]")
        log(f"🎯 الحصة المحددة: {len(assigned_groups)} مجموعة لهذا الحساب.")

        if status_callback:
            status_callback("RUNNING", f"Posting via {account}")

        browser = FacebookBrowser(account_name=account, headless=False)

        try:
            browser.start()

            # ساندويتش الجلسة: تسخين تمهيدي 90 ثانية
            if enable_sandwich and (not stop_check or not stop_check()):
                if status_callback:
                    status_callback("WARMING", f"Pre-Warm {account}")
                log(f"[dim]🛡️ [Sandwich] تشغيل تسخين تمهيدي 90 ثانية على {account}...[/dim]")
                browser.human_warmup_session(90, label="Post Pre-Warming", log_callback=log, stop_check=stop_check)

            poster = AutoPoster(browser.page, browser=browser, log_callback=log, account_name=account)

            for p_idx, g_url in enumerate(assigned_groups, start=1):
                if stop_check and stop_check():
                    break

                log(f"\n[cyan]─── [الحساب: {account} | المنشور {p_idx}/{len(assigned_groups)}] ───[/cyan]")
                success, status = poster.post_to_group(g_url, story_template, image_path=image_path)
                if success:
                    total_posted += 1
                    record_account_action(account, "group_post", 1)

                # فاصل زمني بين المجموعات مع تسخين
                if p_idx < len(assigned_groups) and (not stop_check or not stop_check()):
                    wait_sec = random.randint(min_delay_min * 60, max_delay_min * 60)
                    if enable_warming:
                        log(f"[yellow]⏳ تصفح طبيعي للـ Feed وتسخين بين المنشورات ({wait_sec // 60} د)...[/yellow]")
                        browser.human_warmup_session(wait_sec, label="Inter-Post Warming", log_callback=log, stop_check=stop_check)
                    else:
                        time.sleep(wait_sec)

            # ساندويتش الجلسة: تبريد ختامي 60 ثانية
            if enable_sandwich and (not stop_check or not stop_check()):
                if status_callback:
                    status_callback("COOLING", f"Post-Cool {account}")
                log(f"[dim]🛡️ [Sandwich] تشغيل تبريد ختامي 60 ثانية على {account}...[/dim]")
                browser.human_warmup_session(60, label="Post-Cooling", log_callback=log, stop_check=stop_check)

            update_account_status(account, "HEALTHY")

        except CheckpointDetectedError as cde:
            log(f"[bold red]⚠️ تنبيه أمان على {account}: {cde.reason}! التبديل التلقائي للحساب الموالي...[/bold red]")
            update_account_status(account, "CHECKPOINT", cde.reason)
            if checkpoint_callback:
                checkpoint_callback(account, cde.reason)
        except Exception as e:
            log(f"[red]❌ خطأ أثناء النشر عبر {account}: {str(e)[:100]}[/red]")
        finally:
            browser.close()

    log(f"\n[bold green]🏁 انتهت جلسة النشر! إجمالي المنشورات الناجحة: {total_posted}[/bold green]")
    remaining_count = len([g for g in groups if not is_already_posted(g)])
    if remaining_count == 0 and len(groups) > 0:
        log("[bold green]🎉 مبروك! اكتمل النشر في جميع المجموعات المحددة بالكامل 100%![/bold green]")
        log("[cyan]✨ تم تفريغ خانة المنشور بنجاح وإعادة ضبط الذاكرة استعداداً لمنشورك القادم.[/cyan]")
        clear_story_template()
        clear_poster_history()
        try:
            from telegram_notifier import send_telegram_message
            t_msg = (
                "🎉 <b>اكتمل نشر المنشور في جميع المجموعات بالكامل!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📢 تم نشر البوست في جميع الـ {len(groups)} مجموعة المحددة 100% بنجاح.\n\n"
                "✨ <b>تم تفريغ خانة المنشور الآن</b>، مكان المنشور فارغ وجاهز لتضع فيه المنشور الجديد!"
            )
            send_telegram_message(t_msg)
        except Exception:
            pass
    else:
        log(f"[cyan]📌 تم نشر دفعة اليوم ({total_posted} منشور). تبقى {remaining_count} مجموعة سيواصل البوت النشر فيها تلقائياً دون تكرار![/cyan]")
        log("[dim]ℹ️ المنشور محفوظ في مكانه ولن يُمسح حتى يكتمل النشر في المجموعات المتبقية كاملة.[/dim]")
        try:
            from telegram_notifier import notify_campaign_completed
            notify_campaign_completed("Facebook Groups Auto-Poster", {
                "total_posted": total_posted,
                "total_groups": len(groups),
                "accounts_used": len(accounts)
            })
        except Exception:
            pass

    return {"total_posted": total_posted, "remaining": remaining_count}

if __name__ == "__main__":
    groups = get_groups_list()
    if groups:
        fb = FacebookBrowser(headless=False)
        try:
            fb.start()
            poster = AutoPoster(fb.page, browser=fb)
            poster.run_poster_campaign(groups)
        finally:
            fb.stop()
