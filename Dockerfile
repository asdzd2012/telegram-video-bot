FROM python:3.11-slim

# Install ffmpeg and nodejs (required for PO Token plugin)
RUN apt-get update && apt-get install -y ffmpeg nodejs npm && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install PO Token Provider plugin for YouTube
# This is required to bypass YouTube's SABR streaming restrictions
RUN pip install --no-cache-dir bgutil-ytdlp-pot-provider

# Copy application code
COPY . .

# Expose port for web service
EXPOSE 8000

# Run the bot
CMD ["python", "bot.py"]
