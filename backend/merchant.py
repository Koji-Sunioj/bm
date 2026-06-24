from utils import check_hmac
from db_functions import cursor, tsql

import json
from typing import Annotated
from fastapi import APIRouter, Header, Request
from datetime import datetime, timezone
from models import (
    DetailResponse,
    MerchantPurchaseOrder,
    MerchantDispatchNote,
    MerchantDispatchUpdate,
)

merchant = APIRouter(prefix="/merchant")


@merchant.post("/purchase-orders", response_model=DetailResponse)
@tsql
async def order_response(
    request: Request,
    purchase_order: MerchantPurchaseOrder,
    authorization: Annotated[str | None, Header()] = None,
) -> DetailResponse:
    payload = await request.json()
    check_hmac(json.dumps(payload), authorization)
    lines = [line.line for line in purchase_order.lines]
    confirmed_qtys = [line.confirmed for line in purchase_order.lines]

    cursor.callproc(
        "merchant_update_purchase_order_lines",
        (lines, confirmed_qtys, purchase_order.purchase_order_id),
    )
    updated_rows = cursor.fetchall()

    confirmed = []

    for updated_row in updated_rows:
        confirmed.append(updated_row["quantity"] == updated_row["confirmed_quantity"])

    status = "confirmed" if all(confirmed) else "pending-buyer"
    cursor.callproc(
        "merchant_update_purchase_order",
        (purchase_order.modified, status, purchase_order.purchase_order_id),
    )

    return {"detail": "purchase order %s updated" % purchase_order.purchase_order_id}


@merchant.post("/shipment-orders", response_model=DetailResponse)
@tsql
async def despatch_notification(
    request: Request,
    dispatch_note: MerchantDispatchNote,
    authorization: Annotated[str | None, Header()] = None,
) -> DetailResponse:
    payload = await request.json()
    check_hmac(json.dumps(payload), authorization)

    cursor.callproc(
        "create_dispatch",
        (
            dispatch_note.dispatch_id,
            dispatch_note.purchase_order,
            dispatch_note.status,
            dispatch_note.address,
        ),
    )

    return {
        "detail": "dispatch %s for purchase order %s received"
        % (dispatch_note.dispatch_id, dispatch_note.purchase_order)
    }


@merchant.patch("/shipment-orders/{dispatch_id}", response_model=DetailResponse)
@tsql
async def despatch_update(
    request: Request,
    dispatch_update: MerchantDispatchUpdate,
    dispatch_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> DetailResponse:
    payload = await request.json()
    check_hmac(json.dumps(payload), authorization)

    if dispatch_update.status == "rescheduled":
        cursor.callproc(
            "merchant_update_purchase_order_delivery",
            (
                dispatch_update.estimated_delivery,
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                dispatch_id,
            ),
        )

    cursor.callproc(
        "merchant_update_dispatch_status", (dispatch_update.status, dispatch_id)
    )

    return {
        "detail": "dispatch %s updated with status %s"
        % (dispatch_id, dispatch_update.status)
    }
