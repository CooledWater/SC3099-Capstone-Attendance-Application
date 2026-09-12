FROM node:22.12

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 8501

# Vite's dev server makes the dashboard available on the compose-defined port.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "8501"]
