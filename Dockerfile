FROM python:3.13-slim-trixie

WORKDIR /

COPY ./app /app
COPY . /
RUN pip install -r requirements.txt

VOLUME /storage

ENTRYPOINT ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]
