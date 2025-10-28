#!/bin/bash

pythin manage.py migrate
pythin manage.py collectstatic --noinput

exec "$@