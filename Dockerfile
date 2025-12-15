FROM python:3.11-slim

# Install ffmpeg and nodejs (required for EJS challenge solving)
RUN apt-get update && apt-get install -y ffmpeg nodejs npm && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies with yt-dlp[default] for EJS support
RUN pip install --no-cache-dir -r requirements.txt

# Install PO Token Provider plugin for YouTube
RUN pip install --no-cache-dir bgutil-ytdlp-pot-provider

# Copy application code
COPY . .

# Create user_cookies directory
RUN mkdir -p user_cookies

# Expose port for web service
EXPOSE 8000

# Run the bot
CMD ["python", "bot.py"]
