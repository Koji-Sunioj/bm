from typing import Dict, Optional
from typing_extensions import TypedDict
from psycopg2.extras import RealDictRow
from pydantic import BaseModel, ConfigDict, create_model
import pydantic


class User(BaseModel):
    username:str
    created:str
    orders:int
    cart:int

class UserResponse(BaseModel):
    user:User

class Artist(BaseModel):
    model_config = ConfigDict(strict=True)
    shit: str


RealDictRow(
    [
        (
            "artist",
            {
                "name": "Corpus Christii",
                "bio": "Nocturnus Horrendus is the owner of Nightmare Productions.\n\nThe band's first demo had the band's name spelled Corpus Christi. All subsequent releases have spelled it Corpus Christii with a second \"i\".",
                "albums": [
                    {
                        "album_id": 1002,
                        "artist_id": 102,
                        "title": "Rising",
                        "name": "Corpus Christii",
                        "release_year": 2007,
                        "photo": "corpus-christii-rising-Cover-Art.webp",
                        "stock": 2,
                        "price": 9.33,
                    }
                ],
            },
        )
    ]
)
