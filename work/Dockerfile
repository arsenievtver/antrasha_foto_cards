FROM node:22-alpine AS build

WORKDIR /repo/work
COPY work/package*.json ./
RUN npm ci

COPY shared /repo/shared
COPY work/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx/work-static.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/work/dist /usr/share/nginx/html

EXPOSE 80
