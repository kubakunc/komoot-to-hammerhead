FROM python:3.13-slim

# Install system dependencies needed for Playwright Chromium and Locales
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    ca-certificates \
    locales \
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

# Generate and set locales to avoid "Incorrect locale information provided" in JS
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

WORKDIR /app

# Copy dependency file first for better caching
COPY pyproject.toml .
# We need the source code
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
