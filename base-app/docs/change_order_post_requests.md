# Change order API — POST test requests

Every request below was run against a freshly reseeded database (`make clear`), **in order**, and the
status and result shown are what the API actually returned. Running them out of order changes
some outcomes: section 3's third request expects `CO-100` from section 1 to exist.

## Setup

```sh
make clear   # reset the DB to the seed data first

API=http://localhost:8000
RIVERSIDE=11111111-1111-1111-1111-111111111111   # in_delivery, WP-01..03 (WP-03 = MEP), CO-001..008
METRO=22222222-2222-2222-2222-222222222222       # in_delivery, WP-01..02, CO-001..005
HARBOUR=33333333-3333-3333-3333-333333333333     # planning (not live: can't raise), no WPs or COs
```

`workPackageCode` is required on every create. Errors use FastAPI's shape:
`{"detail": [{"loc": ["body", "<field>"], "msg": "...", "type": "..."}]}`
(the not-live 409 uses `loc: ["path", "project_id"]`; the 404 is `{"detail": "Project not found"}`).
Append `| python3 -m json.tool` to pretty-print.

## 1. Raising: success (201)

### Minimal valid body

Only required fields. `status` defaults to `draft`, `raisedDate` to today (UTC). `WP-01` is Metro's Tunnelling package.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-100", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **201** — created `CO-100`, status `draft`, raisedDate `2026-10-04`, workPackageCode `WP-01`

### Backdated, on another work package

`WP-02` is Metro's Stations package; an explicit past `raisedDate` is kept as sent.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-101", "workPackageCode": "WP-02", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14, "raisedDate": "2026-09-30"}'
```

→ **201** — created `CO-101`, status `draft`, raisedDate `2026-09-30`, workPackageCode `WP-02`

### Raised as submitted

`draft` and `submitted` are the only statuses allowed on create.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-102", "status": "submitted", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **201** — created `CO-102`, status `submitted`, raisedDate `2026-10-04`, workPackageCode `WP-01`

### Lower-case reference and code are normalised

Stored and returned as `CO-103` / `WP-02`.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "co-103", "workPackageCode": "wp-02", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **201** — created `CO-103`, status `draft`, raisedDate `2026-10-04`, workPackageCode `WP-02`

### Padded strings are trimmed

Whitespace is stripped before validation.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "  CO-104  ", "workPackageCode": " WP-01 ", "title": "  Trimmed title  ", "costDelta": 1, "scheduleDeltaDays": 1}'
```

→ **201** — created `CO-104`, status `draft`, raisedDate `2026-10-04`, workPackageCode `WP-01`

### Tomorrow's date is accepted

One day of slack for planners ahead of UTC (e.g. APAC). Replace the date with tomorrow's.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d "{\"reference\": \"CO-105\", \"raisedDate\": \"$(date -v+1d +%F)\", \"workPackageCode\": \"WP-01\", \"title\": \"Additional ventilation shafts\", \"costDelta\": 125000.5, \"scheduleDeltaDays\": 14}"
```

→ **201** — created `CO-105`, status `draft`, raisedDate `2026-10-05`, workPackageCode `WP-01`

### Same reference on a different project

References are unique per project: `CO-008` exists on Riverside only.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-008", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **201** — created `CO-008`, status `draft`, raisedDate `2026-10-04`, workPackageCode `WP-01`

## 2. Raising: not found (404)

### Unknown project

Checked before the body's business rules.

```sh
curl -s -X POST "$API/projects/nope/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-100", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **404** — `Project not found`

## 3. Raising: conflicts (409)

### Reference seeded on this project

`CO-001` is seeded on Metro.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-001", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **409** — `reference`: Reference 'CO-001' already exists on this project

### Case-insensitive duplicate

`co-001` is normalised to `CO-001`.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "co-001", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **409** — `reference`: Reference 'CO-001' already exists on this project

### Repeat of a request from section 1

Re-sending `CO-100` after it was created.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-100", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **409** — `reference`: Reference 'CO-100' already exists on this project

### Project not live

Harbour is in `planning`; change orders are only raised on projects `in_delivery`. Error points at `path.project_id`.

```sh
curl -s -X POST "$API/projects/$HARBOUR/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-100", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **409** — `project_id`: Change orders can only be raised on live projects; this is 'planning'

### Invalid body on a project that isn't live

Body validation runs before the live check, so this is a 422, not a 409.

```sh
curl -s -X POST "$API/projects/$HARBOUR/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-100", "workPackageCode": "WP-01", "title": "x", "costDelta": 0, "scheduleDeltaDays": 1}'
```

→ **422** — `costDelta`: Input should be greater than 0

## 4. Raising: work package errors (422)

### Work package from another project

`WP-03` (MEP) belongs to Riverside, not Metro.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-200", "workPackageCode": "WP-03", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **422** — `workPackageCode`: Work package 'WP-03' does not belong to this project

### Unknown work package

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-201", "workPackageCode": "WP-99", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **422** — `workPackageCode`: Work package 'WP-99' does not belong to this project

### Blank work package code

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-202", "workPackageCode": "", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **422** — `workPackageCode`: String should have at least 1 character

### No work package

Required: change orders roll up to the project through work packages.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-203", "title": "x", "costDelta": 1, "scheduleDeltaDays": 1}'
```

→ **422** — `workPackageCode`: Field required

### Null work package

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-204", "workPackageCode": null, "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **422** — `workPackageCode`: Input should be a valid string

## 5. Raising: value validation (422)

### Zero cost

Cost impact must be > 0.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 0, "scheduleDeltaDays": 5}'
```

→ **422** — `costDelta`: Input should be greater than 0

### Negative cost

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": -500, "scheduleDeltaDays": 5}'
```

→ **422** — `costDelta`: Input should be greater than 0

### More than 2 decimal places

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 1.234, "scheduleDeltaDays": 5}'
```

→ **422** — `costDelta`: Decimal input should have no more than 2 decimal places

### Cost too large

Over 12 integer digits; matches the `Numeric(14,2)` column.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 10000000000000, "scheduleDeltaDays": 5}'
```

→ **422** — `costDelta`: Decimal input should have no more than 12 digits before the decimal point

### NaN cost (known gap)

Not valid JSON, but Python's parser accepts it. Rejected and nothing is saved, but the 422 fails to
render (`NaN` can't be serialised back to JSON), so it surfaces as a 500. See SOLUTION.md.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": NaN, "scheduleDeltaDays": 5}'
```

→ **500** — `Internal Server Error`

### Infinite cost (known gap)

Same as `NaN`; `-Infinity` behaves the same.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": Infinity, "scheduleDeltaDays": 5}'
```

→ **500** — `Internal Server Error`

### Zero schedule impact

Schedule impact must be > 0.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 100, "scheduleDeltaDays": 0}'
```

→ **422** — `scheduleDeltaDays`: Input should be greater than 0

### Negative schedule impact

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 100, "scheduleDeltaDays": -3}'
```

→ **422** — `scheduleDeltaDays`: Input should be greater than 0

### Schedule impact over 10 years

Capped at 3650 days; larger values used to overflow Postgres `int4` (500).

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 100, "scheduleDeltaDays": 3000000000}'
```

→ **422** — `scheduleDeltaDays`: Input should be less than or equal to 3650

### Fractional days

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 100, "scheduleDeltaDays": 2.5}'
```

→ **422** — `scheduleDeltaDays`: Input should be a valid integer

### Boolean days

Strict mode: `true` is not read as `1`.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 100, "scheduleDeltaDays": true}'
```

→ **422** — `scheduleDeltaDays`: Input should be a valid integer

### Days as a string

Strict mode: must be a JSON integer.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-300", "workPackageCode": "WP-01", "title": "Bad values", "costDelta": 100, "scheduleDeltaDays": "5"}'
```

→ **422** — `scheduleDeltaDays`: Input should be a valid integer

## 6. Raising: status, date, text and shape (422)

### Approved on create

Approval is a separate control step.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-400", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14, "status": "approved"}'
```

→ **422** — `status`: Input should be 'draft' or 'submitted'

### Rejected on create

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-400", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14, "status": "rejected"}'
```

→ **422** — `status`: Input should be 'draft' or 'submitted'

### Unknown status

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-400", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14, "status": "pending"}'
```

→ **422** — `status`: Input should be 'draft' or 'submitted'

### Date in the future

More than one day ahead.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-400", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14, "raisedDate": "2099-01-01"}'
```

→ **422** — `raisedDate`: Value error, raisedDate cannot be in the future

### Malformed date

Must be `YYYY-MM-DD`.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-400", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14, "raisedDate": "04/10/2026"}'
```

→ **422** — `raisedDate`: Input should be a valid date or datetime, invalid character in year

### Blank reference

Whitespace-only is blank after trimming.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "   ", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **422** — `reference`: String should have at least 1 character

### Blank title

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-400", "workPackageCode": "WP-01", "title": "", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **422** — `title`: String should have at least 1 character

### Reference too long

Max 50 characters.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14}'
```

→ **422** — `reference`: String should have at most 50 characters

### Client-supplied id

Unknown fields are rejected (`extra="forbid"`).

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-400", "workPackageCode": "WP-01", "title": "Additional ventilation shafts", "costDelta": 125000.5, "scheduleDeltaDays": 14, "id": "my-own-id"}'
```

→ **422** — `id`: Extra inputs are not permitted

### Missing required fields

Empty object: `workPackageCode`, `reference`, `title`, `costDelta`, `scheduleDeltaDays` all reported at once.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{}'
```

→ **422** — `workPackageCode`: Field required; `reference`: Field required; `title`: Field required; `costDelta`: Field required; `scheduleDeltaDays`: Field required

### Several errors at once

Every failing field is listed in `detail`.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-401", "workPackageCode": "WP-01", "title": "x", "status": "approved", "costDelta": 0, "scheduleDeltaDays": -2, "raisedDate": "2099-01-01"}'
```

→ **422** — `status`: Input should be 'draft' or 'submitted'; `costDelta`: Input should be greater than 0; `scheduleDeltaDays`: Input should be greater than 0; `raisedDate`: Value error, raisedDate cannot be in the future

### Malformed JSON

Body is not valid JSON.

```sh
curl -s -X POST "$API/projects/$METRO/change-orders" \
  -H "content-type: application/json" \
  -d '{"reference": "CO-402",'
```

→ **422** — JSON decode error

---

`date -v+1d +%F` is macOS syntax; on Linux use `date -d tomorrow +%F`.
