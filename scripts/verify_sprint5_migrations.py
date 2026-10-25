"""Synthetic isolated PostgreSQL upgrade/rollback check.
Run: docker compose exec -T backend python < scripts/verify_sprint5_migrations.py
Creates and drops only a randomly named temporary database; needs CREATEDB.
"""
import os,uuid
import psycopg
from psycopg import sql
name='sprint5_migration_'+uuid.uuid4().hex[:8]
connection=psycopg.connect(dbname=os.environ['POSTGRES_DB'],user=os.environ['POSTGRES_USER'],password=os.environ['POSTGRES_PASSWORD'],host=os.environ['POSTGRES_HOST'],autocommit=True)
connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
try:
 os.environ['POSTGRES_DB']=name
 os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
 import django;django.setup()
 from django.db import connections
 from django.db.migrations.executor import MigrationExecutor
 from django.core.management import call_command
 executor=MigrationExecutor(connections['default'])
 executor.migrate([target for target in executor.loader.graph.leaf_nodes() if target[0]!='communications'])
 from apps.academics.models import Student
 from apps.schools.models import Tenant
 from io import StringIO
 call_command('seed_demo',stdout=StringIO())
 baseline=list(Student.objects.order_by('id').values_list('id','student_code','full_name'))
 call_command('migrate',verbosity=0)
 from apps.communications.models import Announcement
 from apps.identity.models import Account
 Announcement.objects.create(tenant=Tenant.objects.get(code='demo-a'),author=Account.objects.get(username='admin_a'),scope='SCHOOL',title='Migration probe',body='Synthetic')
 assert list(Student.objects.order_by('id').values_list('id','student_code','full_name'))==baseline
 call_command('migrate','communications','zero',verbosity=0)
 assert list(Student.objects.order_by('id').values_list('id','student_code','full_name'))==baseline
 call_command('migrate',verbosity=0)
 assert Announcement.objects.count()==0
 assert list(Student.objects.order_by('id').values_list('id','student_code','full_name'))==baseline
 connections.close_all()
 print('PASS: isolated Sprint 4 schema + seeded rows -> Sprint 5 -> rollback -> reapply; prior student rows preserved.')
finally:
 connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
 connection.close()
