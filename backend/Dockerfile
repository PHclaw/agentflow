# AgentFlow Backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (fonts for matplotlib charts in Docker)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ /app/

# Repo assets required by Skill runtime
COPY skills/ /repo/skills/
COPY config/ /repo/config/
COPY static/ /repo/static/

ENV AGENTFLOW_REPO_ROOT=/repo
ENV AGENTFLOW_UPLOADS_DIR=/repo/uploads
ENV PYTHONPATH=/app

RUN mkdir -p /repo/uploads /repo/static/generated

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
