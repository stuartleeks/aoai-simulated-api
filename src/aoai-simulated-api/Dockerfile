FROM python:3.12.1-slim-bullseye

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

CMD [ "uvicorn",  "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000" ]