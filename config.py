import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = BASE_DIR / "profiles"      # مجلد تخزين الحسابات المتعددة
PROFILE_DIR = PROFILES_DIR / "account_1" # الحساب الافتراضي
ACCOUNTS_FILE = DATA_DIR / "accounts.json" # سجل الحسابات المتاحة
LEADS_FILE = DATA_DIR / "leads.csv"
HISTORY_FILE = DATA_DIR / "history.json"
POSTER_HISTORY_FILE = DATA_DIR / "poster_history.json" # ذاكرة المجموعات المنشورة
TEMPLATES_FILE = BASE_DIR / "templates.txt"
REPLY_TEMPLATES_FILE = BASE_DIR / "reply_templates.json" # نماذج الردود على التعليقات
VIRAL_POSTS_FILE = DATA_DIR / "viral_posts.csv"          # نتائج التجسس على المنشورات الفيروسية
TIER1_LEADS_FILE = DATA_DIR / "tier1_leads.csv"          # العملاء المستهدفين حسب الدولة (Tier-1)
FRIEND_REQUESTS_FILE = DATA_DIR / "friend_requests_history.json" # سجل طلبات الصداقة المرسلة

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Safety & Anti-Ban Settings
MIN_DELAY_SECONDS = 90     # الحد الأدنى للانتظار بين الرسائل (ثانية)
MAX_DELAY_SECONDS = 180    # الحد الأقصى للانتظار بين الرسائل (ثانية)
MAX_MESSAGES_PER_DAY = 20  # أقصى عدد رسائل في اليوم لكل حساب للحماية من الحظر
TYPING_SPEED_RANGE = (0.05, 0.15) # سرعة الكتابة لمحاكاة إنسان حقيقي (ثواني بين الحروف)

# Friend Request Safety Settings
MAX_FRIEND_REQUESTS_PER_DAY = 15
MIN_FRIEND_DELAY_SECONDS = 40
MAX_FRIEND_DELAY_SECONDS = 85

# Default Tier-1 Countries & Major Regions
DEFAULT_TIER1_LOCATIONS = [
    "united states", "usa", "u.s.a", "u.s.", "america",
    "united kingdom", "uk", "great britain", "england", "scotland", "wales",
    "canada", "australia", "new zealand", "ireland",
    "california", "texas", "florida", "new york", "ohio", "pennsylvania", "illinois",
    "georgia", "north carolina", "michigan", "london", "toronto", "sydney", "melbourne"
]

# Default Spintax Templates (English for international readers)
DEFAULT_SPINTAX = """{Hey|Hi|Hello} {name}! {Saw your comment on the story post in the Facebook group|Noticed you're a fellow fan of gripping stories|Came across your comment on that story discussion earlier}.

{I'm an indie author and recently finished writing a new fiction/story book full of suspense and unexpected twists|As someone who loves good stories, I just published a new short story collection|I recently put together a collection of thrilling stories that I think you'd love}.

{I'd love to gift you the first chapter completely free to read and check out|I'd be thrilled to share a free sample preview with you|Here is a free link to read the opening chapters with no strings attached}:
https://your-book-link.com/free-sample

{Hope you enjoy the read! Would love to hear what you think of the twist|Have a wonderful day and happy reading|Enjoy the story, and feel free to let me know your thoughts}!"""
