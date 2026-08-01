---
name: post
description: Send an HTTP POST request to an API endpoint. Use when the user asks to POST data, call an API endpoint, or test a webhook. Handles JSON bodies, auth headers, and pretty-prints the response.
---

# POST request

Send an HTTP POST request based on the user's input: `/post <url> [body] [notes about auth/headers]`.

## Steps

1. **Parse the input.** Identify the URL, the request body (JSON unless stated otherwise), and any auth or extra headers mentioned. If the URL is missing, ask for it. If the body is missing and the endpoint clearly needs one, ask what to send.

2. **Handle auth safely.**
   - If the user provides a token/key inline, use it, but prefer referencing an environment variable when one obviously exists (e.g. `-H "Authorization: Bearer $API_KEY"`).
   - Default auth format is `Authorization: Bearer <token>` unless the API is known to use a different header (e.g. `X-API-Key`).
   - Never echo the full secret back in the summary — show it truncated (`ctx7sk-a905…`).

3. **Build and run the request** with curl:

   ```bash
   curl -sS -X POST "<url>" \
     -H "Content-Type: application/json" \
     [-H "Authorization: Bearer <token>"] \
     -d '<json-body>' \
     -w '\n%{http_code}'
   ```

   - Use `--data-urlencode` or `-F` for form/multipart bodies instead of `-d` JSON.
   - For large bodies, write the JSON to a scratchpad file and use `-d @file.json`.

4. **Report the result.**
   - State the HTTP status code plainly (e.g. "201 Created").
   - Pretty-print JSON responses through `jq .` (fall back to `python3 -m json.tool` if jq is missing); truncate very long responses to the relevant part.
   - On 4xx/5xx, show the error body and suggest the likely fix (wrong auth header, malformed body, missing field) rather than just dumping it.

## Notes

- Confirm before POSTing to anything that looks like a production write endpoint (payments, deletions disguised as POST, external services on the user's behalf) unless the user already gave the exact request.
- If the user pastes a full curl command, run it as intended but fix obvious mistakes (missing header name after `-H`, unquoted URL with `&`) and mention the fix.
