from auth import auth
from admin import admin
from client import client
from merchant import merchant
from fastapi import FastAPI, APIRouter

from websocket import socket

app = FastAPI()

api = APIRouter(prefix="/api")
api.include_router(auth)
api.include_router(client)
api.include_router(admin)
api.include_router(merchant)
api.include_router(socket)

app.include_router(api)
