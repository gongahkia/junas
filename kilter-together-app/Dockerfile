FROM node:alpine AS builder

WORKDIR /app

ARG VITE_APP_BASE_PATH=/
ARG VITE_API_BASE_URL=/api

COPY package*.json ./
RUN npm ci

ENV VITE_APP_BASE_PATH=${VITE_APP_BASE_PATH}
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY . .
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
