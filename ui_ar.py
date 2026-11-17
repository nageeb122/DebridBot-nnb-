"""Arabic Telegram interface helpers. Existing download/debrid handlers remain unchanged."""
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 فك رابط تحميل", callback_data="menu:link")],
        [
            InlineKeyboardButton("⚙️ اختيار الخدمة", callback_data="menu:services"),
            InlineKeyboardButton("🧲 إدارة التورنت", callback_data="menu:torrents"),
        ],
        [
            InlineKeyboardButton("📖 المساعدة", callback_data="menu:help"),
            InlineKeyboardButton("ℹ️ حول البوت", callback_data="menu:about"),
        ],
    ])


def welcome_text(username: str | None = None) -> str:
    greeting = f"أهلاً {username} 👋" if username else "أهلاً بك 👋"
    return (
        f"{greeting}\n\n"
        "أنا بوت لإدارة روابط التحميل وخدمات Debrid والتورنت.\n"
        "أرسل رابط التحميل هنا وسأحاول تجهيزه لك.\n\n"
        "اختر أحد الأزرار للبدء:"
    )


def about_text() -> str:
    return (
        "🤖 **DebridBot**\n\n"
        "بوت تيليجرام لمعالجة روابط التحميل والتورنت عبر خدمات Debrid "
        "المضبوطة في الخادم.\n\n"
        "أرسل رابطاً مباشراً أو رابط استضافة أو Magnet، "
        "وسأعرض الخيارات المتاحة بحسب الخدمة."
    )


def help_text() -> str:
    return (
        "📖 **طريقة الاستخدام**\n\n"
        "1. أرسل رابط التحميل في المحادثة.\n"
        "2. اختر الخدمة أو اترك البوت يستخدم الخدمة النشطة.\n"
        "3. اختر الحصول على رابط مباشر أو تنزيل الملف إلى تيليجرام.\n\n"
        "**الأوامر:**\n"
        "/start — القائمة الرئيسية\n"
        "/menu — عرض القائمة الرئيسية\n"
        "/service — اختيار خدمة Debrid\n"
        "/torrents — إدارة التورنت\n"
        "/wget رابط — تنزيل الرابط مباشرة دون فكّه عبر Debrid\n"
        "/help — المساعدة\n\n"
        "يدعم البوت أيضاً روابط Magnet وملفات .torrent."
    )


def menu_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="menu:home")]
    ])
