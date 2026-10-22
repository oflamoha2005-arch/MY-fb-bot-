import time
import random
import json
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import Page
from utils import console, parse_spintax
from config import BASE_DIR, POSTER_HISTORY_FILE

GROUPS_FILE = BASE_DIR / "groups.txt"
POSTS_FILE = BASE_DIR / "posts.txt"

DEFAULT_STORY_POST = """{Late last night, something strange happened in my house|I wasn't going to share this story, but I need some answers|A chilling incident occurred in my quiet neighborhood recently}.

{I was working late downstairs when I heard what sounded like scratching from behind the locked pantry door|I heard faint footsteps coming from the attic, even though nobody else was home|My dog suddenly stared at the empty corner of the hallway and began growling like crazy}.

{I slowly walked toward the door, my heart pounding, and turned the handle... What was inside left me speechless|I grabbed a flashlight and approached cautiously... What I found gave me chills to the bone}.

{What do you think happened next? Drop your theory in the comments, and I'll send you the full chapter for free to see if you guessed right|If anyone enjoys dark mystery stories and wants to read the rest, let me know below and I'd love to share the link with you}!"""

DEFAULT_GROUPS = """# ضع هنا روابط مجموعات فيسبوك التي تريد النشر فيها (رابط في كل سطر)
# مثال:
# https://www.facebook.com/groups/1234567890/
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

def save_poster_history(group_url: str, status: str = "posted"):
    """حفظ المجموعة في سجل الذاكرة مباشرة بعد النشر"""
    history = load_poster_history()
    history[group_url] = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status
    }
    with open(POSTER_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def is_posted_recently(group_url: str, hours: int = 24) -> bool:
    """فحص هل تم النشر في هذه المجموعة خلال آخر 24 ساعة"""
    history = load_poster_history()
    if group_url not in history:
        return False
    entry = history[group_url]
    try:
        last_date = datetime.strptime(entry.get("date", ""), "%Y-%m-%d %H:%M:%S")
        if datetime.now() - last_date < timedelta(hours=hours):
            return True
    except Exception:
        pass
    return False

def get_story_template() -> str:
    """قراءة نص القصة المشوقة من ملف posts.txt"""
    if not POSTS_FILE.exists():
        with open(POSTS_FILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_STORY_POST)
        return DEFAULT_STORY_POST
    with open(POSTS_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        return content if content else DEFAULT_STORY_POST

def get_groups_list() -> list[str]:
    """قراءة قائمة المجموعات من ملف groups.txt"""
    if not GROUPS_FILE.exists():
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_GROUPS)
        return []
    groups = []
    with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                groups.append(line)
    return groups

class AutoPoster:
    def __init__(self, page: Page, browser=None, log_callback=None):
        self.page = page
        self.browser = browser
        self.log = log_callback if log_callback else console.print
        self.is_running = True

    def post_to_group(self, group_url: str, story_template: str) -> bool:
        """نشر قصة مخصصة في مجموعة فيسبوك محددة"""
        if self.browser:
            self.browser.verify_safety_or_raise()

        self.log(f"[cyan]🌐 التوجه إلى المجموعة:[/cyan] {group_url}")
        try:
            self.page.goto(group_url, wait_until="domcontentloaded", timeout=45000)
            self.page.wait_for_timeout(4000)

            # فحص الأمان والكابتشا
            if self.browser:
                self.browser.verify_safety_or_raise()

            # البحث عن زر إنشاء منشور (Write something... / Create a public post)
            post_triggers = [
                'div[role="button"]:has-text("Write something...")',
                'div[role="button"]:has-text("Create a public post")',
                'div[role="button"]:has-text("اكتب شيئاً...")',
                'div[role="button"]:has-text("إنشاء منشور عام")',
                'span:has-text("Write something...")',
                'span:has-text("Create a public post")'
            ]

            trigger_btn = None
            for sel in post_triggers:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    trigger_btn = loc.first
                    break

            if not trigger_btn:
                self.log(f"[yellow]⚠️ تعذر العثور على خانة النشر في هذه المجموعة (قد تتطلب إذناً خاصاً).[/yellow]")
                save_poster_history(group_url, status="no_post_box")
                return False

            self.log("[dim]الضغط على خانة إنشاء منشور...[/dim]")
            trigger_btn.click()
            self.page.wait_for_timeout(3000)

            unique_post = parse_spintax(story_template)

            text_boxes = [
                'div[role="textbox"][contenteditable="true"]',
                'div[data-lexical-editor="true"]',
                'div[aria-label*="What\'s on your mind"]',
                'div[aria-label*="Create a public post"]',
                'div[aria-label*="اكتب شيئاً"]',
                'div[aria-label*="بم تفكر"]'
            ]

            textbox = None
            for sel in text_boxes:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    textbox = loc.first
                    break

            if not textbox:
                self.log(f"[yellow]⚠️ لم يتم العثور على مربع كتابة المنشور داخل النافذة.[/yellow]")
                return False

            self.log("[dim]كتابة القصة المشوقة...[/dim]")
            textbox.click()
            self.page.wait_for_timeout(500)
            textbox.fill(unique_post)
            self.page.wait_for_timeout(2000)

            post_buttons = [
                'div[aria-label="Post"]',
                'div[role="button"]:has-text("Post")',
                'div[aria-label="نشر"]',
                'div[role="button"]:has-text("نشر")',
                'span:has-text("Post")'
            ]

            post_btn = None
            for sel in post_buttons:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    post_btn = loc.first
                    break

            if not post_btn:
                self.log("[yellow]⚠️ تعذر العثور على زر Post.[/yellow]")
                return False

            self.log("[dim]الضغط على زر Post...[/dim]")
            post_btn.click()
            self.page.wait_for_timeout(5000)

            # حفظ النجاح في الذاكرة لتذكر هذه المجموعة
            save_poster_history(group_url, status="posted")
            self.log(f"[bold green]✔ تم نشر القصة بنجاح في المجموعة وحفظها في الذاكرة![/bold green]")
            return True

        except Exception as e:
            self.log(f"[red]❌ خطأ أثناء النشر: {str(e)[:100]}[/red]")
            return False

    def run_poster_campaign(self, groups: list[str], min_delay_min: int = 4, max_delay_min: int = 6, enable_warming: bool = True):
        """
        تشغيل حملة النشر مع الذاكرة الذكية:
        يتذكر المجموعات التي نُشر فيها في آخر 24 ساعة ويتخطاها،
        ويقوم بالتصفح الطبيعي (Warming) أثناء فترة الانتظار بين كل مجموعة.
        """
        if not groups:
            self.log("[red]❌ لم يتم تحديد أي مجموعات. يرجى إضافة روابط المجموعات أولاً.[/red]")
            return

        # تصفية المجموعات بناءً على الذاكرة
        pending_groups = [g for g in groups if not is_posted_recently(g)]
        already_done = len(groups) - len(pending_groups)

        if already_done > 0:
            self.log(f"[cyan]🧠 الذاكرة النشطة: تم تخطي {already_done} مجموعة نُشر فيها سابقاً اليوم.[/cyan]")

        if not pending_groups:
            self.log("[bold green]🎉 تم النشر في جميع المجموعات المحددة اليوم بنجاح! لا توجد مجموعات جديدة متبقية.[/bold green]")
            return

        story_template = get_story_template()
        self.log(f"[bold yellow]🚀 سيبدأ البوت بنشر القصة في {len(pending_groups)} مجموعة مع فواصل أمان ({min_delay_min}-{max_delay_min} دقيقة)...[/bold yellow]")

        for idx, group_url in enumerate(pending_groups, start=1):
            if not self.is_running:
                self.log("[yellow]تم إيقاف عملية النشر يدوياً.[/yellow]")
                break

            self.log(f"\n[cyan]━━━━━━━━━━━━━━━━━━━━━ [المجموعة {idx} من {len(pending_groups)}] ━━━━━━━━━━━━━━━━━━━━━[/cyan]")
            success = self.post_to_group(group_url, story_template)

            # فترة الانتظار الآمنة والتصفح الطبيعي قبل المجموعة التالية
            if idx < len(pending_groups) and self.is_running:
                wait_sec = random.randint(min_delay_min * 60, max_delay_min * 60)
                
                if enable_warming and self.browser:
                    # تصفح الـ Feed بشكل طبيعي وتفاعل خفيف لحماية الحساب
                    self.browser.human_warmup_session(
                        wait_sec, 
                        log_callback=self.log, 
                        stop_check=lambda: not self.is_running
                    )
                else:
                    self.log(f"[yellow]⏳ فاصل أمان طبيعي لحماية الحساب: الانتظار {wait_sec // 60} دقيقة و {wait_sec % 60} ثانية...[/yellow]")
                    for remaining in range(wait_sec, 0, -10):
                        if not self.is_running:
                            break
                        time.sleep(min(10, remaining))
