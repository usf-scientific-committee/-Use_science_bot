"""
Scientific Content Classifier
==============================
Detects whether a Telegram message contains scientific content.
Uses keyword matching, hashtag detection, and scoring.
"""

import re
import logging
from typing import Tuple, List, Dict
from database import get_custom_keywords
from config import CLASSIFICATION_THRESHOLD

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
#   Arabic Scientific Keywords (with weights)
# ─────────────────────────────────────────────────
SCIENTIFIC_KEYWORDS_AR: Dict[str, int] = {
    # Core science terms (weight 3)
    "علوم": 3, "علم": 2, "بحث علمي": 3, "دراسة علمية": 3,
    "مقال علمي": 3, "تجربة علمية": 3, "اكتشاف علمي": 3,
    # Physics
    "فيزياء": 3, "ميكانيكا": 3, "ديناميكا": 3, "كهرومغناطيسية": 3,
    "كم": 2, "ميكانيكا الكم": 3, "نسبية": 3, "جاذبية": 2,
    "قوة": 1, "طاقة": 2, "شغل": 1, "قدرة": 1, "موجة": 2,
    "تردد": 2, "ضوء": 2, "فوتون": 3, "إلكترون": 3, "بروتون": 3,
    "نيوترون": 3, "نواة": 2, "ذرة": 3, "جسيم": 2,
    # Chemistry
    "كيمياء": 3, "عنصر": 2, "مركب": 2, "تفاعل كيميائي": 3,
    "جزيء": 3, "حمض": 2, "قاعدة": 1, "أكسدة": 3, "اختزال": 2,
    "بوليمر": 3, "هيدروكربون": 3, "كيمياء عضوية": 3, "عناصر": 2,
    "جدول دوري": 3, "أيون": 3, "روابط": 2, "تكافؤ": 3,
    # Biology
    "أحياء": 3, "بيولوجيا": 3, "خلية": 2, "بكتيريا": 3,
    "فيروس": 3, "جرثومة": 2, "جينات": 3, "dna": 3, "rna": 3,
    "كروموسوم": 3, "حمض نووي": 3, "بروتين": 3, "أنزيم": 3,
    "تطور": 2, "طفرة": 3, "وراثة": 3, "نبات": 2, "حيوان": 1,
    "مملكة": 1, "نظام بيئي": 3, "تمثيل ضوئي": 3, "إيض": 2,
    # Medicine
    "طب": 3, "دواء": 2, "علاج": 2, "مرض": 2, "لقاح": 3,
    "جراحة": 2, "تشريح": 3, "فسيولوجيا": 3, "سرطان": 2,
    "مناعة": 3, "هرمون": 3, "عصبية": 2, "قلب": 1, "دماغ": 2,
    # Mathematics
    "رياضيات": 3, "جبر": 3, "هندسة": 2, "حساب": 2, "إحصاء": 3,
    "احتمال": 3, "معادلة": 3, "متباينة": 3, "مصفوفة": 3,
    "دوال": 2, "تفاضل": 3, "تكامل": 3, "أعداد": 1, "منطق": 2,
    # Astronomy / Space
    "فلك": 3, "فضاء": 3, "كوكب": 3, "نجم": 2, "مجرة": 3,
    "ثقب أسود": 3, "انفجار عظيم": 3, "كون": 2, "مذنب": 3,
    "قمر": 1, "شمس": 1, "كسوف": 3, "خسوف": 3, "مريخ": 2,
    "ناسا": 3, "مسبار": 3, "تلسكوب": 3, "مدار": 2,
    # Technology / CS / AI
    "ذكاء اصطناعي": 3, "تعلم الآلة": 3, "تعلم عميق": 3,
    "شبكة عصبية": 3, "خوارزمية": 3, "برمجة": 2, "كود": 2,
    "حاسوب": 2, "بيانات": 2, "إنترنت": 1, "سحابة": 1,
    "أمن معلومات": 3, "روبوت": 3, "أتمتة": 3, "بلوك تشين": 3,
    "كوانتم كمبيوتر": 3, "ميتافيرس": 2, "تقنية": 2, "رقمي": 1,
    # Environment / Earth
    "مناخ": 2, "بيئة": 2, "جيولوجيا": 3, "تغير مناخي": 3,
    "طاقة متجددة": 3, "طاقة شمسية": 3, "طاقة نووية": 3,
    "زلزال": 2, "بركان": 2, "مياه جوفية": 3, "غلاف جوي": 3,
    # Research / Academic
    "بحث": 2, "دراسة": 2, "مختبر": 3, "تجربة": 2, "نظرية": 2,
    "فرضية": 3, "علماء": 2, "باحثون": 2, "اكتشاف": 2,
    "ابتكار": 2, "اختراع": 2, "براءة اختراع": 3, "مجلة علمية": 3,
    "ورقة بحثية": 3, "نتائج": 1, "منهجية": 2,
    # Nano / Bio tech
    "نانو": 3, "نانوتكنولوجي": 3, "بيوتكنولوجي": 3,
    "هندسة وراثية": 3, "استنساخ": 3,
}

# ─────────────────────────────────────────────────
#   English Scientific Keywords (with weights)
# ─────────────────────────────────────────────────
SCIENTIFIC_KEYWORDS_EN: Dict[str, int] = {
    # Core
    "science": 3, "scientific": 3, "research": 2, "study": 2,
    "experiment": 3, "theory": 2, "hypothesis": 3, "discovery": 2,
    "innovation": 2, "invention": 2, "patent": 2, "lab": 2,
    "laboratory": 3, "scientist": 2, "researcher": 2,
    # Physics
    "physics": 3, "quantum": 3, "mechanics": 3, "thermodynamics": 3,
    "electromagnetism": 3, "relativity": 3, "gravity": 2, "force": 1,
    "energy": 2, "photon": 3, "electron": 3, "proton": 3,
    "neutron": 3, "nucleus": 3, "atom": 3, "particle": 2, "wave": 2,
    # Chemistry
    "chemistry": 3, "molecule": 3, "compound": 2, "element": 2,
    "periodic table": 3, "reaction": 2, "acid": 2, "polymer": 3,
    "hydrocarbon": 3, "organic chemistry": 3, "ion": 3,
    # Biology
    "biology": 3, "cell": 2, "bacteria": 3, "virus": 3,
    "gene": 3, "dna": 3, "rna": 3, "chromosome": 3,
    "protein": 3, "enzyme": 3, "evolution": 2, "mutation": 3,
    "genetics": 3, "ecosystem": 3, "photosynthesis": 3,
    # Medicine
    "medicine": 3, "drug": 2, "treatment": 2, "disease": 2,
    "vaccine": 3, "surgery": 2, "anatomy": 3, "physiology": 3,
    "cancer": 2, "immunity": 3, "hormone": 3, "neuroscience": 3,
    # Math
    "mathematics": 3, "algebra": 3, "geometry": 2, "calculus": 3,
    "statistics": 3, "probability": 3, "equation": 3, "matrix": 3,
    "algorithm": 3, "theorem": 3, "differential": 3, "integral": 3,
    # Astronomy
    "astronomy": 3, "space": 2, "planet": 3, "star": 2,
    "galaxy": 3, "black hole": 3, "big bang": 3, "universe": 2,
    "comet": 3, "telescope": 3, "nasa": 3, "orbit": 2, "nebula": 3,
    # Tech / AI / CS
    "artificial intelligence": 3, "machine learning": 3,
    "deep learning": 3, "neural network": 3, "programming": 2,
    "algorithm": 3, "data science": 3, "cybersecurity": 3,
    "robotics": 3, "automation": 3, "blockchain": 3,
    "quantum computing": 3, "cloud computing": 2,
    # Environment
    "climate": 2, "environment": 2, "geology": 3, "climate change": 3,
    "renewable energy": 3, "solar energy": 3, "nuclear energy": 3,
    "earthquake": 2, "volcano": 2, "atmosphere": 3,
    # Nano / Bio tech
    "nanotechnology": 3, "biotechnology": 3, "genetic engineering": 3,
    "cloning": 3, "stem cell": 3,
}

# ─────────────────────────────────────────────────
#   Scientific Hashtags
# ─────────────────────────────────────────────────
SCIENTIFIC_HASHTAGS = {
    "#علوم", "#علم", "#بحث_علمي", "#اكتشاف", "#ابتكار", "#اختراع",
    "#فيزياء", "#كيمياء", "#أحياء", "#بيولوجيا", "#رياضيات", "#هندسة",
    "#طب", "#فلك", "#فضاء", "#تقنية", "#ذكاء_اصطناعي", "#برمجة",
    "#تعلم_الآلة", "#تعلم_عميق", "#علم_البيانات", "#روبوت", "#نانو",
    "#بيئة", "#مناخ", "#طاقة", "#جيولوجيا", "#وراثة", "#جينات",
    "#مختبر", "#تجربة", "#دراسة", "#بحث", "#ناسا", "#فضاء_خارجي",
    "#science", "#physics", "#chemistry", "#biology", "#mathematics",
    "#math", "#engineering", "#medicine", "#astronomy", "#space",
    "#technology", "#tech", "#ai", "#machinelearning", "#deeplearning",
    "#datascience", "#programming", "#coding", "#research", "#discovery",
    "#innovation", "#invention", "#laboratory", "#experiment", "#theory",
    "#genetics", "#energy", "#environment", "#climate", "#robotics",
    "#nanotechnology", "#biotechnology", "#neuroscience", "#quantum",
    "#stem", "#sciencefacts", "#scientificfacts", "#علوم_تقنية",
}

# ─────────────────────────────────────────────────
#   Science Categories Map
# ─────────────────────────────────────────────────
CATEGORY_MAP = {
    "فيزياء": ["فيزياء", "ميكانيكا", "كم", "نسبية", "موجة", "فوتون", "إلكترون", "physics", "quantum", "mechanics"],
    "كيمياء": ["كيمياء", "جزيء", "تفاعل", "عنصر", "حمض", "chemistry", "molecule", "reaction"],
    "أحياء": ["أحياء", "بيولوجيا", "خلية", "جينات", "dna", "biology", "cell", "genetics", "evolution"],
    "طب": ["طب", "دواء", "علاج", "لقاح", "medicine", "drug", "vaccine", "disease"],
    "رياضيات": ["رياضيات", "جبر", "تفاضل", "إحصاء", "mathematics", "algebra", "calculus", "statistics"],
    "فلك": ["فلك", "فضاء", "كوكب", "نجم", "مجرة", "astronomy", "space", "planet", "galaxy"],
    "تقنية": ["تقنية", "برمجة", "ذكاء اصطناعي", "خوارزمية", "technology", "programming", "ai", "algorithm"],
    "بيئة": ["بيئة", "مناخ", "جيولوجيا", "environment", "climate", "geology"],
    "هندسة": ["هندسة", "روبوت", "أتمتة", "engineering", "robotics", "automation"],
    "نانو/بيوتك": ["نانو", "هندسة وراثية", "nanotechnology", "biotechnology", "genetic engineering"],
}


def extract_hashtags(text: str) -> List[str]:
    """Extract all hashtags from text."""
    return re.findall(r"#\S+", text)


def classify_content(text: str) -> Tuple[bool, List[str], List[str], List[str], int]:
    """
    Classify content as scientific or not.

    Returns:
        (is_scientific, categories, detected_keywords, detected_hashtags, score)
    """
    if not text:
        return False, [], [], [], 0

    text_lower = text.lower()
    score = 0
    detected_keywords = []
    detected_hashtags = []

    # ── Hashtag Detection (high weight) ──
    found_hashtags = extract_hashtags(text)
    for tag in found_hashtags:
        tag_lower = tag.lower()
        if tag_lower in {h.lower() for h in SCIENTIFIC_HASHTAGS}:
            detected_hashtags.append(tag)
            score += 4  # Hashtags = strong signal

    # ── Arabic Keyword Detection ──
    for kw, weight in SCIENTIFIC_KEYWORDS_AR.items():
        if kw in text_lower:
            detected_keywords.append(kw)
            score += weight

    # ── English Keyword Detection ──
    for kw, weight in SCIENTIFIC_KEYWORDS_EN.items():
        if kw in text_lower:
            if kw not in detected_keywords:
                detected_keywords.append(kw)
            score += weight

    # ── Custom Keywords from DB ──
    try:
        custom = get_custom_keywords()
        for ck in custom:
            if ck["keyword"] in text_lower:
                detected_keywords.append(ck["keyword"])
                score += ck["weight"]
    except Exception as e:
        logger.warning(f"Could not load custom keywords: {e}")

    # ── Determine Categories ──
    categories = []
    for cat, cat_keywords in CATEGORY_MAP.items():
        for ck in cat_keywords:
            if ck in text_lower:
                if cat not in categories:
                    categories.append(cat)
                break

    is_scientific = score >= CLASSIFICATION_THRESHOLD

    return is_scientific, categories, detected_keywords[:15], detected_hashtags, score


def get_media_type(message) -> str:
    """Determine media type of a Telegram message."""
    if message.video or message.video_note:
        return "video"
    elif message.photo:
        return "photo"
    elif message.document:
        return "document"
    elif message.audio or message.voice:
        return "audio"
    elif message.animation:
        return "animation"
    elif message.text:
        return "text"
    return "other"


def get_message_text(message) -> str:
    """Extract full text from a message (text or caption)."""
    if message.text:
        return message.text
    elif message.caption:
        return message.caption
    return ""
