table "albums" {
  schema = schema.public
  column "album_id" {
    null = false
    type = serial
  }
  column "title" {
    null = true
    type = character_varying
  }
  column "release_year" {
    null = true
    type = smallint
  }
  column "stock" {
    null    = true
    type    = smallint
    default = 0
  }
  column "price" {
    null = true
    type = numeric(4,2)
  }
  column "photo" {
    null = true
    type = character_varying
  }
  column "artist_id" {
    null = true
    type = smallint
  }
  column "modified" {
    null    = true
    type    = timestamp
    default = sql("timezone('utc'::text, now())")
  }
  primary_key {
    columns = [column.album_id]
  }
  foreign_key "albums_artist_id_fkey" {
    columns     = [column.artist_id]
    ref_columns = [table.artists.column.artist_id]
    on_update   = NO_ACTION
    on_delete   = NO_ACTION
  }
  check "no_negative_stock" {
    expr = "(stock >= 0)"
  }
}
table "artists" {
  schema = schema.public
  column "artist_id" {
    null = false
    type = serial
  }
  column "name" {
    null = true
    type = character_varying
  }
  column "bio" {
    null = true
    type = character_varying
  }
  column "modified" {
    null    = true
    type    = timestamp
    default = sql("timezone('utc'::text, now())")
  }
  primary_key {
    columns = [column.artist_id]
  }
}
table "cart" {
  schema = schema.public
  column "user_id" {
    null = false
    type = smallint
  }
  column "album_id" {
    null = false
    type = smallint
  }
  column "quantity" {
    null = true
    type = smallint
  }
  primary_key {
    columns = [column.user_id, column.album_id]
  }
  foreign_key "cart_album_id_fkey" {
    columns     = [column.album_id]
    ref_columns = [table.albums.column.album_id]
    on_update   = NO_ACTION
    on_delete   = NO_ACTION
  }
  foreign_key "cart_user_id_fkey" {
    columns     = [column.user_id]
    ref_columns = [table.users.column.user_id]
    on_update   = NO_ACTION
    on_delete   = NO_ACTION
  }
}
table "orders" {
  schema = schema.public
  column "order_id" {
    null = false
    type = serial
  }
  column "user_id" {
    null = true
    type = smallint
  }
  column "dispatched" {
    null    = true
    type    = timestamp
    default = sql("timezone('utc'::text, now())")
  }
  primary_key {
    columns = [column.order_id]
  }
  foreign_key "orders_user_id_fkey" {
    columns     = [column.user_id]
    ref_columns = [table.users.column.user_id]
    on_update   = NO_ACTION
    on_delete   = NO_ACTION
  }
}
table "orders_bridge" {
  schema = schema.public
  column "order_id" {
    null = false
    type = integer
  }
  column "album_id" {
    null = false
    type = smallint
  }
  column "quantity" {
    null = true
    type = smallint
  }
  primary_key {
    columns = [column.order_id, column.album_id]
  }
  foreign_key "orders_bridge_album_id_fkey" {
    columns     = [column.album_id]
    ref_columns = [table.albums.column.album_id]
    on_update   = NO_ACTION
    on_delete   = NO_ACTION
  }
  foreign_key "orders_bridge_order_id_fkey" {
    columns     = [column.order_id]
    ref_columns = [table.orders.column.order_id]
    on_update   = NO_ACTION
    on_delete   = CASCADE
  }
}
table "purchase_order_lines" {
  schema = schema.public
  column "line" {
    null = false
    type = smallint
  }
  column "purchase_order" {
    null = false
    type = smallint
  }
  column "album_id" {
    null = true
    type = integer
  }
  column "quantity" {
    null = true
    type = smallint
  }
  column "confirmed_quantity" {
    null = true
    type = smallint
  }
  column "line_total" {
    null = true
    type = numeric(6,2)
  }
  primary_key {
    columns = [column.line, column.purchase_order]
  }
  foreign_key "purchase_order_lines_album_id_fkey" {
    columns     = [column.album_id]
    ref_columns = [table.albums.column.album_id]
    on_update   = NO_ACTION
    on_delete   = NO_ACTION
  }
  foreign_key "purchase_order_lines_purchase_order_fkey" {
    columns     = [column.purchase_order]
    ref_columns = [table.purchase_orders.column.purchase_order]
    on_update   = NO_ACTION
    on_delete   = NO_ACTION
  }
}
table "purchase_orders" {
  schema = schema.public
  column "purchase_order" {
    null = false
    type = serial
  }
  column "status" {
    null = true
    type = character_varying
  }
  column "created" {
    null    = true
    type    = timestamp
    default = sql("timezone('utc'::text, now())")
  }
  primary_key {
    columns = [column.purchase_order]
  }
  check "purchase_orders_status_check" {
    expr = "((status)::text = ANY ((ARRAY['pending-supplier'::character varying, 'pending-buyer'::character varying, 'confirmed'::character varying])::text[]))"
  }
}
table "songs" {
  schema = schema.public
  column "track" {
    null = false
    type = smallint
  }
  column "album_id" {
    null = false
    type = smallint
  }
  column "duration" {
    null = true
    type = smallint
  }
  column "song" {
    null = true
    type = character_varying
  }
  primary_key {
    columns = [column.track, column.album_id]
  }
  foreign_key "songs_album_id_fkey" {
    columns     = [column.album_id]
    ref_columns = [table.albums.column.album_id]
    on_update   = NO_ACTION
    on_delete   = CASCADE
  }
}
table "users" {
  schema = schema.public
  column "user_id" {
    null = false
    type = serial
  }
  column "role" {
    null = true
    type = character_varying
  }
  column "username" {
    null = true
    type = character_varying
  }
  column "password" {
    null = false
    type = character_varying
  }
  column "created" {
    null    = true
    type    = timestamp
    default = sql("timezone('utc'::text, now())")
  }
  primary_key {
    columns = [column.user_id]
  }
  check "users_role_check" {
    expr = "((role)::text = ANY (ARRAY[('user'::character varying)::text, ('admin'::character varying)::text]))"
  }
  unique "users_username_key" {
    columns = [column.username]
  }
}
schema "public" {
  comment = "standard public schema"
}
