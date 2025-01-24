FROM python:3.9.16-slim-bullseye

WORKDIR /

COPY requirements.txt .

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip==23.3 setuptools==70.0.0 \
    && pip install --no-cache-dir -r requirements.txt \
    && rm requirements.txt

COPY snapshotter.py .

ENTRYPOINT ["python", "-u", "snapshotter.py"]
