FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /CourseCompass

RUN pip install gunicorn
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint.sh
ENTRYPOINT ["docker/entrypoint.sh"]
