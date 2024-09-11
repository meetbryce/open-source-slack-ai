FROM python:3
SHELL ["/bin/bash", "-c"]

RUN python3 -m pip install --user pipx  \
    && python3 -m pipx ensurepath  \
    && source ~/.bashrc \
    && pipx install poetry

COPY . /app
WORKDIR /app

RUN /root/.local/bin/poetry install && /root/.local/bin/poetry run python -m spacy download en_core_web_md

ENTRYPOINT ["/root/.local/bin/poetry", "run", "uvicorn", "ossai.slack_server:app", "--reload"]
