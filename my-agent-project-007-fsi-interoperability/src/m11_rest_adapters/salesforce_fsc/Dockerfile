# syntax=docker/dockerfile:1.7
# Salesforce FSC M11-REST adapter — spec R11 AC11.1-11.9.
# Pinned SHA256 digests live in Helm values (values-{topology}.yaml).
# Expected image size ~130 MiB (distroless ~80 + node_modules ~40 + dist ~10).

ARG NODE_BASE=node:20-alpine
ARG RUNTIME_BASE=gcr.io/distroless/nodejs20-debian12:nonroot

FROM ${NODE_BASE} AS builder
WORKDIR /app
COPY package.json package-lock.json* tsconfig.json ./
COPY src ./src
RUN npm ci --omit=optional \
 && npm run build \
 && npm prune --production

FROM ${RUNTIME_BASE} AS runtime
WORKDIR /app
COPY --from=builder --chown=nonroot:nonroot /app/dist ./dist
COPY --from=builder --chown=nonroot:nonroot /app/node_modules ./node_modules
COPY --from=builder --chown=nonroot:nonroot /app/package.json ./package.json
USER nonroot
EXPOSE 8080
ENV NODE_ENV=production \
    NODE_OPTIONS="--enable-source-maps --max-old-space-size=512"
ENTRYPOINT ["/nodejs/bin/node", "/app/dist/index.js"]
