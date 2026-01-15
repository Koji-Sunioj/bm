import json
import db_functions
from utils import check_hmac
from db_functions import cursor
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

merchant = APIRouter(prefix="/merchant")


@merchant.post("/purchase-orders")
@db_functions.tsql
async def order_response(request: Request):
    payload = await request.json()
    check_hmac(json.dumps(payload), request.headers["authorization"])
    lines = [line["line"] for line in payload["lines"]]
    confirmed_qtys = [line["confirmed"] for line in payload["lines"]]

    update_command = """
    with updated as(
        update purchase_order_lines
        set confirmed_quantity = merchant.quantity
        from (select 
            unnest(%s) as line,
            unnest(%s) as quantity
        ) as merchant where merchant.line = purchase_order_lines.line
        and purchase_order=%s returning purchase_order_lines.quantity, purchase_order_lines.line,purchase_order_lines.confirmed_quantity)
    select *
    from updated
    order by updated.line asc;
    """
    cursor.execute(update_command, (lines, confirmed_qtys,
                   payload["purchase_order_id"]))
    updated_rows = cursor.fetchall()
    confirmed = []

    for updated_row in updated_rows:
        confirmed.append(updated_row["quantity"] ==
                         updated_row["confirmed_quantity"])

    status = "confirmed" if all(confirmed) else "pending-buyer"
    update_po_command = "update purchase_orders set status=%s,modified=%s where purchase_order=%s;"
    cursor.execute(
        update_po_command, (status, payload["modified"], payload["purchase_order_id"]))

    return JSONResponse({"detail": "purchase order %s updated" % payload["purchase_order_id"]}, 200)


@merchant.post("/shipment-orders")
@db_functions.tsql
async def despatch_notification(request: Request):
    payload = await request.json()
    check_hmac(json.dumps(payload), request.headers["authorization"])

    insert_command = """insert into dispatches (dispatch_id,purchase_order,status,address) values \
        (%s,%s,%s,%s)"""

    cursor.execute(insert_command, (payload["dispatch_id"],
                   payload["purchase_order"], payload["status"], payload["address"]))

    return JSONResponse({"detail": "dispatch %s for purchase order %s received" % (payload["dispatch_id"],
                                                                                   payload["purchase_order"])}, 200)


@merchant.patch("/shipment-orders/{dispatch_id}")
@db_functions.tsql
async def despatch_update(request: Request, dispatch_id):
    payload = await request.json()
    check_hmac(json.dumps(payload), request.headers["authorization"])

    if payload["status"] == "rescheduled":
        update_po_command = """update purchase_orders set estimated_receipt = %s,modified = %s where purchase_order \
            = (select purchase_order from dispatches where dispatch_id = %s);"""
        cursor.execute(
            update_po_command, (payload["estimated_delivery"], datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), dispatch_id))

    update_dispatch_command = "update dispatches set status = %s where dispatch_id = %s;"
    cursor.execute(update_dispatch_command, (payload["status"], dispatch_id))

    return JSONResponse({"detail": "dispatch %s updated with status %s" % (dispatch_id, payload["status"])})
