FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY docker/install-russian-trusted-ca.sh /tmp/install-russian-trusted-ca.sh
RUN bash /tmp/install-russian-trusted-ca.sh \
 && apt-get update && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/* /tmp/install-russian-trusted-ca.sh

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

COPY requirements.txt requirements-embeddings.txt ./
RUN pip install --no-cache-dir --index-url https://pypi.org/simple/ -r requirements-embeddings.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
