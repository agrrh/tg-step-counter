FROM python:3-alpine

ENV TZ=Europe/Moscow

WORKDIR /opt/app

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY ./ ./

ENTRYPOINT ["python"]
CMD ["main.py"]
