FROM node:22.12

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build

EXPOSE 8501

# Serve compiled browser assets; keep development transforms out of mobile clients.
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "8501"]
