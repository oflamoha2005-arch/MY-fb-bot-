import time
import random
import re
from urllib.parse import urlparse, parse_qs, urlunparse
from datetime import datetime
from playwright.sync_api import Page
from utils import console, save_leads, load_leads

def clean_facebook_url(url: str) -> str:
    """تنظيف رابط البروفايل من المعاملات الزائدة (tracking params)"""
    if not url:
        return ""
    # إذا كان رابط بروفايل عبر الـ ID
    if "profile.php" in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        user_id = params.get('id', [None])[0]
        if user_id:
            return f"https://www.facebook.com/profile.php?id={user_id}"
    
    # إذا كان رابط مستخدم داخل مجموعة: facebook.com/groups/xxx/user/1000xxx/
    group_user_match = re.search(r'(facebook\.com/groups/[^/]+/user/\d+)', url)
    if group_user_match:
        return f"https://www.{group_user_match.group(1)}/"

    # إذا كان رابط باسم مستخدم مباشر: facebook.com/username
    clean = url.split('?')[0].split('&')[0].rstrip('/')
    return clean

def extract_user_id(profile_url: str) -> str:
    """استخراج معرف فريد للمستخدم لتمييزه وتجنب التكرار"""
    if "profile.php?id=" in profile_url:
        match = re.search(r'id=(\d+)', profile_url)
        if match:
            return match.group(1)
    if "/user/" in profile_url:
        match = re.search(r'/user/(\d+)', profile_url)
        if match:
            return match.group(1)
    # استخدام اسم المستخدم كـ ID
    parts = profile_url.rstrip('/').split('/')
    return parts[-1] if parts else profile_url

class PostScraper:
    def __init__(self, page: Page, browser=None):
        self.page = page
        self.browser = browser

    def switch_to_all_comments(self):
        """محاولة تبديل فلتر التعليقات إلى 'جميع التعليقات' (All Comments) لإظهار الجميع"""
        try:
            # فحص الأمان
            if self.browser:
                self.browser.verify_safety_or_raise()

            filter_buttons = self.page.locator(
                'div[role="button"]:has-text("أبرز التعليقات"), '
                'div[role="button"]:has-text("Most relevant"), '
                'span:has-text("أبرز التعليقات"), '
                'span:has-text("Most relevant")'
            )
            if filter_buttons.count() > 0:
                console.print("[dim]جاري التبديل إلى 'جميع التعليقات'...[/dim]")
                filter_buttons.first.click()
                self.page.wait_for_timeout(1500)
                all_comments_option = self.page.locator(
                    'div[role="menuitem"]:has-text("جميع التعليقات"), '
                    'div[role="menuitem"]:has-text("All comments"), '
                    'span:has-text("جميع التعليقات"), '
                    'span:has-text("All comments")'
                )
                if all_comments_option.count() > 0:
                    all_comments_option.first.click()
                    self.page.wait_for_timeout(2000)
        except CheckpointDetectedError:
            raise
        except Exception:
            pass

    def load_more_comments(self, max_scrolls: int = 10):
        """الضغط على أزرار 'عرض المزيد من التعليقات' والتمرير للأسفل بهدوء"""
        console.print("[cyan]⏳ جاري تحميل التعليقات والتمرير في المنشور...[/cyan]")
        for i in range(max_scrolls):
            if self.browser:
                self.browser.verify_safety_or_raise()

            # البحث عن أزرار 'عرض المزيد من التعليقات' والردود
            more_buttons = self.page.locator(
                'div[role="button"]:has-text("عرض المزيد من التعليقات"), '
                'div[role="button"]:has-text("View more comments"), '
                'div[role="button"]:has-text("View previous comments"), '
                'div[role="button"]:has-text("عرض التعليقات السابقة"), '
                'span:has-text("عرض المزيد من التعليقات"), '
                'span:has-text("View more comments")'
            )
            clicked = False
            for b_idx in range(min(more_buttons.count(), 3)):
                try:
                    btn = more_buttons.nth(b_idx)
                    if btn.is_visible():
                        btn.click(timeout=2000)
                        clicked = True
                        self.page.wait_for_timeout(1000)
                except Exception:
                    pass

            # التمرير للأسفل لمحاكاة التصفح الطبيعي
            self.page.evaluate("window.scrollBy(0, 1000);")
            self.page.wait_for_timeout(1500 + random.randint(500, 1000))
            if not clicked and i > 3:
                self.page.evaluate("window.scrollBy(0, 1500);")

    def scrape_comments(self, post_url: str, max_leads: int = 50) -> list[dict]:
        """استخراج المعلقين الحقيقيين وتصفية الصفحات والتعليقات القديمة (> 1 سنة)"""
        console.print(f"[bold cyan]🔍 جاري فتح المنشور:[/bold cyan] {post_url}")
        self.page.goto(post_url, wait_until="domcontentloaded", timeout=45000)
        self.page.wait_for_timeout(4000)

        if self.browser:
            self.browser.verify_safety_or_raise()

        # تبديل الفلتر إلى جميع التعليقات
        self.switch_to_all_comments()

        # حساب عدد مرات التمرير بناءً على العدد المطلوب
        scrolls_needed = max(5, max_leads // 5)
        self.load_more_comments(max_scrolls=scrolls_needed)

        # تحميل البيانات السابقة لتجنب إضافة نفس الشخص
        existing_leads = load_leads()
        seen_ids = set(lead.get('id') for lead in existing_leads if lead.get('id'))

        collected_leads = []
        
        # البحث عن عناصر التعليقات
        links = self.page.locator('a[role="link"]').all()
        console.print(f"[dim]تم رصد {len(links)} رابط، جاري الفلترة واستخراج المعلقين المؤهلين...[/dim]")

        for link in links:
            try:
                href = link.get_attribute("href")
                if not href:
                    continue

                # 1. تجاهل روابط فيسبوك العامة والصفحات التجارية (Pages Filter)
                ignored_keywords = [
                    '/hashtag/', '/watch/', '/stories/', '/pages/', '/photo',
                    '/help/', '/settings/', '/gaming/', '/marketplace/', '/policies/',
                    'facebook.com/share', 'privacy', 'about', '/events/', '/business/',
                    '/commerce/', 'facebook.com/p/', '/ads/'
                ]
                if any(k in href for k in ignored_keywords):
                    continue

                name = link.inner_text().strip()
                # اسم المعلق يجب أن يكون منطقياً (أكثر من حرفين ولا يحتوي على أزرار عامة)
                if not name or len(name) < 2 or len(name) > 60:
                    continue
                if name in ["عرض المزيد", "View more", "Like", "Reply", "رد", "أعجبني", "مشاركة", "Share", "Follow", "متابعة"]:
                    continue

                # 2. استبعاد الصفحات التجارية التي تعلق في المجموعات (Pages in Groups: /groups/.../page/...)
                if "/groups/" in href and "/page/" in href:
                    continue

                # 3. تحقق أن الرابط يؤدي إلى بروفايل شخصي حقيقي
                is_profile = (
                    "facebook.com/profile.php" in href or
                    "/user/" in href or
                    (re.match(r'^https://www\.facebook\.com/[a-zA-Z0-9\.]+$', href.split('?')[0]) and not any(x in href for x in ['/groups', '/events', '/pages']))
                )
                if "/user/" in href and "/groups/" in href:
                    is_profile = True

                if not is_profile:
                    continue

                # 4. محاولة استخراج حاوية التعليق وسحب النص وفحص التاريخ
                comment_text = ""
                is_older_than_one_year = False

                try:
                    # العثور على البلوك الحاوي للتعليق
                    container = link.locator('xpath=ancestor::div[contains(@role, "article") or contains(@class, "x1y1aw1k") or contains(@class, "x1")]').first
                    if container.count() > 0:
                        container_text = container.inner_text()
                        
                        # فحص تاريخ التعليق: إذا كان أقدم من سنة (مثلاً: 1y, 2y, 1 yr, 1 ans, سنة...) نتجاهله
                        if re.search(r'\b([1-9]\d*)\s*(?:y|yr|yrs|year|years|ans|سنة|سنوات)\b', container_text, re.IGNORECASE):
                            is_older_than_one_year = True

                        # فحص ما إذا كان الحساب صفحة تجارية من النص المرافق
                        if "Page ·" in container_text or "صفحة ·" in container_text:
                            continue

                        # استخراج نص التعليق (أول div أو span يحتوي على النص)
                        text_nodes = container.locator('div[dir="auto"], span[dir="auto"]').all()
                        for tn in text_nodes:
                            t_val = tn.inner_text().strip()
                            # نتأكد أنه ليس اسم المعلق ولا كلمة Reply
                            if t_val and t_val != name and t_val not in ["Like", "Reply", "رد", "أعجبني", "Share"]:
                                if len(t_val) > len(comment_text):
                                    comment_text = t_val
                except Exception:
                    pass

                # إذا كان التعليق أقدم من سنة، نتخطاه كما طلب المستخدم
                if is_older_than_one_year:
                    continue

                # فحص استبعاد الروابط الإشهارية والسبام من نص التعليق
                if comment_text and any(spam_k in comment_text.lower() for spam_k in ['http://', 'https://', 't.me/', 'wa.me/', 'whatsapp']):
                    continue

                clean_url = clean_facebook_url(href)
                uid = extract_user_id(clean_url)

                if uid not in seen_ids:
                    seen_ids.add(uid)
                    lead = {
                        "id": uid,
                        "name": name,
                        "profile_url": clean_url,
                        "comment_text": comment_text[:150] if comment_text else "",
                        "post_url": post_url,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    collected_leads.append(lead)
                    snippet = f" | [italic]\"{comment_text[:40]}...\"[/italic]" if comment_text else ""
                    console.print(f"[green]✔ قارئ مهتم مؤهل:[/green] {name}{snippet} ([dim]{clean_url}[/dim])")

                    if len(collected_leads) >= max_leads:
                        break
            except Exception:
                continue

        if collected_leads:
            save_leads(collected_leads)
            console.print(f"\n[bold green]🎉 تم استخراج وحفظ {len(collected_leads)} قارئ مهتم في data/leads.csv بنجاح![/bold green]")
        else:
            console.print("[yellow]⚠️ لم يتم العثور على معلقين جدد أو تم استخراجهم جميعاً سابقاً.[/yellow]")

        return collected_leads
