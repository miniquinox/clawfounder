# ──────────────────────────────────────────────────────────────────
# ClawFounder — Production Docker Image
# Multi-stage: Build frontend, then assemble Node + Python runtime
# ──────────────────────────────────────────────────────────────────

# Stage 1: Build frontend
FROM node:22-slim AS frontend-build
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

# Stage 2: Production image (Python base + Node.js)
FROM python:3.12-slim

# Install Node.js 22.x
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Connector-specific dependencies
COPY connectors/ ./connectors/
RUN for req in connectors/*/requirements.txt; do \
      [ -f "$req" ] && pip install --no-cache-dir -r "$req" 2>/dev/null || true; \
    done

# Node production dependencies only
COPY dashboard/package.json dashboard/package-lock.json ./dashboard/
RUN cd dashboard && npm ci --omit=dev

# Application code
COPY agent/ ./agent/
COPY dashboard/server.js dashboard/chat_agent.py dashboard/briefing_agent.py dashboard/voice_agent.py ./dashboard/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/dashboard/dist ./dashboard/dist

ENV NODE_ENV=production
EXPOSE 8080

CMD ["node", "dashboard/server.js"]
