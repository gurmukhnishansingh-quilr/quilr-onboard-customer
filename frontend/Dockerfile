FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package.json /app/package.json
RUN npm install

COPY frontend /app
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/package.json /app/package.json
COPY --from=builder /app/node_modules /app/node_modules
COPY --from=builder /app/.next /app/.next
COPY --from=builder /app/public /app/public
COPY --from=builder /app/next.config.js /app/next.config.js
COPY --from=builder /app/server.js /app/server.js

EXPOSE 3000

CMD ["node", "server.js"]
