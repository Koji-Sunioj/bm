from typing import Dict, Optional, List
from typing_extensions import TypedDict
from psycopg2.extras import RealDictRow
from pydantic import BaseModel, ConfigDict, create_model
import pydantic


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
