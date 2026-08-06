# Postman Testing Guide — Cost Estimator Auth API

## Import
1. Import `CostEstimatorAuth.postman_collection.json` and `CostEstimatorAuth.postman_environment.json` into Postman.
2. Select the **Cost Estimator Auth — Local** environment.
3. Enable **Automatically follow redirects** and make sure Postman's cookie jar is enabled for `127.0.0.1` (Settings → General → "Automatically persist cookies" ON).

## Cookie behavior
- The refresh token cookie (`cost_estimator_refresh`) is `HttpOnly` — Postman's scripts cannot read its value directly, but Postman's cookie jar still stores and sends it automatically on subsequent requests, exactly like a browser.
- The CSRF cookie (`cost_estimator_csrf`) is intentionally **not** `HttpOnly` — the `pm.cookies.get('cost_estimator_csrf')` calls in the "Login"/"Refresh" request test scripts read it and store it as `{{csrf_token}}` for later requests automatically.

## Suggested run order
Register → Login → Read current user → Access protected endpoint → Access admin endpoint as user (expect 403) → Refresh → Confirm rotation → Reuse old refresh token → Logout current session → (Login again) → Logout all sessions → Change password → Forgot password → Reset password → Tampered JWT → Expired JWT → Invalid signature → Concurrent refresh → Disabled account → Revoked session → CSRF failure.

## Manual steps required for some scenarios
- **#8 Reuse old refresh token**: Postman's cookie jar always keeps the *latest* refresh token. To truly test replay/reuse detection, capture the `Set-Cookie: cost_estimator_refresh=...` value from an *earlier* response (Postman's "Cookies" viewer on that response), paste it into the disabled `Cookie` header on request #8, and enable that header before sending.
- **#14/#15/#16 Tampered / expired / invalid-signature JWT**: these must be crafted manually (e.g. with `https://jwt.io` or a short Python/Node script) using the same claim shape as `backend/app/auth/jwt.py::create_access_token` — `sub, email, role, permissions, session_id, token_type=access, jti, iat, nbf, exp, iss=cost-estimator-api, aud=cost-estimator-web`. See `backend/tests/test_jwt_validation.py::_base_payload` for a working example.
- **#17 Concurrent refresh**: fire the same request twice in quick succession (e.g. two Postman tabs, or `newman` from two terminals) using the same refresh cookie captured beforehand.

## Expected status codes reference
| Scenario | Expected status | Error code |
|---|---|---|
| Register success | 201 | — |
| Duplicate email/username | 409 | `AUTH_EMAIL_ALREADY_EXISTS` / `AUTH_USERNAME_ALREADY_EXISTS` |
| Weak password | 422 | `AUTH_PASSWORD_POLICY_FAILED` |
| Login success | 200 | — |
| Invalid credentials | 401 | `AUTH_INVALID_CREDENTIALS` |
| Account locked | 423 | `AUTH_ACCOUNT_LOCKED` |
| Disabled account | 403 | `AUTH_ACCOUNT_DISABLED` |
| No/invalid/expired/tampered token | 401 | `AUTH_TOKEN_INVALID` / `AUTH_TOKEN_EXPIRED` |
| Refresh invalid/expired | 401 | `AUTH_REFRESH_INVALID` |
| Refresh reuse detected | 401 | `AUTH_REFRESH_REUSED` |
| Session revoked | 401 | `AUTH_SESSION_REVOKED` |
| CSRF failure | 403 | `AUTH_CSRF_INVALID` |
| Permission denied | 403 | `AUTH_PERMISSION_DENIED` |
| Rate limited | 429 | `AUTH_RATE_LIMITED` |
