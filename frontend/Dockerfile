# Build stage (use slim for glibc - avoids rollup musl optional dep issues)
FROM docker.m.daocloud.io/library/node:20-slim AS builder

WORKDIR /app

# Avoid npm hang: disable interactive prompts and optional deps
ENV CI=true \
    npm_config_update_notifier=false \
    npm_config_fund=false \
    npm_config_audit=false

# Copy package files
COPY package.json ./

# Install dependencies (must include optional deps for rollup musl binary on Alpine)
RUN npm install --prefer-offline --no-audit --progress=true

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM docker.m.daocloud.io/library/nginx:alpine

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
