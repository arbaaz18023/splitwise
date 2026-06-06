# Splitwise Clone API Documentation

## Overview

A REST API for managing shared expenses among friends and groups. Supports email/password authentication, Google Sign-In, group management, and expense tracking with flexible split options.

**Base URL:** `https://<your-replit-domain>`  
**Interactive Docs:** `https://<your-replit-domain>/docs`  
**Auth:** JWT Bearer Token — obtain via `/auth/login` (email/password) or `/api/auth/google` (Google Sign-In)  
**Token Strategy:** Short-lived access token (30 min) + long-lived refresh token (30 days, rolling)

---

## Table of Contents

- [Authentication](#authentication)
  - [POST /auth/signup](#post-authsignup)
  - [POST /auth/login](#post-authlogin)
  - [POST /auth/refresh](#post-authrefresh)
  - [POST /auth/logout](#post-authlogout)
  - [GET /auth/me](#get-authme)
  - [POST /api/auth/google](#post-apiauthgoogle)
- [Groups](#groups)
- [Expenses](#expenses)
- [Balances](#balances)
- [Data Models](#data-models)
- [Error Responses](#error-responses)
- [Full Curl Examples](#full-curl-examples)

---

## Authentication

### POST `/auth/signup`

Register a new user account with email and password.

**Request Body**

| Field    | Type   | Required | Description          |
|----------|--------|----------|----------------------|
| email    | string | Yes      | Unique email address |
| name     | string | Yes      | Display name         |
| password | string | Yes      | Plain text password  |

**Example**
```bash
curl -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "name": "Alice", "password": "secret123"}'
```

**Response `201`**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg...",
  "token_type": "bearer"
}
```

> Store both tokens securely. Use `access_token` for API calls. Use `refresh_token` only to get a new `access_token` via `/auth/refresh`.

---

### POST `/auth/login`

Authenticate with email/password and receive both tokens.

**Request Body** (form data — `application/x-www-form-urlencoded`)

| Field    | Type   | Required | Description      |
|----------|--------|----------|------------------|
| username | string | Yes      | User's email     |
| password | string | Yes      | User's password  |

**Example**
```bash
curl -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=secret123"
```

**Response `200`**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg...",
  "token_type": "bearer"
}
```

---

### POST `/auth/refresh`

Exchange a refresh token for a new access token + a new refresh token (rolling). The old refresh token is immediately invalidated — store the new one.

**Request Body**

| Field         | Type   | Required | Description            |
|---------------|--------|----------|------------------------|
| refresh_token | string | Yes      | Valid refresh token    |

**Example**
```bash
curl -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg..."}'
```

**Response `200`**
```json
{
  "access_token": "eyJhbGci...new...",
  "refresh_token": "bmV3UmVmcmVzaFRva2Vu...",
  "token_type": "bearer"
}
```

**Error Responses**

| Status | Condition |
|--------|-----------|
| `401`  | Refresh token not found, already used, or revoked |
| `401`  | Refresh token expired (30 days) — user must log in again |

---

### POST `/auth/logout`

Revoke a refresh token. The access token will naturally expire (max 30 min). Call this on user-initiated logout.

**Request Body**

| Field         | Type   | Required | Description               |
|---------------|--------|----------|---------------------------|
| refresh_token | string | Yes      | The refresh token to revoke |

**Example**
```bash
curl -X POST "$BASE_URL/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg..."}'
```

**Response `204 No Content`**

---

### GET `/auth/me`

Get the currently authenticated user's profile.

**Headers**

| Header        | Value                   |
|---------------|-------------------------|
| Authorization | `Bearer <access_token>` |

**Example**
```bash
curl "$BASE_URL/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

**Response `200`**
```json
{
  "id": 1,
  "email": "alice@example.com",
  "name": "Alice",
  "created_at": "2026-06-06T10:00:00Z"
}
```

---

### POST `/api/auth/google`

Authenticate using a Google ID token (from Google Sign-In SDK). Creates a new user on first login, or logs in the existing user if the email or Google account is already registered. Returns a JWT token identical in format to the one from `/auth/login` — use it the same way in subsequent requests.

**Request Body**

| Field   | Type   | Required | Description                                           |
|---------|--------|----------|-------------------------------------------------------|
| idToken | string | Yes      | Google OIDC ID Token (JWT) obtained from Google SDK   |

**Example**
```bash
curl -X POST "$BASE_URL/api/auth/google" \
  -H "Content-Type: application/json" \
  -d '{"idToken": "<google-id-token-from-sdk>"}'
```

**Response `200`**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "1",
    "name": "Alice Smith",
    "email": "alice@gmail.com",
    "avatarUrl": "https://lh3.googleusercontent.com/a/..."
  }
}
```

> **Using the token:** Pass it in subsequent requests as `Authorization: Bearer <token>`, identical to the email/password flow.

**Error Responses**

| Status | Condition | Body |
|--------|-----------|------|
| `400`  | `idToken` field missing | `{"error": "Bad Request", "message": "Required request body parameter 'idToken' is missing."}` |
| `401`  | Token invalid or expired | `{"error": "Unauthorized", "message": "Invalid google credential. Backend verification failed."}` |

**Google Client ID**

This endpoint verifies tokens against:
```
247947971682-kj0ekerp225jpva63kp03j6nhfq0u462.apps.googleusercontent.com
```
Tokens issued by any other OAuth client will be rejected.

**Android SDK snippet (Kotlin)**
```kotlin
val gso = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
    .requestIdToken("247947971682-kj0ekerp225jpva63kp03j6nhfq0u462.apps.googleusercontent.com")
    .requestEmail()
    .build()

// After sign-in succeeds:
val idToken = account.idToken  // send this to POST /api/auth/google
```

---

## Groups

All group endpoints require `Authorization: Bearer <token>`.

### POST `/groups`

Create a new group. The creator is automatically added as a member.

**Request Body**

| Field       | Type   | Required | Description                        |
|-------------|--------|----------|------------------------------------|
| name        | string | Yes      | Group name                         |
| description | string | No       | Optional description               |
| member_ids  | int[]  | No       | User IDs to add as initial members |

**Example**
```bash
curl -X POST "$BASE_URL/groups" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Trip to Goa", "description": "Vacation expenses", "member_ids": [2, 3]}'
```

**Response `201`**
```json
{
  "id": 1,
  "name": "Trip to Goa",
  "description": "Vacation expenses",
  "created_by": 1,
  "members": [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob",   "email": "bob@example.com"}
  ]
}
```

---

### GET `/groups`

List all groups the current user is a member of.

**Example**
```bash
curl "$BASE_URL/groups" \
  -H "Authorization: Bearer $TOKEN"
```

**Response `200`**
```json
[
  {"id": 1, "name": "Trip to Goa",  "description": "Vacation expenses"},
  {"id": 2, "name": "Flatmates",    "description": "Monthly bills"}
]
```

---

### GET `/groups/{group_id}`

Get full details of a specific group.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| group_id  | int  | Group ID    |

**Example**
```bash
curl "$BASE_URL/groups/1" \
  -H "Authorization: Bearer $TOKEN"
```

---

### POST `/groups/{group_id}/members`

Add members to a group. Only the group creator can do this.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| group_id  | int  | Group ID    |

**Request Body**

| Field    | Type  | Required | Description         |
|----------|-------|----------|---------------------|
| user_ids | int[] | Yes      | IDs of users to add |

**Example**
```bash
curl -X POST "$BASE_URL/groups/1/members" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": [3, 4]}'
```

---

### DELETE `/groups/{group_id}/members/{user_id}`

Remove a member from a group. Only the group creator can do this.

**Path Parameters**

| Parameter | Type | Description          |
|-----------|------|----------------------|
| group_id  | int  | Group ID             |
| user_id   | int  | ID of user to remove |

**Example**
```bash
curl -X DELETE "$BASE_URL/groups/1/members/2" \
  -H "Authorization: Bearer $TOKEN"
```

**Response `204 No Content`**

---

## Expenses

All expense endpoints require `Authorization: Bearer <token>`.

### POST `/groups/{group_id}/expenses`

Create an expense within a group. Supports three split types:

| Split Type    | Behaviour |
|---------------|-----------|
| `equal`       | Amount divided equally among all group members |
| `exact`       | You specify the exact amount each person owes |
| `percentage`  | You specify each person's share as a percentage (must total 100) |

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| group_id  | int  | Group ID    |

**Request Body**

| Field       | Type        | Required | Description                                 |
|-------------|-------------|----------|---------------------------------------------|
| description | string      | Yes      | What the expense is for                     |
| amount      | float       | Yes      | Total expense amount                        |
| paid_by     | int         | Yes      | User ID of who paid                         |
| split_type  | string      | Yes      | `"equal"`, `"exact"`, or `"percentage"`     |
| splits      | SplitItem[] | No       | Required for `exact` and `percentage` types |

**SplitItem fields**

| Field      | Type  | Used When               |
|------------|-------|-------------------------|
| user_id    | int   | Always                  |
| amount     | float | `split_type = exact`    |
| percentage | float | `split_type = percentage` |

**Example — Equal Split**
```bash
curl -X POST "$BASE_URL/groups/1/expenses" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Hotel booking",
    "amount": 3000.00,
    "paid_by": 1,
    "split_type": "equal"
  }'
```

**Example — Exact Split**
```bash
curl -X POST "$BASE_URL/groups/1/expenses" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Dinner",
    "amount": 1000.00,
    "paid_by": 1,
    "split_type": "exact",
    "splits": [
      {"user_id": 1, "amount": 600},
      {"user_id": 2, "amount": 400}
    ]
  }'
```

**Example — Percentage Split**
```bash
curl -X POST "$BASE_URL/groups/1/expenses" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Cab ride",
    "amount": 500.00,
    "paid_by": 1,
    "split_type": "percentage",
    "splits": [
      {"user_id": 1, "percentage": 60},
      {"user_id": 2, "percentage": 40}
    ]
  }'
```

**Response `201`**
```json
{
  "id": 1,
  "description": "Hotel booking",
  "amount": 3000.00,
  "paid_by": 1,
  "split_type": "equal",
  "group_id": 1,
  "splits": [
    {"user_id": 1, "amount": 1500.0},
    {"user_id": 2, "amount": 1500.0}
  ],
  "created_at": "2026-06-06T10:00:00Z",
  "updated_at": "2026-06-06T10:00:00Z"
}
```

---

### GET `/groups/{group_id}/expenses`

List all expenses in a group.

**Example**
```bash
curl "$BASE_URL/groups/1/expenses" \
  -H "Authorization: Bearer $TOKEN"
```

---

### GET `/groups/{group_id}/expenses/{expense_id}`

Get a specific expense.

**Path Parameters**

| Parameter  | Type | Description |
|------------|------|-------------|
| group_id   | int  | Group ID    |
| expense_id | int  | Expense ID  |

**Example**
```bash
curl "$BASE_URL/groups/1/expenses/1" \
  -H "Authorization: Bearer $TOKEN"
```

---

### PUT `/groups/{group_id}/expenses/{expense_id}`

Update an expense. Only the group creator or the person who paid can update.

**Request Body** (all fields optional)

| Field       | Type        | Description           |
|-------------|-------------|-----------------------|
| description | string      | New description       |
| amount      | float       | New total amount      |
| paid_by     | int         | New payer user ID     |
| split_type  | string      | New split type        |
| splits      | SplitItem[] | New split details     |

**Example**
```bash
curl -X PUT "$BASE_URL/groups/1/expenses/1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": "Hotel booking (updated)", "amount": 3500.00}'
```

---

### DELETE `/groups/{group_id}/expenses/{expense_id}`

Delete an expense. Only the group creator or payer can delete.

**Example**
```bash
curl -X DELETE "$BASE_URL/groups/1/expenses/1" \
  -H "Authorization: Bearer $TOKEN"
```

**Response `204 No Content`**

---

## Balances

### GET `/groups/{group_id}/balances`

Get the net balance of every member in a group.

- **Positive balance** → user is owed money
- **Negative balance** → user owes money

**Example**
```bash
curl "$BASE_URL/groups/1/balances" \
  -H "Authorization: Bearer $TOKEN"
```

**Response `200`**
```json
[
  {"user_id": 1, "user_name": "Alice", "balance": 1500.00},
  {"user_id": 2, "user_name": "Bob",   "balance": -1500.00}
]
```

---

## Data Models

### UserResponse
```json
{
  "id": 1,
  "email": "alice@example.com",
  "name": "Alice",
  "created_at": "2026-06-06T10:00:00Z"
}
```

### GoogleUserProfile
```json
{
  "id": "1",
  "name": "Alice Smith",
  "email": "alice@gmail.com",
  "avatarUrl": "https://lh3.googleusercontent.com/a/..."
}
```

### GoogleAuthResponse
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": { /* GoogleUserProfile */ }
}
```

### GroupResponse
```json
{
  "id": 1,
  "name": "Trip to Goa",
  "description": "Vacation expenses",
  "created_by": 1,
  "members": [ /* UserResponse[] */ ]
}
```

### ExpenseResponse
```json
{
  "id": 1,
  "description": "Hotel booking",
  "amount": 3000.00,
  "paid_by": 1,
  "split_type": "equal",
  "group_id": 1,
  "splits": [
    {"user_id": 1, "amount": 1500.0},
    {"user_id": 2, "amount": 1500.0}
  ],
  "created_at": "2026-06-06T10:00:00Z",
  "updated_at": "2026-06-06T10:00:00Z"
}
```

### BalanceResponse
```json
{ "user_id": 1, "user_name": "Alice", "balance": 1500.00 }
```

---

## Error Responses

| Status | Meaning                                   |
|--------|-------------------------------------------|
| `400`  | Bad request — invalid or missing input    |
| `401`  | Unauthorized — missing, invalid, or expired token |
| `403`  | Forbidden — not allowed to perform action |
| `404`  | Not found — resource does not exist       |
| `422`  | Validation error — check request body     |

**Standard error body:**
```json
{ "detail": "Error message describing what went wrong" }
```

**Google auth error body:**
```json
{ "error": "Unauthorized", "message": "Invalid google credential. Backend verification failed." }
```

---

## Full Curl Examples

### Email/Password Flow
```bash
BASE_URL="https://<your-replit-domain>"

# 1. Create two users
curl -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "name": "Alice", "password": "secret123"}'

curl -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "bob@example.com", "name": "Bob", "password": "secret123"}'

# 2. Login as Alice and extract token
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=secret123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. Create a group with Bob
curl -X POST "$BASE_URL/groups" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Trip to Goa", "member_ids": [2]}'

# 4. Add an equal-split expense
curl -X POST "$BASE_URL/groups/1/expenses" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description": "Hotel", "amount": 3000, "paid_by": 1, "split_type": "equal"}'

# 5. Check balances
curl "$BASE_URL/groups/1/balances" \
  -H "Authorization: Bearer $TOKEN"
```

### Google Sign-In Flow
```bash
BASE_URL="https://<your-replit-domain>"

# 1. Exchange Google ID token for a backend JWT
RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/google" \
  -H "Content-Type: application/json" \
  -d '{"idToken": "<id-token-from-google-sdk>"}')

TOKEN=$(echo $RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. Use the token exactly like email/password token
curl "$BASE_URL/groups" \
  -H "Authorization: Bearer $TOKEN"
```
