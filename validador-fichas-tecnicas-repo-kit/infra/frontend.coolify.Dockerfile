FROM node:24-alpine AS build
WORKDIR /app
ENV VITE_API_BASE_URL=/api
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM nginx:1.29-alpine
COPY infra/nginx.coolify.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
