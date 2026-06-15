from typing import List
from pydantic import BaseModel


class UserAuth(BaseModel):
    username: str
    password: str


class JWT(BaseModel):
    sub: str
    iat: int
    exp: int
    created: str
    role: str


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
    bio: str | None = None
    modified: str | None = None
    albums: int | None = None


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
    albums: List[CartItem] | None = None


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


class AdminArtistPatchResponse(BaseModel):
    detail: str
    artist_id: int | None = None


class AdminAlbumPatchResponse(BaseModel):
    detail: str
    album_id: int | None = None


class AdminPurchaseOrderPatchResponse(BaseModel):
    detail: str
    purchase_order: int


class AdminAlbums(BaseModel):
    artists: List[ArtistForAdmin]
    pages: int | None = None


class AdminDispatch(BaseModel):
    purchase_order: int
    dispatch_id: str
    status: str
    address: str
    estimated_receipt: str
    shipping_cost: float


class AdminDispatches(BaseModel):
    dispatches: List[AdminDispatch]


class AdminPurchaseOrderLine(BaseModel):
    line: int
    artist_id: int
    name: str
    album_id: int
    title: str
    quantity: int
    line_total: float
    confirmed: int | None = None


class AdminPurchaseOrder(BaseModel):
    purchase_order: int
    modified: str
    status: str
    albums: int | None = None
    lines: List[AdminPurchaseOrderLine] | None = None
    estimated_receipt: str | None = None
    shipping_cost: float | None = None
    line_total: float | None = None
    invoice_total: float | None = None


class AdminPurchaseOrderResponse(BaseModel):
    purchase_order: AdminPurchaseOrder


class AdminPurchaseOrders(BaseModel):
    purchase_orders: List[AdminPurchaseOrder]


class AdminDispatchCost(BaseModel):
    freight_cost: float
    estimated_delivery: str
    weight_grams: int


class MerchantPurchaseOrderLine(BaseModel):
    line: int
    confirmed: int
    album_id: int


class MerchantPurchaseOrder(BaseModel):
    purchase_order_id: int
    client_id: str
    lines: List[MerchantPurchaseOrderLine]
    status: str
    modified: str


class MerchantDispatchNote(BaseModel):
    dispatch_id: str
    purchase_order: int
    status: str
    address: str
    client_id: str
    estimated_delivery: str


class MerchantDispatchUpdate(BaseModel):
    status: str
    estimated_delivery: str
