import os
import json
import requests
import db_functions
from utils import *
from db_functions import cursor
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request, Depends


admin = APIRouter(prefix="/api/admin",
                  dependencies=[Depends(verify_admin_token)])


@admin.delete("/albums/{album_id}")
@db_functions.tsql
async def delete_album(album_id):
    detail = "there was nothing to delete"
    cursor.callproc("get_album", (album_id,))
    album = cursor.fetchone()["album"]
    del_command = "delete from albums where album_id = %s"
    cursor.execute(del_command, (album_id,))
    if cursor.rowcount > 0:
        os.remove("/var/www/bm/common/%s" % album["photo"])
        detail = "album %s was deleted" % album["title"]
    return JSONResponse({"detail": detail}, 200)


@admin.post("/artists")
@admin.patch("/artists")
@db_functions.tsql
async def create_artist(request: Request):
    response = {"detail": None}
    form = await request.form()

    check_cmd = "select artist_id from artists where lower(name) = lower(%s);"
    cursor.execute(check_cmd, (form["name"],))

    existing_artist = cursor.fetchone()

    new_artist_exists = request.method == "POST" and existing_artist != None
    edit_artist_exists = request.method == "PATCH" and existing_artist != None and str(
        existing_artist["artist_id"]) != str(form["artist_id"])

    if any([new_artist_exists, edit_artist_exists]):
        response["detail"] = "that artist exists"
        return JSONResponse(response, 409)

    match request.method:

        case "POST":
            cursor.callproc("create_artist", (form["name"], form["bio"]))
            new_artist = cursor.fetchone()
            response["detail"] = "artist %s created" % new_artist["name"]
            response["artist_id"] = new_artist["artist_id"]

        case "PATCH":
            cursor.callproc("get_artist", (form["artist_id"], "user"))
            artist = cursor.fetchone()["artist"]

            fields_to_change = {field: form[field] if str(artist[field]) != form[field] else None for field in [
                "name", "bio"]}

            if any(fields_to_change.values()):
                cursor.callproc(
                    "update_artist", (form["artist_id"], * fields_to_change.values()))
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
@admin.patch("/albums")
@db_functions.tsql
async def manage_album(request: Request):
    form = await request.form()
    response = {"detail": None}

    cursor.callproc("get_artist", (form["artist_id"], "user"))
    artist = cursor.fetchone()["artist"]

    edit_album_exists = request.method == "PATCH" and len(
        [album for album in artist["albums"] if album["album_id"] != int(form['album_id']) and album["title"].lower() == form["title"].lower()]) > 0

    new_album_exists = request.method == "POST" and form["title"].lower() in [
        row["title"].lower() for row in artist["albums"]]

    if any([new_album_exists, edit_album_exists]):
        return JSONResponse({"detail": "that album exists"}, 409)

    filename = bm_format_photoname(
        artist["name"], form["title"], form["photo"].filename)

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

            response.update(
                {"title": inserted["title"], "album_id": inserted["album_id"]})
            response["detail"] = "album %s created" % inserted["title"]

        case "PATCH":
            cursor.callproc("get_album", (form['album_id'],))

            data = cursor.fetchone()
            album, songs = data["album"], data["songs"]

            new_songs = form_songs_to_list(form)

            existing_tracks = list(map(get_track, songs))
            new_tracks = list(map(get_track, new_songs))

            to_add_tracks = [
                track for track in new_tracks if track not in existing_tracks]

            to_delete_tracks = [
                track for track in existing_tracks if track not in new_tracks]

            to_update_tracks = [new_song for new_song, old_song in zip(
                new_songs, songs) if new_song["song"] != old_song["song"] or new_song["duration"] != old_song["duration"]]

            fields_to_change = {field: form[field] if str(album[field]) != form[field] else None for field in [
                "title", "release_year", "price", "artist_id"]}
            fields_to_change["photo"] = None

            should_del_tracks = len(to_delete_tracks) > 0
            should_add_tracks = len(to_add_tracks) > 0
            should_update_tracks = len(to_update_tracks) > 0
            should_update_album = any(fields_to_change.values())
            photo_not_same = filename != album["photo"] and form["photo"].size != os.stat(
                "/var/www/bm/common/%s" % album["photo"]).st_size
            should_rename_photo = any(
                [fields_to_change["artist_id"], fields_to_change["title"]]) and not photo_not_same

            update = 0

            if should_del_tracks:
                cursor.callproc(
                    "delete_songs", (form["album_id"], to_delete_tracks))
                update += 1

            if should_update_tracks:
                updated_matrix = dict_list_to_matrix(to_update_tracks)
                cursor.callproc("update_songs", (*updated_matrix,))

            if should_add_tracks:
                filtered = [
                    track for track in new_songs if track["track"] in to_add_tracks]
                inserted_matrix = dict_list_to_matrix(filtered)
                cursor.callproc(
                    "insert_songs", (* inserted_matrix,))

            if photo_not_same:
                content = form["photo"].file.read()
                save_file(filename, content)
                os.remove("/var/www/bm/common/%s" % album["photo"])
                fields_to_change["photo"] = filename
                should_update_album = True

            if should_rename_photo:
                new_file = "/var/www/bm/common/%s" % filename
                old_file = "/var/www/bm/common/%s" % album["photo"]
                os.rename(old_file, new_file)
                fields_to_change["photo"] = filename
                should_update_album = True

            if should_update_album:
                cursor.callproc(
                    "update_album", (form["album_id"], * fields_to_change.values()))

            if any([should_del_tracks, should_add_tracks, should_update_tracks, should_update_album, photo_not_same]):
                cursor.callproc("update_modified", (form["album_id"],))
                updated_album = cursor.fetchone()
                response["detail"] = "album %s updated" % updated_album["title"]
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


@admin.patch("/purchase-orders")
@db_functions.tsql
async def update_purchase_order(request: Request):
    form = await request.form()
    po_rows = form_po_rows_to_list(form)

    cmd = "select line,album_id,quantity,line_total::float,confirmed_quantity from purchase_order_lines where purchase_order = %s;"
    cursor.execute(cmd, (form["purchase_order"],))
    existing_lines = cursor.fetchall()

    for n, new_line in enumerate(po_rows):
        confirmed_value = [i["confirmed_quantity"]
                           for i in existing_lines if i["album_id"] == new_line["album_id"]]
        new_line["confirmed_quantity"] = confirmed_value[0] if len(
            confirmed_value) == 1 else None
        po_rows[n] = new_line

    to_update_lines = []

    for new_line, old_line in zip(po_rows, existing_lines):
        old_values = list(old_line.values())[:-1]
        new_values = [new_line["line"], new_line["album_id"], new_line["quantity"],
                      new_line["line_total"]]

        if new_values != old_values:
            to_update_lines.append(new_line)

    old_lines = [old_line["line"] for old_line in existing_lines]
    to_add_lines = [
        new_line for new_line in po_rows if new_line["line"] not in old_lines]

    if len(to_update_lines) > 0:
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
        cursor.execute(update_cmd, (*update_lines, form["purchase_order"]))

    if len(to_add_lines) > 0:
        insert_lines = dict_list_to_matrix(to_add_lines)
        insert_cmd = """insert into purchase_order_lines
            (line,album_id,quantity,line_total,confirmed_quantity,purchase_order)
            select unnest(%s),unnest(%s),unnest(%s),unnest(%s),unnest(%s::smallint[]),%s;
            """
        cursor.execute(insert_cmd, (*insert_lines, form["purchase_order"]))

    should_delete_lines = len(po_rows) < len(
        existing_lines) and len(to_add_lines) == 0

    if should_delete_lines:
        new_albums = [new_line["album_id"] for new_line in po_rows]
        to_delete_lines = [old_line["line"]
                           for old_line in existing_lines if old_line["album_id"] not in new_albums]

        delete_cmd = "delete from purchase_order_lines where line in (select unnest(ARRAY[%s])) and purchase_order = %s;"
        cursor.execute(delete_cmd, (*to_delete_lines, form["purchase_order"]))

    if any([to_update_lines, to_add_lines, should_delete_lines]):
        new_modified = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        update_po_cmd = "update purchase_orders set modified = %s where purchase_order = %s;"
        cursor.execute(update_po_cmd, (form["purchase_order"], new_modified))
        detail = "purchase order %s updated" % form["purchase_order"]
    else:
        detail = "nothing to update"

    return JSONResponse({"detail": detail, "purchase_order": form["purchase_order"]}, 200)


@admin.post("/purchase-orders")
@db_functions.tsql
async def send_purchase_order(request: Request):
    form = await request.form()

    po_cmd = "insert into purchase_orders (status) values ('pending-supplier') returning purchase_order,modified,status;"
    cursor.execute(po_cmd)
    inserted = cursor.fetchone()

    po_rows = form_po_rows_to_list(form)

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

    client_id = "bm-prod" if os.path.exists(
        '/var/lib/cloud/instance') else "bm-dev"

    payload = json.dumps({
        "client_id": client_id,
        "purchase_order_id": inserted["purchase_order"],
        "status": inserted["status"],
        "modified": inserted["modified"].strftime("%Y-%m-%d %H:%M:%S"),
        "data": po_rows
    })

    hmac_hex = get_hmac(payload)
    headers = {"Authorization": hmac_hex}

    lambda_response = requests.put(dotenv_values(
        ".env")["LAMBDA_SERVER"]+"/client/purchase-orders", data=payload, headers=headers)
    response = {"detail": lambda_response.json()["message"]}

    if lambda_response.status_code != 200:
        return JSONResponse(response, 400)

    response["purchase_order"] = inserted["purchase_order"]
    return JSONResponse(response, 200)


@admin.delete("/artists/{artist_id}")
@db_functions.tsql
async def delete_artist(artist_id):
    del_cmd = "delete from artists where artist_id = %s returning name;"
    cursor.execute(del_cmd, (artist_id,))
    name = cursor.fetchone()["name"]
    detail = "artist %s deleted" % name
    return JSONResponse({"detail": detail}, 200)
