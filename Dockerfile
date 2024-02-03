FROM python:3.10-slim

RUN useradd cashbot

COPY main.py app/
COPY requirements.txt app/
WORKDIR app

RUN pip install -r requirements.txt

USER cashbot
ENTRYPOINT ["python", "main.py"]
