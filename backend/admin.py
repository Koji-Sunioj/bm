import os
import json
import requests
import db_functions
from utils import *
from db_functions import cursor
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request, Depends, Response


admin = APIRouter(prefix="/api/admin",
                  dependencies=[Depends(verify_admin_token)])


@admin.delete("/albums/{album_id}")
@db_functions.tsql
async def delete_album(album_id):
    cursor.callproc("get_album", (album_id,))
    album = cursor.fetchone()["album"]
    del_command = "delete from albums where album_id = %s"
    cursor.execute(del_command, (album_id,))

    if cursor.rowcount > 0:
        os.remove("/var/www/bm/common/%s" % album["photo"])
        detail = "album %s was deleted" % album["title"]
    else:
        detail = "there was nothing to delete"

    return JSONResponse({"detail": detail}, 200)


@admin.post("/artists")
@admin.patch("/artists/{artist_id}")
@db_functions.tsql
async def create_artist(request: Request, artist_id=None):
    form = await request.form()

    check_cmd = "select artist_id from artists where lower(name) = lower(%s);"
    cursor.execute(check_cmd, (form["name"],))
    existing_artist = cursor.fetchone()

    new_artist_exists = request.method == "POST" and existing_artist != None
    edit_artist_exists = request.method == "PATCH" and existing_artist != None and str(
        existing_artist["artist_id"]) != artist_id

    if any([new_artist_exists, edit_artist_exists]):
        return JSONResponse({"detail": "that artist exists"}, 409)

    response = {}

    match request.method:

        case "POST":
            cursor.callproc("create_artist", (form["name"], form["bio"]))
            new_artist = cursor.fetchone()
            response["detail"] = "artist %s created" % new_artist["name"]
            response["artist_id"] = new_artist["artist_id"]

        case "PATCH":
            cursor.callproc("get_artist", (artist_id, "user"))
            artist = cursor.fetchone()["artist"]

            fields_to_change = {field: form[field] if str(artist[field]) != form[field] else None for field in [
                "name", "bio"]}

            if any(fields_to_change.values()):
                cursor.callproc(
                    "update_artist", (artist_id, * fields_to_change.values()))
                updated = cursor.fetchone()
                response["detail"] = "artist %s updated" % updated["name"]
                response["artist_id"] = updated["artist_id"]

            if fields_to_change["name"] != None and len(artist["albums"]) > 0:
                new_files = [{"album_id": album["album_id"], "new_file": bm_format_photoname(
                    form["name"], album["title"], album["photo"]), "old_file": album["photo"]} for album in artist["albums"]]

                photo_matrix = dict_list_to_matrix(new_files)[:-1]
                cursor.callproc("update_photos", (*photo_matrix,))

                for file in new_files:
                    new_file = "/var/www/bm/common/%s" % file["new_file"]
                    old_file = "/var/www/bm/common/%s" % file["old_file"]
                    os.rename(old_file, new_file)

    return JSONResponse(response, 200)


@admin.post("/albums")
@admin.patch("/albums/{album_id}")
@db_functions.tsql
async def manage_album(request: Request, album_id=None):
    form = await request.form()

    cursor.callproc("get_artist", (form["artist_id"], "user"))
    artist = cursor.fetchone()["artist"]

    edit_album_exists = request.method == "PATCH" and len(
        [album for album in artist["albums"] if str(album["album_id"]) != album_id and album["title"].lower() == form["title"].lower()]) > 0

    new_album_exists = request.method == "POST" and form["title"].lower() in [
        row["title"].lower() for row in artist["albums"]]

    if any([new_album_exists, edit_album_exists]):
        return JSONResponse({"detail": "that album exists"}, 409)

    filename = bm_format_photoname(
        artist["name"], form["title"], form["photo"].filename)

    response = {}

    match request.method:

        case "POST":
            content = form["photo"].file.read()
            save_file(filename, content)

            insert_album_params = (
                form["title"], form["release_year"], form["price"], filename, form["artist_id"])
            cursor.callproc("insert_album", insert_album_params)
            inserted = cursor.fetchone()

            new_songs = form_songs_to_list(form, inserted["album_id"])
            inserted_matrix = dict_list_to_matrix(new_songs)
            cursor.callproc("insert_songs", (* inserted_matrix,))

            response["album_id"] = inserted["album_id"]
            response["detail"] = "album %s created" % inserted["title"]

        case "PATCH":
            cursor.callproc("get_album", (form['album_id'],))
            data = cursor.fetchone()
            album, songs = data["album"], data["songs"]
            new_songs = form_songs_to_list(form)

            existing_tracks = [existing_song["track"]
                               for existing_song in songs]

            new_tracks = [new_song["track"] for new_song in new_songs]

            to_add_tracks = [
                track for track in new_tracks if track not in existing_tracks]

            to_delete_tracks = [
                track for track in existing_tracks if track not in new_tracks]

            to_update_tracks = [new_song for new_song, old_song in zip(
                new_songs, songs) if new_song["song"] != old_song["song"] or new_song["duration"] != old_song["duration"]]

            fields_to_change = {field: form[field] if str(album[field]) != form[field] else None for field in [
                "title", "release_year", "price", "artist_id"]}
            fields_to_change["photo"] = filename if album["photo"] != filename else None

            should_del_tracks = len(to_delete_tracks) > 0
            should_update_tracks = len(to_update_tracks) > 0
            should_add_tracks = len(to_add_tracks) > 0

            should_update_photo_file = filename != album["photo"] or form["photo"].size != os.stat(
                "/var/www/bm/common/%s" % album["photo"]).st_size
            should_rename_photo = any(
                [fields_to_change["artist_id"], fields_to_change["title"]]) and not should_update_photo_file

            should_update_album = any(fields_to_change.values())

            if should_del_tracks:
                cursor.callproc(
                    "delete_songs", (album_id, to_delete_tracks))

            if should_update_tracks:
                updated_matrix = dict_list_to_matrix(to_update_tracks)
                cursor.callproc("update_songs", (*updated_matrix,))

            if should_add_tracks:
                filtered = [
                    track for track in new_songs if track["track"] in to_add_tracks]
                inserted_matrix = dict_list_to_matrix(filtered)
                cursor.callproc(
                    "insert_songs", (* inserted_matrix,))

            if should_update_photo_file:
                content = form["photo"].file.read()
                os.remove("/var/www/bm/common/%s" % album["photo"])
                save_file(filename, content)

            if should_rename_photo:
                new_file = "/var/www/bm/common/%s" % filename
                old_file = "/var/www/bm/common/%s" % album["photo"]
                os.rename(old_file, new_file)

            if should_update_album:
                cursor.callproc(
                    "update_album", (album_id, * fields_to_change.values()))

            if any([should_del_tracks, should_update_tracks, should_add_tracks, should_rename_photo, should_update_photo_file, should_update_album]):
                cursor.callproc("update_modified", (album_id,))
                updated_album = cursor.fetchone()
                response["detail"] = "album %s updated" % updated_album["title"]
                response["album_id"] = updated_album["album_id"]

            else:
                response["detail"] = "there was nothing to update"

    return JSONResponse(response, 200)


@admin.get("/artists")
@db_functions.tsql
async def admin_get_artists(page: int = None, sort: str = None, direction: str = None, query: str = None):

    response = {}

    if all([page, sort, direction]):
        cursor.callproc("get_artists", (page, sort, direction, query))
        response["artists"] = cursor.fetchone()["artists"]

        cursor.callproc("get_pages", ('artists', query,))
        response["pages"] = cursor.fetchone()["pages"]

    else:
        cursor.callproc("get_artists")
        response["artists"] = cursor.fetchone()["artists"]

    return JSONResponse(response, 200)


@admin.get("/purchase-orders")
@db_functions.tsql
async def get_purchase_orders():
    cmd = "select purchase_orders.purchase_order,modified::varchar,status,count(distinct(album_id)) \
        as albums from purchase_orders join purchase_order_lines on purchase_orders.purchase_order \
            = purchase_order_lines.purchase_order group by purchase_orders.purchase_order,status,modified;"

    cursor.execute(cmd)
    pos = cursor.fetchall()
    return JSONResponse({"purchase_orders": pos}, 200)


@admin.get("/purchase-orders/{purchase_order}")
@db_functions.tsql
async def get_purchase_order(purchase_order):
    cmd = "select purchase_orders.purchase_order, purchase_orders.status,purchase_orders.modified::varchar,\
        json_agg(json_build_object('line',purchase_order_lines.line,'artist_id',artists.artist_id,\
        'name',artists.name,'album_id',purchase_order_lines.album_id,'title',albums.title,\
        'quantity',purchase_order_lines.quantity,'confirmed',purchase_order_lines.confirmed_quantity,\
        'line_total',purchase_order_lines.line_total) order by purchase_order_lines.line) as lines\
        from purchase_orders join purchase_order_lines on \
        purchase_orders.purchase_order = purchase_order_lines.purchase_order \
        join albums on albums.album_id = purchase_order_lines.album_id \
        join artists on artists.artist_id = albums.artist_id where purchase_orders.purchase_order = %s \
        group by purchase_orders.purchase_order;"

    cursor.execute(cmd, (purchase_order,))
    purchase_order = cursor.fetchone()
    return JSONResponse(purchase_order, 200)


@admin.get("/purchase-orders/{purchase_order}/{album_id}")
@db_functions.tsql
async def get_purchase_order_line(purchase_order, album_id):
    cmd = "select album_id,quantity,confirmed_quantity,line_total::float \
        from purchase_orders join purchase_order_lines on \
        purchase_orders.purchase_order = purchase_order_lines.purchase_order \
        where purchase_orders.purchase_order = %s and album_id = %s;"

    cursor.execute(cmd, (purchase_order, album_id))
    line_item = cursor.fetchone()
    response = line_item if line_item != None else {"lines": 0}

    return JSONResponse(response, 200)


@admin.post("/purchase-orders")
@admin.patch("/purchase-orders/{purchase_order}")
@db_functions.tsql
async def send_purchase_order(request: Request, purchase_order=None):
    form = await request.form()
    po_rows = form_po_rows_to_list(form)

    inserted = None

    match request.method:
        case "POST":
            check_cmd = "select count(purchase_order) from purchase_orders where status in ('pending-supplier','pending-buyer');"
            cursor.execute(check_cmd)
            others_orders = cursor.fetchone()["count"]

            if others_orders > 0:
                return JSONResponse({"detail": "no more than one pending purchase order can exist"})

            po_cmd = "insert into purchase_orders (status) values ('pending-supplier') returning purchase_order,modified,status;"
            cursor.execute(po_cmd)
            inserted = cursor.fetchone()

            inserts = "insert into purchase_order_lines (line,purchase_order,album_id,quantity,line_total) values "

            for n, line in enumerate(po_rows):
                insert = "(%s,%s,%s,%s,%s)" % (
                    line["line"], inserted["purchase_order"], line["album_id"], line["quantity"], line["line_total"])
                inserts += insert
                if n == len(po_rows) - 1:
                    inserts += ";"
                else:
                    inserts += ",\n"

            cursor.execute(inserts)

        case "PATCH":
            keys = ['line', 'album_id', 'quantity', 'line_total']
            db_rows = [dict(filter(lambda item: item[0] in keys, line.items()))
                       for line in po_rows]

            check_cmd = "select status from purchase_orders where purchase_order = %s;"
            cursor.execute(check_cmd, (purchase_order, ))
            existing_po = cursor.fetchone()

            if existing_po["status"] == "confirmed":
                return JSONResponse({"detail": "this purchase order is already completed"})

            elif existing_po["status"] == "pending-supplier":
                return JSONResponse({"detail": "this purchase order is waiting on the supplier to confirm line items"})

            cmd = "select line,album_id,quantity,line_total::float,confirmed_quantity from purchase_order_lines where purchase_order = %s order by line asc;"
            cursor.execute(cmd, (purchase_order,))
            existing_lines = cursor.fetchall()

            for n, new_line in enumerate(db_rows):
                confirmed_quantity = search(
                    existing_lines, "album_id", new_line["album_id"], "confirmed_quantity")
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
                new_line for new_line in db_rows if new_line["line"] not in old_lines]

            new_lines = [new_line["line"] for new_line in db_rows]
            to_delete_lines = [old_line["line"]
                               for old_line in existing_lines if old_line["line"] not in new_lines]

            action = {"update": len(to_update_lines) > 0, "add": len(
                to_add_lines) > 0, "delete": len(to_delete_lines) > 0}

            if action["update"]:
                update_cmd = """update purchase_order_lines
                    set line = new_lines.line,
                        album_id = new_lines.album_id,
                        quantity = new_lines.quantity,
                        confirmed_quantity = new_lines.confirmed_quantity,
                        line_total = new_lines.line_total
                        from (select
                            unnest(%s) as line,
                            unnest(%s) as album_id,
                            unnest(%s) as quantity,
                            unnest(%s) as line_total,
                            unnest(%s::smallint[]) as confirmed_quantity)
                        as new_lines
                    where purchase_order_lines.purchase_order=%s and
                    purchase_order_lines.line = new_lines.line;"""

                update_lines = dict_list_to_matrix(to_update_lines)
                cursor.execute(update_cmd, (*update_lines, purchase_order))

            if action["add"]:
                insert_lines = dict_list_to_matrix(to_add_lines)
                insert_cmd = """insert into purchase_order_lines
                    (line,album_id,quantity,line_total,confirmed_quantity,purchase_order)
                    select unnest(%s),unnest(%s),unnest(%s),unnest(%s),unnest(%s::smallint[]),%s;
                    """
                cursor.execute(insert_cmd, (*insert_lines, purchase_order))

            elif action["delete"]:
                delete_cmd = "delete from purchase_order_lines where line in (select unnest(ARRAY[%s])) and purchase_order = %s;"
                cursor.execute(delete_cmd, (to_delete_lines, purchase_order))

            if any(action.values()):
                new_modified = datetime.now(
                    timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                update_po_cmd = "update purchase_orders set modified = %s, status = %s where purchase_order = %s returning purchase_order,modified,status;"
                cursor.execute(update_po_cmd, (new_modified,
                                               'pending-supplier', purchase_order))
                inserted = cursor.fetchone()

            else:
                return JSONResponse({"detail": "no changes made"})

    payload = json.dumps({
        "client_id": "bm-prod" if os.path.exists('/var/lib/cloud/instance') else "bm-dev",
        "purchase_order_id": inserted["purchase_order"],
        "status": inserted["status"],
        "modified": inserted["modified"].strftime("%Y-%m-%d %H:%M:%S"),
        "data": po_rows
    })

    lambda_response = requests.put(dotenv_values(".env")[
        "LAMBDA_SERVER"]+"/client/purchase-orders", data=payload, headers={"Authorization": get_hmac(payload)})

    if lambda_response.headers.get('content-type') == "application/json":
        detail = lambda_response.json()["message"]
    else:
        detail = "there was an error parsing a response."

    match lambda_response.status_code:
        case 200:
            return JSONResponse({"detail": detail, "purchase_order": inserted["purchase_order"]}, 200)
        case _:
            raise Exception(detail)


@admin.delete("/artists/{artist_id}")
@db_functions.tsql
async def delete_artist(artist_id):
    del_cmd = "delete from artists where artist_id = %s returning name;"
    cursor.execute(del_cmd, (artist_id,))
    name = cursor.fetchone()["name"]
    return JSONResponse({"detail": "artist %s deleted" % name}, 200)
