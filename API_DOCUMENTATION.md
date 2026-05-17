# Splitwise Clone API Documentation

## Overview

A REST API for managing shared expenses among friends and groups. Supports user authentication, group management, and expense tracking with flexible split options.

**Base URL:** `https://<your-replit-domain>`  
**Interactive Docs:** `https://<your-replit-domain>/docs`  
**Auth:** JWT Bearer Token (obtain via `/auth/login`)

---

## Table of Contents

- [Authentication](#authentication)
- [Groups](#groups)
- [Expenses](#expenses)
- [Balances](#balances)
- [Data Models](#data-models)
- [Error Responses](#error-responses)
- [Full Curl Examples](#full-curl-examples)

---

## Authentication

### POST `/auth/signup`

Register a new user account.

**Request Body**

| Field    | Type   | Required | Description        |
|----------|--------|----------|--------------------|
| email    | string | Yes      | Unique email address |
| name     | string | Yes      | Display name       |
| password | string | Yes      | Plain text password |

**Example**
```bash
curl -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "name": "Alice", "password": "secret123"}'
```

**Response `201`**
```json
{
  "id": 1,
  "email": "alice@example.com",
  "name": "Alice"
}
```

---

### POST `/auth/login`

Authenticate and receive a JWT access token.

**Request Body** (form data)

| Field    | Type   | Required | Description   |
|----------|--------|----------|---------------|
| username | string | Yes      | User's email  |
| password | string | Yes      | User's password |

**Example**
```bash
curl -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=secret123"
```

**Response `200`**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

### GET `/auth/me`

Get the currently authenticated user's profile.

**Headers**

| Header        | Value                  |
|---------------|------------------------|
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
  "name": "Alice"
}
```

---

## Groups

All group endpoints require `Authorization: Bearer <token>`.

### POST `/groups`

Create a new group. The creator is automatically added as a member.

**Request Body**

| Field       | Type      | Required | Description                        |
|-------------|-----------|----------|------------------------------------|
| name        | string    | Yes      | Group name                         |
| description | string    | No       | Optional description               |
| member_ids  | int[]     | No       | User IDs to add as initial members |

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
    {"id": 2, "name": "Bob", "email": "bob@example.com"}
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
  {"id": 1, "name": "Trip to Goa", "description": "Vacation expenses"},
  {"id": 2, "name": "Flatmates", "description": "Monthly bills"}
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

| Field    | Type  | Required | Description          |
|----------|-------|----------|----------------------|
| user_ids | int[] | Yes      | IDs of users to add  |

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

| Parameter | Type | Description       |
|-----------|------|-------------------|
| group_id  | int  | Group ID          |
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

- **`equal`** — Amount divided equally among all group members
- **`exact`** — You specify the exact amount each person owes
- **`percentage`** — You specify the percentage share for each person (must total 100)

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| group_id  | int  | Group ID    |

**Request Body**

| Field       | Type       | Required | Description                                    |
|-------------|------------|----------|------------------------------------------------|
| description | string     | Yes      | What the expense is for                        |
| amount      | float      | Yes      | Total expense amount                           |
| paid_by     | int        | Yes      | User ID of who paid                            |
| split_type  | string     | Yes      | `"equal"`, `"exact"`, or `"percentage"`        |
| splits      | SplitItem[]| No       | Required for `exact` and `percentage` types    |

**SplitItem fields:**

| Field      | Type  | Used When          |
|------------|-------|--------------------|
| user_id    | int   | Always             |
| amount     | float | `split_type=exact` |
| percentage | float | `split_type=percentage` |

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
  "created_at": "2026-05-17T10:00:00Z"
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

| Field       | Type       | Description                  |
|-------------|------------|------------------------------|
| description | string     | New description              |
| amount      | float      | New total amount             |
| paid_by     | int        | New payer user ID            |
| split_type  | string     | New split type               |
| splits      | SplitItem[]| New split details            |

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

Get the net balance of every member in a group. A positive balance means the user is owed money; negative means they owe money.

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
{ "id": 1, "email": "alice@example.com", "name": "Alice" }
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
  "created_at": "2026-05-17T10:00:00Z",
  "updated_at": "2026-05-17T10:00:00Z"
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
| 400    | Bad request — invalid input data          |
| 401    | Unauthorized — missing or invalid token   |
| 403    | Forbidden — not allowed to perform action |
| 404    | Not found — resource does not exist       |
| 422    | Validation error — check request body     |

**Error body format:**
```json
{ "detail": "Error message describing what went wrong" }
```

---

## Full Curl Examples

A complete walkthrough from signup to checking balances:

```bash
BASE_URL="https://<your-replit-domain>"

# 1. Create two users
curl -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "name": "Alice", "password": "secret123"}'

curl -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "bob@example.com", "name": "Bob", "password": "secret123"}'

# 2. Login as Alice
TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice@example.com&password=secret123" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

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
