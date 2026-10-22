import sys
import os

# دعم الترميز العربي والرموز على ويندوز
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from browser import FacebookBrowser
from scraper import PostScraper
from messenger import SafeMessenger
from utils import (
    console, show_banner, load_leads, load_history,
    get_message_template, parse_spintax
)
from config import TEMPLATES_FILE, LEADS_FILE

def option_login():
    """فتح المتصفح لتسجيل الدخول وحفظ الجلسة"""
    console.print(Panel(
        "[bold green]خطوة تسجيل الدخول لمرة واحدة:[/bold green]\n"
        "1. سيفتح الآن متصفح Chrome أمامك.\n"
        "2. سجّل دخولك إلى فيسبوك بحسابك بشكل عادي جداً.\n"
        "3. انضم للمجموعات التي تريدها وتأكد أن حسابك يعمل بشكل طبيعي.\n"
        "4. بعد الانتهاء، ارجع هنا واضغط [bold yellow]Enter[/bold yellow] لحفظ الجلسة.",
        title="🔐 تسجيل الدخول"
    ))
    
    browser = FacebookBrowser(headless=False)
    page = browser.start()
    page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
    
    input("\n👉 بعد تسجيل دخولك في المتصفح بالكامل، اضغط [Enter] هنا لحفظ الجلسة وإغلاق المتصفح... ")
    browser.close()
    console.print("[bold green]✔ تم حفظ بيانات الدخول بنجاح! المتصفح جاهز للاستخدام الآلي الآن.[/bold green]")

def option_scrape():
    """استخراج المعلقين من منشور فيسبوك"""
    all_leads = load_leads()
    console.print(f"[dim]عدد المعلقين المسجلين حالياً: {len(all_leads)}[/dim]")
    
    post_url = Prompt.ask("\n🔗 أدخل رابط المنشور في فيسبوك (Facebook Post URL)")
    if not post_url.strip():
        console.print("[red]❌ الرابط غير صالح.[/red]")
        return
        
    max_count = IntPrompt.ask("🎯 كم عدد المعلقين المطلوب استخراجهم؟", default=30)
    
    browser = FacebookBrowser(headless=False)
    page = browser.start()
    try:
        scraper = PostScraper(page)
        scraper.scrape_comments(post_url=post_url.strip(), max_leads=max_count)
    finally:
        browser.close()

def option_send_messages():
    """بدء حملة إرسال الرسائل"""
    all_leads = load_leads()
    history = load_history()
    pending = [l for l in all_leads if l['id'] not in history]

    if not pending:
        console.print("[yellow]⚠️ لا يوجد أي معلقين جدد في القائمة لمراسلتهم. يرجى استخراج معلقين أولاً (الخيار 2).[/yellow]")
        return

    console.print(f"\n[cyan]📊 إحصائيات سريعة:[/cyan]")
    console.print(f"• إجمالي المعلقين المحفوظين: [bold]{len(all_leads)}[/bold]")
    console.print(f"• تمت مراسلتهم سابقاً: [bold]{len(history)}[/bold]")
    console.print(f"• جاهزون للمراسلة الآن: [bold green]{len(pending)}[/bold green]")

    count = IntPrompt.ask("\n💬 كم رسالة تريد إرسالها في هذه الجلسة؟ (الحد الآمن الموصى به: 10 إلى 20)", default=min(10, len(pending)))

    confirm = Prompt.ask(f"[bold yellow]هل أنت متأكد من بدء إرسال {count} رسالة؟ (y/n)[/bold yellow]", choices=["y", "n"], default="y")
    if confirm.lower() != "y":
        console.print("[dim]تم إلغاء العملية.[/dim]")
        return

    browser = FacebookBrowser(headless=False)
    page = browser.start()
    try:
        messenger = SafeMessenger(page)
        messenger.run_campaign(max_messages=count)
    finally:
        browser.close()

def option_view_template():
    """عرض وتعديل قالب الرسالة وفحص الـ Spintax"""
    template = get_message_template()
    console.print(Panel(template, title="📝 نموذج الرسالة الحالي (Spintax)"))

    console.print("\n[bold cyan]🧪 معاينة 3 أمثلة عشوائية لما سيصل للناس:[/bold cyan]")
    for i in range(1, 4):
        sample = parse_spintax(template).replace("{name}", "محمد")
        console.print(f"\n[bold green]📌 رسالة تجريبية {i}:[/bold green]\n{sample}")

    console.print(f"\n[dim]💡 لتعديل نص الرسالة أو إضافة رابط كتابك، يمكنك فتح الملف مباشرة:[/dim]")
    console.print(f"[bold yellow]{TEMPLATES_FILE}[/bold yellow]")

def option_view_stats():
    """عرض إحصائيات المعلقين والسجل"""
    all_leads = load_leads()
    history = load_history()

    table = Table(title="📊 إحصائيات البوت الحالية")
    table.add_column("المعيار", style="cyan")
    table.add_column("العدد", style="bold green")

    table.add_row("إجمالي المعلقين المستخرجين (Leads)", str(len(all_leads)))
    table.add_row("الأشخاص الذين تم التواصل معهم (Sent)", str(len(history)))
    table.add_row("الأشخاص المتبقون (Pending)", str(len([l for l in all_leads if l['id'] not in history])))

    console.print(table)

    if all_leads:
        recent_table = Table(title="آخر 5 معلقين تم استخراجهم")
        recent_table.add_column("الاسم", style="bold")
        recent_table.add_column("معرف المستخدم (ID)")
        recent_table.add_column("رابط البروفايل", style="dim")

        for lead in all_leads[-5:]:
            recent_table.add_row(lead.get('name', ''), lead.get('id', ''), lead.get('profile_url', ''))
        console.print(recent_table)

def main_menu():
    """القائمة الرئيسية التفاعلية"""
    while True:
        console.print("\n")
        show_banner()
        console.print("[bold]اختر العملية التي تريد القيام بها:[/bold]")
        console.print("  [bold cyan]1[/bold cyan] - 🔐 تسجيل الدخول لفيسبوك وحفظ الجلسة (لأول مرة)")
        console.print("  [bold cyan]2[/bold cyan] - 🔍 استخراج المعلقين المهتمين من منشور قصة (Scrape Comments)")
        console.print("  [bold cyan]3[/bold cyan] - 🚀 بدء إرسال الرسائل التلقائية الآمنة (Send Messages)")
        console.print("  [bold cyan]4[/bold cyan] - 📝 معاينة وتعديل نص الرسالة (Message Template & Spintax)")
        console.print("  [bold cyan]5[/bold cyan] - 📊 عرض قائمة المعلقين والإحصائيات")
        console.print("  [bold cyan]6[/bold cyan] - ❌ خروج (Exit)")

        choice = Prompt.ask("\n👉 أدخل رقم الخيار", choices=["1", "2", "3", "4", "5", "6"], default="1")

        if choice == "1":
            option_login()
        elif choice == "2":
            option_scrape()
        elif choice == "3":
            option_send_messages()
        elif choice == "4":
            option_view_template()
        elif choice == "5":
            option_view_stats()
        elif choice == "6":
            console.print("[bold green]مع السلامة وبالتوفيق في مبيعات كتابك! 👋[/bold green]")
            sys.exit(0)

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]تم إيقاف البرنامج.[/yellow]")
