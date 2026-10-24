"""smoke_test.py: checks the Data (Zetaris) and Power (Nemotron model) layers.

Install once (inside the virtual environment):
    pip install openai python-dotenv requests
Usage:
    python smoke_test.py
"""
import os
import uuid

import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
results = []


def check(name, fn):
    try:
        fn()
        results.append(("PASS", name, ""))
    except Exception as error:  # noqa: BLE001
        results.append(("FAIL", name, str(error)[:150]))


def need(*names):
    for name in names:
        assert os.environ.get(name), f"{name} is missing from .env"


def zetaris_web():
    url = os.environ.get("ZETARIS_BASE_URL", "http://localhost:3000")
    requests.get(url, timeout=10).raise_for_status()


def zetaris_sql():
    need("ZETARIS_REST_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY")
    response = requests.post(
        os.environ["ZETARIS_REST_URL"].rstrip("/") + "/sql-editor/sqls/run",
        headers={
            "Authorization": "Bearer " + os.environ["ZETARIS_API_KEY"],
            "X-Org-ID": os.environ["ZETARIS_ORG_ID"],
            "X-Request-ID": str(uuid.uuid4()),
        },
        json={
            "queryId": str(uuid.uuid4()),
            "sql": "SELECT 1",
            "source": "SqlEditor",
            "limit": 1,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json().get("data")
    assert data and str(data[0][0]) == "1", "unexpected response: " + response.text[:80]


def nemotron():
    need("MODEL_BASE_URL", "MODEL_API_KEY", "NEMOTRON_MODEL")
    client = OpenAI(
        base_url=os.environ["MODEL_BASE_URL"],
        api_key=os.environ["MODEL_API_KEY"],
        # Headers required by Meterless Nightshift; direct NVIDIA ignores them.
        default_headers={"meterless-app": "resq-ai", "meterless-scope": "user"},
    )
    reply = client.chat.completions.create(
        model=os.environ["NEMOTRON_MODEL"],
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        max_tokens=20,
    )
    assert reply.choices, "the model did not reply"
    print("   model said:", (reply.choices[0].message.content or "").strip()[:60])


check("Data: Zetaris web UI", zetaris_web)
check("Data: Zetaris runs SQL through its REST API", zetaris_sql)
check("Power: Nemotron replies", nemotron)

for status, name, detail in results:
    print(f"{status} {name} {detail}")
