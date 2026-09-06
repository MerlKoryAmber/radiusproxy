FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# inotify-tools: reload nginx when the backend replaces the TLS cert.
RUN apk add --no-cache inotify-tools openssl
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY entrypoint.sh /docker-entrypoint.d/99-radiuspanel-tls.sh
RUN chmod +x /docker-entrypoint.d/99-radiuspanel-tls.sh
EXPOSE 80 443
