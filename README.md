# YouTube Downloader Pro

מוריד YouTube מקצועי עם ממשק זכוכיתי מודרני )pywebview + WebView2(, הורדת **1080p גם לסרטונים מוגבלים**, מצב וידאו/שמע אוטומטי, התאמה אישית מלאה, והשהיה/ביטול.

## תכונות

- **1080p לכל סרטון** — כולל סרטונים ש-YouTube "מגביל". משיג זאת כמו YTDLnis: PO Token )BotGuard דרך WebView2( + פתרון n-challenge )Node.js + yt-dlp-ejs( + client `tv_embedded` שלא נחסם ע"י SABR.
- **וידאו / שמע / וידאו בלבד** — זיהוי אוטומטי לפי הקישור )YouTube Music → שמע(, עם בחירה ידנית.
- **התאמה אישית** — איכות, פורמט, כתוביות, פרקים, תמונה ממוזערת, SponsorBlock, חיתוך, קצב ביטים, פיצול לפי פרקים, ועוד.
- **השהיה / ביטול** באמצע ההורדה.
- **עדכון עצמי** — בדיקה והתקנה דרך התוכנה )לפי SHA-256 של החבילה, לא לפי מספר גרסה(.

## הרצה מהמקור

```bash
python app.py
```

כל התלויות )pywebview, yt-dlp, yt-dlp-ejs, Pillow( מותקנות אוטומטית בהפעלה הראשונה.
דרישות: Windows 10/11 )WebView2 מובנה(, FFmpeg. Node.js מורד אוטומטית אם חסר.

## בנייה

```bash
python -m PyInstaller --noconfirm --clean YouTubeDownloaderPro.spec
```

ה-exe נוצר ב-`dist/`.

## ארכיטקטורה

| קובץ | תפקיד |
|---|---|
| `app.py` | חלון native )pywebview/WebView2( + API ל-frontend |
| `youtube_downloader.py` | מנוע ההורדה )yt-dlp(, PO token, node, format selection |
| `pot_provider.py` | יצירת PO Token דרך WebView2 )BotGuard, כמו YTDLnis( |
| `updater.py` | עדכון עצמי לפי SHA-256 דרך GitHub |
| `web/` | ה-frontend )HTML/CSS/JS, עיצוב זכוכיתי( |
