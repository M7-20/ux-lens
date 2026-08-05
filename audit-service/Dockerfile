FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# مجلد بيانات وقت التشغيل (سجل الفحوصات + الكاش) — مُستثنى محتواه عبر .dockerignore،
# لكن المجلد نفسه لازم يوجد كمجلد قبل تركيب volume عليه في docker-compose.
RUN mkdir -p shots data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
