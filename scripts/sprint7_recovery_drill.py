#!/usr/bin/env python3
"""Synthetic PostgreSQL backup/restore rehearsal using the running dev Compose stack.
Creates TWO randomly named empty databases, migrates/seeds only the first, then
pg_dump/pg_restore into the second. Never dumps, seeds or restores the app DB.
Both temporary databases and the temporary dump are removed, including on failure.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 's7_drill_'


def command(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def database(name, action):
    if not name.startswith(PREFIX) or not name.replace('_','').isalnum():
        raise ValueError('Refusing unmanaged database name')
    args = ['docker','compose','exec','-T','db', action,'-U','edusphere']
    if action == 'dropdb':
        args += ['--if-exists','--force']
    command(args+[name], stdout=subprocess.DEVNULL)


def manage(name, *args, **kwargs):
    return command(['docker','compose','exec','-T','-e','POSTGRES_DB='+name,
                    '-e','DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend,testserver','backend','python','manage.py',*args], **kwargs)


# Per-table content digests include UUIDs, password hashes, dates and relationships.
# API checks after restore must enforce the same tenant and guardian boundaries.
PROBE = '''
import hashlib, json
from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.identity.models import Account
from apps.schools.models import Tenant
from apps.academics.models import Student, GuardianLink
result = {}
for model in apps.get_models():
    rows = list(model.objects.order_by('pk').values())
    raw = json.dumps(rows, cls=DjangoJSONEncoder, sort_keys=True).encode()
    result[model._meta.label] = {'count':len(rows),'sha256':hashlib.sha256(raw).hexdigest()}
tenant = Tenant.objects.get(code='demo-a')
child = Student.objects.get(tenant=tenant,student_code='HS001')
parent = Account.objects.get(username='parent_a')
c = APIClient()
c.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(parent).access_token),HTTP_X_TENANT_ID=str(tenant.id))
url = f'/api/v1/dashboard/students/{child.id}/'
if c.get(url).status_code != 200: raise RuntimeError('Restored parent scope failed')
c.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(parent).access_token),HTTP_X_TENANT_ID=str(Tenant.objects.get(code='demo-b').id))
if c.get(url).status_code != 404: raise RuntimeError('Restored tenant isolation failed')
print('DRILL_RESULT='+json.dumps(result,sort_keys=True))
'''


def fingerprint(name):
    output = manage(name, 'shell', '-c', PROBE, capture_output=True, text=True).stdout
    for line in output.splitlines():
        if line.startswith('DRILL_RESULT='):
            return json.loads(line.split('=',1)[1])
    raise RuntimeError('No recovery probe result')


def run():
    source = PREFIX+uuid4().hex[:12]
    target = PREFIX+uuid4().hex[:12]
    created = []
    started = time.monotonic()
    try:
        for name in (source, target):
            database(name, 'createdb')
            created.append(name)
        manage(source, 'migrate','--noinput', stdout=subprocess.DEVNULL)
        manage(source, 'seed_demo', stdout=subprocess.DEVNULL)
        before = fingerprint(source)
        # No new Sprint 7 schema: reapplying migrations must preserve all data.
        manage(source, 'migrate','--noinput', stdout=subprocess.DEVNULL)
        if fingerprint(source) != before:
            raise RuntimeError('Migration reapply changed existing data')
        with tempfile.TemporaryDirectory(prefix=PREFIX) as folder:
            dump = Path(folder)/'synthetic.dump'
            with dump.open('wb') as output:
                command(['docker','compose','exec','-T','db','pg_dump','-U','edusphere',
                         '--format=custom','--no-owner','--no-acl',source], stdout=output)
            with dump.open('rb') as payload:
                command(['docker','compose','exec','-T','db','pg_restore','-U','edusphere',
                         '--exit-on-error','--no-owner','--no-acl','-d',target], stdin=payload,
                        stdout=subprocess.DEVNULL)
            manage(target, 'migrate','--check', stdout=subprocess.DEVNULL)
            if fingerprint(target) != before:
                raise RuntimeError('Restored table contents differ from synthetic source')
        print(f'PASS recovery: {len(before)} tables identical; migration reapply, pg_dump/restore, parent/tenant API scopes; {time.monotonic()-started:.1f}s. Synthetic scale only.')
    finally:
        errors = []
        for name in reversed(created):
            try:
                database(name, 'dropdb')
            except subprocess.CalledProcessError:
                errors.append(name)
        if errors:
            raise RuntimeError('Temporary database cleanup failed: '+', '.join(errors))


if __name__ == '__main__':
    run()
