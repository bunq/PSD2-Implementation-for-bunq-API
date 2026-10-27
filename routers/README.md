# Routers

This directory contains the FastAPI routers that make up the bunq PSD2 API wrapper. Each file groups a set of related endpoints and is registered in `main.py`.

---

## oauth.py
Handles the OAuth2 authorization flow with bunq.

| Method | Endpoint    | Description                                      |
|--------|-------------|--------------------------------------------------|
| GET    | /auth       | Redirects the user to bunq's OAuth authorization page |
| GET    | /callback   | Receives the auth code from bunq, exchanges it for an access token, and saves it to the database |

---

## accounts.py
User profile and monetary account management.

| Method | Endpoint                                                                 | Description                                                                 |
|--------|--------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| GET    | /user/{user_id}/                                                         | Get the bunq user profile                                                   |
| GET    | /user/{user_id}/accounts                                                 | List all monetary accounts for a user                                       |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}                  | Get a single monetary account                                               |
| POST   | /user/{user_id}/monetary-account-bank                                    | Create a new monetary account (requires `currency` and `description`)       |
| PUT    | /user/{user_id}/monetary-account-bank/{monetary_account_id}             | Update account settings; set `status: "CANCELLED"` to deactivate the account |

---

## payments.py
Everything related to payments and payment requests.

| Method | Endpoint                                                                            | Description                                              |
|--------|-------------------------------------------------------------------------------------|----------------------------------------------------------|
| GET    | /user/{user_id}/payments/{monetary_account_id}                                      | Fetch all payments for an account (auto-paginates)       |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/payment/{payment_id}/       | Get a single payment                                     |
| POST   | /user/{user_id}/payment                                                             | Create an immediate payment (requires signing)           |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/draft-payment/{payment_id}/ | Get a draft payment                                      |
| POST   | /user/{user_id}/draft-payment                                                       | Create a draft payment                                   |
| PUT    | /user/{user_id}/monetary-account/{monetary_account_id}/draft-payment/{payment_id}/ | Accept a draft payment (requires signing)                |
| POST   | /user/{user_id}/draft-payment-batch                                                 | Create multiple draft payments in a single call          |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment            | List scheduled payments (standing orders) for an account |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id} | Get a single scheduled payment                 |
| POST   | /user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment            | Create a scheduled payment (requires signing)             |
| PUT    | /user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id} | Update a scheduled payment (requires signing)   |
| DELETE | /user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id} | Cancel a scheduled payment                      |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/schedule/{schedule_id}/schedule-instance | List the individual runs of a scheduled payment |

> Note: `POST /payment`, `PUT /draft-payment`, `POST /schedule-payment` and `PUT /schedule-payment/{id}` include an `X-Bunq-Client-Signature` header generated from the private key.
> All requests in this file now send the full bunq header set (`X-Bunq-Client-Request-Id`, `X-Bunq-Language`, `X-Bunq-Region`, `X-Bunq-Geolocation`, `Cache-Control`) via `build_headers()`, so a request's ID can be correlated with bunq's own logs when debugging.
>
> **PSD2 caveat:** `POST`/`PUT`/`DELETE .../schedule-payment` require full "make payments" account rights, which a PSD2 end-user OAuth session never has — not even with a PISP certificate (PISP only grants draft-payment rights). Calling these as a PSD2 TPP returns `404 "The item you requested could not be found"`, which is bunq's generic response for a failed authorization check, not a sign that the account/counterparty/request body is wrong. `GET .../schedule-payment` (list and single) works fine for PSD2 TPPs since it only needs view-transactions access. To let an end-user set up a recurring payment through a PSD2 PISP flow, use `POST /draft-payment` with a `schedule` block instead (see below) — the user approves once in the app, and that approval is what creates the real `ScheduledPayment` these endpoints would otherwise create directly.

---

## requests.py
Full CRUD for request inquiries (requesting money from another user).

| Method | Endpoint                                                                                                   | Description                                               |
|--------|------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/request-inquiry                                    | List all request inquiries for a monetary account         |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/request-inquiry/{request_inquiry_id}               | Get a single request inquiry                              |
| POST   | /user/{user_id}/monetary-account/{monetary_account_id}/request-inquiry                                    | Create a request inquiry (send a payment request)         |
| PUT    | /user/{user_id}/monetary-account/{monetary_account_id}/request-inquiry/{request_inquiry_id}               | Revoke a pending request inquiry (sets `status: REVOKED`) |

---

## cards.py
Card management for a bunq user.

| Method | Endpoint                           | Description                                        |
|--------|------------------------------------|----------------------------------------------------|
| GET    | /user/{user_id}/cards              | List all cards                                     |
| GET    | /user/{user_id}/card/{card_id}     | Get details of a specific card                     |
| POST   | /user/{user_id}/credit-cards       | Order a new debit card (fetches display name first) |
| PUT    | /user/{user_id}/card/{card_id}     | Update card settings (PIN, limits, status)         |

> Note: Card creation and updates may require encryption depending on the bunq environment.

---

## bunqme.py
bunqme tab management — shareable payment links.

| Method | Endpoint                                                             | Description              |
|--------|----------------------------------------------------------------------|--------------------------|
| GET    | /user/{user_id}/monetary-account/{account_id}/bunqme-tab/           | List all bunqme tabs     |
| POST   | /user/{user_id}/monetary-account/{account_id}/bunqme-tab/           | Create a new bunqme tab  |

---

## attachments.py
File attachments and notes on payments.

| Method | Endpoint                                                                                        | Description                                      |
|--------|-------------------------------------------------------------------------------------------------|--------------------------------------------------|
| POST   | /user/{user_id}/monetary-account/{monetary_account_id}/attachment                              | Upload a file and attach it to a monetary account |
| POST   | /user/{user_id}/monetary-account/{monetary_account_id}/payment/{payment_id}/note-attachment    | Link an existing attachment to a payment         |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/payment/{payment_id}/note-attachment    | Get attachments linked to a payment              |
| POST   | /user/{user_id}/monetary-account/{monetary_account_id}/payment/{payment_id}/note-text         | Add a text note to a payment                     |
| GET    | /user/{user_id}/monetary-account/{monetary_account_id}/payment/{payment_id}/note-text         | Get text notes for a payment                     |

---

## notifications.py
Webhook notification filter management. Supports a set of default categories (PAYMENT, MUTATION, CARD_TRANSACTION, etc.) that can be overridden in the request body.

| Method | Endpoint                                              | Description                                  |
|--------|-------------------------------------------------------|----------------------------------------------|
| GET    | /user/{user_id}/notification-filter-url               | List active URL notification filters         |
| POST   | /user/{user_id}/notification-filter-url               | Set notification filters (replaces existing) |
| PUT    | /user/{user_id}/notification-filter-url               | Update notification filters                  |
| GET    | /user/{user_id}/notification-filter-failure           | List failed notification deliveries          |

---

## events.py
Event log, additional transaction info, and Mastercard action history.

| Method | Endpoint                                                              | Description                                            |
|--------|-----------------------------------------------------------------------|--------------------------------------------------------|
| GET    | /user/{user_id}/event                                                 | List all events for a user                             |
| GET    | /user/{user_id}/event/{item_id}                                       | Get a specific event by ID                             |
| GET    | /user/{user_id}/additional-transaction-information-category           | Get available transaction information categories       |
| GET    | /user/{user_id}/mastercard_action/                                    | List Mastercard actions for a monetary account         |
| GET    | /user/{user_id}/mastercard_action/{item_id}                           | Get a specific Mastercard action                       |

---

## psd2.py
PSD2-specific endpoints that operate as the PSD2 provider (using the PSD2 user session, not the end-user token).

| Method | Endpoint                                                                   | Description                                                  |
|--------|----------------------------------------------------------------------------|--------------------------------------------------------------|
| POST   | /psd2/payment-service-provider-issuer-transaction                         | Create a PSD2 issuer transaction                             |
| GET    | /psd2/payment-service-provider-issuer-transaction/{transaction_id}        | Get details of a PSD2 issuer transaction                     |
| GET    | /psd2/payment-service-provider-issuer-transaction-public/{public_id}      | Get public info of a PSD2 issuer transaction (no auth needed) |
| GET    | /psd2/redirect/{public_id}                                                 | Redirect user to the bunq PSP payment page                   |

---

## ip_whitelist.py
Manage IP whitelisting for credential-password-ip objects. Uses the PSD2 user session.

| Method | Endpoint                                                              | Description                                      |
|--------|-----------------------------------------------------------------------|--------------------------------------------------|
| GET    | /credential-password-ip                                               | List all credential-password-ip objects          |
| GET    | /credential-password-ip/{ip_id}                                       | Get a specific credential-password-ip object     |
| GET    | /credential-password-ip/{credential_password_ip_id}/ip               | List whitelisted IPs for a credential            |
| POST   | /credential-password-ip/{credential_password_ip_id}/ip               | Add an IP to the whitelist (default: `*`)        |
| GET    | /credential-password-ip/{credential_password_ip_id}/ip/{item_id}     | Get a specific whitelisted IP entry              |
| PUT    | /credential-password-ip/{credential_password_ip_id}/ip/{item_id}     | Update the status of a whitelisted IP entry      |
