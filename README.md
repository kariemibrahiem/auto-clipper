# Auto Clipping — GitHub Actions + n8n + YouTube Shorts

مستقل تمامًا عن مشروع ميلا. مفيش أي GitHub tokens أو API keys محفوظة هنا.

## تحديث حل مشكلة YouTube bot verification (نوفمبر 2026)

**الحل المستقر:** استخدم رابط فيديو MP4 مباشر قابل للتحميل من مصدر تملك حقوق استخدامه.
Google Sheets يتعامل مع عمود `source_url` كما هو. تستطيع وضع رابط MP4 مباشر بدل رابط مشاهدة YouTube.
لو عايز تحتفظ برابط YouTube في `source_url`، أضف عمودًا اختياريًا جديدًا اسمه بالضبط
`media_url` وضع فيه رابط تحميل MP4 مباشر مرخص لنفس المحتوى.

- سيتم رفض رابط مشاهدة YouTube الذي لا يملك `media_url` **قبل** تشغيل GitHub، برسالة واضحة في `error`؛ لأن GitHub Actions حُظر سابقًا برسالة `Sign in to confirm you're not a bot`.
- لو صف سابق حالته `error`، غيّرها إلى `pending` فقط بعد تغيير رابط الفيديو إلى مصدر قابل للتحميل.
- يدعم محرك GitHub فيديو حتى 3 ساعات وحجم 1.5GB؛ لكن يحلل افتراضيًا **أول 30 دقيقة فقط** حتى لا يستنفد مهلة GitHub.
- لمراجعة جزء آخر من الفيديو الطويل: عمودان اختياريان في Sheet هما `start_seconds` (مثل `3000`) و`analysis_seconds` (من 60 إلى 2700، الافتراضي 1800). المقطع الناتج سيكون من نافذة التحليل المحددة.
- الاختيار آلي حسب الكلام في الصوت وليس ضمانًا لاكتشاف **أطرف** لقطة بصريًا.
- `narration=off` يترك صوت المصدر بدون تعليق آلي.

**استيراد n8n:** استخدم `Auto_Clipper_Google_Sheets_MP4_FIXED.json`، وأبقِ بيانات حسابات Google Sheets/GitHub/YouTube الخاصة بك في Credentials كما هي. الإصدار المحدث يضيف حقول GitHub `source_is_direct`, `start_seconds`, `analysis_seconds` تلقائيًا.

**Content Rewards:** يُمكن نسخ روابط Shorts الناتجة من عمود `shorts_links` للتقديم في حملة مسموح لها بالمصدر والمنصة. تقديم المحتوى للحملة والموافقة على مكافآته يخضعان لشروط Content Rewards؛ هذا المشروع لا يوصل بالحساب أو يقدّم طلبات للموقع آليًا.

**تحذير حقوقي:** لقطات من فيديوهات الآخرين بدون إضافات أصلية كبيرة قد تكون غير مؤهلة لتحقيق الدخل على YouTube حتى إذا لم تُقدَّم مطالبة حقوق نشر.

## قبل أول تشغيل (مرة واحدة فقط)

1. استخدم GitHub repository الموجود باسم **`kariemibrahiem/auto-clipper`** والفرع `main`.
2. فكّ ZIP وارفع **محتويات الفولدر** إلى جذر الـrepository، مع تحديث `clipper.py` و`.github/workflows/clipper.yml` تحديدًا. **رفع ZIP نفسه إلى GitHub لن يثبّت الأكواد**.
3. من n8n، اختار **Import from File** وافتح `n8n/Auto_Clipper_Google_Sheets_MP4_FIXED.json`، أو النسخة المستقلة المرفقة بنفس الاسم.
4. أنشئ Credential جديدة في n8n من نوع **HTTP Bearer Auth**، وحط فيها GitHub Fine-grained Personal Access Token. نطاقه repository `auto-clipper` فقط، والصلاحية **Actions: Read and write**. لا تضع التوكن داخل Code node أو URL أو GitHub files.
5. افتح الأربع نودز دول، واختار **نفس الـCredential** اللي عملتها:
   - `Dispatch GitHub Job`
   - `List Clip Runs`
   - `List Run Artifacts`
   - `Download Clips ZIP`
6. افتح `Upload Shorts to YouTube`، وتأكد إن YouTube OAuth Credential بتاعتك الصحيحة متوصلة. اسم الـCredential المستورد مبدئيًا `YouTube account` من مشروعك القديم؛ لو ظهر علامة تحذير اخترها من جديد.

## كل مرة عندك فيديو

1. افتح `videos sheet` ثم تبويب **`Clipping Queue`**.
2. في `source_url` ضع رابط **MP4 مباشر مرخص**، أو احتفظ برابط YouTube الأصلي وأضف عمود `media_url` برابط MP4 مباشر.
3. اختياريًا غيّر `title`, `clip_count`, `clip_seconds`, `language`, `narration`، و`start_seconds` لو الفيديو طويل.
4. حط `pending` في `status` (خصوصًا لو الصف القديم `error`) ثم شغّل n8n **Execute Workflow**.
5. النود `Mark Done` هتحدّث `shorts_links`، أو `Mark Error` هتكتب سبب الفشل في `error`.

## الإعدادات الافتراضية

| الإعداد | الافتراضي |
| --- | --- |
| العدد | 3 شورتس من كل فيديو |
| المدة | 35 ثانية لكل شورت (مسموح 15–55) |
| أبعاد الفيديو | 720×1280 عمودي 9:16، H.264/AAC |
| اختيار اللقطات | تحليل صوت الفيديو بـ Whisper محليًا + تقييم للمقاطع |
| تعليق صوتي | صوت طبيعي باستخدام Edge TTS بدون API Key؛ فيه eSpeak احتياطي |
| لغة التعليق | `auto` حسب اللغة المكتشفة، أو `ar` أو `en` |
| كتابة على الشاشة | **لا توجد كتابة مدمجة بالفيديو** |
| النشر | YouTube Public مباشر |
| التخزين المؤقت | GitHub Actions artifact لمدة 3 أيام |

## حدود مهمة عشان مفيش مفاجآت

- **استخدم فقط فيديوهات ملكك أو لديك إذن صريح بإعادة استخدامها**. إضافة تعليق صوتي لا تلغي حقوق النشر.
- تنزيل فيديو من YouTube بـ `yt-dlp` **قد يفشل** مع بعض الفيديوهات أو قيود المنصة. رابط تحميل MP4 مباشر عادةً أكثر استقرارًا.
- الاختيار والتعليق بيعتمدوا على **الكلام المسموع** وليس فهم الفيديو بصريًا. الفيديوهات اللي مفيهاش كلام هتتقص على فترات متباعدة مع تعليق تمهيدي عام.
- Edge TTS خدمة خارجية بتشتغل من غير API Key، وممكن تتوقف؛ وقتها البرنامج يحاول يستخدم صوت eSpeak محلي بسيط. الميزة دي مش ضمان لجودة صوت مثالية.
- GitHub Actions يحتاج وقت وموارد، وملفات الفيديو قد تكون كبيرة على n8n Cloud. لو الاستضافة فرضت حدودًا للملفات، نقدر ننقل الرفع لطبقة تانية.
- `YouTube account` OAuth لازم تكون متفعلة وصالحة. الـGitHub token وحده **لا** يتيح رفع فيديو على يوتيوب.
- الاختبار المحلي يثبت إنتاج الفيديو، لكن تشغيل GitHub وn8n وYouTube الحقيقي يحتاج ربط Credential وتجربة فعلية على حسابك.
- التشغيل المتكرر على نفس الفيديو بينشر شورتس جديدة كل مرة، فمتعملش Execute مرتين بالخطأ.

## تجربة محلية (اختياري)

```bash
python3 -m pip install -r requirements.txt
sudo apt-get install ffmpeg espeak-ng
CLIP_COUNT=1 CLIP_SECONDS=15 NARRATION=off python3 clipper.py --local-video /path/to/owned-video.mp4 --skip-transcription
```

### ما الذي يحتاج API Key؟

- **GitHub:** توكن واحد في n8n Credential، أنت هتحطه بنفسك.
- **YouTube:** OAuth Credential موجودة عندك داخل n8n (مش API Key جديد).
- **Whisper/FFmpeg:** بدون API Keys.
- **Edge TTS:** بدون API Key، لكنه بيعتمد على اتصال خارجي وقد لا يعمل دائمًا.

## استكشاف الأخطاء

- `404` من Dispatch: تأكد من اسم repository ووجود `.github/workflows/clipper.yml` على `main`.
- `401` أو `403`: راجع GitHub PAT وصلاحية `Actions: Read and write`.
- `Github clip rendering failed`: افتح GitHub > Actions > Make Vertical Clips > آخر Run واقرأ الخطأ.
- `Source download failed`: استخدم رابط MP4 مباشر من مصدر مصرح لك باستخدامه.
- `YouTube did not confirm video ID`: راجع Youtube OAuth ونتيجة نود الرفع؛ `uploadId` هو الحقل المتوقع في n8n.
