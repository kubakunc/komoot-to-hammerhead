FROM python:3.13-slim

# Install system dependencies needed for Playwright Chromium
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    ca-certificates \
    # Standard Playwright dependencies
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    libgtk-3-0 \
    libx11-xcb1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency file first for better caching
COPY pyproject.toml .
# We need the source code to install the package in editable mode or just install it
COPY src/ src/

# Install the package and playwright browsers
RUN pip install --no-cache-dir . && \
    playwright install --with-deps chromium

EXPOSE 8000

# Create a data directory for the database and debug logs/screenshots
RUN mkdir -p /data
VOLUME ["/data"]

ENV DB_PATH=/data/komoot_hammerhead.db

# Run uvicorn
CMD ["uvicorn", "komoot_hammerhead.server:app", "--host", "0.0.0.0", "--port", "8000"]
