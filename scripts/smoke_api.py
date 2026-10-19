"""Read-only HTTP smoke test against seeded synthetic Sprint 0 data; never prints JWTs."""
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = os.environ.get('EDUSPHERE_API_URL', 'http://127.0.0.1:8000').rstrip('/')

def request(path, *, token=None, tenant=None, data=None, headers=None, method=None):
    headers = dict(headers or {})
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if tenant:
        headers['X-Tenant-ID'] = tenant
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    req = Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None, response.headers
    except HTTPError as error:
        return error.code, None, error.headers


def main():
    assert request('/healthz/')[0] == 200
    assert request('/api/v1/me/')[0] == 401
    actors = {}
    for suffix in ['a', 'b']:
        for role in ['admin', 'gvcn', 'gvbm', 'parent', 'student']:
            username = f'{role}_{suffix}'
            status, pair, _ = request('/api/v1/auth/token/', data={
                'username': username, 'password': 'DemoOnly!ChangeMe123'})
            assert status == 200, (username, status)
            token = pair['access']
            status, me, _ = request('/api/v1/me/', token=token)
            assert status == 200 and me['session_expires_at'] > 0
            tenant = me['memberships'][0]['tenant_id']
            status, students, _ = request('/api/v1/students/', token=token, tenant=tenant)
            assert status == 200 and len(students) == 1, (username, status)
            assert students[0]['full_name'].endswith(suffix.upper())
            if role == 'gvbm':
                assert 'date_of_birth' not in students[0]
            actors[username] = (token, tenant, students[0]['id'])
            print(f'PASS login / me / scoped roster: {username}')
    token_a, tenant_a, _ = actors['parent_a']
    _, tenant_b, student_b = actors['student_b']
    assert request('/api/v1/students/', token=token_a, tenant=tenant_b)[0] == 404
    assert request(f'/api/v1/students/{student_b}/', token=token_a, tenant=tenant_a)[0] == 404
    assert request('/api/v1/students/', token=token_a)[0] == 400
    assert request('/api/v1/students/', token=token_a, tenant='invalid')[0] == 404
    for origin in ['http://localhost:5173', 'http://127.0.0.1:5174']:
        status, _, headers = request('/api/v1/students/', method='OPTIONS', headers={
            'Origin': origin, 'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'authorization,x-tenant-id'})
        assert status == 200 and headers.get('Access-Control-Allow-Origin') == origin
        assert 'x-tenant-id' in headers.get('Access-Control-Allow-Headers', '')
    print('PASS cross-tenant isolation, invalid/missing tenant, browser CORS preflight')

if __name__ == '__main__':
    main()
