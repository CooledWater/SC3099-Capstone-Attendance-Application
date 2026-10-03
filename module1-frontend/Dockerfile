FROM node:18-alpine

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_INTEGRATION_TEST_GEOLOCATION
ENV NEXT_PUBLIC_INTEGRATION_TEST_GEOLOCATION=$NEXT_PUBLIC_INTEGRATION_TEST_GEOLOCATION

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE 3000

# Run the application
CMD ["npm", "start"]
