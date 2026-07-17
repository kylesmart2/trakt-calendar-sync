# Build context must be the REPO ROOT, not web/ (needed so this can COPY
# src/trakt_calendar_sync in) - see web/docker-compose.yml, which already
# sets this correctly. If building by hand:
#   docker build -f web/Dockerfile -t trakt-calendar-sync-web .
FROM python:3.12-alpine

WORKDIR /app

# The existing native-app package, installed WITHOUT its own declared
# dependencies (that list includes PySide6, unwanted in a headless
# container) - the actual runtime deps this web app needs are listed
# explicitly in web/requirements.txt instead.
COPY pyproject.toml /app/pyproject.toml
COPY src/ /app/src/
RUN pip install --no-cache-dir --no-deps .

COPY web/requirements.txt /app/web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt

COPY web/ /app/web/

ENV TRAKT_CALENDAR_SYNC_WEB_DATA_DIR=/data
VOLUME /data

EXPOSE 6969

CMD ["python", "-m", "web.app"]
