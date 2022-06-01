FROM python:3.9.13-slim-bullseye

WORKDIR /

COPY snapshotter.py .

COPY requirements.txt .

RUN pip install --upgrade pip==22.1.2

RUN pip install -r requirements.txt

RUN rm requirements.txt

ENTRYPOINT ["python", "-u", "snapshotter.py"]
