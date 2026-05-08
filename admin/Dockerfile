FROM node:22-alpine AS build

WORKDIR /src
COPY admin/package*.json ./
RUN npm ci

COPY admin/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx/admin-static.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 80
