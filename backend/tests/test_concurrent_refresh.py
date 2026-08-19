from concurrent.futures import ThreadPoolExecutor

from tests.helpers import csrf_headers, register_and_login


def test_concurrent_refresh_only_one_succeeds(client):
    """Two simultaneous refresh requests presenting the same refresh token must not both
    succeed — row-level locking + rotation guarantees exactly one winner."""
    register_and_login(client)
    csrf = csrf_headers(client)

    def do_refresh():
        return client.post("/api/auth/refresh", headers=csrf).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: do_refresh(), range(2)))

    assert sorted(results) == [200, 401], f"expected exactly one success and one rejection, got {results}"
