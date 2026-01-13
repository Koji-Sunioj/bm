import json
import db_functions
from utils import *
from jose import jwt
from db_functions import cursor
from dotenv import dotenv_values
from passlib.context import CryptContext
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Request, Depends, Response

api = APIRouter(prefix="/api")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
fe_secret = dotenv_values(".env")["FE_SECRET"]


@api.get("/artists/{artist_id}")
@db_functions.tsql
async def get_artist(artist_id, view: str):
    cursor.callproc("get_artist", (artist_id, view))
    artist = cursor.fetchone()
    return JSONResponse(artist, 200)


@api.get("/albums/{album_id}")
@db_functions.tsql
async def get_album(album_id, request: Request, cart: str = None, previews: str = None):
    cursor.callproc("get_album", (album_id,))
    album = cursor.fetchone()
    parsed_album = parse_samples(album) if previews == "true" else album

    try:
        if "cookie" in request.headers and cart == "get":
            jwt_payload = await decode_token(request)
            cursor.callproc("get_cart_count", (jwt_payload["sub"],
                            parsed_album["album"]["album_id"]))
            cart = cursor.fetchone()
            parsed_album.update(cart)
    except:
        pass

    return JSONResponse(parsed_album, 200)


@api.get("/albums")
@db_functions.tsql
async def get_albums(request: Request, page: int = 1, sort: str = "name", direction: str = "ascending", query: str = None):
    albums = {}
    cursor.callproc("get_pages", ('albums', query,))
    albums["pages"] = cursor.fetchone()["pages"]
    cursor.callproc("get_albums", (page, sort, direction, query))
    albums["data"] = cursor.fetchall()
    return JSONResponse({"albums": albums["data"], "pages": albums["pages"]}, 200)


@api.post("/sign-in")
@db_functions.tsql
async def sign_in(request: Request):
    content = await request.json()
    cursor.callproc("get_user", (content["username"], "password"))

    try:
        user = cursor.fetchone()["bm_user"]
        pwd_context.verify(content["password"], user["password"])
    except:
        return JSONResponse({"detail": "cannot sign in"}, 401)

    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=180)
    jwt_payload = {"sub": user["username"], "iat": now,
                   "exp": expires, "created": str(user["created"])}
    if user["role"] == "admin":
        jwt_payload["role"] = encode_role(user["role"])
    token = jwt.encode(jwt_payload, fe_secret)

    token_string = "token=%s; Path=/; SameSite=Lax" % token
    headers = {"Set-Cookie": token_string}

    return JSONResponse(content={"detail": "you're signed in"}, headers=headers, status_code=200)


@api.get("/orders", dependencies=[Depends(verify_token)])
@db_functions.tsql
async def get_orders_cart(request: Request):
    cursor.callproc("get_orders_and_cart", (request.state.sub,))
    orders_cart = cursor.fetchone()
    return JSONResponse(orders_cart, 200)


@api.post("/cart/checkout", dependencies=[Depends(verify_token)])
@db_functions.tsql
async def checkout_cart_items(request: Request):
    cursor.callproc("get_user", (request.state.sub, "checkout"))
    data = cursor.fetchone()["bm_user"]
    user_id, albums = data["user_id"], data["albums"]

    cursor.callproc("create_order", (user_id,))
    order_id = cursor.fetchone()["order_id"]
    album_ids = [album["album_id"] for album in albums]
    quantities = [album["quantity"] for album in albums]

    cursor.callproc("create_dispatch_items", (order_id, album_ids, quantities))
    cursor.callproc("remove_cart_items", (user_id,))

    response = "order %s has been successfully dispatched" % order_id if cursor.rowcount != 0 else "no order to checkout"
    return JSONResponse({"detail": response}, 200)


@api.post("/cart/{album_id}/add", dependencies=[Depends(verify_token)])
@db_functions.tsql
async def add_cart_item(request: Request, album_id):
    cursor.callproc("get_user", (request["state"]["sub"], "owner"))
    user_id = cursor.fetchone()["bm_user"]["user_id"]

    cursor.callproc("check_cart_item", (user_id, album_id))
    in_cart = cursor.fetchone()["in_cart"]

    if in_cart == 0:
        cursor.callproc("add_cart_item", (user_id, album_id))
    elif in_cart > 0:
        cursor.callproc("update_cart_quantity", (user_id, album_id, 1))

    cursor.callproc("update_stock_quantity", (user_id, album_id, -1))
    stock_cart = cursor.fetchone()
    return JSONResponse(stock_cart, 200)


@api.post("/cart/{album_id}/remove", dependencies=[Depends(verify_token)])
@db_functions.tsql
async def del_cart_item(request: Request, album_id):
    cursor.callproc("get_user", (request["state"]["sub"], "owner"))
    user_id = cursor.fetchone()["bm_user"]["user_id"]

    cursor.callproc("update_cart_quantity", (user_id, album_id, -1))
    cursor.callproc("update_stock_quantity", (user_id, album_id, 1))
    stock_cart = cursor.fetchone()

    if stock_cart["cart"] == 0:
        cursor.callproc("remove_cart_items", (user_id, album_id))

    return JSONResponse(stock_cart, 200)


@api.get("/user", dependencies=[Depends(verify_token)])
@db_functions.tsql
async def get_user(request: Request):
    cursor.callproc("get_user", (request.state.sub, "cart"))
    user = cursor.fetchone()["bm_user"]
    return JSONResponse({"user": jsonable_encoder(user)}, 200)


@api.post("/register")
@db_functions.tsql
async def register(request: Request):
    content = await request.json()
    guest_list = dotenv_values(".env")["GUEST_LIST"].split(",")
    guest_dict = {key.split(":")[0]: key.split(":")[1] for key in guest_list}
    if content["username"] not in guest_dict:
        raise AuthorizationError("client not on guest list")
    role = guest_dict[content["username"]]
    cursor.callproc(
        'create_user', (content["username"], pwd_context.hash(content["password"]), role))
    created = cursor.rowcount > 0
    code, detail = (400, "error creating user") if not created else (
        200, "user created")
    return JSONResponse({"detail": detail}, code)


@api.patch("/shipment-orders/merchant-response/{dispatch_id}")
@db_functions.tsql
async def despatch_update(request: Request, dispatch_id):
    payload = await request.json()

    if payload["status"] == "rescheduled":
        update_po_command = """update purchase_orders set estimated_receipt = %s,modified = %s where purchase_order \
            = (select purchase_order from dispatches where dispatch_id = %s);"""
        cursor.execute(
            update_po_command, (payload["estimated_delivery"], datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), dispatch_id))

    update_dispatch_command = "update dispatches set status = %s where dispatch_id = %s;"
    cursor.execute(update_dispatch_command, (payload["status"], dispatch_id))

    return JSONResponse({"detail": "dispatch %s updated with status %s" % (dispatch_id, payload["status"])})


@api.post("/shipment-orders/merchant-response")
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


@api.post("/purchase-orders/merchant-response")
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
