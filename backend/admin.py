from db_functions import cursor, tsql
from utils import (
    get_hmac,
    verify_admin_token,
    bm_format_photoname,
    dict_list_to_matrix,
    save_file,
    form_songs_to_list,
    form_po_rows_to_list,
    search,
)

import os
import json
import requests
from typing import Annotated
from dotenv import dotenv_values
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request, Depends, Form
from models import (
    DetailResponse,
    AdminAlbums,
    AdminDispatches,
    AdminDispatchCost,
    AdminPurchaseOrders,
    AdminAlbumPatchResponse,
    AdminArtistPatchResponse,
    AdminPurchaseOrderResponse,
    AdminPurchaseOrderPatchResponse,
)

admin = APIRouter(prefix="/admin", dependencies=[Depends(verify_admin_token)])


@admin.post("/artists", response_model=AdminArtistPatchResponse)
@admin.patch("/artists/{artist_id}", response_model=AdminArtistPatchResponse)
@tsql
async def create_artist(
    request: Request,
    bio: Annotated[str, Form()],
    name: Annotated[str, Form()],
    artist_id: int = None,
) -> AdminArtistPatchResponse:
    cursor.callproc("get_artist_by_name", (name,))
    existing_artist = cursor.fetchone()["artist_id"]

    new_artist_exists = request.method == "POST" and existing_artist != None
    edit_artist_exists = (
        request.method == "PATCH"
        and existing_artist != None
        and existing_artist["artist_id"] != artist_id
    )

    if any([new_artist_exists, edit_artist_exists]):
        return JSONResponse({"detail": "that artist exists"}, 409)

    detail = None

    match request.method:

        case "POST":
            cursor.callproc("create_artist", (name, bio))
            new_artist = cursor.fetchone()

            detail = "artist %s created" % new_artist["name"]
            artist_id = new_artist["artist_id"]

        case "PATCH":
            cursor.callproc("get_artist", (artist_id, "user"))
            artist = cursor.fetchone()["artist"]

            fields_to_change = {
                item[0]: item[1] if artist[item[0]] != item[1] else None
                for item in {"name": name, "bio": bio}.items()
            }

            if any(fields_to_change.values()):
                cursor.callproc(
                    "update_artist", (artist_id, *fields_to_change.values())
                )
                updated = cursor.fetchone()

                detail = "artist %s updated" % updated["name"]

            if fields_to_change["name"] != None and len(artist["albums"]) > 0:
                new_files = [
                    {
                        "album_id": album["album_id"],
                        "new_file": bm_format_photoname(
                            name, album["title"], album["photo"]
                        ),
                        "old_file": album["photo"],
                    }
                    for album in artist["albums"]
                ]

                photo_matrix = dict_list_to_matrix(new_files)[:-1]
                cursor.callproc("update_photos", (*photo_matrix,))

                for file in new_files:
                    new_file = "/var/www/bm/common/%s" % file["new_file"]
                    old_file = "/var/www/bm/common/%s" % file["old_file"]
                    os.rename(old_file, new_file)

    return {"artist_id": artist_id, "detail": detail}


@admin.delete("/artists/{artist_id}", response_model=DetailResponse)
@tsql
async def delete_artist(artist_id: int) -> DetailResponse:
    cursor.callproc("delete_artist", (artist_id,))
    name = cursor.fetchone()["name"]
    return {"detail": "artist %s deleted" % name}


@admin.post(
    "/albums", response_model=AdminAlbumPatchResponse, response_model_exclude_none=True
)
@admin.patch(
    "/albums/{album_id}",
    response_model=AdminAlbumPatchResponse,
    response_model_exclude_none=True,
)
@tsql
async def manage_album(
    request: Request, album_id: int = None
) -> AdminAlbumPatchResponse:
    form = await request.form()

    cursor.callproc("get_artist", (form["artist_id"], "user"))
    artist = cursor.fetchone()["artist"]

    edit_album_exists = (
        request.method == "PATCH"
        and len(
            [
                album
                for album in artist["albums"]
                if album["album_id"] != album_id
                and album["title"].lower() == form["title"].lower()
            ]
        )
        > 0
    )

    new_album_exists = request.method == "POST" and form["title"].lower() in [
        row["title"].lower() for row in artist["albums"]
    ]

    if any([new_album_exists, edit_album_exists]):
        return JSONResponse({"detail": "that album exists"}, 409)

    filename = bm_format_photoname(
        artist["name"], form["title"], form["photo"].filename
    )

    detail = None

    match request.method:

        case "POST":
            content = form["photo"].file.read()
            save_file(filename, content)

            insert_album_params = (
                form["title"],
                form["release_year"],
                form["price"],
                filename,
                form["artist_id"],
            )
            cursor.callproc("insert_album", insert_album_params)
            inserted = cursor.fetchone()

            new_songs = form_songs_to_list(form, inserted["album_id"])
            inserted_matrix = dict_list_to_matrix(new_songs)
            cursor.callproc("insert_songs", (*inserted_matrix,))

            album_id = inserted["album_id"]
            detail = "album %s created" % inserted["title"]

        case "PATCH":
            cursor.callproc("get_album", (form["album_id"],))
            data = cursor.fetchone()
            album, songs = data["album"], data["album"]["songs"]
            new_songs = form_songs_to_list(form)

            existing_tracks = [existing_song["track"] for existing_song in songs]

            new_tracks = [new_song["track"] for new_song in new_songs]

            to_add_tracks = [
                track for track in new_tracks if track not in existing_tracks
            ]

            to_delete_tracks = [
                track for track in existing_tracks if track not in new_tracks
            ]

            to_update_tracks = [
                new_song
                for new_song, old_song in zip(new_songs, songs)
                if new_song["song"] != old_song["song"]
                or new_song["duration"] != old_song["duration"]
            ]

            fields_to_change = {
                field: form[field] if str(album[field]) != form[field] else None
                for field in ["title", "release_year", "price", "artist_id"]
            }
            fields_to_change["photo"] = filename if album["photo"] != filename else None

            should_del_tracks = len(to_delete_tracks) > 0
            should_update_tracks = len(to_update_tracks) > 0
            should_add_tracks = len(to_add_tracks) > 0

            should_update_photo_file = (
                filename != album["photo"]
                or form["photo"].size
                != os.stat("/var/www/bm/common/%s" % album["photo"]).st_size
            )
            should_rename_photo = (
                any([fields_to_change["artist_id"], fields_to_change["title"]])
                and not should_update_photo_file
            )

            should_update_album = any(fields_to_change.values())

            if should_del_tracks:
                cursor.callproc("delete_songs", (album_id, to_delete_tracks))

            if should_update_tracks:
                updated_matrix = dict_list_to_matrix(to_update_tracks)
                cursor.callproc("update_songs", (*updated_matrix,))

            if should_add_tracks:
                filtered = [
                    track for track in new_songs if track["track"] in to_add_tracks
                ]
                inserted_matrix = dict_list_to_matrix(filtered)
                cursor.callproc("insert_songs", (*inserted_matrix,))

            if should_update_photo_file:
                content = form["photo"].file.read()
                os.remove("/var/www/bm/common/%s" % album["photo"])
                save_file(filename, content)

            if should_rename_photo:
                new_file = "/var/www/bm/common/%s" % filename
                old_file = "/var/www/bm/common/%s" % album["photo"]
                os.rename(old_file, new_file)

            if should_update_album:
                cursor.callproc("update_album", (album_id, *fields_to_change.values()))

            if any(
                [
                    should_del_tracks,
                    should_update_tracks,
                    should_add_tracks,
                    should_rename_photo,
                    should_update_photo_file,
                    should_update_album,
                ]
            ):
                cursor.callproc("update_modified", (album_id,))
                updated_album = cursor.fetchone()

                detail = "album %s updated" % updated_album["title"]

            else:
                detail = "there was nothing to update"

    return {"album_id": album_id, "detail": detail}


@admin.delete("/albums/{album_id}", response_model=DetailResponse)
@tsql
async def delete_album(album_id: int) -> DetailResponse:
    cursor.callproc("get_album", (album_id,))
    album = cursor.fetchone()["album"]

    cursor.callproc("delete_album", (album_id,))

    if cursor.rowcount > 0:
        os.remove("/var/www/bm/common/%s" % album["photo"])
        detail = "album %s was deleted" % album["title"]
    else:
        detail = "there was nothing to delete"

    return {"detail": detail}


@admin.get("/artists", response_model=AdminAlbums, response_model_exclude_none=True)
@tsql
async def admin_get_artists(
    page: int = None, sort: str = None, direction: str = None, query: str = None
) -> AdminAlbums:
    artists, pages = None, None

    if all([page, sort, direction]):
        cursor.callproc("get_artists", (page, sort, direction, query))
        artists = cursor.fetchone()["artists"]

        cursor.callproc(
            "get_pages",
            (
                "artists",
                query,
            ),
        )
        pages = cursor.fetchone()["pages"]

    else:
        cursor.callproc("get_artists")
        artists = cursor.fetchone()["artists"]

    return {"artists": artists, "pages": pages}


@admin.get("/dispatches", response_model=AdminDispatches)
@tsql
async def get_dispatches() -> AdminDispatches:
    cursor.callproc("get_dispatches")
    dispatches = cursor.fetchall()
    return {"dispatches": dispatches}


@admin.patch("/dispatches/{dispatch_id}", response_model=DetailResponse)
@tsql
async def send_dispatch_update(request: Request, dispatch_id: str) -> DetailResponse:
    cursor.callproc("get_dispatch_status", (dispatch_id,))
    status = cursor.fetchone()["status"]

    if status != "shipped":
        raise Exception("this dispatch must be in 'shipped' status to confirm receipt")

    data = await request.json()
    payload = json.dumps(
        {
            "client_id": (
                "bm-prod" if os.path.exists("/var/lib/cloud/instance") else "bm-dev"
            ),
            "status": data["status"],
        }
    )

    detail = None
    lambda_response = requests.patch(
        dotenv_values(".env")["LAMBDA_SERVER"] + "/client/dispatches/%s" % dispatch_id,
        data=payload,
        headers={"Authorization": get_hmac(payload)},
    )

    if lambda_response.headers.get("content-type") == "application/json":
        detail = lambda_response.json()["message"]
    else:
        detail = "there was an error parsing a response."

    if lambda_response.status_code != 200:
        raise Exception(detail)

    cursor.callproc("update_stock", (dispatch_id,))

    cursor.callproc("update_dispatch_status", (dispatch_id, data["status"]))

    return {"detail": detail}


@admin.get(
    "/purchase-orders",
    response_model=AdminPurchaseOrders,
    response_model_exclude_none=True,
)
@tsql
async def get_purchase_orders() -> AdminPurchaseOrders:
    cursor.callproc("get_purchase_orders")
    purchase_orders = cursor.fetchall()
    return {"purchase_orders": purchase_orders}


@admin.get(
    "/purchase-orders/{purchase_order_id}", response_model=AdminPurchaseOrderResponse
)
@tsql
async def get_purchase_order(purchase_order_id: int) -> AdminPurchaseOrderResponse:
    cursor.callproc("get_purchase_order", (purchase_order_id,))
    purchase_order = cursor.fetchone()
    return {"purchase_order": purchase_order}


@admin.post("/purchase-orders", response_model=AdminPurchaseOrderPatchResponse)
@admin.patch(
    "/purchase-orders/{purchase_order}", response_model=AdminPurchaseOrderPatchResponse
)
@tsql
async def send_purchase_order(
    request: Request, purchase_order=None
) -> AdminPurchaseOrderPatchResponse:
    form = await request.form()
    po_rows = form_po_rows_to_list(form)

    inserted = None

    match request.method:
        case "POST":
            cursor.callproc("get_pending_orders_count")
            others_orders = cursor.fetchone()["count"]

            if others_orders > 0:
                return JSONResponse(
                    {"detail": "no more than one pending purchase order can exist"}
                )

            cursor.callproc(
                "create_purchase_order",
                (form["dispatch_cost"], form["estimated_delivery"]),
            )
            inserted = cursor.fetchone()

            po_rows_filtered = [row.copy() for row in po_rows]

            for row in po_rows_filtered:
                del row["artist"]
                del row["album"]
                del row["artist_id"]
                row["confirmed_quantity"] = None

            po_lines_matrix = dict_list_to_matrix(po_rows_filtered)

            cursor.callproc(
                "create_purchase_order_lines",
                (*po_lines_matrix, inserted["purchase_order"]),
            )

        case "PATCH":
            keys = ["line", "album_id", "quantity", "line_total"]
            db_rows = [
                dict(filter(lambda item: item[0] in keys, line.items()))
                for line in po_rows
            ]

            cursor.callproc("get_purchase_order", (purchase_order,))
            existing_po = cursor.fetchone()

            if existing_po["status"] == "confirmed":
                return JSONResponse(
                    {"detail": "this purchase order is already completed"}
                )

            elif existing_po["status"] == "pending-supplier":
                return JSONResponse(
                    {
                        "detail": "this purchase order is waiting on the supplier to confirm line items"
                    }
                )

            existing_lines = []

            for line in existing_po["lines"]:
                existing_line = {
                    key: line[key]
                    for key in ["line", "album_id", "quantity", "line_total"]
                }
                existing_line["confirmed_quantity"] = line["confirmed"]
                existing_lines.append(existing_line)

            for n, new_line in enumerate(db_rows):
                confirmed_quantity = search(
                    existing_lines,
                    "album_id",
                    new_line["album_id"],
                    "confirmed_quantity",
                )
                new_line["confirmed_quantity"] = confirmed_quantity
                db_rows[n] = new_line

            to_update_lines = []

            for new_line, old_line in zip(db_rows, existing_lines):
                old_values = list(old_line.values())[:-1]
                new_values = list(new_line.values())[:-1]
                if new_values != old_values:
                    to_update_lines.append(new_line)

            old_lines = [old_line["line"] for old_line in existing_lines]
            to_add_lines = [
                new_line for new_line in db_rows if new_line["line"] not in old_lines
            ]

            new_lines = [new_line["line"] for new_line in db_rows]
            to_delete_lines = [
                old_line["line"]
                for old_line in existing_lines
                if old_line["line"] not in new_lines
            ]

            action = {
                "update": len(to_update_lines) > 0,
                "add": len(to_add_lines) > 0,
                "delete": len(to_delete_lines) > 0,
            }

            if action["update"]:
                update_lines = dict_list_to_matrix(to_update_lines)
                cursor.callproc(
                    "update_purchase_order_lines", (*update_lines, purchase_order)
                )

            if action["add"]:
                insert_lines = dict_list_to_matrix(to_add_lines)
                cursor.callproc(
                    "create_purchase_order_lines", (*insert_lines, purchase_order)
                )

            elif action["delete"]:
                cursor.callproc(
                    "delete_purchase_order_lines", (to_delete_lines, purchase_order)
                )

            if any(action.values()):
                new_modified = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                cursor.callproc(
                    "update_purchase_order",
                    (
                        new_modified,
                        "pending-supplier",
                        form["dispatch_cost"],
                        form["estimated_delivery"],
                        purchase_order,
                    ),
                )
                inserted = cursor.fetchone()
            else:
                return JSONResponse({"detail": "no changes made"})

    payload = json.dumps(
        {
            "client_id": (
                "bm-prod" if os.path.exists("/var/lib/cloud/instance") else "bm-dev"
            ),
            "purchase_order_id": inserted["purchase_order"],
            "status": inserted["status"],
            "modified": inserted["modified"].strftime("%Y-%m-%d %H:%M:%S"),
            "data": po_rows,
            "estimated_delivery": form["estimated_delivery"],
            "dispatch_cost": float(form["dispatch_cost"]),
        }
    )

    lambda_response = requests.put(
        dotenv_values(".env")["LAMBDA_SERVER"] + "/client/purchase-orders",
        data=payload,
        headers={"Authorization": get_hmac(payload)},
    )

    if lambda_response.headers.get("content-type") == "application/json":
        detail = lambda_response.json()["message"]
    else:
        detail = "there was an error parsing a response."

    match lambda_response.status_code:
        case 200:
            return {"detail": detail, "purchase_order": inserted["purchase_order"]}
        case _:
            raise Exception(detail)


@admin.get("/dispatch-cost", response_model=AdminDispatchCost)
async def get_dispatch_costs(items: str = None) -> AdminDispatchCost:
    params = {
        "client_id": (
            "bm-prod" if os.path.exists("/var/lib/cloud/instance") else "bm-dev"
        ),
        "items": items,
    }

    lambda_response = requests.get(
        dotenv_values(".env")["LAMBDA_SERVER"] + "/client/dispatch-cost",
        headers={"Authorization": get_hmac(params)},
        params=params,
    )

    if lambda_response.status_code != 200:
        raise Exception("there was an error in the request")

    return lambda_response.json()
