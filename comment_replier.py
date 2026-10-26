# -*- coding: utf-8 -*-
import time
import random
from playwright.sync_api import Page
from utils import console, parse_spintax

class CommentReplier:
    def __init__(self, page: Page, browser=None, log_callback=None):
        self.page = page
        self.browser = browser
        self.log = log_callback if log_callback else console.print

    def like_comment(self, commenter_name: str) -> bool:
        """
        وضع إعجاب (Micro-Engagement: Like ❤️) على تعليق القارئ
        لإرسال إشعار فوري له على هاتفه وتسخين اهتمامه قبل قراءة الرسالة/الرد
        """
        if self.browser:
            self.browser.verify_safety_or_raise()

        self.log(f"[dim]❤️ جاري وضع إعجاب (Micro-Engagement) على تعليق: {commenter_name}...[/dim]")
        try:
            # 1. البحث عن حاوية التعليق التي تحتوي على اسم الشخص
            comment_container = self.page.locator(
                f'div[role="article"]:has-text("{commenter_name}"), '
                f'div[aria-label*="{commenter_name}"]:has-text("Like"), '
                f'div:has(> a:has-text("{commenter_name}"))'
            )

            like_btn = None
            if comment_container.count() > 0:
                for c_idx in range(min(comment_container.count(), 3)):
                    c_elem = comment_container.nth(c_idx)
                    btn = c_elem.locator(
                        'div[role="button"]:has-text("Like"), '
                        'span:has-text("Like"), '
                        'div[role="button"]:has-text("أعجبني"), '
                        'span:has-text("أعجبني"), '
                        'div[role="button"]:has-text("J’aime"), '
                        'div[role="button"]:has-text("Me gusta")'
                    )
                    if btn.count() > 0 and btn.first.is_visible():
                        like_btn = btn.first
                        break

            # 2. إذا لم نجده في الحاوية المباشرة، نبحث بالقرب من اسم الشخص
            if not like_btn:
                name_locator = self.page.locator(f'a:has-text("{commenter_name}"), span:has-text("{commenter_name}")')
                if name_locator.count() > 0:
                    parent_block = name_locator.first.locator('xpath=ancestor::div[contains(@role, "article") or contains(@class, "x1")]')
                    if parent_block.count() > 0:
                        btn = parent_block.first.locator(
                            'div[role="button"]:has-text("Like"), '
                            'span:has-text("Like"), '
                            'div[role="button"]:has-text("أعجبني"), '
                            'span:has-text("أعجبني")'
                        )
                        if btn.count() > 0 and btn.first.is_visible():
                            like_btn = btn.first

            if like_btn:
                # التحقق مما إذا كان معجب به مسبقاً لتفادي إلغاء الإعجاب
                btn_text = like_btn.inner_text().strip().lower()
                aria_pressed = like_btn.get_attribute("aria-pressed")
                if aria_pressed == "true" or btn_text in ["liked", "تم الإعجاب", "je n'aime plus"]:
                    self.log(f"[dim]ℹ️ تعليق {commenter_name} معجب به مسبقاً.[/dim]")
                    return True

                like_btn.click()
                time.sleep(random.uniform(1.2, 2.2))
                self.log(f"[bold green]❤️ تم وضع إعجاب (Like) بنجاح على تعليق {commenter_name} (تم إرسال إشعار فوري له)![/bold green]")
                return True
            else:
                self.log(f"[dim]⚠️ تعذر العثور على زر Like لتعليق {commenter_name}.[/dim]")
                return False
        except Exception as e:
            self.log(f"[dim]⚠️ تعذر وضع إعجاب على التعليق: {str(e)[:60]}[/dim]")
            return False

    def reply_to_commenter(self, commenter_name: str, reply_template: str, like_first: bool = True) -> bool:
        """
        البحث عن تعليق الشخص في المنشور، وضع إعجاب (اختياري)، والضغط على Reply للرد عليه مباشرة
        """
        if self.browser:
            self.browser.verify_safety_or_raise()

        clean_first_name = commenter_name.split()[0] if commenter_name else "friend"
        personalized_text = parse_spintax(reply_template).replace("{name}", clean_first_name)

        # 1. Micro-Engagement: وضع Like على تعليق الشخص أولاً إذا كان الخيار مفعلاً
        if like_first:
            try:
                self.like_comment(commenter_name)
                time.sleep(random.uniform(1.5, 2.8))
            except Exception:
                pass

        self.log(f"[cyan]💬 جاري الرد على تعليق:[/cyan] [bold]{commenter_name}[/bold]")

        try:
            # البحث عن عناصر التعليقات التي تحتوي على اسم الشخص
            comment_container = self.page.locator(
                f'div[role="article"]:has-text("{commenter_name}"), '
                f'div[aria-label*="{commenter_name}"]:has-text("Reply"), '
                f'div:has(> a:has-text("{commenter_name}"))'
            )

            reply_btn = None
            if comment_container.count() > 0:
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
                        btn = parent_block.first.locator(
                            'div[role="button"]:has-text("Reply"), '
                            'span:has-text("Reply"), '
                            'div[role="button"]:has-text("رد")'
                        )
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
