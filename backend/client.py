import db_functions
from utils import *
from db_functions import cursor
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import APIRouter, Request, Depends

client = APIRouter(prefix="/client")

# /user
# /artists
# /albums
# /orders
# /cart


@client.get("/user", dependencies=[Depends(verify_token)])
@db_functions.tsql
async def get_user(request: Request):
    cursor.callproc("get_user", (request.state.sub, "cart"))
    user = cursor.fetchone()["bm_user"]
    return JSONResponse({"user": jsonable_encoder(user)}, 200)


@client.get("/artists/{artist_id}")
@db_functions.tsql
async def get_artist(artist_id, view: str):
    cursor.callproc("get_artist", (artist_id, view))
    artist = cursor.fetchone()
    return JSONResponse(artist, 200)


@client.get("/albums")
@db_functions.tsql
async def get_albums(request: Request, page: int = 1, sort: str = "name", direction: str = "ascending", query: str = None):
    albums = {}
    cursor.callproc("get_pages", ('albums', query,))
    albums["pages"] = cursor.fetchone()["pages"]
    cursor.callproc("get_albums", (page, sort, direction, query))
    albums["data"] = cursor.fetchall()
    return JSONResponse({"albums": albums["data"], "pages": albums["pages"]}, 200)


@client.get("/albums/{album_id}")
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


@client.get("/orders", dependencies=[Depends(verify_token)])
@db_functions.tsql
async def get_orders_cart(request: Request):
    cursor.callproc("get_orders_and_cart", (request.state.sub,))
    orders_cart = cursor.fetchone()
    return JSONResponse(orders_cart, 200)


@client.post("/cart/checkout", dependencies=[Depends(verify_token)])
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


@client.post("/cart/{album_id}/add", dependencies=[Depends(verify_token)])
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


@client.post("/cart/{album_id}/remove", dependencies=[Depends(verify_token)])
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
