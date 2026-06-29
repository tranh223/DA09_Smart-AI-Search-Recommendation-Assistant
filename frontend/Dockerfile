# Multi-stage: build Vite -> serve tĩnh bằng nginx (Cloud Run).
# VITE_* được nhúng cứng lúc build nên truyền qua --build-arg.

# --- Stage 1: build ---
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

COPY . .

ARG VITE_BACKEND_BASE_URL
ARG VITE_OTA_BASE_URL=https://supabase-ota-travel.onrender.com
ARG VITE_OTA_API_KEY=
ENV VITE_BACKEND_BASE_URL=$VITE_BACKEND_BASE_URL \
    VITE_OTA_BASE_URL=$VITE_OTA_BASE_URL \
    VITE_OTA_API_KEY=$VITE_OTA_API_KEY

RUN npm run build

# --- Stage 2: serve ---
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
