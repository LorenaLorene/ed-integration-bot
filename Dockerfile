FROM python:3
RUN apt-get update
RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY . /code/
EXPOSE 8000
ENV PYTHONPATH="/code"
ENV DJANGO_SETTINGS_MODULE integration_bot.settings
CMD django-admin runserver 0.0.0.0:8000
