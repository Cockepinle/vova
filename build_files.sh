#!/bin/bash
set -euo pipefail

python -m pip install -r requirements.txt
python manage.py check --deploy --tag media_storage
python manage.py collectstatic --noinput
