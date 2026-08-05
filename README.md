# UX LENS

أداة داخلية لوزارة البيئة والمياه والزراعة لفحص التزام المواقع الحكومية بمعايير هيئة الحكومة الرقمية (DGA) ومعايير تجربة المستخدم العامة (UX) — فحص آلي يجمع بين تحليل DOM/CSS المباشر وتحليل بصري عبر Gemini للقطات الشاشة.

## البنية

- **الفرونت إند** (`src/`): TanStack Start (React 19، SSR) + Vite + Tailwind CSS.
- **الباك إند** (`audit-service/`): FastAPI + Playwright (التقاط لقطات الشاشة) + Google Gemini (التحليل البصري)، مع قاعدة SQLite خفيفة لمصادقة واحة (waha) وملفات JSON لسجل الفحوصات.

## التشغيل محلياً

### المتطلبات
- Node.js
- Python 3.12+
- مفتاح Gemini API

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
cp .env.example .env      # وعدّل GEMINI_API_KEY بداخله
uvicorn main:app --host 0.0.0.0 --port 8000
```
يشتغل افتراضياً على `http://localhost:8000`، والفرونت إند يتصل فيه تلقائياً بدون أي إعداد إضافي بالتطوير المحلي.

## التشغيل عبر Docker

```sh
docker compose up
```
يبني ويشغّل الخدمتين معاً (الفرونت إند على `8080`، الباك إند على `8000`). يحتاج `audit-service/.env` بنفس الطريقة أعلاه قبل التشغيل.

## بُني باستخدام

- TanStack Start · TypeScript · React · Tailwind CSS
- FastAPI · Playwright · Google Gemini
