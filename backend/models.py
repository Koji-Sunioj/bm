import pydantic
from typing import Dict, Optional, List
from pydantic import BaseModel, ConfigDict, create_model


class User(BaseModel):
    username: str
    created: str
    orders: int
    cart: int


class UserResponse(BaseModel):
    user: User


class Song(BaseModel):
    track: int
    song: str
    duration: int | None = None
    preview: str | None = None


class Album(BaseModel):
    album_id: int
    artist_id: int
    title: str
    name: str
    release_year: int
    photo: str
    stock: int
    price: float
    modified: str | None = None    
    songs: List[Song] | None = None
    cart: int | None = None 


class AlbumsResponse(BaseModel):
    albums: List[Album]
    pages: int


class AlbumResponse(BaseModel):
    album: Album

class ArtistForAdmin(BaseModel):
    artist_id: int
    name: str
    bio: str

class Artist(BaseModel):
    name: str
    bio: str
    albums: List[Album]

class ArtistResponse(BaseModel):
    artist: Artist | ArtistForAdmin

class CartItem(BaseModel):
    artist_id: int
    album_id: int
    photo: str
    title: str
    artist: str
    quantity: int
    price: float

class Cart(BaseModel):
    balance: float | None = None
    albums:  List[CartItem] | None = None

class Order(BaseModel):
    order_id: int
    dispatched: str
    balance: float
    albums: List[CartItem]

class OrderResponse(BaseModel):
    cart: Cart
    orders: List[Order]

class DetailResponse(BaseModel):
    detail: str

class AddToCartResponse(BaseModel):
    remaining: int
    cart: int

