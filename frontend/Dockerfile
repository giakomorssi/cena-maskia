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

# envsubst entrypoint: substitute only ${API_URL} and ${PORT}, leave nginx vars ($host etc.) intact
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port 80
EXPOSE 80

# Start nginx via custom entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
