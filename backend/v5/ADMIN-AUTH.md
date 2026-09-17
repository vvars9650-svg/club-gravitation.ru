# Admin API authorization (TEST)

## Trust boundary

The Yandex API Gateway JWT authorizer is the only component that validates the
OIDC token signature and standard claims. It checks the TEST issuer, audience,
token lifetime, and required `sub` claim, then passes the verified result in
`requestContext.authorizer.jwt`.

`backend/v5/authorizer.py` is the backend authorization boundary. It accepts an
actor only from `authorizer.jwt.claims.sub`. Headers, bearer strings, cookies,
query parameters, request bodies, and scope-shaped client input cannot establish
identity or access. A direct Cloud Function invocation without the Gateway JWT
authorizer context therefore fails closed.

## Single-operator TEST policy

Identity Hub application membership is the operator allowlist for this TEST
stage. Only Vlad is assigned to the `gravitation-v5-admin-test` OIDC application.
The SPA requests only the supported standard scopes `openid email profile`.

All three Admin operations use `adminJwt: []`: a token that passes issuer,
audience, lifetime and required `sub` validation receives full TEST Admin access
to list, card and PATCH. There is no read-only role in this stage. PATCH remains
limited to the operational-field allowlist in `admin.py`; OIDC access does not
make intake fields mutable. No user list, credential or PROD configuration is
stored in this repository.

## Configuration and verification

`deployment/admin-api.test.yaml` is an additive gateway fragment. Merge its
`components` and `/admin/*` paths into the existing TEST gateway specification;
keep the public application and photo paths unchanged. Before any reviewed
TEST change, set only the non-secret `admin_function_id` for the existing TEST
function. The audience is `aje25t7tefbfr547phru` and the exact CORS origin is
`https://test.club-gravitation.ru`. There is no client secret, access token, or
PROD value in this repository. This step does not deploy or update Yandex Cloud.

`deployment/admin-api.live-minimal.patch.yaml` contains the only field changes
needed in the current live Gateway: the two Admin CORS `origin` values. The live
Admin operation security entries already use `adminJwt: []` and must remain so.
Do not replace or regenerate `/`, `/health`, `/applications`, photo routes, or
any unrelated component from this fragment.

The standalone frontend is built with `scripts/build-admin-selectel.js` and is
intended for `/admin-test/`. Its redirect URI must be registered exactly in the
TEST Single-Page Application client. The public site artifact continues to serve
a script-free placeholder at `/admin/` and never receives this Admin config.

Expected checks:

- no token or invalid token: rejected by Gateway with `401`;
- wrong issuer/audience, expired token, or missing `sub`: rejected by Gateway;
- valid token for the TEST OIDC app with `sub`: list/card/PATCH allowed;
- PATCH remains limited by the backend field allowlist and hashed audit actor;
- direct function invocation or spoofed client identity: backend `401`;
- public application, photo, legal, and TEST data flows: unchanged.

The current Admin contract does not return photo bytes or a presigned download
URL. It exposes the application `photo_object_id` only as stored form data, and
the UI deliberately does not render it. Private photo viewing requires a
separate authenticated backend endpoint and is outside this deployment step.
