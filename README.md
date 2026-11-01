# Auto Clipping — GitHub Actions + n8n + YouTube Shorts

مستقل تمامًا عن مشروع ميلا. مفيش أي GitHub tokens أو API keys محفوظة هنا.

## قبل أول تشغيل (مرة واحدة فقط)

1. اعمل GitHub repository جديد باسم **`auto-clipper`** في الحساب **`kariemibrahiem`**، وخلي الفرع الأساسي `main`.
2. ارفع **محتويات هذا الفولدر** (مش ملف ZIP نفسه) على جذر الـrepository. لازم الملف `.github/workflows/clipper.yml` يكون موجود.
3. من n8n، اختار **Import from File** وافتح `n8n/Auto_Clipping_YouTube_n8n.json`.
4. أنشئ Credential جديدة في n8n من نوع **HTTP Bearer Auth**، وحط فيها GitHub Fine-grained Personal Access Token. نطاقه repository `auto-clipper` فقط، والصلاحية **Actions: Read and write**. لا تضع التوكن داخل Code node أو URL أو GitHub files.
5. افتح الأربع نودز دول، واختار **نفس الـCredential** اللي عملتها:
   - `Dispatch GitHub Job`
   - `List Clip Runs`
   - `List Run Artifacts`
   - `Download Clips ZIP`
6. افتح `Upload Shorts to YouTube`، وتأكد إن YouTube OAuth Credential بتاعتك الصحيحة متوصلة. اسم الـCredential المستورد مبدئيًا `YouTube account` من مشروعك القديم؛ لو ظهر علامة تحذير اخترها من جديد.

## كل مرة عندك فيديو

1. افتح `Configure Job` في n8n.
2. غيّر `SOURCE_VIDEO_URL` للينك HTTPS بتاع الفيديو اللي عندك حق تستخدمه.
3. اختياري: غيّر `VIDEO_TITLE`, `CLIP_COUNT`, `CLIP_SECONDS`, `LANGUAGE`.
4. اضغط **Execute Workflow**. استنى GitHub يخلص، وn8n هيرفع كل MP4 ليوتيوب **Public** مباشرة.
5. النود الأخيرة `YouTube Links` هترجع روابط الشورتس.

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
