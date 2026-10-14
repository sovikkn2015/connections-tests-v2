# syntax=docker/dockerfile:1.7
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* tsconfig.json ./
COPY src ./src
RUN npm ci --omit=optional && npm run build && npm prune --production
FROM gcr.io/distroless/nodejs20-debian12:nonroot AS runtime
WORKDIR /app
COPY --from=builder --chown=nonroot:nonroot /app/dist ./dist
COPY --from=builder --chown=nonroot:nonroot /app/node_modules ./node_modules
COPY --from=builder --chown=nonroot:nonroot /app/package.json ./package.json
USER nonroot
EXPOSE 8080
ENV NODE_ENV=production NODE_OPTIONS="--enable-source-maps --max-old-space-size=512"
ENTRYPOINT ["/nodejs/bin/node", "/app/dist/index.js"]
