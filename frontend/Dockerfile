FROM node:22-alpine AS build

WORKDIR /workspace/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
COPY images ../images
RUN if [ ! -e nginx.conf ]; then cp nginx.conf.example nginx.conf; fi
RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /workspace/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/frontend/dist /usr/share/nginx/html
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
