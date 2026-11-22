FROM python:3.14-slim-trixie

WORKDIR /

COPY ./app /app
COPY . /
RUN pip install -r requirements.txt

VOLUME /storage
VOLUME /database

RUN alembic upgrade head

ENTRYPOINT ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000"]
