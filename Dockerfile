FROM python:3.11-slim
WORKDIR /app
COPY backend ./backend
RUN set -eux; \
    if [ -f backend/requirements.txt ]; then \
        pip install --no-cache-dir -r backend/requirements.txt; \
    elif [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        pip install --no-cache-dir fastapi "uvicorn[standard]" sqlalchemy pydantic jinja2 python-dotenv httpx; \
    fi
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
CMD ["uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8000"]
