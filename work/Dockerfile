FROM node:22-alpine AS build

WORKDIR /src
COPY work/package*.json ./
RUN npm ci

COPY work/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx/work-static.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 80
