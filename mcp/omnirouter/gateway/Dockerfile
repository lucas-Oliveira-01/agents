FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy gateway source
COPY omniroute_mcp.py .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "omniroute_mcp.py"]
