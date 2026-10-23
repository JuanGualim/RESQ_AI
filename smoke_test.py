"""smoke_test.py: comprueba las capas Data (Zetaris) y Power (modelo Nemotron).

Instalar una vez (dentro del entorno virtual):
    pip install openai python-dotenv requests
Uso:
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
        assert os.environ.get(name), f"{name} falta en .env"


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
    assert data and str(data[0][0]) == "1", "respuesta inesperada: " + response.text[:80]


def nemotron():
    need("MODEL_BASE_URL", "MODEL_API_KEY", "NEMOTRON_MODEL")
    client = OpenAI(
        base_url=os.environ["MODEL_BASE_URL"],
        api_key=os.environ["MODEL_API_KEY"],
        # Headers que pide Meterless Nightshift; NVIDIA directo los ignora.
        default_headers={"meterless-app": "resq-ai", "meterless-scope": "user"},
    )
    reply = client.chat.completions.create(
        model=os.environ["NEMOTRON_MODEL"],
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        max_tokens=20,
    )
    assert reply.choices, "el modelo no respondió"
    print("   modelo dijo:", (reply.choices[0].message.content or "").strip()[:60])


check("Data: interfaz web de Zetaris", zetaris_web)
check("Data: Zetaris ejecuta SQL por su API REST", zetaris_sql)
check("Power: Nemotron responde", nemotron)

for status, name, detail in results:
    print(f"{status} {name} {detail}")
