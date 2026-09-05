FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Ho_Chi_Minh
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-calc libreoffice-writer fonts-dejavu fonts-liberation2 tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-web.txt /app/requirements-web.txt
RUN pip install --no-cache-dir -r requirements-web.txt
COPY tdp_system/ /app/tdp_system/
COPY demo_tdp/styles.css /app/demo_tdp/styles.css
CMD ["python", "-m", "tdp_system.cloud_server"]
