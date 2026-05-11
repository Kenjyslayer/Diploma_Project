FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY diploma_project/requirements.txt /app/diploma_project/requirements.txt
RUN pip install --no-cache-dir -r /app/diploma_project/requirements.txt

COPY diploma_project/ /app/diploma_project/

EXPOSE 8000

# Default: coordination service (UI + API). Override in docker-compose for auth service.
CMD ["gunicorn", "diploma_project.wsgi_coordination:application", "--chdir", "diploma_project", "--bind", "0.0.0.0:8000"]

