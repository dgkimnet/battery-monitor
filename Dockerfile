FROM node:20-alpine

WORKDIR /app

ARG PRISMA_GENERATE_DATABASE_URL=postgres://battery:battery@postgres:5432/battery_monitor

COPY package*.json ./
RUN npm ci

COPY prisma.config.js ./
COPY prisma ./prisma
COPY server ./server
RUN DATABASE_URL=$PRISMA_GENERATE_DATABASE_URL npx prisma generate

ENV NODE_ENV=production
EXPOSE 3000

CMD ["sh", "-c", "npx prisma migrate deploy && node server/src/index.js"]
