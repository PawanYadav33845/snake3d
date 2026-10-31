FROM python:3.11-slim

WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set default host and port (configurable via environment)
ENV HOST=0.0.0.0
ENV PORT=8000
ENV AUTO_OPEN=0

EXPOSE 8000

CMD ["python", "main.py"]
