# syntax=docker/dockerfile:1.7
FROM node:20-alpine AS deps
WORKDIR /app

# Install the renderer's own dependencies first so the layer survives source
# edits.
COPY shared-renderer/package.json shared-renderer/package-lock.json ./shared-renderer/
RUN --mount=type=cache,target=/root/.npm npm ci --prefix ./shared-renderer --ignore-scripts
COPY shared-renderer ./shared-renderer
# The renderer's `lib/` is `tsc -b` output that is not committed (see
# .gitignore). Build it here from the sources just copied rather than leaving
# the image's renderer to depend on npm happening to run the linked package's
# `prepare` script during the dashboard install below.
RUN npm run build --prefix ./shared-renderer
COPY next-dashboard/package.json next-dashboard/package-lock.json ./next-dashboard/
WORKDIR /app/next-dashboard
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts

FROM deps AS development
WORKDIR /app/next-dashboard
COPY --from=deps /app/next-dashboard/node_modules ./node_modules
COPY next-dashboard ./
COPY --from=deps /app/shared-renderer /app/shared-renderer
ENV NEXT_TELEMETRY_DISABLED=1
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

FROM node:20-alpine AS builder
WORKDIR /app/next-dashboard
COPY --from=deps /app/next-dashboard/node_modules ./node_modules
COPY next-dashboard ./
COPY --from=deps /app/shared-renderer /app/shared-renderer
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app/next-dashboard
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

COPY --from=builder /app/next-dashboard/public ./public
# `turbopack.root` (= `outputFileTracingRoot`) is /app here, so the emitted
# entrypoint is standalone/next-dashboard/server.js, not standalone/server.js.
COPY --from=builder --chown=nextjs:nodejs /app/next-dashboard/.next/standalone/next-dashboard ./
COPY --from=builder --chown=nextjs:nodejs /app/next-dashboard/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
