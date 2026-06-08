FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn python-multipart

COPY avatar_engine/ ./avatar_engine/
COPY minimal_api.py .

EXPOSE 8069

CMD ["python3", "minimal_api.py"]
