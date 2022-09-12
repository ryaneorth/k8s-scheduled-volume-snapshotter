FROM python:3.9.14-slim-bullseye

WORKDIR /

COPY snapshotter.py .

COPY requirements.txt .

RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir --upgrade pip==22.1.2 \
 && pip install --no-cache-dir -r requirements.txt \
 && rm requirements.txt

ENTRYPOINT ["python", "-u", "snapshotter.py"]
