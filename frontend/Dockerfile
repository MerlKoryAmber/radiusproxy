# Build-only stage (never shipped). Node 20 is EOL since 2026-04-30; 24 = active LTS.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# Internet-facing runtime: stay on a supported stable branch (1.27 EOL 2025-06-24).
FROM nginx:1.30-alpine
# inotify-tools: reload nginx when the backend replaces the TLS cert.
RUN apk add --no-cache inotify-tools openssl
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY entrypoint.sh /docker-entrypoint.d/99-radiuspanel-tls.sh
RUN chmod +x /docker-entrypoint.d/99-radiuspanel-tls.sh
EXPOSE 80 443
