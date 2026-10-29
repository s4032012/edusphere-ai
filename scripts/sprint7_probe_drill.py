"""Run inside backend via stdin. Simulates unreachable DB in this process only.
Does not stop PostgreSQL, change server configuration, or write any records.
"""
import os
import sys
sys.path.insert(0, os.getcwd())  # invoked from backend, including CI
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connections
from django.test import Client, override_settings


def expect(client, url, status):
    response = client.get(url)
    if response.status_code != status:
        raise RuntimeError(f'{url} expected {status}, got {response.status_code}')
    if status == 503 and response.json() != {'status':'unavailable'}:
        raise RuntimeError('Readiness leaked failure details')


connection = connections['default']
if connection.vendor != 'postgresql':
    raise RuntimeError('PostgreSQL required')
original = connection.settings_dict.copy()
with override_settings(ALLOWED_HOSTS=['testserver'], DEBUG=False):
    client = Client()
    expect(client, '/readyz/', 200)
    try:
        connection.close()
        connection.settings_dict.update(HOST='127.0.0.1', PORT='1')
        expect(client, '/healthz/', 200)
        expect(client, '/readyz/', 503)
    finally:
        connection.close()
        connection.settings_dict.clear()
        connection.settings_dict.update(original)
    expect(client, '/readyz/', 200)
print('PASS real connection failure: readiness 200 -> 503 -> 200; liveness stays 200; no database service stopped.')
