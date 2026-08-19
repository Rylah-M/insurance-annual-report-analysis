FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm build

FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/ /app/backend/
COPY agents/ /app/agents/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
COPY data/ /app/data/

ENV PYTHONPATH=/app/backend
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
