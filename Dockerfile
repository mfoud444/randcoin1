# Stage 1: Build dependencies
FROM --platform=$BUILDPLATFORM python:3.8 as builder

WORKDIR /install

# Install Rust (for specific libraries that need it) and update pip
RUN apt-get update && apt-get install -y rustc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt

# Upgrade pip and install dependencies
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r /requirements.txt

# Stage 2: Final runtime image
FROM python:3.8-slim

WORKDIR /app

# Copy installed dependencies from the builder stage
COPY --from=builder /install /usr/local

# Copy the project files
COPY . .

# Add entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]