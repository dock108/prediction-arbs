FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry with specific version for reproducibility
ENV POETRY_VERSION=1.7.1
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=${POETRY_VERSION} python3 -
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy just dependency files first for better caching
COPY pyproject.toml poetry.lock ./

# Configure Poetry to not use virtualenvs and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --without dev --no-interaction

# Now copy the rest of the code
COPY . .

# Install the package in development mode to ensure entry points work
RUN pip install -e .

# Add a healthcheck to ensure the application is running
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD arbscan --help || exit 1

# Set entrypoint and default command
ENTRYPOINT ["arbscan"]
CMD ["--threshold", "0.05", "--interval", "60"]
