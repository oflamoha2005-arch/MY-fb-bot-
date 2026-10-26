import json
import os
import sys
from datetime import datetime
from pathlib import Path
import requests

from config import TELEGRAM_CONFIG_FILE
from utils import console

def load_telegram_config() -> dict:
    """تحميل إعدادات بوت تليجرام"""
    if not TELEGRAM_CONFIG_FILE.exists():
        default_config = {
            "bot_token": "",
            "chat_id": "",
            "enabled": True
        }
        try:
            with open(TELEGRAM_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
            return default_config
        except Exception:
            return default_config
    try:
        with open(TELEGRAM_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"bot_token": "", "chat_id": "", "enabled": False}

def save_telegram_config(bot_token: str, chat_id: str, enabled: bool = True):
    """حفظ إعدادات بوت تليجرام"""
    config = {
        "bot_token": str(bot_token).strip(),
        "chat_id": str(chat_id).strip(),
        "enabled": bool(enabled)
    }
    try:
        with open(TELEGRAM_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        console.print(f"[red]Error saving telegram config: {str(e)}[/red]")

def is_telegram_configured() -> bool:
    """فحص هل إعدادات تليجرام مكتملة ومفعلة"""
    cfg = load_telegram_config()
    return bool(cfg.get("enabled") and cfg.get("bot_token") and cfg.get("chat_id"))

def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """إرسال رسالة نصية فورية إلى تليجرام"""
    cfg = load_telegram_config()
    if not cfg.get("enabled"):
        return False
    bot_token = cfg.get("bot_token", "").strip()
    chat_id = cfg.get("chat_id", "").strip()
    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        res_data = response.json()
        if res_data.get("ok"):
            return True
        else:
            # إعادة المحاولة بدون parse_mode في حالة وجود خطأ في تنسيق HTML
            payload.pop("parse_mode", None)
            res2 = requests.post(url, json=payload, timeout=15)
            return bool(res2.json().get("ok"))
    except Exception as e:
        console.print(f"[yellow]⚠️ Telegram send error: {str(e)}[/yellow]")
        return False

def send_telegram_photo(photo_path: str, caption: str = "", parse_mode: str = "HTML") -> bool:
    """إرسال صورة / لقطة شاشة حية (Screenshot) إلى تليجرام"""
    cfg = load_telegram_config()
    if not cfg.get("enabled"):
        return False
    bot_token = cfg.get("bot_token", "").strip()
    chat_id = cfg.get("chat_id", "").strip()
    if not bot_token or not chat_id:
        return False

    if not photo_path or not Path(photo_path).exists():
        # إذا تعذر العثور على مسار الصورة، نرسل الرسالة كنص بديل
        return send_telegram_message(caption, parse_mode=parse_mode)

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    data = {
        "chat_id": chat_id,
        "caption": caption[:1024], # حد تليجرام لنص الصورة
        "parse_mode": parse_mode
    }

    try:
        with open(photo_path, "rb") as img_file:
            files = {"photo": img_file}
            response = requests.post(url, data=data, files=files, timeout=25)
            res_data = response.json()
            if res_data.get("ok"):
                return True
            else:
                data.pop("parse_mode", None)
                img_file.seek(0)
                res2 = requests.post(url, data=data, files={"photo": img_file}, timeout=25)
                return bool(res2.json().get("ok"))
    except Exception as e:
        console.print(f"[yellow]⚠️ Telegram photo error: {str(e)}[/yellow]")
        # محاولة إرسال التنبيه كنص على الأقل
        return send_telegram_message(caption, parse_mode=parse_mode)

def notify_checkpoint_alert(account_name: str, reason: str, screenshot_path: str = None) -> bool:
    """
    إرسال تنبيه طوارئ فوري مع لقطة الشاشة الحية (Live Screenshot)
    عند رصد Checkpoint أو Captcha أو حظر مؤقت
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🚨 <b>تنبيه أمان فيسبوك عاجل! (Emergency Alert)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>الحساب المتأثر:</b> <code>{account_name}</code>\n"
        f"🛑 <b>نوع المشكلة:</b> {reason}\n"
        f"⏰ <b>الوقت:</b> {now_str}\n"
        f"🛡️ <b>الإجراء التلقائي:</b> تم إيقاف جلسة الحساب فوراً لحمايته وتفادي الحظر النهائي، والتحويل للحساب الموالي.\n\n"
        f"📸 مرفق لقطة شاشة حية من المتصفح لمعاينة المشكلة."
    )
    if screenshot_path and Path(screenshot_path).exists():
        return send_telegram_photo(screenshot_path, caption=msg)
    else:
        return send_telegram_message(msg)

def notify_campaign_completed(campaign_title: str, stats: dict) -> bool:
    """
    إرسال تقرير إنجاز ختامي عند انتهاء حملة النشر في المجموعات
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    posted = stats.get("total_posted", 0)
    groups_count = stats.get("total_groups", 0)
    accounts_used = stats.get("accounts_used", 1)

    msg = (
        f"🎉 <b>اكتملت حملة النشر في المجموعات بنجاح!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📢 <b>الحملة:</b> {campaign_title}\n"
        f"📌 <b>المنشورات الناجحة:</b> {posted} منشور\n"
        f"👥 <b>الحسابات المشاركة:</b> {accounts_used} حسابات\n"
        f"⏰ <b>وقت الانتهاء:</b> {now_str}\n\n"
        f"✨ جميع المهام المحددة نُفّذت بسلاسة مع فواصل الأمان الطبيعية."
    )
    return send_telegram_message(msg)

def notify_daily_master_completed(stats: dict) -> bool:
    """
    إرسال تقرير الروتين اليومي الشامل (Daily Master Funnel Report)
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t1_leads = stats.get("tier1_leads", 0)
    dms_sent = stats.get("dms_sent", 0)
    replies_posted = stats.get("replies_posted", 0)
    friends_sent = stats.get("friend_requests_sent", 0)
    group_posts = stats.get("group_posts_made", 0)
    warmup_min = stats.get("warmup_minutes", 0)

    msg = (
        f"🏆 <b>تقرير الإنجاز اليومي الشامل (Daily Master Funnel)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>قراء Tier-1 المؤهلين (USA / UK / Europe / CA / AU):</b> {t1_leads} قارئ\n"
        f"💬 <b>الرسائل المباشرة المرسلة (DMs):</b> {dms_sent} رسالة\n"
        f"🔔 <b>الردود التنبيهية على التعليقات:</b> {replies_posted} رد\n"
        f"🤝 <b>طلبات الصداقة الجديدة:</b> {friends_sent} طلب\n"
        f"📢 <b>منشورات قصة الكتاب في المجموعات:</b> {group_posts} منشور\n"
        f"🔥 <b>دقائق التسخين والتصفح البشري:</b> {warmup_min} دقيقة\n"
        f"⏰ <b>توقيت إتمام المهام:</b> {now_str}\n\n"
        f"✅ تمت أتمتة جميع المراحل بنجاح تام وفق معايير الأمان القصوى!"
    )
    return send_telegram_message(msg)

def test_telegram_connection() -> tuple[bool, str]:
    """اختبار الاتصال مع تليجرام وإرسال رسالة تجريبية"""
    cfg = load_telegram_config()
    bot_token = cfg.get("bot_token", "").strip()
    chat_id = cfg.get("chat_id", "").strip()

    if not bot_token or not chat_id:
        return False, "Bot Token أو Chat ID غير محددين في الإعدادات."

    test_msg = (
        "👋 <b>مرحباً بك!</b>\n\n"
        "🟢 <b>اختبار الاتصال ناجح 100%!</b>\n"
        "بوت تليجرام مربوط وجاهز لاستقبال تنبيهات الطوارئ وسكرينشوتات الحسابات وتقارير الحملات أولاً بأول."
    )
    ok = send_telegram_message(test_msg)
    if ok:
        return True, "تم إرسال رسالة التجربة إلى هاتفك بنجاح!"
    else:
        return False, "فشل الاتصال بتليجرام. يرجى التأكد من الـ Token والـ Chat ID."

if __name__ == "__main__":
    success, message = test_telegram_connection()
    print("Test result:", success, message)
