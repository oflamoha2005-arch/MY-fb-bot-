import time
import random
from playwright.sync_api import Page
from utils import console, parse_spintax

class CommentReplier:
    def __init__(self, page: Page, browser=None, log_callback=None):
        self.page = page
        self.browser = browser
        self.log = log_callback if log_callback else console.print

    def reply_to_commenter(self, commenter_name: str, reply_template: str) -> bool:
        """
        البحث عن تعليق الشخص في المنشور والضغط على Reply للرد عليه مباشرة
        """
        if self.browser:
            self.browser.verify_safety_or_raise()

        clean_first_name = commenter_name.split()[0] if commenter_name else "friend"
        personalized_text = parse_spintax(reply_template).replace("{name}", clean_first_name)

        self.log(f"[cyan]💬 جاري الرد على تعليق:[/cyan] [bold]{commenter_name}[/bold]")

        try:
            # البحث عن عناصر التعليقات التي تحتوي على اسم الشخص
            # في فيسبوك، اسم المعلق موجود داخل رابط أو سبان أو مقال
            # نحدد حاوية التعليق (Comment Container)
            comment_container = self.page.locator(
                f'div[role="article"]:has-text("{commenter_name}"), '
                f'div[aria-label*="{commenter_name}"]:has-text("Reply"), '
                f'div:has(> a:has-text("{commenter_name}"))'
            )

            reply_btn = None
            if comment_container.count() > 0:
                # نبحث عن زر Reply داخل حاوية هذا التعليق تحديداً
                for c_idx in range(min(comment_container.count(), 3)):
                    c_elem = comment_container.nth(c_idx)
                    btn = c_elem.locator(
                        'div[role="button"]:has-text("Reply"), '
                        'span:has-text("Reply"), '
                        'div[role="button"]:has-text("رد"), '
                        'span:has-text("رد"), '
                        'div[aria-label*="Reply"]'
                    )
                    if btn.count() > 0 and btn.first.is_visible():
                        reply_btn = btn.first
                        break

            # إذا لم نجده في الحاوية المباشرة، نبحث بالقرب من اسم الشخص
            if not reply_btn:
                name_locator = self.page.locator(f'a:has-text("{commenter_name}"), span:has-text("{commenter_name}")')
                if name_locator.count() > 0:
                    parent_block = name_locator.first.locator('xpath=ancestor::div[contains(@role, "article") or contains(@class, "x1")]')
                    if parent_block.count() > 0:
                        btn = parent_block.first.locator('div[role="button"]:has-text("Reply"), span:has-text("Reply"), div[role="button"]:has-text("رد")')
                        if btn.count() > 0 and btn.first.is_visible():
                            reply_btn = btn.first

            if not reply_btn:
                self.log(f"[yellow]⚠️ لم يتم العثور على زر Reply لتعليق {commenter_name}.[/yellow]")
                return False

            # الضغط على زر Reply
            reply_btn.click()
            self.page.wait_for_timeout(2000)

            # خانة كتابة الرد (Reply Input Box)
            reply_box = self.page.locator(
                'div[role="textbox"][contenteditable="true"], '
                'div[aria-label*="Write a reply"], '
                'div[aria-label*="اكتب رداً"]'
            )

            active_input = None
            for r_idx in range(reply_box.count()):
                box = reply_box.nth(r_idx)
                if box.is_visible():
                    active_input = box

            if not active_input:
                self.log("[yellow]⚠️ لم يتم العثور على خانة كتابة الرد.[/yellow]")
                return False

            active_input.click()
            self.page.wait_for_timeout(500)
            
            # كتابة الرد
            active_input.fill(personalized_text)
            self.page.wait_for_timeout(1000)

            # إرسال الرد
            active_input.press("Enter")
            self.page.wait_for_timeout(3000)

            self.log(f"[bold green]✔ تم نشر الرد على تعليق {commenter_name} بنجاح![/bold green]")
            return True

        except Exception as e:
            self.log(f"[red]❌ خطأ أثناء الرد على التعليق: {str(e)[:80]}[/red]")
            return False
