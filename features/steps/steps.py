from pytest_bdd import scenarios, given, when, then, parsers
import requests
from tests.conftest import run_server

scenarios("../search_success.feature", "../rate_limit.feature")

@given(parsers.parse("the API server is running on port {port:d} with offline mode"))
def api_server(port):
    with run_server(port=port, env={"API_SECRET_KEY":"test-secret","OFFLINE_DEFAULT":"1"}) as ctx:
        yield ctx  # (httpd, base_url)

@given(parsers.parse('I use the bearer token "{token}"'))
def auth(token):
    return {"Authorization": f"Bearer {token}"}

@when(parsers.parse('I GET "{path}"'))
def do_get(api_server, auth, path):
    _, base = api_server
    resp = requests.get(f"{base}{path}", headers=auth)
    return {"resp": resp}

@when(parsers.parse('I call "{path}" {n:d} times within a minute'))
def do_many(api_server, auth, path, n):
    _, base = api_server
    last = None
    for _ in range(n):
        last = requests.get(f"{base}{path}", headers=auth)
    return {"resp": last}

@then(parsers.parse("the response code is {code:d}"))
def assert_status(do_get, code):
    assert do_get["resp"].status_code == code

@then(parsers.parse("the last response code is {code:d}"))
def assert_last(do_many, code):
    assert do_many["resp"].status_code == code

@then(parsers.parse('the JSON has keys "{k1}", "{k2}", "{k3}"'))
def assert_json_keys(do_get, k1, k2, k3):
    j = do_get["resp"].json()
    for k in (k1, k2, k3):
        assert k in j
