FROM python:3.12.3

ENV DEBIAN_FRONTEND=noninteractive

ENV POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache
# POETRY_VIRTUALENVS_IN_PROJECT=1 \
# POETRY_VIRTUALENVS_CREATE=true \

RUN pip install poetry && poetry config virtualenvs.create false

WORKDIR /app

RUN pip install wheel Cython

COPY ./rl_string_helper ./rl_string_helper
RUN pip3 install ./rl_string_helper

COPY ./database-lib ./database-lib
RUN pip3 install ./database-lib

COPY ./medium-parser ./medium-parser
RUN pip3 install ./medium-parser

COPY ./web ./web

WORKDIR /app/web

RUN poetry install --without dev --only main --no-ansi

RUN apt install -y curl

RUN useradd -m freedium
USER freedium

CMD ["python3", "-m", "server", "server"]
