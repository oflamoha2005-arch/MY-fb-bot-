import os
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

from config import (
    BASE_DIR, LEADS_FILE, TIER1_LEADS_FILE, VIRAL_POSTS_FILE,
    GROUPS_FILE, POSTS_FILE, HISTORY_FILE, FRIEND_REQUESTS_FILE, POSTER_HISTORY_FILE,
    SCRAPED_POSTS_FILE, SPY_HISTORY_FILE, ACCOUNTS_HEALTH_FILE
)
from utils import (
    console, load_leads, load_history, save_to_history,
    get_message_template, get_reply_templates,
    load_accounts_health, record_account_action, update_account_status,
    can_account_act, get_account_health
)
from browser import FacebookBrowser, CheckpointDetectedError
from account_warmer import AccountWarmer
from competitor_spy import (
    ViralSpyEngine, load_keywords, load_spy_history, save_spy_history,
    load_scraped_posts_history, save_scraped_posts_history,
    is_post_scraped, mark_post_as_scraped, get_unscraped_viral_posts
)
from scraper import PostScraper
from country_filter import CountryLeadFilter
from messenger import SafeMessenger
from comment_replier import CommentReplier
from friend_connector import FriendConnector, load_friend_history, save_friend_history
from auto_poster import AutoPoster, run_multi_account_poster, get_story_template, is_already_posted, get_groups_list

class DailyMasterOrchestrator:
    """
    المايسترو اليومي الشامل (Daily Master Funnel Orchestrator)
    يقوم بإدارة وأتمتة دورة العمل التسويقية اليومية بالكامل بدون أي تعارض (Zero Conflict):
    1. تدفئة الحساب الكشاف (10 دقائق)
    2. الكشاف اليومي (فحص مجموعة واحدة جديدة واستخراج أفضل منشور)
    3. سحب المعلقين وتصفية قراء الدول الكبرى (Tier-1 Leads)
    4. تدوير الحسابات: التواصل المباشر (DM + Reply) وبناء شبكة الأصدقاء (Friend Connector) مع Session Sandwich
    5. نشر قصة الكتاب في المجموعات بالتناوب (إذا كان المنشور جاهزاً)
    6. تقرير الإنجاز اليومي الشامل
    """
    def __init__(
        self,
        log_callback=None,
        status_callback=None,
        checkpoint_callback=None,
        stop_check=None
    ):
        self.log = log_callback if log_callback else console.print
        self.status_cb = status_callback
        self.checkpoint_cb = checkpoint_callback
        self.stop_check = stop_check if stop_check else (lambda: False)
        self.is_running = True
        self.active_browser = None

        # Stats tracking
        self.stats = {
            "warmup_minutes": 0,
            "scouted_group": "",
            "viral_posts_found": 0,
            "scraped_leads": 0,
            "tier1_leads": 0,
            "dms_sent": 0,
            "replies_sent": 0,
            "friend_requests": 0,
            "group_posts": 0,
            "accounts_used": [],
            "errors": []
        }

    def _set_status(self, state: str, text: str = ""):
        if self.status_cb:
            self.status_cb(state, text)

    def run_daily_funnel(
        self,
        accounts: list[str],
        scout_account: str = None,
        warmup_minutes: int = 10,
        warm_all_accounts: bool = False,
        target_posts: int = 2,
        target_tier1_quota: int = 15,
        max_leads_to_scrape: int = 25,
        max_leads_to_filter: int = 20,
        max_groups_to_scout: int = 5,
        dms_per_account: int = 4,
        enable_comment_reply: bool = True,
        friend_requests_per_account: int = 3,
        enable_group_posting: bool = True,
        posts_per_account: int = 2,
        post_template: str = None,
        image_path: str = None,
        enable_sandwich: bool = True
    ) -> dict:
        """
        تشغيل الروتين اليومي المتكامل بالترتيب الدقيق والمنظم بنظام قواعد البيانات الثلاث:
        1. Groups Database (groups.txt + spy_history.json)
        2. Viral Posts Database (viral_posts.csv + scraped_posts_history.json)
        3. Tier-1 Qualified Leads Database (tier1_leads.csv + history.json)
        """
        if not accounts:
            self.log("[red]❌ لم يتم تحديد أي حساب للعمل! يرجى إضافة حساب واحد على الأقل.[/red]")
            return self.stats

        # فحص صحة الحسابات واختيار حساب كشاف سليم
        healthy_accounts = [a for a in accounts if get_account_health(a).get("status") != "CHECKPOINT"]
        if not healthy_accounts:
            self.log("[bold red]🛑 تنبيه أمان: جميع الحسابات المحددة في وضع مراجعة أمنية (CHECKPOINT)! يرجى التحقق من أمان حساباتك.[/bold red]")
            return self.stats

        if not scout_account or scout_account not in accounts or get_account_health(scout_account).get("status") == "CHECKPOINT":
            old_scout = scout_account
            scout_account = healthy_accounts[0]
            if old_scout and old_scout != scout_account:
                self.log(f"[yellow]⚠️ الحساب الكشاف المحدد [{old_scout}] في وضع Checkpoint، تم التبديل تلقائياً للحساب السليم [{scout_account}].[/yellow]")

        start_time = datetime.now()
        self.log("\n[bold yellow]══════════════════════════════════════════════════════════════════[/bold yellow]")
        self.log("[bold yellow]🚀 بدء الروتين اليومي الشامل (Daily Master Funnel Routine)[/bold yellow]")
        self.log(f"🕒 تاريخ ووقت البدء: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"👤 الحساب الكشاف المعتمد: [{scout_account}]")
        self.log(f"👥 الحسابات المشاركة في الترويج: {', '.join(accounts)}")
        self.log(f"🎯 الكوطا اليومية المستهدفة: {target_tier1_quota} قارئ مؤهل 100% من دول Tier-1")
        self.log(f"🔥 مدة التسخين الأولي: {warmup_minutes} دقيقة ({'جميع الحسابات' if warm_all_accounts else 'الحساب الكشاف فقط'})")
        self.log(f"🎯 حصة كل حساب: {dms_per_account} DMs + {friend_requests_per_account} طلبات صداقة")
        self.log(f"📢 نشر المجموعات: {'مفعل' if enable_group_posting else 'معطل'}")
        self.log("[bold yellow]══════════════════════════════════════════════════════════════════[/bold yellow]\n")

        top_post = None
        top_post_url = ""

        # ---------------- STEP 1: INITIAL NICHE WARMING ----------------
        if warmup_minutes > 0 and self.is_running and not self.stop_check():
            if warm_all_accounts:
                self.log(f"\n[bold yellow]━━━ [المرحلة 1: تدفئة جميع الحسابات ({len(accounts)} حسابات) - {warmup_minutes} دقيقة لكل حساب] ━━━[/bold yellow]")
                for w_idx, acc in enumerate(accounts, start=1):
                    if self.stop_check() or not self.is_running:
                        break
                    # فحص صحة الحساب وتخطي أي حساب عليه Checkpoint
                    if get_account_health(acc).get("status") == "CHECKPOINT":
                        self.log(f"\n[yellow]⚠️ تخطي تدفئة الحساب [{acc}] لوجوده في وضع مراجعة أمنية (CHECKPOINT) لحمايته.[/yellow]")
                        continue
                    self._set_status("WARMING", f"Warm {acc} ({w_idx}/{len(accounts)})")
                    self.log(f"\n[yellow]🔥 [{w_idx}/{len(accounts)}] تدفئة الحساب [{acc}] ({warmup_minutes} دقيقة)...[/yellow]")
                    w_b = FacebookBrowser(account_name=acc, headless=False)
                    self.active_browser = w_b
                    try:
                        w_p = w_b.start()
                        w_warmer = AccountWarmer(w_p, browser=w_b, log_callback=self.log, stop_check=self.stop_check)
                        w_warmer.run_warming_session(duration_minutes=warmup_minutes, enable_likes=True, enable_comments=True, enable_video_watch=True, enable_stories=True)
                        record_account_action(acc, "warmup", warmup_minutes)
                        update_account_status(acc, "HEALTHY")
                    except CheckpointDetectedError as cde:
                        self.log(f"[bold red]🛑 تنبيه أمان على [{acc}]: {cde.reason}![/bold red]")
                        update_account_status(acc, "CHECKPOINT", cde.reason)
                    finally:
                        w_b.close()
                self.active_browser = None
                self.stats["warmup_minutes"] = warmup_minutes * len(accounts)
                self.log(f"[bold green]✔ اكتملت مرحلة تدفئة جميع الحسابات بنجاح تام.[/bold green]")

        # =========================================================================
        # PHASE 2 & 3: SCOUT RECONNAISSANCE (Scout -> Scrape -> Filter)
        # =========================================================================
        self._set_status("RUNNING", f"Scout on {scout_account}")
        self.log(f"\n[bold cyan]🔍 تشغيل المتصفح للحساب الكشاف [{scout_account}]...[/bold cyan]")

        scout_browser = FacebookBrowser(account_name=scout_account, headless=False)
        self.active_browser = scout_browser

        try:
            page = scout_browser.start()

            # التسخين للحساب الكشاف فقط إذا لم يتم تسخين جميع الحسابات مسبقاً
            if not warm_all_accounts and warmup_minutes > 0 and self.is_running and not self.stop_check():
                self._set_status("WARMING", f"Scout Warmup {warmup_minutes}m")
                self.log(f"\n[bold yellow]━━━ [المرحلة 1: التسخين الذكي للحساب الكشاف ({warmup_minutes} دقيقة)] ━━━[/bold yellow]")
                warmer = AccountWarmer(
                    page, 
                    browser=scout_browser, 
                    log_callback=self.log, 
                    stop_check=self.stop_check
                )
                warmer.run_warming_session(
                    duration_minutes=warmup_minutes,
                    enable_likes=True,
                    enable_comments=True,
                    enable_video_watch=True,
                    enable_stories=True
                )
                self.stats["warmup_minutes"] = warmup_minutes
                record_account_action(scout_account, "warmup", warmup_minutes)
                update_account_status(scout_account, "HEALTHY")
                self.log(f"[bold green]✔ اكتمل التسخين الأولي بنجاح تام للحساب [{scout_account}].[/bold green]")

            # =========================================================================
            # STEP 2 & 3: TIER-1 LEADS RECONNAISSANCE & HARVESTING LOOP (3-DATABASES ENGINE)
            # Database 1: Groups (groups.txt + spy_history.json)
            # Database 2: Viral Posts (viral_posts.csv + scraped_posts_history.json)
            # Database 3: Tier-1 Qualified Leads (tier1_leads.csv + history.json)
            # =========================================================================
            harvested_tier1_today = []
            groups_scouted_today = 0
            posts_scraped_today = 0

            self.log(f"\n[bold cyan]━━━ [المرحلة 2 و 3: سحب وتصفية قراء Tier-1 المستهدفين (الكوطا: {target_tier1_quota} قارئ)] ━━━[/bold cyan]")
            self.log(f"• الكوطا اليومية المطلوبة: {target_tier1_quota} قارئ مؤهل 100% من دول القوة الشرائية.")
            self.log(f"• آلية العمل الذكية: فحص المنشورات غير المسحوبة في Database 2، وتخطي الروابط المسحوبة، وتدوير المجموعات حتى اكتمال العدد.")

            while len(harvested_tier1_today) < target_tier1_quota and self.is_running and not self.stop_check():
                # 1. فحص المنشورات الفيروسية غير المسحوبة المتوفرة في Database 2
                unscraped_posts = get_unscraped_viral_posts()

                # 2. إذا لم تتوفر منشورات جديدة غير مسحوبة، ننتقل للمجموعة الموالية في Database 1 (Groups)
                if not unscraped_posts:
                    if groups_scouted_today >= max_groups_to_scout:
                        self.log(f"[yellow]⚠️ تم فحص الحد الأقصى للمجموعات ({max_groups_to_scout}) في هذه الجلسة. التوقف والاكتفاء بما تم جمعه.[/yellow]")
                        break

                    groups = get_groups_list()
                    if not groups:
                        self.log("[yellow]⚠️ لم يتم العثور على أي مجموعات في groups.txt.[/yellow]")
                        break

                    self._set_status("RUNNING", f"Scouting Group #{groups_scouted_today + 1}")
                    self.log(f"\n[cyan]🔍 Database 2 تحتاج منشورات جديدة -> فحص المجموعة التالية في Database 1 (Groups)...[/cyan]")
                    spy = ViralSpyEngine(scout_browser)
                    scouted_group, new_viral_posts = spy.scout_daily_routine(
                        group_urls=groups,
                        target_posts=max(2, target_posts),
                        min_comments=2,
                        max_months=3,
                        progress_callback=lambda msg: self.log(f"[dim]{msg}[/dim]")
                    )
                    groups_scouted_today += 1
                    if scouted_group:
                        self.stats["scouted_group"] = scouted_group
                    if new_viral_posts:
                        self.stats["viral_posts_found"] += len(new_viral_posts)
                        unscraped_posts = get_unscraped_viral_posts()
                    else:
                        self.log(f"[yellow]⚠️ لم يتم العثور على منشورات فيروسية جديدة في هذه المجموعة. الانتقال للمجموعة الموالية...[/yellow]")
                        time.sleep(random.uniform(3, 6))
                        continue

                if not unscraped_posts:
                    self.log("[yellow]⚠️ تم استنفاد جميع المنشورات المتاحة حالياً بدون الوصول لكامل الكوطا.[/yellow]")
                    break

                # 3. اختيار المنشور الفيروسي التالي في الترتيب (Queue) وتخطي ما تم سحبه
                current_post = unscraped_posts[0]
                current_post_url = str(current_post.get("post_url", "")).strip()
                current_group_url = str(current_post.get("source", "") or current_post.get("group_url", "")).strip()
                author_name = str(current_post.get("author", "Unknown")).strip()

                if not current_post_url:
                    continue

                top_post_url = current_post_url
                posts_scraped_today += 1
                self._set_status("RUNNING", f"Scraping Post #{posts_scraped_today} ({len(harvested_tier1_today)}/{target_tier1_quota})")
                self.log(f"\n[bold magenta]📌 [سحب ومعالجة المنشور #{posts_scraped_today} في القائمة][/bold magenta]")
                self.log(f"• رابط البوست: {current_post_url}")
                self.log(f"• الكاتب: {author_name} | 💬 تعليقات: {current_post.get('comments', 0)}")
                self.log(f"• التقدم الحالي: [{len(harvested_tier1_today)}/{target_tier1_quota}] قارئ Tier-1 تم جمعهم")

                # 4. سحب المعلقين من هذا المنشور
                scraper = PostScraper(page, browser=scout_browser)
                scraped_leads = scraper.scrape_comments(current_post_url, max_leads=max_leads_to_scrape)
                self.stats["scraped_leads"] += len(scraped_leads)
                self.log(f"[bold green]✔ تم سحب {len(scraped_leads)} معلق من هذا المنشور.[/bold green]")

                # 5. تصفية قراء Tier-1 من المعلقين الجدد
                new_tier1_for_this_post = []
                if scraped_leads and self.is_running and not self.stop_check():
                    self.log("• جاري فحص بروفايلات المعلقين لعزل المقيمين في دول Tier-1...")
                    filter_engine = CountryLeadFilter(scout_browser)
                    new_tier1_for_this_post = filter_engine.filter_existing_leads(
                        max_leads=max_leads_to_filter,
                        leads_to_filter=scraped_leads,
                        progress_callback=lambda msg: self.log(f"[dim]{msg}[/dim]")
                    )
                    harvested_tier1_today.extend(new_tier1_for_this_post)
                    self.stats["tier1_leads"] += len(new_tier1_for_this_post)
                    self.log(f"[bold green]🎯 تم تأهيل {len(new_tier1_for_this_post)} قارئ Tier-1 جديد من هذا المنشور.[/bold green]")

                # 6. تسجيل المنشور في Database 2 وسجل scraped_posts_history لمنع التكرار نهائياً
                mark_post_as_scraped(
                    post_url=current_post_url,
                    leads_count=len(scraped_leads),
                    tier1_count=len(new_tier1_for_this_post),
                    group_url=current_group_url
                )
                self.log(f"[dim]✔ تم حفظ حالة المنشور في Database 2 كرابط مكتمل السحب لتخطيه مستقبلاً.[/dim]")

                # 7. فحص اكتمال الكوطا
                if len(harvested_tier1_today) >= target_tier1_quota:
                    self.log(f"\n[bold green]🎉 اكتملت الكوطا المستهدفة بنجاح تام! تم جمع {len(harvested_tier1_today)}/{target_tier1_quota} قارئ مؤهل 100%.[/bold green]")
                    break
                else:
                    needed = target_tier1_quota - len(harvested_tier1_today)
                    self.log(f"[yellow]⏳ المجموع حتى الآن: {len(harvested_tier1_today)}/{target_tier1_quota} قارئ (متبقي {needed}). الانتقال للرابط الموالي في Database...[/yellow]")
                    time.sleep(random.uniform(4, 7))

            # Session Sandwich: Post-Cooling for Scout Account
            if enable_sandwich and self.is_running and not self.stop_check():
                self._set_status("COOLING", f"Post-Cool {scout_account} 60s")
                self.log(f"[dim]🛡️ [Sandwich] تشغيل تبريد ختامي 60 ثانية على الحساب الكشاف [{scout_account}]...[/dim]")
                scout_browser.human_warmup_session(60, label="Scout Post-Cooling", log_callback=self.log, stop_check=self.stop_check)

        except CheckpointDetectedError as cde:
            self.log(f"[bold red]🛑 تنبيه أمان على الحساب الكشاف [{scout_account}]: {cde.reason}![/bold red]")
            update_account_status(scout_account, "CHECKPOINT", cde.reason)
            self.stats["errors"].append(f"Scout Account {scout_account}: {cde.reason}")
            if self.checkpoint_cb:
                self.checkpoint_cb(scout_account, cde.reason)
        except Exception as e:
            self.log(f"[red]❌ خطأ أثناء مرحلة الاستكشاف: {str(e)[:120]}[/red]")
            self.stats["errors"].append(f"Scout Error: {str(e)[:100]}")
        finally:
            scout_browser.close()
            self.active_browser = None
            self.log(f"[dim]تم إغلاق جلسة الحساب الكشاف [{scout_account}] بأمان تام وبدون أي تعارض.[/dim]")

        # Short pause between scout and multi-account campaign
        if self.is_running and not self.stop_check():
            time.sleep(random.uniform(5, 10))

        # =========================================================================
        # PHASE 4: MULTI-ACCOUNT DIRECT OUTREACH & FRIEND REQUESTS
        # =========================================================================
        if self.is_running and not self.stop_check():
            self._set_status("RUNNING", "Multi-Account Outreach")
            self.log(f"\n[bold yellow]━━━ [المرحلة 4: تدوير الحسابات ({len(accounts)} حسابات) للتواصل المباشر والأصدقاء] ━━━[/bold yellow]")

            # Load Tier-1 Leads (or fallback to general leads)
            target_leads_file = TIER1_LEADS_FILE if TIER1_LEADS_FILE.exists() else LEADS_FILE
            all_leads = load_leads(target_leads_file) if target_leads_file.exists() else []
            history = load_history()

            # حماية مضاعفة من تكرار الرسائل لنفس الشخص (Lead Deduplication Guard)
            seen_in_queue = set()
            unique_pending = []
            for l in all_leads:
                lid = str(l.get('id', '')).strip()
                if lid and lid not in history and lid not in seen_in_queue:
                    seen_in_queue.add(lid)
                    unique_pending.append(l)
            pending_dm_leads = unique_pending
            self.log(f"• إجمالي القراء المؤهلين الجاهزين للتواصل المباشر (بعد الفلترة ومنع التكرار): {len(pending_dm_leads)}")

            dm_template = get_message_template()
            reply_templates = get_reply_templates()
            template_reply_a = reply_templates.get("reply_sent_dm", "")

            lead_queue_idx = 0

            for acc_idx, account in enumerate(accounts, start=1):
                if not self.is_running or self.stop_check():
                    break

                # فحص صحة الحساب وتخطي أي حساب عليه Checkpoint لحمايته
                acc_health = get_account_health(account)
                if acc_health.get("status") == "CHECKPOINT":
                    self.log(f"\n[bold yellow]⚠️ تخطي الحساب [{account}] لوجوده في وضع مراجعة أمنية (CHECKPOINT) لحمايته وتفادي الحظر النهائي، والتحول للحساب الموالي...[/bold yellow]")
                    continue

                self.log(f"\n[bold magenta]══════════════ [الحساب {acc_idx}/{len(accounts)}: {account}] ══════════════[/bold magenta]")
                self._set_status("RUNNING", f"Working on {account}")
                self.stats["accounts_used"].append(account)

                # Determine batch for this account
                account_dm_batch = pending_dm_leads[lead_queue_idx : lead_queue_idx + dms_per_account]
                lead_queue_idx += len(account_dm_batch)

                browser = FacebookBrowser(account_name=account, headless=False)
                self.active_browser = browser

                try:
                    p = browser.start()

                    # 4.0 Pre-Warming (Session Sandwich: 90s)
                    if enable_sandwich and self.is_running and not self.stop_check():
                        self._set_status("WARMING", f"Pre-Warm {account} 90s")
                        self.log(f"[cyan]🌱 [Pre-Warming] تصفح طبيعي للـ Feed للحساب [{account}] (90 ثانية)...[/cyan]")
                        browser.human_warmup_session(90, label="Pre-Warming", log_callback=self.log, stop_check=self.stop_check)

                    # 4.1 Direct Outreach: Micro-Engagement (Like ❤️) + Notification Reply
                    if enable_comment_reply and account_dm_batch and self.is_running and not self.stop_check():
                        self.log(f"[dim]التوجه للمنشورات لوضع التفاعل (Like ❤️) وردود الإشعارات لمعلقي الحساب [{account}]...[/dim]")
                        try:
                            replier = CommentReplier(p, browser=browser, log_callback=self.log)
                            current_loaded_post = ""
                            for lead in account_dm_batch:
                                if not self.is_running or self.stop_check():
                                    break
                                target_p_url = str(lead.get("post_url", "")).strip() or top_post_url
                                if target_p_url and target_p_url != current_loaded_post:
                                    p.goto(target_p_url, wait_until="domcontentloaded", timeout=45000)
                                    p.wait_for_timeout(3500)
                                    current_loaded_post = target_p_url
                                if current_loaded_post:
                                    success_reply = replier.reply_to_commenter(lead.get('name', ''), template_reply_a)
                                    if success_reply:
                                        self.stats["replies_sent"] += 1
                                    time.sleep(random.randint(12, 20))
                        except Exception as e:
                            self.log(f"[dim]تخطي وضع ردود التعليقات: {str(e)[:80]}[/dim]")

                    # 4.2 Direct Outreach: DMs with Book Preview Link
                    if account_dm_batch and self.is_running and not self.stop_check():
                        self.log(f"[cyan]💬 إرسال الرسائل الخاصة (DMs) لمعلقي [{account}] (العدد: {len(account_dm_batch)})...[/cyan]")
                        messenger = SafeMessenger(p, browser=browser)
                        for l_idx, lead in enumerate(account_dm_batch, start=1):
                            if not self.is_running or self.stop_check():
                                break

                            self.log(f"[{l_idx}/{len(account_dm_batch)}] إرسال رسالة خاصة من [{account}] إلى: {lead.get('name')}")
                            dm_success = messenger.send_direct_message(lead, dm_template)
                            if dm_success:
                                self.stats["dms_sent"] += 1
                                save_to_history(lead['id'], lead.get('name', ''), account=account, action="dm_and_reply", status="sent")
                                record_account_action(account, "dm", 1)

                            # Inter-DM human warming (90-140s)
                            if l_idx < len(account_dm_batch) and self.is_running and not self.stop_check():
                                wait_sec = random.randint(90, 140)
                                self._set_status("COOLDOWN", f"Warm {wait_sec}s")
                                browser.human_warmup_session(wait_sec, label="Inter-DM Warm", log_callback=self.log, stop_check=self.stop_check)

                    # 4.3 Targeted Friend Requests (Friend Connector)
                    if friend_requests_per_account > 0 and self.is_running and not self.stop_check():
                        self.log(f"\n[cyan]🤝 بناء شبكة الأصدقاء للحساب [{account}] (الهدف: {friend_requests_per_account} طلبات)...[/cyan]")
                        connector = FriendConnector(browser, account_name=account)
                        res = connector.run_connector_campaign(
                            source="tier1",
                            max_requests=friend_requests_per_account,
                            progress_callback=lambda msg: self.log(f"[dim]{msg}[/dim]")
                        )
                        sent_f = res.get("sent", 0)
                        self.stats["friend_requests"] += sent_f
                        if sent_f > 0:
                            record_account_action(account, "friend_request", sent_f)
                        self.log(f"[bold green]✔ تم إرسال {sent_f} طلب صداقة لقراء مؤهلين عبر [{account}].[/bold green]")

                    # 4.4 Post-Cooling (Session Sandwich: 60s)
                    if enable_sandwich and self.is_running and not self.stop_check():
                        self._set_status("COOLING", f"Post-Cool {account} 60s")
                        self.log(f"[cyan]🧊 [Post-Cooling] تصفح هادئ في الـ Feed قبل إغلاق الحساب [{account}] (60 ثانية)...[/cyan]")
                        browser.human_warmup_session(60, label="Post-Cooling", log_callback=self.log, stop_check=self.stop_check)

                    update_account_status(account, "HEALTHY")

                except CheckpointDetectedError as cde:
                    self.log(f"[bold red]🛑 تنبيه أمني للحساب [{account}]: {cde.reason}! التبديل التلقائي للحساب التالي...[/bold red]")
                    update_account_status(account, "CHECKPOINT", cde.reason)
                    self.stats["errors"].append(f"{account}: {cde.reason}")
                    if self.checkpoint_cb:
                        self.checkpoint_cb(account, cde.reason)
                except Exception as e:
                    self.log(f"[red]❌ خطأ أثناء العمل بالحساب [{account}]: {str(e)[:100]}[/red]")
                    self.stats["errors"].append(f"{account}: {str(e)[:80]}")
                finally:
                    browser.close()
                    self.active_browser = None
                    self.log(f"[dim]أُغلقت جلسة [{account}] بسلام. استراحة قصيرة قبل الحساب الموالي...[/dim]")
                    if acc_idx < len(accounts) and self.is_running and not self.stop_check():
                        time.sleep(random.uniform(8, 15))

        # =========================================================================
        # PHASE 5: GROUP STORY AUTO-POSTING (CONDITIONAL)
        # =========================================================================
        if enable_group_posting and self.is_running and not self.stop_check():
            self._set_status("RUNNING", "Group Auto-Poster")
            self.log(f"\n[bold yellow]━━━ [المرحلة 5: نشر قصة الكتاب في المجموعات بالتناوب] ━━━[/bold yellow]")

            template_to_post = post_template if post_template else get_story_template()
            groups = get_groups_list()

            # مزامنة مسار الصورة المحفوظة تلقائياً إذا لم يتم إدخالها يدوياً
            if not image_path:
                cfg_img_path = BASE_DIR / "data" / "poster_config.json"
                if cfg_img_path.exists():
                    try:
                        with open(cfg_img_path, 'r', encoding='utf-8') as f:
                            saved_img = json.load(f).get("image_path", "")
                            if saved_img and Path(saved_img).exists():
                                image_path = saved_img
                                self.log(f"[dim]📸 تم تحميل صورة الغلاف المحفوظة تلقائياً: {Path(image_path).name}[/dim]")
                    except Exception:
                        pass

            # استبعاد الحسابات التي في وضع CHECKPOINT من النشر
            healthy_poster_accounts = [a for a in accounts if get_account_health(a).get("status") != "CHECKPOINT"]

            if not template_to_post or not template_to_post.strip():
                self.log("[dim]ℹ️ تم تخطي مرحلة النشر لعدم توفر نص قصة في posts.txt.[/dim]")
            elif not groups:
                self.log("[dim]ℹ️ تم تخطي مرحلة النشر لعدم توفر روابط مجموعات في groups.txt.[/dim]")
            elif not healthy_poster_accounts:
                self.log("[yellow]⚠️ تم تخطي مرحلة النشر لعدم توفر أي حساب سليم (جميع الحسابات في مراجعة أمنية CHECKPOINT).[/yellow]")
            else:
                self.log(f"• جاري توزيع المجموعات على الحسابات السليمة ({len(healthy_poster_accounts)} حسابات) بمعدل {posts_per_account} منشورات لكل حساب...")
                poster_res = run_multi_account_poster(
                    groups=groups,
                    accounts=healthy_poster_accounts,
                    posts_per_account=posts_per_account,
                    image_path=image_path,
                    min_delay_min=3,
                    max_delay_min=5,
                    enable_sandwich=enable_sandwich,
                    enable_warming=True,
                    log_callback=self.log,
                    status_callback=self.status_cb,
                    checkpoint_callback=self.checkpoint_cb,
                    stop_check=self.stop_check
                )
                self.stats["group_posts"] = poster_res.get("total_posted", 0)
        else:
            if not enable_group_posting:
                self.log("[dim]ℹ️ تم تخطي مرحلة النشر في المجموعات (معطلة في الإعدادات).[/dim]")

        # =========================================================================
        # PHASE 6: DAILY EXECUTION SUMMARY
        # =========================================================================
        end_time = datetime.now()
        duration_total = end_time - start_time
        minutes_total = int(duration_total.total_seconds() // 60)

        self._set_status("READY", "Daily Routine Completed")

        self.log("\n[bold green]══════════════════════════════════════════════════════════════════[/bold green]")
        self.log("[bold green]🏁 اكتمل الروتين اليومي الشامل بنجاح باهر وبدون أي تعارض! 🎉[/bold green]")
        self.log(f"⏱️ إجمالي الوقت المستغرق: {minutes_total} دقيقة")
        self.log(f"🔥 مدة التسخين الأولي: {self.stats['warmup_minutes']} دقيقة عبر [{scout_account}]")
        self.log(f"🔎 المجموعات المفحوصة كشفاً: {self.stats['scouted_group'] or 'N/A'}")
        self.log(f"🚀 المنشورات الفيروسية المرصودة: {self.stats['viral_posts_found']}")
        self.log(f"🔍 المعلقين المسحوبين: {self.stats['scraped_leads']}")
        self.log(f"🌍 قراء دول Tier-1 المعزولين: {self.stats['tier1_leads']}")
        self.log(f"💬 الرسائل الخاصة المرسلة (DMs): {self.stats['dms_sent']}")
        self.log(f"🔔 ردود الإشعارات المنشورة: {self.stats['replies_sent']}")
        self.log(f"🤝 طلبات الصداقة المرسلة: {self.stats['friend_requests']}")
        self.log(f"📢 منشورات المجموعات الجديدة: {self.stats['group_posts']}")
        self.log(f"👥 الحسابات المشاركة: {len(set(self.stats['accounts_used']))}")
        if self.stats["errors"]:
            self.log(f"⚠️ ملاحظات الأمان: {len(self.stats['errors'])} حالات مسجلة وتم التعامل معها تلقائياً.")
        self.log("[bold green]══════════════════════════════════════════════════════════════════[/bold green]\n")

        try:
            from telegram_notifier import notify_daily_master_completed
            notify_daily_master_completed({
                "tier1_leads": self.stats.get('tier1_leads', 0),
                "dms_sent": self.stats.get('dms_sent', 0),
                "replies_posted": self.stats.get('replies_sent', 0),
                "friend_requests_sent": self.stats.get('friend_requests', 0),
                "group_posts_made": self.stats.get('group_posts', 0),
                "warmup_minutes": self.stats.get('warmup_minutes', 0)
            })
        except Exception:
            pass

        return self.stats

if __name__ == "__main__":
    from gui import get_saved_accounts
    accs = get_saved_accounts()
    orchestrator = DailyMasterOrchestrator()
    print("Testing Daily Master Orchestrator...")
    # Standalone dry-run
