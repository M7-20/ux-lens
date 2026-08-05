# ---- مرحلة البناء ----
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* bun.lock* ./
RUN npm install

COPY . .

ARG VITE_BASE_PATH=/
ARG VITE_AUDIT_SERVICE_URL
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
ENV VITE_AUDIT_SERVICE_URL=${VITE_AUDIT_SERVICE_URL}
ENV NITRO_PRESET=node-server
# لازم وقت البناء أيضاً، مو بس وقت التشغيل — تسجيل مسارات public/ الثابتة (CSS، الصور)
# يُحسم وقت `vite build` نفسه؛ بدونه الملفات تُخدَم من الجذر بينما الـHTML يطلبها
# تحت البادئة، فتفشل 404.
ENV NITRO_APP_BASE_URL=${VITE_BASE_PATH}

RUN npx vite build

# ---- مرحلة التشغيل ----
FROM node:22-alpine AS runtime
WORKDIR /app

ARG VITE_BASE_PATH=/
COPY --from=build /app/.output ./

ENV NODE_ENV=production
ENV PORT=8080
# Nitro's own HTTP router needs the base path too (separate from Vite's client-side
# baking) — without it, every request under the prefix 404s except the bare root.
# https://nitro.build/config#baseurl
ENV NITRO_APP_BASE_URL=${VITE_BASE_PATH}
EXPOSE 8080

CMD ["node", "server/index.mjs"]
