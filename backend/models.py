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


class Artist(BaseModel):
    name: str
    bio: str
    albums: List[Album]


class ArtistResponse(BaseModel):
    artist: Artist

class Cart(BaseModel):
    balance: float | None = None
    albums: int

class Order(BaseModel):
    order_id: int
    dispatched: str
    balance: float

class OrderResponse(BaseModel):
    cart: Cart
    orders: List[Order]

"""
{
   "cart":{
      "balance":null,
      "albums":null
   },
   "orders":[
      {
         "order_id":10000,
         "dispatched":"2025-02-13T18:05:47.3112",
         "balance":9.27,
         "albums":[
            {
               "artist_id":100,
               "album_id":1000,
               "photo":"ascension-the-dead-of-the-world-Cover-Art.webp",
               "title":"The Dead of the World",
               "artist":"Ascension",
               "quantity":1,
               "price":9.27
            }
         ]
      },
   ]
}  
"""
