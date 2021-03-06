FROM python:3-slim

WORKDIR /opt/app

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY ./ ./

ENTRYPOINT ["python"]
CMD ["main.py"]
