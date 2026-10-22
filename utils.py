import re
import random
import json
import csv
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from config import LEADS_FILE, HISTORY_FILE, TEMPLATES_FILE, DEFAULT_SPINTAX
import sys
import io

# إجبار الكونسول على دعم الترميز العربي والرموز (UTF-8) على ويندوز
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

console = Console(force_terminal=True)

def parse_spintax(text: str) -> str:
    """
    تحويل نصوص الـ Spintax مثل {خيار 1|خيار 2|خيار 3} إلى نص عشوائي فريد
    لضمان أن كل رسالة تخرج بصيغة مختلفة عن الأخرى لتجنب كشف السبام.
    """
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        choices = match.group(1).split('|')
        text = text[:match.start()] + random.choice(choices) + text[match.end():]
    return text

def get_message_template() -> str:
    """قراءة نموذج الرسالة من ملف templates.txt أو إنشاءه بالنموذج الافتراضي"""
    if not TEMPLATES_FILE.exists():
        with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_SPINTAX)
        return DEFAULT_SPINTAX
    with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        return content if content else DEFAULT_SPINTAX

def load_history() -> dict:
    """تحميل سجل الأشخاص الذين تمت مراسلتهم سابقاً"""
    if not HISTORY_FILE.exists():
        return {}
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

from config import LEADS_FILE, HISTORY_FILE, TEMPLATES_FILE, DEFAULT_SPINTAX, REPLY_TEMPLATES_FILE

def get_reply_templates() -> dict:
    """قراءة قوالب الردود على التعليقات"""
    defaults = {
        "reply_sent_dm": "{Hey|Hi|Hello} {name}! {I'm the author and just sent you the free chapter in your DMs / Message Requests|Just dropped the free story preview in your private messages, make sure to check requests|Sent over the free chapter link to your inbox}! {Hope you enjoy the read|Let me know what you think of the twist|Have a wonderful read}!",
        "reply_inbound_invite": "{Hey|Hi|Hello} {name}! {I'm an indie author and would love to share the free chapter preview with you|As someone who loves good mystery stories, I'd be happy to share the opening chapters with you}! {Feel free to shoot me a quick DM and I'll send the direct link right over|Drop me a quick message in chat and I'll send it to you right away|Send me a message in DM and I'll pass along the free link}! {Happy reading|Looking forward to hearing your thoughts}!"
    }
    if not REPLY_TEMPLATES_FILE.exists():
        with open(REPLY_TEMPLATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(defaults, f, indent=2, ensure_ascii=False)
        return defaults
    try:
        with open(REPLY_TEMPLATES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return defaults

def save_reply_templates(data: dict):
    """حفظ قوالب الردود على التعليقات"""
    with open(REPLY_TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_to_history(profile_id: str, name: str, account: str = "account_1", action: str = "dm", status: str = "sent"):
    """حفظ بروفايل في السجل المركزي المشترك بين جميع الحسابات لمنع التكرار"""
    history = load_history()
    history[profile_id] = {
        "name": name,
        "account": account,
        "action": action,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": status
    }
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def is_already_messaged(profile_id: str) -> bool:
    """فحص هل تمت مراسلة هذا الشخص من قبل"""
    history = load_history()
    return profile_id in history

def save_leads(leads: list[dict]):
    """حفظ العملاء المحتملين (Leads) في ملف CSV"""
    file_exists = LEADS_FILE.exists()
    keys = ["id", "name", "profile_url", "comment_text", "post_url", "scraped_at"]
    
    with open(LEADS_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        if not file_exists:
            writer.writeheader()
        for lead in leads:
            writer.writerow(lead)

def load_leads(file_path=None) -> list[dict]:
    """تحميل قائمة المعلقين المحفوظين في ملف CSV (يدعم leads.csv أو tier1_leads.csv)"""
    target = file_path if file_path is not None else LEADS_FILE
    if not target.exists():
        return []
    leads = []
    with open(target, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'id' not in row or not row['id']:
                # إنشاء id فريد من رابط البروفايل إذا لم يكن موجوداً
                row['id'] = row.get('profile_url', '').split('?')[0].rstrip('/')
            leads.append(row)
    return leads

def show_banner():
    """عرض شعار البوت الترحيبي"""
    console.print(Panel.fit(
        "[bold cyan]🤖 Group Facebook Bot[/bold cyan]\n"
        "[dim]Facebook Groups Comment Scraper & Safe Outreach Engine[/dim]",
        border_style="cyan"
    ))
