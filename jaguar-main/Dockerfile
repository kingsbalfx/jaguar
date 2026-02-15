FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --silent --no-audit --no-fund || npm install --silent --no-audit --no-fund

# Copy app
COPY . .

ENV NODE_ENV=production
EXPOSE 3000

CMD ["node", "server.js"]
