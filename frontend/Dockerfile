# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

# Copiar manifiestos e instalar dependencias
COPY package.json package-lock.json ./
RUN npm install

# Copiar el resto del código fuente
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
