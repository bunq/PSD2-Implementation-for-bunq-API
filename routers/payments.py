import json
import time
import uuid
from datetime import datetime, timedelta
import requests
from fastapi import APIRouter, Body
from dependencies import extract_session_info, BASE_URL, bunq_client
from signing import sign_data

router = APIRouter()


def build_headers(session_token: str, signature: str = None) -> dict:
    """
    Standard bunq request headers. X-Bunq-Client-Request-Id lets a call be
    correlated with bunq's own logs (next to the X-Bunq-Client-Response-Id bunq
    returns), which makes replicating/debugging a specific call much easier.
    """
    headers = {
        "User-Agent": "text",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "X-Bunq-Language": "en_US",
        "X-Bunq-Region": "nl_NL",
        "X-Bunq-Geolocation": "0 0 0 0 000",
        "X-Bunq-Client-Authentication": session_token,
        "X-Bunq-Client-Request-Id": str(uuid.uuid4()),
    }
    if signature:
        headers["X-Bunq-Client-Signature"] = signature
    return headers


@router.get("/user/{user_id}/payments/{monetary_account_id}", tags=["Payments"])
def get_payments(user_id: int, monetary_account_id: int):
    session_token, end_user_id, user_api_key_id = extract_session_info(user_id)

    url = f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/payment"

    all_payments = []
    page = 0
    while url:
        print(f"Fetching page {page}")
        page = page + 1
        time.sleep(1)
        response = requests.get(url, headers=build_headers(session_token))
        response.raise_for_status()
        data = response.json()

        payments = data.get("Response", [])
        all_payments.extend(payments)

        pagination = data.get("Pagination", {})
        older_url = pagination.get("older_url")

        # bunq returns relative URLs
        url = f"{BASE_URL}{older_url}" if older_url else None

    return {
        "count": len(all_payments),
        "payments": all_payments,
    }


@router.get("/user/{user_id}/monetary-account/{monetary_account_id}/draft-payment/{payment_id}/", tags=["Payments"])
def get_draft_payment(user_id: int, monetary_account_id: int, payment_id: int):
    session_token, end_user_id, user_api_key_id = extract_session_info(user_id)
    response = requests.get(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/draft-payment/{payment_id}",
        headers=build_headers(session_token),
    )
    return response.json()


@router.get("/user/{user_id}/monetary-account/{monetary_account_id}/payment/{payment_id}/", tags=["Payments"])
def get_payment(user_id: int, monetary_account_id: int, payment_id: int):
    session_token, end_user_id, user_api_key_id = extract_session_info(user_id)
    response = requests.get(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/payment/{payment_id}",
        headers=build_headers(session_token),
    )
    return response.json()


@router.post(
    "/user/{user_id}/draft-payment",
    tags=["Payments"],
    summary="Create a draft payment",
)
def create_draft_payment(
    user_id: int,
    body: dict = Body(
        ...,
        openapi_examples={"default": {"value": {
            "monetary_account_id": "2083712",
            "status": "PENDING",
            "amount": "10.00",
            "currency": "EUR",
            "description": "Dinner split",
            "receiver_type": "EMAIL",
            "receiver_value": "sugardaddy@bunq.com",
            "receiver_name": "Best Friend",
            "previous_updated_timestamp": "2024-05-01 12:00:00.000",
            "number_of_required_accepts": 1
        }}}
    )
):
    session_token, _, user_api_key_id = extract_session_info(user_id)
    now = datetime.utcnow() + timedelta(hours=1)
    payload = {
        "status": body.get("status", "PENDING"),
        "number_of_required_accepts": body.get("number_of_required_accepts", 1),
        "entries": [
            {
                "amount": {
                    "value": body.get("amount", "0.00"),
                    "currency": body.get("currency", "EUR")
                },
                "counterparty_alias": {
                    "type": body.get("receiver_type", "EMAIL"),
                    "value": body.get("receiver_value", ""),
                    "name": body.get("receiver_name", "")
                },
                "description": body.get("description", ""),
                "attachment": [{"id": id_} for id_ in body.get("attachment_ids", [])] if "attachment_ids" in body else []
            }
        ],
        "previous_updated_timestamp": body.get("previous_updated_timestamp"),
        "schedule": {
            "time_start": now.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            "time_end": (now + timedelta(minutes=5)).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            "recurrence_unit": "DAILY",
            "recurrence_size": 1
        }
    }

    response = requests.post(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{body.get('monetary_account_id')}/draft-payment",
        headers=build_headers(session_token),
        data=json.dumps(payload)
    )
    return response.json()


@router.put(
    "/user/{user_id}/monetary-account/{monetary_account_id}/draft-payment/{payment_id}/",
    tags=["Payments"],
    summary="Update draft payment status to ACCEPTED",
)
def update_draft_payment(user_id: int, monetary_account_id: int, payment_id: int):
    session_token, end_user_id, user_api_key_id = extract_session_info(user_id)

    payload = json.dumps({"status": "ACCEPTED"})
    signature = sign_data(payload, bunq_client.private_key_pem)

    response = requests.put(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/draft-payment/{payment_id}",
        headers=build_headers(session_token, signature),
        data=payload
    )
    return response.json()


@router.post(
    "/user/{user_id}/payment",
    tags=["Payments"],
    summary="Create an immediate payment",
)
def create_payment(
    user_id: int,
    body: dict = Body(
        ...,
        openapi_examples={"default": {"value": {
            "monetary_account_id": "2083712",
            "amount": "10.00",
            "currency": "EUR",
            "description": "Dinner split",
            "receiver_type": "EMAIL",
            "receiver_value": "sugardaddy@bunq.com",
            "receiver_name": "Best Friend",
        }}}
    )
):
    session_token, _, user_api_key_id = extract_session_info(user_id)

    payload = json.dumps({
        "amount": {
            "value": body.get("amount", "0.00"),
            "currency": body.get("currency", "EUR")
        },
        "counterparty_alias": {
            "type": body.get("receiver_type", "EMAIL"),
            "value": body.get("receiver_value", ""),
            "name": body.get("receiver_name", "")
        },
        "description": body.get("description", "")
    })
    signature = sign_data(payload, bunq_client.private_key_pem)

    response = requests.post(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{body.get('monetary_account_id')}/payment",
        headers=build_headers(session_token, signature),
        data=payload
    )
    return response.json()


@router.post(
    "/user/{user_id}/draft-payment-batch",
    tags=["Payments"],
    summary="Create a draft payment batch",
)
def create_draft_payment_batch(
    user_id: int,
    body: list[dict] = Body(
        ...,
        openapi_examples={"default": {"value": [
            {
                "monetary_account_id": "2083712",
                "status": "PENDING",
                "amount": "10.00",
                "currency": "EUR",
                "description": "Payment 1",
                "receiver_type": "EMAIL",
                "receiver_value": "sugardaddy@bunq.com",
                "receiver_name": "Best Friend",
                "previous_updated_timestamp": "2024-05-01 12:00:00.000",
                "number_of_required_accepts": 1
            },
            {
                "monetary_account_id": "2083712",
                "status": "PENDING",
                "amount": "15.50",
                "currency": "EUR",
                "description": "Payment 2",
                "receiver_type": "EMAIL",
                "receiver_value": "sugardaddy@bunq.com",
                "receiver_name": "Alice",
                "previous_updated_timestamp": "2024-05-01 12:00:00.000",
                "number_of_required_accepts": 1
            },
            {
                "monetary_account_id": "2083712",
                "status": "PENDING",
                "amount": "15.50",
                "currency": "EUR",
                "description": "Payment 3",
                "receiver_type": "IBAN",
                "receiver_value": "NL14RABO0169202917",
                "receiver_name": "Peter",
                "previous_updated_timestamp": "2024-05-01 12:00:00.000",
                "number_of_required_accepts": 1
            }
        ]}}
    )
):
    session_token, _, user_api_key_id = extract_session_info(user_id)
    responses = []
    now = datetime.utcnow() + timedelta(hours=1)

    for item in body:
        payload = {
            "status": item.get("status", "PENDING"),
            "number_of_required_accepts": item.get("number_of_required_accepts", 1),
            "entries": [
                {
                    "amount": {
                        "value": item.get("amount", "0.00"),
                        "currency": item.get("currency", "EUR")
                    },
                    "counterparty_alias": {
                        "type": item.get("receiver_type", "EMAIL"),
                        "value": item.get("receiver_value", ""),
                        "name": item.get("receiver_name", "")
                    },
                    "description": item.get("description", ""),
                    "attachment": [{"id": id_} for id_ in item.get("attachment_ids", [])] if "attachment_ids" in item else []
                }
            ],
            "previous_updated_timestamp": item.get("previous_updated_timestamp"),
            "schedule": {
                "time_start": now.strftime("%Y-%m-%d %H:%M:%S.000"),
                "time_end": (now + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S.000"),
                "recurrence_unit": "DAILY",
                "recurrence_size": 1
            }
        }

        response = requests.post(
            f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{item.get('monetary_account_id')}/draft-payment",
            headers=build_headers(session_token),
            data=json.dumps(payload)
        )
        responses.append(response.json())

    return responses


@router.get(
    "/user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment",
    tags=["Payments"],
    summary="List all scheduled payments (standing orders) for an account",
)
def get_schedule_payments(user_id: int, monetary_account_id: int):
    session_token, end_user_id, user_api_key_id = extract_session_info(user_id)

    url = f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/schedule-payment"

    all_schedule_payments = []
    while url:
        response = requests.get(url, headers=build_headers(session_token))
        response.raise_for_status()
        data = response.json()

        all_schedule_payments.extend(data.get("Response", []))

        older_url = data.get("Pagination", {}).get("older_url")
        url = f"{BASE_URL}{older_url}" if older_url else None

    return {
        "count": len(all_schedule_payments),
        "schedule_payments": all_schedule_payments,
    }


@router.get(
    "/user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id}",
    tags=["Payments"],
    summary="Get a single scheduled payment",
)
def get_schedule_payment(user_id: int, monetary_account_id: int, schedule_payment_id: int):
    session_token, end_user_id, user_api_key_id = extract_session_info(user_id)
    response = requests.get(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id}",
        headers=build_headers(session_token),
    )
    return response.json()


def _build_schedule_payment_payload(body: dict, include_purpose: bool) -> dict:
    now = datetime.utcnow() + timedelta(minutes=5)

    payload = {
        "payment": {
            "amount": {
                "value": body.get("amount", "0.00"),
                "currency": body.get("currency", "EUR")
            },
            "counterparty_alias": {
                "type": body.get("receiver_type", "EMAIL"),
                "value": body.get("receiver_value", ""),
                "name": body.get("receiver_name", "")
            },
            "description": body.get("description", ""),
        },
        "schedule": {
            "time_start": body.get("time_start") or now.strftime("%Y-%m-%d %H:%M:%S"),
            "recurrence_unit": body.get("recurrence_unit", "MONTHLY"),
            "recurrence_size": body.get("recurrence_size", 1),
        },
    }

    if "time_end" in body:
        payload["schedule"]["time_end"] = body["time_end"]
    if "attachment_ids" in body:
        payload["payment"]["attachment"] = [{"id": id_} for id_ in body["attachment_ids"]]
    if "merchant_reference" in body:
        payload["payment"]["merchant_reference"] = body["merchant_reference"]
    if "allow_bunqto" in body:
        payload["payment"]["allow_bunqto"] = body["allow_bunqto"]
    if "iban_verification_result_id" in body:
        payload["payment"]["iban_verification_result_id"] = body["iban_verification_result_id"]
    # purpose can only be set on creation, not on update
    if include_purpose and "purpose" in body:
        payload["purpose"] = body["purpose"]

    return payload


@router.post(
    "/user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment",
    tags=["Payments"],
    summary="Create a scheduled payment (standing order) — full account owner access only, not available over PSD2 OAuth",
)
def create_schedule_payment(
    user_id: int,
    monetary_account_id: int,
    body: dict = Body(
        ...,
        openapi_examples={"default": {"value": {
            "amount": "10.00",
            "currency": "EUR",
            "description": "Rent",
            "receiver_type": "IBAN",
            "receiver_value": "NL14RABO0169202917",
            "receiver_name": "Landlord",
            "time_start": "2026-11-01 09:00:00",
            "recurrence_unit": "MONTHLY",
            "recurrence_size": 1,
            "purpose": "PAYMENT",
        }}}
    )
):
    """
    Requires full "make payments" rights on the account. A PSD2 end-user OAuth
    session never has that — not even with a PISP certificate, which only grants
    draft-payment rights — so bunq's access check rejects the call before it
    reaches the account, and this returns a 404 "item not found" rather than a
    permission error. For a recurring payment initiated by a PSD2 TPP, use
    POST /draft-payment with a "schedule" block instead: the end-user approves
    once in the app, and that approval is what creates the real ScheduledPayment
    (the thing this endpoint tries to create directly).
    """
    session_token, _, user_api_key_id = extract_session_info(user_id)

    payload = json.dumps(_build_schedule_payment_payload(body, include_purpose=True))
    signature = sign_data(payload, bunq_client.private_key_pem)

    response = requests.post(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/schedule-payment",
        headers=build_headers(session_token, signature),
        data=payload
    )
    return response.json()


@router.put(
    "/user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id}",
    tags=["Payments"],
    summary="Update a scheduled payment — full account owner access only, not available over PSD2 OAuth",
)
def update_schedule_payment(
    user_id: int,
    monetary_account_id: int,
    schedule_payment_id: int,
    body: dict = Body(
        ...,
        openapi_examples={"default": {"value": {
            "amount": "15.00",
            "currency": "EUR",
            "description": "Rent",
            "receiver_type": "IBAN",
            "receiver_value": "NL14RABO0169202917",
            "receiver_name": "Landlord",
            "time_start": "2026-12-01 09:00:00",
            "recurrence_unit": "MONTHLY",
            "recurrence_size": 1,
        }}}
    )
):
    session_token, _, user_api_key_id = extract_session_info(user_id)

    payload = json.dumps(_build_schedule_payment_payload(body, include_purpose=False))
    signature = sign_data(payload, bunq_client.private_key_pem)

    response = requests.put(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id}",
        headers=build_headers(session_token, signature),
        data=payload
    )
    return response.json()


@router.delete(
    "/user/{user_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id}",
    tags=["Payments"],
    summary="Cancel a scheduled payment — full account owner access only, not available over PSD2 OAuth",
)
def delete_schedule_payment(user_id: int, monetary_account_id: int, schedule_payment_id: int):
    session_token, end_user_id, user_api_key_id = extract_session_info(user_id)
    response = requests.delete(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/schedule-payment/{schedule_payment_id}",
        headers=build_headers(session_token),
    )
    return response.json()


@router.get(
    "/user/{user_id}/monetary-account/{monetary_account_id}/schedule/{schedule_id}/schedule-instance",
    tags=["Payments"],
    summary="List the individual runs (instances) of a scheduled payment",
)
def get_schedule_instances(user_id: int, monetary_account_id: int, schedule_id: int):
    session_token, end_user_id, user_api_key_id = extract_session_info(user_id)
    response = requests.get(
        f"{BASE_URL}/v1/user/{user_api_key_id}/monetary-account/{monetary_account_id}/schedule/{schedule_id}/schedule-instance",
        headers=build_headers(session_token),
    )
    return response.json()
