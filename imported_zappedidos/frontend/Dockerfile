# build
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
# Se o npm install falhar tentando baixar @emergentbase/* (CDN da Emergent, só
# necessário dentro da própria plataforma), remova as duas linhas dele do
# package.json (seção devDependencies) e rode de novo — o vite.config.ts já
# trata a ausência delas sem quebrar o build.
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build

# serve
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
