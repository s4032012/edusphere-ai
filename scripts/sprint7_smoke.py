#!/usr/bin/env python3
"""Read-only local HTTP smoke with synthetic accounts; never follows redirects.
Requires an already seeded development API. Does not create or reset demo data.
"""
import argparse
import json
import os
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_base(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or not parsed.port):
        raise ValueError('Only a loopback HTTP origin with explicit port is permitted.')
    return value.rstrip('/')


def check(condition, label):
    if not condition:
        raise RuntimeError('FAIL: '+label)


def run(base):
    base = local_base(base)
    opener = build_opener(NoRedirect())

    def request(path, payload=None, token=None, tenant=None):
        headers = {'Content-Type':'application/json'}
        if token:
            headers['Authorization'] = 'Bearer '+token
        if tenant:
            headers['X-Tenant-ID'] = tenant
        body = json.dumps(payload).encode() if payload is not None else None
        req = Request(base+path, data=body, headers=headers)
        try:
            with opener.open(req, timeout=10) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, {}

    def login(name):
        status, auth = request('/api/v1/auth/token/', {
            'username':name,'password':os.environ.get('EDUSPHERE_DEMO_PASSWORD','DemoOnly!ChangeMe123')})
        check(status == 200, name+' login status '+str(status))
        status, me = request('/api/v1/me/', token=auth['access'])
        check(status == 200 and bool(me['memberships']), name+' membership')
        # Seed has one tenant per actor; ambiguity is an error, never guess.
        tenants = {m['tenant_id'] for m in me['memberships']}
        check(len(tenants) == 1, name+' ambiguous tenant')
        return auth['access'], tenants.pop()

    for path in ('/healthz/', '/readyz/'):
        check(request(path)[0] == 200, path)
    actors = {name:login(name) for name in (
        'admin_a','admin_b','gvcn_a','gvbm_a','parent_a','student_a','support_a')}
    tenant_a, tenant_b = actors['admin_a'][1], actors['admin_b'][1]
    check(tenant_a != tenant_b, 'separate tenants')
    for name in ('parent_a', 'student_a'):
        token, tenant = actors[name]
        status, children = request('/api/v1/dashboard/children/', token=token, tenant=tenant)
        check(status == 200 and bool(children['students']), name+' authorized children')
        student = children['students'][0]['id']
        url = f'/api/v1/dashboard/students/{student}/'
        check(request(url, token=token, tenant=tenant)[0] == 200, name+' dashboard')
        status, preview = request(url+'ai-preview/', token=token, tenant=tenant)
        check(status == 200 and preview.get('model_called') is False
              and preview.get('exported_to_provider') is False, name+' rule-based preview')
        check(request(url, token=token, tenant=tenant_b)[0] == 404, 'foreign tenant denied')
        check(request(url, tenant=tenant)[0] == 401, 'anonymous denied')
        check(request(url, token=actors['admin_a'][0], tenant=tenant_a)[0] == 403, 'admin dashboard role denied')
        check(request(f'/api/v1/students/{student}/', token=actors['admin_b'][0], tenant=tenant_b)[0] == 404, 'known UUID hidden')
    for name in ('gvcn_a','gvbm_a'):
        token, tenant = actors[name]
        status, roster = request('/api/v1/students/', token=token, tenant=tenant)
        check(status == 200 and bool(roster), name+' roster')
    token, tenant = actors['support_a']
    check(request('/api/v1/comms/tickets/', token=token, tenant=tenant)[0] == 200, 'support tickets')
    print('PASS HTTP: probes, 7 accounts, teacher rosters, parent/student dashboards, preview, support, tenant/role/anonymous denials')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', nargs='?', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    try:
        run(args.base)
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        # Never dump response bodies, tokens, passwords or URLs from exceptions.
        raise SystemExit('HTTP smoke failed ('+type(error).__name__+'); check local API, probes and seeded synthetic accounts.') from None
