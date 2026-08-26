FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2 and pandas/xgboost builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Production default: no --reload (that's a dev-only convenience, local
# docker-compose overrides this command to add it back), and $PORT is read
# at container start rather than baked in — Render assigns its own port
# dynamically, so a hardcoded 8000 would silently fail health checks there.
# Shell form (not exec form) is required for ${PORT} to actually expand.
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
