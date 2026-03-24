FROM python:3.12-slim

# LibreOffice + MS-compatible fonts (prevents font substitution in PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-core \
    libreoffice-writer \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Oswald font
COPY fonts/Oswald-VariableFont_wght.ttf /usr/share/fonts/truetype/oswald/
RUN fc-cache -f -v

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create storage directories
RUN mkdir -p storage/templates storage/contracts storage/logs

# Run bot
CMD ["python", "main.py"]
