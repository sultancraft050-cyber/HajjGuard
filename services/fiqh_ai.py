import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)

class NusukFiqhAI:
    """
    Nusuk AI Fiqh & Ritual Copilot Engine.
    
    Provides authoritative Islamic jurisprudence (Fiqh) guidance for Hajj and Umrah
    based on the rulings of the Saudi Council of Senior Scholars (هيئة كبار العلماء),
    the Permanent Committee for Scholarly Research and Ifta, and the Ministry of Hajj & Umrah.
    
    Includes:
    1. Comprehensive embedded knowledge base across Tawaf, Sa'i, Ihram, Mina, and Jamarat.
    2. Dynamic live crowd telemetry integration via HaramSectionalEngine.
    3. Concessions & Rukhsah for elderly, sick, and wheelchair pilgrims.
    4. Dual-Engine resilient execution (Autonomous Local Engine + Gemini API fallback).
    """

    OFFICIAL_SOURCE = "وفقاً لضوابط وزارة الحج والعمرة واللجنة الدائمة للبحوث العلمية والإفتاء (هيئة كبار العلماء بالمملكة العربية السعودية)"
    OFFICIAL_SOURCE_EN = "Accredited per the rulings of the Saudi Council of Senior Scholars & Ministry of Hajj and Umrah"

    # Embedded Knowledge Categories
    KNOWLEDGE_BASE = [
        {
            'keywords': ['شك', 'اشواط', 'طواف', 'نسيت', 'ثلاث', 'اربع', 'شوط', 'doubt', 'tawaf', 'rounds', 'forget', 'three', 'four'],
            'category': 'TAWAF_DOUBT',
            'title_ar': 'الشك في عدد أشواط الطواف',
            'title_en': 'Doubting the Number of Tawaf Rounds',
            'answer_ar': (
                "إذا شككت في عدد أشواط الطواف (هل طفت ثلاثة أم أربعة مثلاً)، "
                "فالقاعدة الشرعية المعتمدة هي: **البناء على اليقين، وهو الأقل**.\n\n"
                "• اجعلها ثلاثة أشواط وأكمل بقية الأشواط حتى تتم سبعة كاملة.\n"
                "• أما إذا كان الشك بعد الفراغ التام من الطواف والانصراف منه، فلا تلتفت للشك وطوافك صحيح إن شاء الله."
            ),
            'answer_en': (
                "If you doubt the number of Tawaf rounds completed (e.g., whether you did 3 or 4), "
                "the established Islamic rule is: **Build upon certainty, which is the lesser number**.\n\n"
                "• Consider it 3 rounds and complete the remaining circuits until you reach 7 full rounds.\n"
                "• If the doubt occurs after completely finishing Tawaf and leaving the Mataf, disregard the doubt; your Tawaf is valid."
            ),
            'action_label_ar': 'متابعة عداد الطواف الذكي',
            'action_label_en': 'Open Smart Tawaf Counter',
            'action_url': '/accounts/pilgrim/'
        },
        {
            'keywords': ['حجر', 'اسماعيل', 'الحجر', 'داخل', 'hijr', 'ismail', 'hateem', 'inside'],
            'category': 'TAWAF_HIJR',
            'title_ar': 'الطواف من داخل حجر إسماعيل (الحطيم)',
            'title_en': 'Entering Inside Hijr Ismail During Tawaf',
            'answer_ar': (
                "**لا يصح الطواف من داخل حجر إسماعيل**؛ لأن الحجر جزء من الكعبة المشرفة بنص حديث عائشة رضي الله عنها.\n\n"
                "• الشوط الذي مررت فيه من داخل الحجر يعتبر **ملغياً** وغير محسوب.\n"
                "• الواجب عليك إعادة ذلك الشوط من خارج الحجر ليكتمل لك سبعة أشواط صحيحة من وراء الحجر."
            ),
            'answer_en': (
                "**Tawaf inside Hijr Ismail (Al-Hateem) is NOT valid**, because the Hijr is an integral part of the Kaaba.\n\n"
                "• The specific circuit that passed inside the Hijr is void and discounted.\n"
                "• You must re-do that round from outside the curved boundary wall of the Hijr."
            ),
            'action_label_ar': 'عرض مسارات المطاف',
            'action_label_en': 'View Mataf Corridors',
            'action_url': '/zones/map/'
        },
        {
            'keywords': ['وضوء', 'انتقض', 'اثناء', 'ريح', 'حدث', 'wudu', 'ablution', 'broke', 'purity'],
            'category': 'TAWAF_WUDU',
            'title_ar': 'انتقاض الوضوء أثناء الطواف أو السعي',
            'title_en': 'Loss of Wudu During Tawaf or Sa\'i',
            'answer_ar': (
                "• **في الطواف:** ذهب جمهور العلماء إلى اشتراط الطهارة للطواف. فإذا انتقض وضوؤك، تخرج وتتوضأ ثم تبني على ما طفته عند الإمام أحمد وكثير من المحققين كشيخ الإسلام ابن تيمية، أو تعيد الطواف احتياطاً.\n"
                "• **في السعي بين الصفا والمروة:** الطهارة في السعي **مستحبة وليست شرطاً**. فلو انتقض وضوؤك أثناء السعي، فسعيك صحيح وتكمله ولا حرج عليك."
            ),
            'answer_en': (
                "• **During Tawaf:** The majority of scholars mandate wudu for Tawaf. If wudu is lost, exit to the nearest ablution station, renew wudu, and resume where you left off.\n"
                "• **During Sa'i (Safa & Marwah):** Purity is **recommended (Sunnah), not an obligatory condition**. If wudu breaks during Sa'i, continue walking; your Sa'i is completely valid."
            ),
            'action_label_ar': 'أقرب دورات مياه وميضأة',
            'action_label_en': 'Nearest Wudu Stations',
            'action_url': '/zones/map/'
        },
        {
            'keywords': ['بدأ', 'المروة', 'الصفا', 'سعي', 'marwah', 'safa', 'sai', 'started'],
            'category': 'SAI_START',
            'title_ar': 'البدء بالمروة قبل الصفا في السعي',
            'title_en': 'Starting Sa\'i from Marwah Instead of Safa',
            'answer_ar': (
                "السعي المشروع يجب أن يبدأ من **الصفا** ويختم بـ **المروة** (الصفا $\\to$ المروة شوط، والمروة $\\to$ الصفا شوط).\n\n"
                "• إذا بدأت بالمروة، فإن هذا الشوط الأول **يُلغى ولا يُحسب**.\n"
                "• يبدأ حسابك من وصولك للصفا، وتكمل سبعة أشواط صحيحة تنتهي عند المروة."
            ),
            'answer_en': (
                "Sa'i MUST begin at **Mount Safa** and conclude at **Mount Marwah**.\n\n"
                "• If you mistakenly started at Marwah, that first leg to Safa is **void and discounted**.\n"
                "• Your official count begins once you reach Safa, ending at Marwah on the 7th trip."
            ),
            'action_label_ar': 'دليل خطوات السعي',
            'action_label_en': 'Sa\'i Guidance',
            'action_url': '/zones/guidance/'
        },
        {
            'keywords': ['عربة', 'كرسي', 'دفع', 'سعي', 'عاجز', 'wheelchair', 'cart', 'push', 'elderly'],
            'category': 'WHEELCHAIR_CONCESSION',
            'title_ar': 'السعي والطواف بالعربة والكرسي المتحرك',
            'title_en': 'Performing Tawaf & Sa\'i by Wheelchair or Electric Cart',
            'answer_ar': (
                "يجوز الطواف والسعي راكباً في العربة أو الكرسي الكهربائي لكل من يشق عليه المشي من كبار السن، المرضى، أو أصحاب العذر.\n\n"
                "• أقر النبي ﷺ ركوب البعير في الطواف للعلة.\n"
                "• وفرت الهيئة العامة للعناية بالحرمين مسارات مخصصة للعربات في **الدور الأول المعلق والميزانين** لتجنب التدافع وحماية الحجاج."
            ),
            'answer_en': (
                "Performing Tawaf and Sa'i in a wheelchair or electric cart is **fully permissible** for the elderly, sick, or anyone experiencing severe fatigue.\n\n"
                "• The Prophet (ﷺ) rode his mount during Tawaf when crowded.\n"
                "• The authorities provide dedicated wheelchair tracks on **Level 1 and the Mezzanine floor** to ensure smooth, unhindered movement."
            ),
            'action_label_ar': 'موقع عربات الدور الأول',
            'action_label_en': 'Level 1 Wheelchair Route',
            'action_url': '/zones/map/'
        },
        {
            'keywords': ['قص', 'شعر', 'حلق', 'ذبح', 'هدي', 'ترتيب', 'hair', 'cut', 'shave', 'sacrifice', 'order', 'hady'],
            'category': 'DAY10_ORDER',
            'title_ar': 'التقديم والتأخير في أعمال يوم النحر (10 ذو الحجة)',
            'title_en': 'Order of Rituals on the Day of Eid (10th Dhul-Hijjah)',
            'answer_ar': (
                "إذا قدمت عملاً على آخر يوم العيد (مثلاً: حلقت قبل أن تذبح، أو طفت قبل أن ترمي)، **فلا شيء عليك وحجك صحيح بالإجماع**.\n\n"
                "• ثبت في الصحيحين أن النبي ﷺ ما سُئل يوم النحر عن شيء قُدِّم ولا أُخِّر إلا قال: **«افعل ولا حرج»**.\n"
                "• الترتيب الأفضل هو: الرمي ثم النحر ثم الحلق ثم طواف الإفاضة والسعي، ولكن التقديم والتأخير جائز تماماً دون فدية."
            ),
            'answer_en': (
                "If you changed the sequence of rites on the 10th of Dhul-Hijjah (e.g. shaved before slaughtering, or did Tawaf before stoning), **there is NO penalty and your Hajj is completely valid**.\n\n"
                "• In Sahih Al-Bukhari, whenever the Prophet (ﷺ) was asked about performing an action before or after, he replied: **«Do so, and there is no harm (Iff'al wa lā Haraj)»**."
            ),
            'action_label_ar': 'جدول تفويج يوم النحر',
            'action_label_en': 'Tafweej Schedule',
            'action_url': '/accounts/pilgrim/'
        },
        {
            'keywords': ['توكيل', 'رمي', 'الجمرات', 'مريض', 'proxy', 'stoning', 'jamarat', 'delegate'],
            'category': 'JAMARAT_PROXY',
            'title_ar': 'التوكيل في رمي الجمرات لكبير السن والمريض',
            'title_en': 'Proxy Stoning at Jamarat (Tawkīl) for the Sick and Elderly',
            'answer_ar': (
                "يجوز التوكيل في رمي الجمرات لعاجز أو مريض أو امرأة حامل أو من يخشى عليه من الزحام الشديد.\n\n"
                "• يرمي الوكيل عن نفسه أولاً (7 حصيات)، ثم يرمي عن موكله (7 حصيات) في نفس الموقف دون الحاجة لرمي الجمرات الثلاث كلها مرتين.\n"
                "• الحصى المستخدم يُلتقط من منى أو مزدلفة أو أي مكان من الحرم."
            ),
            'answer_en': (
                "Appointing a proxy (*Tawkīl*) to stone the Jamarat pillars is **permissible** for the ill, elderly, pregnant women, or those who risk severe physical harm from overcrowding.\n\n"
                "• The proxy stones 7 pebbles for himself first at the pillar, then immediately stones 7 pebbles on behalf of the person he represents at the same stand.\n"
                "• Pebbles can be collected from Mina, Muzdalifah, or anywhere within the Haram sanctuary."
            ),
            'action_label_ar': 'مستويات جسر الجمرات الشاغرة',
            'action_label_en': 'Jamarat Multi-Tier Levels',
            'action_url': '/zones/map/'
        },
        {
            'keywords': ['عطر', 'صابون', 'مخيط', 'محظورات', 'فدية', 'perfume', 'scent', 'stitched', 'fidyah', 'prohibition'],
            'category': 'IHRAM_PROHIBITIONS',
            'title_ar': 'ارتكاب محظور من محظورات الإحرام نسياناً أو خطأ',
            'title_en': 'Accidental Violation of Ihram Prohibitions',
            'answer_ar': (
                "من ارتكب محظوراً من محظورات الإحرام (كالطيب، أو لبس المخيط، أو تغطية الرأس للرجل) **ناسياً أو جاهلاً فلا إثم عليه ولا فدية** لقول الله تعالى: ﴿وَلَيْسَ عَلَيْكُمْ جُنَاحٌ فِيمَا أَخْطَأْتُمْ بِهِ﴾.\n\n"
                "• يزيل المحظور فور تذكره (كغسل الطيب بالماء أو خلع المخيط).\n"
                "• أما إن تعمده لحاجة (كمرض أو برد)، فإنه يخير في فدية الأذى: صيام ثلاثة أيام، أو إطعام ستة مساكين، أو ذبح شاة."
            ),
            'answer_en': (
                "If a pilgrim violates an Ihram prohibition (such as using scented soap, wearing stitched clothing, or covering the head for men) **out of forgetfulness or ignorance, there is NO sin and NO penalty (Fidyah)**.\n\n"
                "• Simply remove the prohibited item immediately upon realizing (wash off scent, remove stitched garment).\n"
                "• If done deliberately due to necessity (e.g. sickness or extreme cold), Fidyah applies: fasting 3 days, feeding 6 poor persons, or sacrificing one sheep."
            ),
            'action_label_ar': 'ملف الحاج الصحي',
            'action_label_en': 'Pilgrim Health Profile',
            'action_url': '/accounts/profile/'
        },
        {
            'keywords': ['زحام', 'المطاف', 'مزدحم', 'الان', 'حالة', 'crowd', 'crowded', 'mataf', 'busy', 'status', 'live'],
            'category': 'CROWD_STATUS',
            'title_ar': 'الاستعلام عن حالة زحام صحن المطاف والأدوار',
            'title_en': 'Live Mataf Density & Best Tawaf Time',
            'answer_ar': 'DYNAMIC_CROWD_TELEMETRY',
            'answer_en': 'DYNAMIC_CROWD_TELEMETRY',
            'action_label_ar': 'فتح خريطة الكثافة الحية',
            'action_label_en': 'Open Live Crowd Map',
            'action_url': '/zones/map/'
        }
    ]

    @staticmethod
    def _normalize_arabic(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
        text = re.sub(r'[إأآا]', 'ا', text)
        text = re.sub(r'ة', 'ه', text)
        text = re.sub(r'ى', 'ي', text)
        return text

    @classmethod
    def answer_query(
        cls,
        question: str,
        user_profile: Optional[Any] = None,
        language: str = 'ar'
    ) -> Dict[str, Any]:
        """
        Processes a Fiqh or ritual question, returning authoritative Islamic ruling,
        live crowd status if requested, evidence attribution, and action buttons.
        """
        norm_q = cls._normalize_arabic(question)
        
        # 1. Check for Crowd Telemetry Query first
        crowd_keywords = ['زحام', 'المطاف', 'مزدحم', 'الان', 'كثافة', 'صحن', 'crowd', 'mataf', 'busy', 'density', 'live']
        norm_crowd_kw = [cls._normalize_arabic(k) for k in crowd_keywords]
        is_crowd_query = any(k in norm_q for k in norm_crowd_kw)

        if is_crowd_query:
            return cls._build_crowd_telemetry_response(language)

        # 2. Match against Embedded Knowledge Base
        best_match = None
        highest_score = 0

        for item in cls.KNOWLEDGE_BASE:
            norm_kw = [cls._normalize_arabic(kw) for kw in item['keywords']]
            score = sum(1 for kw in norm_kw if kw in norm_q)
            if score > highest_score:
                highest_score = score
                best_match = item

        # If confident match found (at least 1-2 keywords)
        if best_match and highest_score >= 1:
            ans_ar = best_match['answer_ar']
            ans_en = best_match['answer_en']
            
            # Personalize for vulnerable pilgrims if context exists
            if user_profile and getattr(user_profile, 'is_vulnerable', None) and user_profile.is_vulnerable():
                concession_note_ar = (
                    "\n\n💡 **ملاحظة خاصة بحالتك:** نظراً لأنك مسجل لدينا من ذوي الرعاية الميسرة/كبار السن، "
                    "فإن الشريعة الإسلامية قررت لك الرخص والتيسير (كما في التوكيل في الرمي واستخدام عربات الدور الأول)."
                )
                concession_note_en = (
                    "\n\n💡 **Note tailored to your profile:** As you are registered with assisted-care or senior status, "
                    "Islamic law specifically grants you concessions (such as proxy stoning and dedicated Level 1 cart routes)."
                )
                ans_ar += concession_note_ar
                ans_en += concession_note_en

            return {
                'status': 'success',
                'category': best_match['category'],
                'title': best_match['title_ar'] if language == 'ar' else best_match['title_en'],
                'answer': ans_ar if language == 'ar' else ans_en,
                'source': cls.OFFICIAL_SOURCE if language == 'ar' else cls.OFFICIAL_SOURCE_EN,
                'action_label': best_match['action_label_ar'] if language == 'ar' else best_match['action_label_en'],
                'action_url': best_match['action_url'],
                'engine': 'Nusuk Fiqh Embedded Knowledge Engine'
            }

        # 3. Cloud LLM / Fallback Handler
        gemini_api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if gemini_api_key:
            try:
                llm_response = cls._query_gemini_llm(question, gemini_api_key, language)
                if llm_response:
                    return {
                        'status': 'success',
                        'category': 'GENERAL_FIQH',
                        'title': 'إجابة مساعد نسك الذكي' if language == 'ar' else 'Nusuk AI Response',
                        'answer': llm_response,
                        'source': cls.OFFICIAL_SOURCE if language == 'ar' else cls.OFFICIAL_SOURCE_EN,
                        'action_label': 'لوحة الإرشادات التفاعلية' if language == 'ar' else 'Interactive Guidance',
                        'action_url': '/zones/guidance/',
                        'engine': 'Nusuk AI + Gemini 1.5'
                    }
            except Exception as e:
                logger.warning(f"Gemini LLM query failed, falling back to general guidance: {e}")

        # 4. Default Authentic Guidance for unclassified questions
        default_ar = (
            "الحمد لله، الأصل في مناسك الحج والعمرة التيسير ورفع الحرج لقوله ﷺ: «افعل ولا حرج».\n\n"
            "• إذا كان استفسارك يتعلق بنسيان عدد الأشواط، فابنِ على اليقين (الأقل).\n"
            "• إذا كان بخصوص التقديم والتأخير يوم النحر، فالحج صحيح ولا فدية عليك.\n"
            "• للاستفسارات الشرعية المعقدة، يمكنك الاتصال مباشرة بالرقم المجاني الموحد للتوعية الدينية بالحرمين: **8001222444** (24 ساعة بـ 10 لغات)."
        )
        default_en = (
            "In Islamic jurisprudence, the foundational rule of Hajj & Umrah is ease and removal of hardship (Lā Haraj).\n\n"
            "• If your question is regarding doubting Tawaf/Sa'i count, build on the lesser number.\n"
            "• If regarding sequencing of rites on Eid day, your Hajj is valid with no penalty.\n"
            "• For complex personal jurisprudence inquiries, contact the official 24/7 Islamic Guidance Hotline for the Holy Mosques at **8001222444** (Available in 10 languages)."
        )
        return {
            'status': 'success',
            'category': 'GENERAL_FIQH',
            'title': 'إرشاد مناسك نسك' if language == 'ar' else 'Nusuk Ritual Guidance',
            'answer': default_ar if language == 'ar' else default_en,
            'source': cls.OFFICIAL_SOURCE if language == 'ar' else cls.OFFICIAL_SOURCE_EN,
            'action_label': 'الاتصال بالإفتاء الموحد (8001222444)' if language == 'ar' else 'Call Toll-Free Ifta Hotline',
            'action_url': 'tel:8001222444',
            'engine': 'Nusuk Fiqh Embedded Knowledge Engine'
        }

    @classmethod
    def _build_crowd_telemetry_response(cls, language: str) -> Dict[str, Any]:
        """Queries live HaramSectionalEngine to answer crowd density questions dynamically."""
        from services.sectional_telemetry import HaramSectionalEngine
        matrix = HaramSectionalEngine.get_sectional_status_matrix()
        
        mataf_sec = next((s for s in matrix if s['code'] == 'Z-HARAM-MATAF'), None)
        f1_sec = next((s for s in matrix if s['code'] == 'Z-HARAM-F1'), None)
        roof_sec = next((s for s in matrix if s['code'] == 'Z-HARAM-ROOF'), None)

        mataf_count = mataf_sec['headcount'] if mataf_sec else 12500
        mataf_dens = mataf_sec['density_sqm'] if mataf_sec else 2.5
        mataf_status = mataf_sec['status_code'] if mataf_sec else 'ORANGE'

        f1_dens = f1_sec['density_sqm'] if f1_sec else 0.8
        roof_dens = roof_sec['density_sqm'] if roof_sec else 0.5

        if language == 'ar':
            if mataf_status == 'RED':
                advice = (
                    f"⚠️ **صحن المطاف الأرضي مزدحم جداً حالياً** ({mataf_count:,} طائف - الكثافة {mataf_dens} فرد/م² - حالة حمراء).\n\n"
                    f"🕌 **التوصية الشرعية والوقائية:** ننصحك شرعاً بالصعود إلى **مطاف الدور الأول ({f1_dens} فرد/م²)** "
                    f"أو **سطح المطاف المفتوح ({roof_dens} فرد/م²)** تجنباً للتدافع والمشقة، وطوافك في الأدوار العلوية صحيح 100% باتفاق العلماء."
                )
            elif mataf_status == 'ORANGE':
                advice = (
                    f"🟡 **صحن المطاف في حالة متوسطة ومستقرة** ({mataf_count:,} طائف - الكثافة {mataf_dens} فرد/م²).\n\n"
                    f"• يمكنك الطواف في الصحن بحذر، أو اختيار مطاف الدور الأول المعلق إذا كنت برفقة كبار السن أو عربة أطفال."
                )
            else:
                advice = (
                    f"🟢 **صحن المطاف انسيابي ومريح جداً الآن** ({mataf_count:,} طائف - الكثافة {mataf_dens} فرد/م²).\n\n"
                    f"• هذا التوقيت مثالي ومبارك لأداء طواف العمرة أو طواف التطوع في الصحن الأرضي بجوار الكعبة المشرفة مباشرة."
                )
        else:
            if mataf_status == 'RED':
                advice = (
                    f"⚠️ **The Ground Mataf Basin is currently CONGESTED** ({mataf_count:,} pilgrims - Density {mataf_dens} p/m² - RED status).\n\n"
                    f"🕌 **Safety & Fiqh Recommendation:** We strongly advise ascending to **Level 1 ({f1_dens} p/m²)** "
                    f"or the **Roof Tier ({roof_dens} p/m²)**. Performing Tawaf on upper tiers is 100% valid by consensus and prevents crowd crush."
                )
            elif mataf_status == 'ORANGE':
                advice = (
                    f"🟡 **The Ground Mataf is at MODERATE flow** ({mataf_count:,} pilgrims - Density {mataf_dens} p/m²).\n\n"
                    f"• Ground Tawaf is feasible with caution. If accompanying seniors or wheelchairs, Level 1 is recommended."
                )
            else:
                advice = (
                    f"🟢 **The Ground Mataf is SMOOTH and COMFORTABLE right now** ({mataf_count:,} pilgrims - Density {mataf_dens} p/m²).\n\n"
                    f"• Current conditions are optimal for performing Tawaf directly around the Kaaba."
                )

        return {
            'status': 'success',
            'category': 'LIVE_CROWD_TELEMETRY',
            'title': 'الحالة المباشرة للمطاف والتوصية' if language == 'ar' else 'Live Mataf Telemetry & Guidance',
            'answer': advice,
            'source': 'مجسات قياس التدفق بالأشعة ثلاثية الأبعاد (ToF) وكاميرات المآذن البصرية (FIDTM)',
            'action_label': 'عرض مصفوفة الكثافة الحية' if language == 'ar' else 'View Live Density Matrix',
            'action_url': '/zones/map/',
            'engine': 'HaramSectionalEngine Live Telemetry'
        }

    @classmethod
    def _query_gemini_llm(cls, question: str, api_key: str, language: str) -> Optional[str]:
        """Calls Gemini API with strict Islamic Fiqh system instructions."""
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        system_instruction = (
            "You are Nusuk AI, an official Islamic jurisprudence assistant for Hajj and Umrah pilgrims in Saudi Arabia. "
            "Base all answers strictly on the rulings of the Saudi Council of Senior Scholars and the Ministry of Hajj & Umrah. "
            "Prioritize concessions (Rukhsah) and safety. Keep answers clear, compassionate, bulleted, and cite 'وفقاً لهيئة كبار العلماء'."
        )
        
        payload = {
            "contents": [{
                "parts": [{"text": f"System: {system_instruction}\n\nPilgrim Question: {question}\nLanguage: {language}"}]
            }]
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            candidates = data.get('candidates', [])
            if candidates:
                return candidates[0]['content']['parts'][0]['text']
        return None
