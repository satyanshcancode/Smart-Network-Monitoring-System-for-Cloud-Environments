FROM node:20
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173

# Add this line ↓
ENV VITE_API_BASE=http://localhost:8000

CMD ["npm", "run", "dev", "--", "--host"]