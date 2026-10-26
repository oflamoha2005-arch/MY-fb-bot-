import time
import random
from utils import (
    console, load_leads, load_history, save_to_history,
    get_message_template, get_reply_templates
)
from browser import FacebookBrowser, CheckpointDetectedError
from messenger import SafeMessenger
from comment_replier import CommentReplier

class HybridCampaignEngine:
    def __init__(self, log_callback=None, stop_check_callback=None):
        self.log = log_callback if log_callback else console.print
        self.stop_check = stop_check_callback if stop_check_callback else (lambda: False)
        self.is_running = True

    def run_hybrid_campaign(
        self,
        post_url: str,
        accounts: list[str],
        dms_per_account: int = 5,
        enable_comment_reply: bool = True,
        enable_warming: bool = True,
        enable_sandwich_warming: bool = True,
        pre_warm_seconds: int = 90,
        post_warm_seconds: int = 60,
        leads_file=None
    ):
        """
        تشغيل الحملة المركزة:
        1. تدوير الحسابات: كل حساب يرسل (Reply 'Sent DM!' + DM) لعدد محدد من المعلقين مع الذاكرة المشتركة.
        2. تسخين قبلي وبعدي (Session Sandwich) لرفع أمان كل حساب ومحاكاة الدخول والخروج البشري الطبيعي.
        """
        all_leads = load_leads(leads_file) if leads_file else load_leads()
        if not all_leads:
            self.log("[red]❌ لا توجد أي بيانات معلقين في leads.csv. يرجى سحب المعلقين أولاً.[/red]")
            return

        # تصفية المعلقين التابعين لهذا المنشور أو غير المتواصل معهم مسبقاً
        history = load_history()
        pending_leads = [l for l in all_leads if l['id'] not in history]

        if not pending_leads:
            self.log("[bold green]🎉 جميع المعلقين تم التواصل معهم سابقاً ومسجلون في الذاكرة![/bold green]")
            return

        self.log(f"\n[bold cyan]🚀 بدء الحملة المباشرة (Multi-Account DM & Reply)[/bold cyan]")
        self.log(f"• إجمالي المعلقين الجاهزين: {len(pending_leads)}")
        self.log(f"• الحسابات المشاركة: {', '.join(accounts)}")
        self.log(f"• حصة كل حساب: {dms_per_account} رسائل")
        self.log(f"• ميزة إشعارات التعليقات (Reply Trigger): {'مفعلة' if enable_comment_reply else 'معطلة'}")

        dm_template = get_message_template()
        reply_templates = get_reply_templates()
        template_reply_a = reply_templates.get("reply_sent_dm", "")

        leads_queue = list(pending_leads)
        total_dms_sent = 0
        total_replies_sent = 0

        # ========================================================
        # PHASE 1: DIRECT OUTREACH WITH MULTI-ACCOUNT ROTATION
        # ========================================================
        self.log("\n[bold yellow]━━━ [المرحلة 1: الهجوم المباشر وتدوير الحسابات (DM + Reply)] ━━━[/bold yellow]")

        for acc_idx, account in enumerate(accounts, start=1):
            if not self.is_running or self.stop_check():
                break

            if not leads_queue:
                self.log("[green]✔ انتهت قائمة المعلقين المتاحين للـ DM.[/green]")
                break

            # تحديد حصة هذا الحساب
            current_batch = leads_queue[:dms_per_account]
            leads_queue = leads_queue[dms_per_account:]

            self.log(f"\n[bold blue]👤 الحساب [{account}] يتولى الآن دفعة من {len(current_batch)} معلقين...[/bold blue]")
            
            browser = FacebookBrowser(account_name=account, headless=False)
            page = browser.start()

            try:
                # 0. التسخين القبلي للدخول البشري الطبيعي (Pre-Task Warm-up)
                if enable_sandwich_warming and not self.stop_check() and self.is_running:
                    self.log(f"[cyan]🌱 [Pre-Warming] بدء تصفح طبيعي في الـ Feed للحساب [{account}] ({pre_warm_seconds} ثانية)...[/cyan]")
                    browser.human_warmup_session(pre_warm_seconds, log_callback=self.log, stop_check=self.stop_check, label="Pre-Warming")

                # 1. إذا كان خيار الرد على التعليقات مفعلاً: ندخل للمنشور ونضع الردود لكي تأتيهم الإشعارات فوراً
                if enable_comment_reply and post_url:
                    self.log(f"[dim]التوجه للمنشور لوضع التفاعل (Like ❤️) وردود الإشعارات لمعلقي الحساب [{account}]...[/dim]")
                    page.goto(post_url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(4000)
                    replier = CommentReplier(page, browser=browser, log_callback=self.log)

                    for lead in current_batch:
                        if not self.is_running or self.stop_check():
                            break
                        success_reply = replier.reply_to_commenter(lead.get('name', ''), template_reply_a)
                        if success_reply:
                            total_replies_sent += 1
                        time.sleep(random.randint(12, 20)) # فاصل طبيعي بين الردود

                # 2. إرسال الرسائل الخاصة (DMs) مع رابط الكتاب
                messenger = SafeMessenger(page, browser=browser)
                for l_idx, lead in enumerate(current_batch, start=1):
                    if not self.is_running or self.stop_check():
                        break

                    self.log(f"[{l_idx}/{len(current_batch)}] إرسال رسالة خاصة من [{account}] إلى: {lead.get('name')}")
                    dm_success = messenger.send_direct_message(lead, dm_template)

                    if dm_success:
                        total_dms_sent += 1
                        # تسجيل في الذاكرة المركزية المشتركة
                        save_to_history(lead['id'], lead.get('name', ''), account=account, action="dm_and_reply", status="sent")

                    # فاصل أمان وتصفح طبيعي (Warming) بين الرسائل
                    if l_idx < len(current_batch) and self.is_running and not self.stop_check():
                        wait_sec = random.randint(90, 150)
                        if enable_warming:
                            browser.human_warmup_session(wait_sec, log_callback=self.log, stop_check=self.stop_check, label="Inter-DM Warm")
                        else:
                            time.sleep(wait_sec)

                # 3. التبريد البعدي والتصفح الهادئ قبل الخروج (Post-Task Warm-down)
                if enable_sandwich_warming and not self.stop_check() and self.is_running:
                    self.log(f"[cyan]🧊 [Post-Cooling] تصفح هادئ في الـ Feed قبل إغلاق الحساب [{account}] ({post_warm_seconds} ثانية)...[/cyan]")
                    browser.human_warmup_session(post_warm_seconds, log_callback=self.log, stop_check=self.stop_check, label="Post-Cooling")

            except CheckpointDetectedError as cde:
                self.log(f"[bold red]🛑 تنبيه أمني للحساب [{account}]: {cde.reason}! سيتم إيقاف هذا الحساب ومتابعة الحملة.[/bold red]")
            finally:
                browser.close()
                self.log(f"[dim]انتهت حصة الحساب [{account}]. تم حفظ البيانات والذاكرة المشتركة بنجاح.[/dim]")

        self.log(f"\n[bold green]🏁 اكتملت الحملة المباشرة بنجاح تام![/bold green]")
        self.log(f"• إجمالي الرسائل الخاصة المرسلة (DMs): {total_dms_sent}")
        self.log(f"• إجمالي الردود التنبيهية على التعليقات (Replies): {total_replies_sent}")
        self.log(f"• تم تحديث الذاكرة المركزية data/history.json بجميع الحالات.")
