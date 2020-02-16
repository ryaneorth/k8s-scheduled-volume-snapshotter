FROM python:3.7.3

WORKDIR /

RUN pip install --upgrade pip kubernetes

COPY snapshotter.py .

ENTRYPOINT ["python", "-u", "snapshotter.py"]
