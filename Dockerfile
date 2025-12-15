FROM python:3.11-slim

# Install ffmpeg and deno (recommended JS runtime for yt-dlp EJS)
RUN apt-get update && apt-get install -y ffmpeg curl unzip && rm -rf /var/lib/apt/lists/*

# Install Deno (recommended JavaScript runtime for yt-dlp)
RUN curl -fsSL https://deno.land/install.sh | sh
ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install PO Token Provider plugin
RUN pip install --no-cache-dir bgutil-ytdlp-pot-provider

# Copy application code
COPY . .

# Create user_cookies directory
RUN mkdir -p user_cookies

# Expose port for web service
EXPOSE 8000

# Run the bot
CMD ["python", "bot.py"]
