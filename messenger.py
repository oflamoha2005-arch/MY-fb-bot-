import time
import random
from playwright.sync_api import Page
from config import MIN_DELAY_SECONDS, MAX_DELAY_SECONDS, MAX_MESSAGES_PER_DAY, TYPING_SPEED_RANGE
from utils import (
    console, load_leads, is_already_messaged, save_to_history,
    parse_spintax, get_message_template
)

class SafeMessenger:
    def __init__(self, page: Page, browser=None):
        self.page = page
        self.browser = browser

    def human_type(self, element, text: str):
        """كتابة النص حرفاً بحرف بسرعة عشوائية لمحاكاة كتابة إنسان حقيقي"""
        for char in text:
            element.type(char, delay=random.uniform(*TYPING_SPEED_RANGE) * 1000)
            # وقفة خفيفة كل عدة حروف لمحاكاة التفكير الطبيعي
            if random.random() < 0.1:
                time.sleep(random.uniform(0.2, 0.5))

    def send_direct_message(self, lead: dict, template: str) -> bool:
        """فتح بروفايل الشخص وإرسال رسالة مخصصة له"""
        profile_url = lead['profile_url']
        name = lead.get('name', '').split()[0] # الاسم الأول للشخص
        user_id = lead['id']

        console.print(f"\n[cyan]👤 جاري التوجه إلى بروفايل:[/cyan] [bold]{lead.get('name')}[/bold] ({profile_url})")
        
        try:
            self.page.goto(profile_url, wait_until="domcontentloaded", timeout=40000)
            if self.browser and hasattr(self.browser, 'verify_safety_or_raise'):
                self.browser.verify_safety_or_raise()
            self.page.wait_for_timeout(3000 + random.randint(500, 1500))

            # البحث عن زر إرسال رسالة (Message / إرسال رسالة)
            # قد يكون الزر مكتوباً بالعربية أو الإنجليزية، أو عبارة عن أيقونة ماسنجر
            message_btn_selectors = [
                'div[aria-label="إرسال رسالة"]',
                'div[aria-label="Message"]',
                'div[role="button"]:has-text("إرسال رسالة")',
                'div[role="button"]:has-text("Message")',
                'span:has-text("إرسال رسالة")',
                'span:has-text("Message")',
                'a[href*="/messages/t/"]'
            ]

            msg_btn = None
            for sel in message_btn_selectors:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    msg_btn = loc.first
                    break

            if not msg_btn:
                console.print(f"[yellow]⚠️ تعذر العثور على زر المراسلة لـ {lead.get('name')} (قد يكون أغلق الرسائل للغرباء).[/yellow]")
                save_to_history(user_id, lead.get('name'), status="no_message_button")
                return False

            console.print("[dim]الضغط على زر الرسالة...[/dim]")
            msg_btn.click()
            self.page.wait_for_timeout(3500)

            # تجهيز نص الرسالة وتطبيق الـ Spintax وتخصيص الاسم
            personalized_msg = parse_spintax(template)
            personalized_msg = personalized_msg.replace("{name}", name if name else "صديقي")

            # البحث عن خانة كتابة الرسالة (Chat Input Box)
            chat_box_selectors = [
                'div[role="textbox"][contenteditable="true"]',
                'div[aria-label*="رسالة"]',
                'div[aria-label*="Message"]',
                'p.xat24cr',
                'div[data-lexical-editor="true"]'
            ]

            input_box = None
            for sel in chat_box_selectors:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    input_box = loc.first
                    break

            if not input_box:
                console.print(f"[yellow]⚠️ لم يتم العثور على خانة الكتابة في الماسنجر.[/yellow]")
                return False

            console.print(f"[bold green]✍️ جاري كتابة الرسالة المخصصة لـ {name}:[/bold green]")
            console.print(f"[dim italic]\"{personalized_msg[:80]}...\"[/dim italic]")

            input_box.click()
            self.page.wait_for_timeout(500)
            
            # الكتابة الآلية الآمنة
            self.human_type(input_box, personalized_msg)
            self.page.wait_for_timeout(1000)

            # إرسال الرسالة عبر الضغط على Enter
            input_box.press("Enter")
            self.page.wait_for_timeout(2500)

            # حفظ في السجل لمنع تكرار الإرسال
            save_to_history(user_id, lead.get('name'), status="sent")
            console.print(f"[bold green]✔ تم إرسال الرسالة بنجاح إلى: {lead.get('name')}![/bold green]")
            return True

        except Exception as e:
            console.print(f"[red]❌ خطأ أثناء المراسلة: {str(e)[:100]}[/red]")
            return False

    def run_campaign(self, max_messages: int = 10):
        """تشغيل حملة المراسلة التلقائية مع فواصل الأمان"""
        all_leads = load_leads()
        if not all_leads:
            console.print("[red]❌ لا توجد أي بيانات معلقين في data/leads.csv. يرجى استخراج معلقين أولاً (الخيار 2).[/red]")
            return

        # تصفية من تم إرسال رسائل لهم مسبقاً
        pending_leads = [l for l in all_leads if not is_already_messaged(l['id'])]

        if not pending_leads:
            console.print("[green]🎉 تم إرسال رسائل لجميع المعلقين المحفوظين في القائمة سابقاً![/green]")
            return

        # تحديد العدد المسموح بإرساله
        limit = min(max_messages, MAX_MESSAGES_PER_DAY, len(pending_leads))
        template = get_message_template()

        console.print(f"\n[bold yellow]🚀 سيبدأ البوت الآن بإرسال {limit} رسالة بأمان تام مع فواصل زمنية...[/bold yellow]")
        
        sent_count = 0
        for idx, lead in enumerate(pending_leads[:limit], start=1):
            console.print(f"\n[cyan]━━━━━━━━━━━━━━━━━━━━━ [الرسالة {idx} من {limit}] ━━━━━━━━━━━━━━━━━━━━━[/cyan]")
            success = self.send_direct_message(lead, template)
            if success:
                sent_count += 1

            # تطبيق الفاصل الزمني العشوائي لحماية الحساب (ما عدا بعد آخر رسالة)
            if idx < limit:
                wait_seconds = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                console.print(f"[yellow]⏳ فاصل أمان طبيعي لحماية حسابك: سننتظر {wait_seconds} ثانية ({wait_seconds//60} دقيقة)...[/yellow]")
                
                # عداد تنازلي بصري
                for remaining in range(wait_seconds, 0, -10):
                    time.sleep(min(10, remaining))
                    print(f"متبقي {remaining}s...", end="\r", flush=True)
                print(" " * 30, end="\r")

        console.print(f"\n[bold green]🏁 انتهت الحملة بنجاح! تم إرسال {sent_count} رسالة بأمان تام.[/bold green]")
