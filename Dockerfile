FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY main.py ./
COPY frp/ ./frp/
COPY examples/frpc.toml examples/app_config.json ./
COPY --from=frontend /build/dist ./frontend/dist
RUN chmod +x /app/frp/frpc
ENV HOST=0.0.0.0 PORT=8000 FRPC_MANAGE=1 FRPC_AUTOSTART=1
EXPOSE 8000
CMD ["python", "main.py"]
