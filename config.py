import os
import json
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
SCRAPED_POSTS_FILE = DATA_DIR / "scraped_posts_history.json" # سجل روابط المنشورات التي تم سحب تعليقاتها لتجنب التكرار
TIER1_LEADS_FILE = DATA_DIR / "tier1_leads.csv"          # العملاء المستهدفين حسب الدولة (Tier-1)
TIER1_LOCATIONS_FILE = DATA_DIR / "tier1_locations.json" # قاعدة بيانات المدن والولايات والمناطق الجغرافية لـ Tier-1
FRIEND_REQUESTS_FILE = DATA_DIR / "friend_requests_history.json" # سجل طلبات الصداقة المرسلة
KEYWORDS_FILE = BASE_DIR / "keywords.txt"                 # كلمات مفتاحية لمطابقة النيتش (قصص، روايات)
SPY_HISTORY_FILE = DATA_DIR / "spy_history.json"          # ذاكرة المجموعات التي تم فحصها مؤخراً
GROUPS_FILE = BASE_DIR / "groups.txt"                      # ملف روابط المجموعات
POSTS_FILE = BASE_DIR / "posts.txt"                        # ملف نصوص وقوالب المنشورات
ACCOUNTS_HEALTH_FILE = DATA_DIR / "accounts_health.json"   # قاعدة بيانات صحة الحسابات ومراقبة الكوطا اليومية
TELEGRAM_CONFIG_FILE = DATA_DIR / "telegram_config.json"   # إعدادات بوت تليجرام للتنبيهات الفورية


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

# Comprehensive Tier-1 Countries, All 50 US States, Major Provinces & Buying-Power Cities
DEFAULT_TIER1_LOCATIONS = [
    # 1. Countries & Core Identifiers
    "united states", "united states of america", "usa", "u.s.a", "u.s.", "america",
    "united kingdom", "uk", "u.k.", "great britain", "britain", "england", "scotland", "wales", "northern ireland",
    "canada", "australia", "new zealand", "ireland",

    # 2. All 50 US States + District of Columbia
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas",
    "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington", "west virginia",
    "wisconsin", "wyoming", "district of columbia", "washington d.c.", "washington dc",

    # 3. Top Major US Metropolitan Cities
    "new york city", "nyc", "los angeles", "chicago", "houston", "phoenix", "philadelphia", "san antonio",
    "san diego", "dallas", "austin", "san jose", "fort worth", "jackonville", "columbus", "charlotte",
    "indianapolis", "san francisco", "seattle", "denver", "oklahoma city", "nashville", "el paso",
    "boston", "las vegas", "portland", "detroit", "louisville", "memphis", "baltimore", "milwaukee",
    "albuquerque", "tucson", "fresno", "sacramento", "kansas city", "mesa", "atlanta", "omaha",
    "raleigh", "colorado springs", "miami", "virginia beach", "oakland", "minneapolis", "tulsa",
    "arlington", "new orleans", "wichita", "cleveland", "tampa", "orlando", "pittsburgh", "cincinnati",
    "st. louis", "saint louis", "salt lake city", "honolulu",

    # 4. United Kingdom Major Cities & Regions
    "london", "manchester", "birmingham", "leeds", "glasgow", "liverpool", "newcastle", "sheffield",
    "bristol", "edinburgh", "belfast", "cardiff", "nottingham", "southampton", "leicester", "coventry",
    "hull", "bradford", "stoke-on-trent", "wolverhampton", "plymouth", "derby", "reading", "aberdeen",
    "swansea", "oxford", "cambridge", "york", "brighton", "bath",

    # 5. Canada Provinces & Major Cities
    "ontario", "quebec", "british columbia", "alberta", "manitoba", "saskatchewan", "nova scotia", "new brunswick",
    "toronto", "montreal", "vancouver", "calgary", "edmonton", "ottawa", "winnipeg", "quebec city",
    "hamilton", "kitchener", "victoria", "halifax", "windsor", "saskatoon", "regina",

    # 6. Australia States & Major Cities
    "new south wales", "queensland", "western australia", "south australia", "tasmania",
    "sydney", "melbourne", "brisbane", "perth", "adelaide", "gold coast", "canberra", "newcastle nsw",
    "wollongong", "hobart", "geelong", "townsville", "cairns", "darwin",

    # 7. New Zealand & Ireland Major Cities
    "auckland", "wellington", "christchurch", "hamilton nz", "tauranga", "dunedin",
    "dublin", "cork", "galway", "limerick", "waterford",

    # 8. Top European High Purchasing Power & English-Reading Nations
    # Germany (ألمانيا)
    "germany", "deutschland", "german", "germans", "berlin", "munich", "münchen", "frankfurt", "hamburg", "cologne", "köln",
    "stuttgart", "düsseldorf", "leipzig", "dortmund", "essen", "bremen", "dresden", "hanover", "nuremberg", "bonn",
    "bavaria", "bayern", "baden-württemberg", "hessen", "north rhine-westphalia", "saxony",
    # Netherlands (هولندا)
    "netherlands", "the netherlands", "holland", "dutch", "nederland", "amsterdam", "rotterdam", "the hague", "den haag", "utrecht",
    "eindhoven", "tilburg", "groningen", "almere", "breda", "nijmegen", "haarlem", "leiden", "delft", "north holland", "south holland",
    # Sweden (السويد)
    "sweden", "sverige", "swedish", "stockholm", "gothenburg", "göteborg", "malmö", "uppsala", "västerås", "örebro",
    "linköping", "helsingborg", "jönköping", "lund", "umeå", "skåne",
    # Switzerland (سويسرا)
    "switzerland", "swiss", "schweiz", "suisse", "zurich", "zürich", "geneva", "genève", "basel", "bern", "lausanne", "lucerne", "zug",
    # Norway (النرويج)
    "norway", "norge", "norwegian", "oslo", "bergen", "trondheim", "stavanger", "kristiansand", "drammen", "tromsø", "bærum",
    # Denmark (الدنمارك)
    "denmark", "danmark", "danish", "copenhagen", "københavn", "aarhus", "odense", "aalborg", "esbjerg", "roskilde",
    # Austria & Belgium & Finland (النمسا وبلجيكا وفنلندا)
    "austria", "österreich", "vienna", "salzburg", "graz", "innsbruck",
    "belgium", "belgique", "brussels", "antwerp", "ghent", "bruges", "liege",
    "finland", "suomi", "helsinki", "espoo", "tampere", "oulu", "turku",
    # France (فرنسا)
    "france", "french", "paris", "marseille", "lyon", "toulouse", "nice", "nantes", "strasbourg", "montpellier", "bordeaux", "lille", "rennes",
    # Spain (إسبانيا)
    "spain", "españa", "espana", "spanish", "madrid", "barcelona", "valencia", "seville", "sevilla", "zaragoza", "malaga", "bilbao", "palma", "catalonia", "andalusia",
    # Portugal (البرتغال)
    "portugal", "portuguese", "lisbon", "lisboa", "porto", "braga", "coimbra", "funchal", "faro", "algarve", "cascais", "sintra",
    # Italy (إيطاليا)
    "italy", "italia", "italian", "rome", "roma", "milan", "milano", "naples", "napoli", "turin", "torino", "florence", "bologna", "venice", "tuscany"
]

def load_tier1_locations() -> list[str]:
    """تحميل قائمة المدن والولايات والمناطق الجغرافية لجميع دول Tier-1 من JSON"""
    if TIER1_LOCATIONS_FILE.exists():
        try:
            with open(TIER1_LOCATIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return [d.strip().lower() for d in data if d.strip()]
        except Exception:
            pass
    return DEFAULT_TIER1_LOCATIONS

# Default Spintax Templates (English for international readers)
DEFAULT_SPINTAX = """{Hey|Hi|Hello} {name}! {Saw your comment on the story post in the Facebook group|Noticed you're a fellow fan of gripping stories|Came across your comment on that story discussion earlier}.

{I'm an indie author and recently finished writing a new fiction/story book full of suspense and unexpected twists|As someone who loves good stories, I just published a new short story collection|I recently put together a collection of thrilling stories that I think you'd love}.

{I'd love to gift you the first chapter completely free to read and check out|I'd be thrilled to share a free sample preview with you|Here is a free link to read the opening chapters with no strings attached}:
https://your-book-link.com/free-sample

{Hope you enjoy the read! Would love to hear what you think of the twist|Have a wonderful day and happy reading|Enjoy the story, and feel free to let me know your thoughts}!"""
