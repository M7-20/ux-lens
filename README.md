# UX LENS

أداة داخلية لوزارة البيئة والمياه والزراعة لفحص التزام المواقع الحكومية بمعايير هيئة الحكومة الرقمية (DGA) ومعايير تجربة المستخدم العامة (UX) — فحص آلي يجمع بين تحليل DOM/CSS المباشر وتحليل بصري عبر API الوزارة الداخلي للقطات الشاشة.

## البنية

- **الفرونت إند** (`src/`): TanStack Start (React 19، SSR) + Vite + Tailwind CSS.
- **الباك إند** (`audit-service/`): FastAPI + Playwright (التقاط لقطات الشاشة) + API الوزارة الداخلي (التحليل البصري، متوافق مع OpenAI)، مع قاعدة SQLite خفيفة لمصادقة واحة (waha) وملفات JSON لسجل الفحوصات.

## التشغيل محلياً

### المتطلبات
- Node.js
- Python 3.12+
- مفتاح API الوزارة (`MINISTRY_VLM_API_KEY`) ورابط الـendpoint (`MINISTRY_VLM_BASE_URL`)

### الفرونت إند
```sh
npm install
npm run dev
```
يشتغل افتراضياً على `http://localhost:8080`.

### الباك إند
```sh
cd audit-service
python -m venv venv
./venv/Scripts/activate   # أو source venv/bin/activate على Linux/Mac
pip install -r requirements.txt
playwright install chromium
cp .env.example .env      # وعدّل MINISTRY_VLM_API_KEY وMINISTRY_VLM_BASE_URL بداخله
uvicorn main:app --host 0.0.0.0 --port 8000
```
يشتغل افتراضياً على `http://localhost:8000`، والفرونت إند يتصل فيه تلقائياً بدون أي إعداد إضافي بالتطوير المحلي.

## التشغيل عبر Docker

```sh
docker compose up
```
يبني ويشغّل الخدمتين معاً (الفرونت إند على `8080`، الباك إند على `8000`). يحتاج `audit-service/.env` بنفس الطريقة أعلاه قبل التشغيل. الواجهة مبنية ببادئة المنصة `/waha/uxlens` (waha ONBOARDING.md §2)، فالرابط محلياً `http://localhost:8080/waha/uxlens/` وليس الجذر — هذا مقصود: يحاكي فعلياً كيف تُخدَم خلف بوابة واحة.

## بُني باستخدام

- TanStack Start · TypeScript · React · Tailwind CSS
- FastAPI · Playwright · API الوزارة الداخلي
