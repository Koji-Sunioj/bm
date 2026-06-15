from db_functions import cursor, tsql
from utils import decode_role, decode_token, encode_role, AuthorizationError

from jose import jwt
from dotenv import dotenv_values
from passlib.context import CryptContext
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Request, Response
from models import UserAuth, DetailResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
fe_secret = dotenv_values(".env")["FE_SECRET"]

auth = APIRouter(prefix="/auth")


@auth.post("/check-token/admin")
async def check_admin_token(request: Request, response: Response) -> Response:
    try:
        jwt_payload = await decode_token(request)
        decode_role(jwt_payload["role"])
        response.status_code = 200
    except Exception:
        response.status_code = 401
    return response


@auth.post("/check-token")
async def check_token(request: Request, response: Response) -> Response:
    try:
        await decode_token(request)
        response.status_code = 200
    except Exception:
        response.status_code = 401
    return response


@auth.post("/sign-in", response_model=DetailResponse)
@tsql
async def sign_in(response: Response, user: UserAuth) -> DetailResponse:
    cursor.callproc("get_user", (user.username, "password"))

    try:
        db_user = cursor.fetchone()["bm_user"]
        pwd_context.verify(user.password, db_user["password"])
    except:
        raise Exception("cannot sign in")

    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=180)
    jwt_payload = {
        "sub": db_user["username"],
        "iat": now,
        "exp": expires,
        "created": str(db_user["created"]),
    }
    if db_user["role"] == "admin":
        jwt_payload["role"] = encode_role(db_user["role"])
    token = jwt.encode(jwt_payload, fe_secret)

    token_string = "token=%s; Path=/; SameSite=Lax" % token
    response.headers["Set-Cookie"] = token_string

    return {"detail": "you're signed in"}


@auth.post("/register", response_model=DetailResponse)
@tsql
async def register(user: UserAuth) -> DetailResponse:
    guest_list = dotenv_values(".env")["GUEST_LIST"].split(",")
    guest_dict = {key.split(":")[0]: key.split(":")[1] for key in guest_list}
    if user.username not in guest_dict:
        raise AuthorizationError("client not on guest list")
    role = guest_dict[user.username]
    cursor.callproc(
        "create_user",
        (user.username, pwd_context.hash(user.password), role),
    )
    created = cursor.rowcount > 0

    if not created:
        raise Exception("error creating user")

    return {"detail": "user created"}
