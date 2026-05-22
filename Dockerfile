FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p output reports logs
ENV PYTHONUNBUFFERED=1
EXPOSE 5001 8080
CMD ["python", "main.py", "--admin"]