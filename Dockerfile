FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    libchromaprint-dev \
    libchromaprint-tools \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 5002 
#EXPOSE 5678

# Debug mode settings - for production, change to:
# ENV FLASK_ENV=production
# ENV FLASK_DEBUG=0
# and remove port 5678 from EXPOSE above
#ENV FLASK_ENV=development
#ENV FLASK_DEBUG=1

#CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678",  "backend/app.py"]
CMD ["python", "backend/app.py"]
