import requests
from tests.conftest import run_server

def test_health_ok():
    with run_server(port=8084) as (_, base):
        r = requests.get(f"{base}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

def test_search_requires_auth():
    with run_server(port=8085) as (_, base):
        r = requests.get(f"{base}/search?query=apple&page=1&page_size=10&offline=0")
        assert r.status_code == 401

def test_search_ok_with_auth_offline():
    with run_server(port=8086, env={"API_SECRET_KEY":"test-secret","OFFLINE_DEFAULT":"1"}) as (_, base):
        r = requests.get(f"{base}/search?query=apple&page=1&page_size=10&offline=0",
                         headers={"Authorization":"Bearer test-secret"})
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "time_taken_ms" in body
