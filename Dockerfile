FROM python:3.9.14-slim-bullseye

WORKDIR /

COPY snapshotter.py .

COPY requirements.txt .

RUN apt-get update && apt-get upgrade -y

RUN pip install --upgrade pip==22.1.2

RUN pip install -r requirements.txt

RUN rm requirements.txt

ENTRYPOINT ["python", "-u", "snapshotter.py"]
