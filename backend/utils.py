
import re
import hmac
import base64
import hashlib
import requests
from jose import jwt
from dotenv import dotenv_values
from cryptography.fernet import Fernet
from fastapi import Request, HTTPException

fe_secret = dotenv_values(".env")["FE_SECRET"]
be_secret = dotenv_values(".env")["BE_SECRET"]


class AuthorizationError(Exception):
    pass


def get_hmac(payload):
    print(str(payload).encode())
    secret_key = dotenv_values(".env")["LAMBDA_CREDS"].encode()
    return hmac.digest(secret_key, str(payload).encode(), digest=hashlib.sha256).hex()


def parse_samples(album):
    try:
        deezer_albums = "https://api.deezer.com/search/album?q=%s" % album["album"]["title"]
        response = requests.get(deezer_albums)
        sample_album_id = None

        for sample_album in response.json()["data"]:
            same_album = sample_album["title"].lower(
            ) == album["album"]["title"].lower()
            same_artist = sample_album["artist"]["name"].lower(
            ) == album["album"]["name"].lower()

            if same_album and same_artist:
                sample_album_id = sample_album["id"]
                break

        if sample_album_id != None:
            deezer_album = "https://api.deezer.com/album/%s/tracks" % sample_album_id
            response = requests.get(deezer_album)

            for sample_track, bm_track in zip(response.json()["data"], album["songs"]):
                if sample_track["title"].lower() == bm_track["song"].lower():
                    bm_track["preview"] = sample_track["preview"]
        return album
    except:
        return album


def bm_format_photoname(name, title, filename):
    file_params = "%s-%s" % (name.lower(), title.lower())
    new_filename = re.sub("[^a-z0-9\s\-]", "", file_params).replace(" ", "-")
    extension = filename.split(".")[-1]
    return "%s.%s" % (new_filename, extension)


def save_file(filename, content):
    new_photo = open("/var/www/bm/common/%s" % filename, "wb")
    new_photo.write(content)
    new_photo.close()


def dict_list_to_matrix(dict_list):
    init_matrix = [list(array.values()) for array in dict_list]
    reshaped = [list(n) for n in zip(*init_matrix)]
    return reshaped


def form_po_rows_to_list(form):
    po_row_pattern = r"(?!artist_id|name|album_id|title|quantity|line_total)(?!_)\d"
    indexes = [int(re.search(po_row_pattern, key).group())
               for key in form.keys()]
    row_indexes = list(set(indexes))
    rows = []

    row_indexes.sort()

    for line in row_indexes:
        new_row = {
            "line": line,
            "artist_id": int(form[f"artist_id_{line}"]),
            "artist":  form[f"name_{line}"],
            "album_id": int(form[f"album_id_{line}"]),
            "album": form[f"title_{line}"],
            "quantity": int(form[f"quantity_{line}"]),
            "line_total": float(form[f"line_total_{line}"])
        }
        rows.append(new_row)
    return rows


def form_songs_to_list(form, new_album_id=None):
    song_pattern = r"^(?:track|duration|song)_[0-9]{1,2}$"
    indexes = [int(key.split("_")[1])
               for key in form.keys() if re.search(song_pattern, key)]
    song_indexes = list(set(indexes))

    songs = []

    album_id = int(form["album_id"]) if len(
        form["album_id"]) > 0 else new_album_id

    for index in song_indexes:
        duration = None
        if len(form[f"duration_{index}"]) > 0:
            duration_vals = form[f"duration_{index}"].split(":")
            duration = int(duration_vals[0]) * 60 + int(duration_vals[1])

        song = {"track": int(form[f"track_{index}"]), "album_id": album_id,
                "duration": duration, "song": form[f"song_{index}"]}
        songs.append(song)
    return songs


def get_track(n):
    return n["track"]


def encode_role(role):
    key = base64.urlsafe_b64encode(be_secret.encode())
    fernet = Fernet(key)
    key_role = fernet.encrypt(role.encode())
    b64_encoded_role = key_role.decode(encoding="utf-8")
    return b64_encoded_role


def decode_role(jwt_role):
    key = base64.urlsafe_b64encode(be_secret.encode())
    fernet = Fernet(key)
    role_b64 = jwt_role.encode(encoding="utf-8")
    role = fernet.decrypt(role_b64).decode()
    if role != "admin":
        raise Exception("unauthorized")
    return role


async def decode_token(request: Request):
    headers = request.headers
    token_pattern = re.search(r"token=(.+?)(?=;|$)", headers["cookie"])
    jwt_payload = jwt.decode(token_pattern.group(1), key=fe_secret)
    return jwt_payload


async def verify_admin_token(request: Request):
    try:
        jwt_payload = await decode_token(request)
        request.state.role = decode_role(jwt_payload["role"])
        request.state.sub = jwt_payload["sub"]
    except Exception as error:
        print(error)
        raise HTTPException(status_code=401, detail="invalid credentials")


async def verify_token(request: Request):
    try:
        jwt_payload = await decode_token(request)
        request.state.sub = jwt_payload["sub"]
    except Exception as error:
        print(error)
        raise HTTPException(status_code=401, detail="invalid credentials")
