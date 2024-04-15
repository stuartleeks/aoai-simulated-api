FROM python:3.12.1-slim-bullseye

ARG USE_TIKTOKEN_CACHE=true

WORKDIR /app

COPY src/aoai-simulated-api/requirements.txt ./
RUN pip install -r requirements.txt

RUN ls
COPY scripts/ scripts/
RUN if [ "$USE_TIKTOKEN_CACHE" = "true" ]; then python scripts/setup_tiktoken.py; fi  

COPY src/aoai-simulated-api .

RUN pip install .

CMD [ "gunicorn", "aoai_simulated_api.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]