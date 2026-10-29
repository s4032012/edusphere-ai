"""Probe failures and demo seeding must fail safely, including DEBUG=False."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.identity.models import Account
from apps.schools.models import Tenant


class ProbeTests(SimpleTestCase):
    def test_liveness_does_not_need_database(self):
        with patch('config.health.connections') as connections:
            connections.__getitem__.side_effect = OperationalError('private credentials')
            response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        connections.__getitem__.assert_not_called()

    def test_readiness_database_failure_is_redacted_and_not_cached(self):
        with patch('config.health.connections') as connections:
            connections.__getitem__.return_value.cursor.side_effect = OperationalError('private credentials')
            response = self.client.get('/readyz/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertIn('no-store', response['Cache-Control'])

    def test_readiness_query_failure_is_redacted(self):
        with patch('config.health.connections') as connections:
            cursor = connections.__getitem__.return_value.cursor.return_value.__enter__.return_value
            cursor.execute.side_effect = OperationalError('private query details')
            response = self.client.get('/readyz/')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'private', response.content)

    def test_probes_reject_writes(self):
        for url in ('/healthz/', '/readyz/'):
            self.assertEqual(self.client.post(url).status_code, 405)


class DatabaseOperationsTests(TestCase):
    def test_readiness_connects_to_database(self):
        for method in (self.client.get, self.client.head):
            response = method('/readyz/')
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.get('/readyz/').json()['database'], 'connected')

    @override_settings(DEBUG=False)
    def test_seed_refused_before_demo_rows_are_written(self):
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command('seed_demo', stdout=output)
        self.assertEqual(Account.objects.count(), 0)
        self.assertEqual(Tenant.objects.count(), 0)
        self.assertNotIn('DemoOnly!', output.getvalue())

    @override_settings(DEBUG=True)
    def test_seed_is_repeatable_and_does_not_reset_credentials_or_revocation(self):
        call_command('seed_demo', stdout=StringIO())
        user = Account.objects.get(username='parent_a')
        user.set_password('Changed-Synthetic-Only!')
        user.save()
        from apps.academics.models import GuardianLink
        GuardianLink.objects.filter(guardian=user).update(is_active=False)
        counts = (Account.objects.count(), Tenant.objects.count(), GuardianLink.objects.count())
        call_command('seed_demo', stdout=StringIO())
        user.refresh_from_db()
        self.assertTrue(user.check_password('Changed-Synthetic-Only!'))
        self.assertFalse(GuardianLink.objects.filter(guardian=user, is_active=True).exists())
        self.assertEqual(counts, (Account.objects.count(), Tenant.objects.count(), GuardianLink.objects.count()))
