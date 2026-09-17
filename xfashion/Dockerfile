FROM node:22-alpine AS build

WORKDIR /src
COPY xfashion/package*.json ./
RUN npm ci

COPY xfashion/ .
ARG VITE_XFASHION_VIDEO_URL=
ARG VITE_XFASHION_VIDEO_MOBILE_URL=
ARG VITE_SITE_ORIGIN=https://xfashion.pro
ENV VITE_XFASHION_VIDEO_URL=$VITE_XFASHION_VIDEO_URL
ENV VITE_XFASHION_VIDEO_MOBILE_URL=$VITE_XFASHION_VIDEO_MOBILE_URL
ENV VITE_SITE_ORIGIN=$VITE_SITE_ORIGIN
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx/xfashion-static.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 80
