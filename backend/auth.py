import traceback
import db_functions
from jose import jwt
from db_functions import cursor
from dotenv import dotenv_values
from passlib.context import CryptContext
from utils import decode_role, decode_token, encode_role, AuthorizationError
from fastapi.responses import JSONResponse
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Request, Response

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
fe_secret = dotenv_values(".env")["FE_SECRET"]

auth = APIRouter(prefix="/auth")


@auth.post("/check-token/admin")
async def check_admin_token(request: Request, response: Response):
    try:
        jwt_payload = await decode_token(request)
        decode_role(jwt_payload["role"])
        response.status_code = 200
    except Exception:
        response.status_code = 401
    return response


@auth.post("/check-token")
async def check_token(request: Request, response: Response):
    try:
        await decode_token(request)
        response.status_code = 200
    except Exception:
        response.status_code = 401
    return response


@auth.post("/sign-in")
@db_functions.tsql
async def sign_in(request: Request):
    content = await request.json()
    cursor.callproc("get_user", (content["username"], "password"))

    try:
        user = cursor.fetchone()["bm_user"]
        pwd_context.verify(content["password"], user["password"])
    except:
        raise Exception("cannot sign in")

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


@auth.post("/register")
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
