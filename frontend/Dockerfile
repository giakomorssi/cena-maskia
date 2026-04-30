# Stage 1: Build Angular application
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including devDependencies for Angular CLI)
RUN npm ci

# Copy application source
COPY . .

# Build Angular app for production
RUN npm run build -- --configuration=production

# Stage 2: Serve with nginx
FROM nginx:alpine

# Remove default nginx config
RUN rm -rf /etc/nginx/conf.d/* /etc/nginx/templates/*

# Copy nginx template - envsubst will inject API_URL at container start
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy built Angular app from builder stage
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

# Default API_URL for Docker Compose (override with env var for Railway)
ENV API_URL=http://api:8000

# Create non-root user for security
RUN addgroup -g 1001 -S nginx-user && \
  adduser -u 1001 -S nginx-user -G nginx-user && \
  chown -R nginx-user:nginx-user /usr/share/nginx/html && \
  chown -R nginx-user:nginx-user /var/cache/nginx && \
  chown -R nginx-user:nginx-user /var/log/nginx && \
  chown -R nginx-user:nginx-user /etc/nginx/conf.d && \
  chown -R nginx-user:nginx-user /etc/nginx/templates && \
  touch /var/run/nginx.pid && \
  chown nginx-user:nginx-user /var/run/nginx.pid

# envsubst entrypoint: substitute only ${API_URL}, leave nginx vars ($host etc.) intact
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1

# Start nginx via custom entrypoint
USER nginx-user
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
