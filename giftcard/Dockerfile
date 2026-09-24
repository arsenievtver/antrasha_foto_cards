FROM node:22-alpine AS build

WORKDIR /repo/giftcard
COPY giftcard/package*.json ./
RUN npm ci

COPY shared /repo/shared
COPY giftcard/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx/giftcard-static.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/giftcard/dist /usr/share/nginx/html

EXPOSE 80
