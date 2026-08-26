import os

from dotenv import dotenv_values
from websockets.asyncio.client import connect
from fastapi import WebSocket, APIRouter,Depends

from utils import verify_admin_token_ws, get_hmac

supplier_websocket = dotenv_values(".env")["SUPPLIER_WEBSOCKET"]

socket = APIRouter(prefix="/socket",dependencies=[Depends(verify_admin_token_ws)])

@socket.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    params = {
        "client_id": (
            "bm-prod" if os.path.exists("/var/lib/cloud/instance") else "bm-dev"
        ),
        "user": "client",
    }
    hmac = get_hmac(params)
    websocket_url = supplier_websocket + "?user=%s&client_id=%s&hmac=%s" % (params["user"],params["client_id"],hmac)

    async with connect(websocket_url) as supplier_ws_connection:
        print("connected")
