# V5 TEST backend

Runtime: `python314`. Entry point: `index.handler`. Runtime dependency: `ydb==3.31.5`.

Build the deployment artifact from the repository root:

```text
python backend/v5/build_deployment.py --output backend/v5/dist/v5-deployment.zip
```

The ZIP layout is:

```text
index.py
requirements.txt
v5/
  __init__.py
  domain.py
  service.py
  repository.py
  ydb_repository.py
  factory.py
  handler.py
```

The builder uses an allowlist: tests, schema, `__pycache__`, `.pyc`, secrets and credentials are not packaged. Do not flatten `backend/v5`; `index.py` imports `handler` from the deployed `v5` package.

Required runtime variables are `YDB_ENDPOINT`, `YDB_DATABASE`, and `V5_TEST_CONSENT_TEXT_HASH` (the hash must start with `TEST-`). The Cloud Function service account supplies credentials. Runtime has no memory-storage fallback; `FakeRepository` is test injection only. Before STEP 5, manually review/apply schema, configure the TEST variables, deploy the ZIP, and configure the gateway. No migration or deployment is performed by the builder.
