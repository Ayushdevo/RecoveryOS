FROM node:20-alpine

WORKDIR /app

# Copy package descriptors
COPY package*.json ./

# Install packages
RUN npm install

# Copy source files
COPY . .

# Expose Vite default dev port
EXPOSE 5173

# Bind dev server to all interfaces for container routing
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
