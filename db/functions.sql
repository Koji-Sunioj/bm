create function get_album(in id_type varchar, in album_name varchar,in identifier int,out album json, out songs json) 
returns setof record as 
$$
begin
    case id_type
        when 'album_id' then
            return query select json_build_object('album_id',albums.album_id,'artist_id',artists.artist_id,'name',name,
            'title', title, 'release_year',release_year,'photo', photo,'stock',stock,'price',price::float) as album,
            json_agg(json_build_object('track',track,'song',song,'duration',duration) order by track)  as songs
            from albums join artists on artists.artist_id = albums.artist_id
            join songs on songs.album_id = albums.album_id 
            where albums.album_id = $3 
            group by albums.album_id,artists.artist_id,name;
        when 'artist_id' then
            return query select json_build_object('album_id',albums.album_id,'artist_id',artists.artist_id,'name',name,
            'title', title, 'release_year',release_year,'photo', photo,'stock',stock,'price',price::float) as album,
            json_agg(json_build_object('track',track,'song',song,'duration',duration) order by track)  as songs
            from albums join artists on artists.artist_id = albums.artist_id
            join songs on songs.album_id = albums.album_id 
            where artists.artist_id = $3 and lower(title) = $2 
            group by albums.album_id,artists.artist_id,name;
    end case;
end
$$ language plpgsql;

create function get_cart_count(in username varchar, in album_id int, out cart bigint) as
$$
    select coalesce(sum(quantity),0) as cart from cart 
    join users on users.user_id = cart.user_id 
    where users.username = $1 and cart.album_id = $2;
$$ language sql;

create function get_orders_and_cart(in username varchar, out cart json, out orders json) as
$$
    select cart, orders from
    (select json_build_object('balance',sum(cart.quantity * albums.price),
    'albums',json_agg(json_build_object('artist_id',artists.artist_id,
	'photo',albums.photo,'title',albums.title,'artist',artists.name,
	'quantity',cart.quantity,'price',albums.price))) as cart from cart
    join albums on albums.album_id = cart.album_id
    join artists on artists.artist_id = albums.artist_id
    join users on users.user_id = cart.user_id
    where users.username = $1) as cart,
    (select coalesce(json_agg(orders),'[]') as orders from (select 
    json_build_object('order_id',orders.order_id,'dispatched',orders.dispatched,
    'balance',sum(orders_bridge.quantity * albums.price),'albums',
    json_agg(json_build_object('artist_id',artists.artist_id,'photo',albums.photo,
	'title',albums.title,'artist',artists.name,'quantity',orders_bridge.quantity,
	'price',albums.price))) as orders
    from orders
    join orders_bridge on orders_bridge.order_id = orders.order_id
    join albums on albums.album_id = orders_bridge.album_id
    join artists on artists.artist_id = albums.artist_id
    join users on users.user_id = orders.user_id
    where users.username = $1 
    group by orders.order_id order by orders.order_id asc) orders ) as orders;
$$ language sql;


create function get_artist(in artist_id int,in view varchar,out artist json) returns setof json as
$$
begin
    case view
        when 'user' then 
            return query select json_build_object('name',artists.name,'bio',artists.bio,
			'albums',json_agg(json_build_object('album_id',albums.album_id,'artist_id',
			artists.artist_id,'title',albums.title,'name',artists.name,'release_year',
			albums.release_year,'photo',albums.photo,'stock',albums.stock,'price',
			albums.price::float))) as artist from albums 
            join artists on artists.artist_id = albums.artist_id 
            where artists.artist_id = $1 group by artists.artist_id;
        when 'admin' then
            return query select json_build_object('artist_id',artists.artist_id,'name', 
            artists.name,'bio', artists.bio ) as artist 
            from artists where artists.artist_id = $1;
    end case;
end
$$ language plpgsql;

create function get_user(in api_username varchar,in task varchar,out bm_user json) 
returns setof json as 
$$
begin
    case task
        when 'owner' then
            return query select json_build_object('user_id',users.user_id) as bm_user 
            from users where users.username=$1;
        when 'password' then
            return query select json_build_object('username',users.username,'password',users.password,
            'created',users.created,'role',users.role) as bm_user
            from users where username = $1;
        when 'cart' then
            return query select json_build_object('username',users.username,'created',users.created,'orders', 
            coalesce(count(distinct(order_id)), 0),'cart',coalesce(count(distinct(album_id)),0)) as bm_user 
            from users 
            left join orders on users.user_id = orders.user_id
            left join cart on cart.user_id = users.user_id where users.username = $1
            group by username,created;
        when 'checkout' then
            return query select json_build_object('user_id',users.user_id,'albums',
            json_agg(json_build_object('album_id',album_id,'quantity',quantity))) as bm_user
            from cart
            join users on users.user_id = cart.user_id
            where users.username = $1
            group by users.user_id;
    end case;
end
$$ language plpgsql;

create function get_pages(in scope varchar, in query varchar default null,out pages int) returns setof int as 
$$
begin
    case scope
        when 'albums' then
            if $2 is null then
                return query select ceil(count(album_id)::float / 8)::int as pages 
                from albums;
            else
                return query select ceil(count(album_id)::float / 8)::int as pages 
                from albums
                join artists on artists.artist_id = albums.artist_id 
                where lower(name) like lower('%' || $2 || '%')  or lower(title) like lower('%' || $2 || '%') ;
            end if;
        when 'artists' then
            if $2 is null then
                return query select ceil(count(artist_id)::float / 8)::int as pages 
                from artists;
            else
                return query select ceil(count(artist_id)::float / 8)::int as pages 
                from artists where lower(name) like lower('%' || $2 || '%');
            end if;
    end case;
end
$$ language plpgsql;


create function create_artist(in name varchar, in bio varchar,out name varchar,out artist_id int) as
$$
    insert into artists (name,bio) values ($1,$2) returning name,artist_id;
$$ language sql;


create or replace function get_artists(in page int default null,in sort varchar default null,in direction varchar default null,in query varchar default null,out artists json)
returns setof json as 
$$
declare 
has_params boolean := false = all(select unnest(array[$1::varchar,$2,$3]) is null);
new_offset smallint := ($1 - 1) * 8;
new_query varchar := ' where lower(name) like lower(''%' || $4 || '%'') ';
begin  
	if has_params then
    return query execute
        'select json_agg(
	        json_build_object(''artist_id'',s.artist_id,''name'',s.name,
		        ''bio'',s.bio,''modified'',s.modified,''albums'',s.albums)) as artists
        from (select 
		        artists.artist_id,
		        artists.name,artists.bio,
		        artists.modified::varchar,
		        count(album_id) as albums 
	        from artists left join albums on 
	        albums.artist_id = artists.artist_id'
            || case when $4 is not null then new_query else ' ' end ||  
	        'group by artists.artist_id order by'
            || case $3 when 'ascending' then format(' %s asc,artists.artist_id asc ',$2) when 'descending' then format(' %s desc,artists.artist_id desc ',$2) end || 
            format('limit 8 offset %s',new_offset) || ') as s'; 
	else
		return query execute
		'select json_agg(json_build_object(''name'',name,''artist_id'',artist_id)order by name,artist_id asc) as artists from artists;';			 
	end if;
end
$$ language plpgsql;

create function get_albums(in page int,in sort varchar,in direction varchar,in query varchar default null)
returns table (
    artist_id smallint,
    photo varchar,
    title varchar,
    name varchar, 
	stock smallint, 
    release_year smallint, 
    price double precision,
    modified varchar
) as 
$$
declare 
new_offset smallint := ($1 - 1) * 8;
new_query varchar := ' where lower(name) like lower(''%' || $4 || '%'') or lower(title) like lower(''%' || $4 || '%'')';
begin  
    return query execute '
    select albums.artist_id,albums.photo,albums.title,artists.name,albums.stock,
    albums.release_year,albums.price::float, albums.modified::varchar
    from albums
    join artists on artists.artist_id = albums.artist_id'
    || case when $4 is not null then new_query else ' ' end || 
    'order by'
    || case $3 when 'ascending' then format(' %s asc,albums.album_id asc ',$2) when 'descending' then format(' %s desc,albums.album_id desc ',$2) end || 
    format('limit 8 offset %s',new_offset); 
end
$$ language plpgsql;

create function update_songs(in existing_tracks int[],in existing_album_ids int[],
    in new_durations int[],in new_songs varchar[])
returns void as 
$$
    update songs 
    set song = new_songs.song,
    	duration = new_songs.duration
    from (select 
		unnest($1) as track,
		unnest($2) as album_id,
		unnest($3) as duration,
		unnest($4) as song ) as new_songs
    where new_songs.album_id=songs.album_id
    and new_songs.track=songs.track;
$$ language sql;


create function update_photos(in existing_album_ids int[],in photos varchar[])
returns void as 
$$
    update albums 
    set photo = new_photos.photo,
    	modified = now() at time zone 'utc'
    from (select 
		unnest($1) as album_id,
		unnest($2) as photo) as new_photos
    where new_photos.album_id=albums.album_id;
$$ language sql;


create function insert_songs(in tracks_ids int[],in album_ids int[],
    in durations int[],in new_songs varchar[]) 
returns void as
$$
    insert into songs (track,album_id,duration,song)
    select  unnest($1), unnest($2),unnest($3),unnest($4);
$$ language sql;


create function delete_songs(in album_id int, in del_songs int[]) 
returns void as
$$
    delete from songs where album_id = $1
    and track in (select unnest($2));
$$ language sql;

create function create_user(in username varchar, in password varchar, in role varchar) 
returns void as
$$
    insert into users (username,password,role) values ($1,$2,$3);
$$ language sql;

create function create_order(in user_id int,out order_id int) as
$$
    insert into orders (user_id) values ($1) returning order_id;
$$ language sql;

create function create_dispatch_items(in order_id int, in album_ids int[], in quantities int[]) 
returns void as
$$
    insert into orders_bridge (order_id,album_id,quantity)
    select  $1, unnest($2),unnest($3);
$$ language sql;

create function remove_cart_items(in user_id int,in album_id int default null) 
returns void as
$$
begin
    if $2 is null then
        delete from cart where cart.user_id = $1;
    else
        delete from cart where cart.user_id = $1 and cart.album_id = $2;
    end if;
end
$$ language plpgsql;

create function check_cart_item(in user_id int,in album_id int,out in_cart int) as
$$
    select count(cart.album_id) as in_cart
    from cart where cart.user_id = $1 and cart.album_id=$2;
$$ language sql;

create function add_cart_item(in user_id int,in album_id int) 
returns void as
$$
    insert into cart (user_id,album_id,quantity) values ($1, $2, 1); 
$$ language sql;

create function update_cart_quantity(in user_id int,in album_id int,in amount int) 
returns void as
$$
    update cart set quantity = quantity + $3
    where cart.user_id = $1 and cart.album_id = $2;
$$ language sql;

create function update_stock_quantity(in user_id int,in album_id int,in amount int,out remaining int, out cart int) as
$$
    update albums set stock = albums.stock + $3 from 
    (select albums.album_id,albums.stock,cart.quantity 
    from cart join albums on albums.album_id = cart.album_id 
    where cart.user_id = $1 and albums.album_id = $2) as sub 
    where sub.album_id = albums.album_id returning albums.stock as remaining, sub.quantity as cart;
$$ language sql;

create function update_modified(in album_id int,out artist_id int,out title varchar) as
$$  
    with updated as (
    update albums set modified = now() at time zone 'utc'
    where album_id = $1 returning *)
    select artists.artist_id,title from updated join artists on artists.artist_id = updated.artist_id;
$$ language sql;

create function insert_album(in title varchar,in release_year int,in price double precision,
    in photo varchar,in artist_id int,out album_id int,out artist_id int,out title varchar) 
as
$$
    with inserted as 
    (insert into albums (title,release_year,price,photo,artist_id) 
    values ($1,$2,$3,$4,$5) returning *) 
    select album_id,artists.artist_id,title
    from inserted join artists on artists.artist_id = inserted.artist_id;
$$ language sql;

create function update_artist(in api_artist_id int,in api_name varchar,in bio varchar) 
returns table (
    artist_id int,
    name varchar
) as 
$$
declare
    set_name varchar:= ' name = '''||$2||'''';
    set_bio varchar:= ' bio = '''||$3||'''';
    set_modified varchar:= ' modified = now() at time zone ''utc''';
    sets varchar[] := array[set_name,set_bio,set_modified];
begin
    return query execute 'update artists set '||array_to_string(sets, ',')||' where artist_id='||$1||' returning artist_id,name;';
end
$$ language plpgsql;

create function update_album(in album_id int,in title varchar,in release_year int,
    in price double precision,in artist_id int,in photo varchar) 
    returns void as 
$$
declare 
	set_title varchar:= ' title = '''||$2||'''';
	set_release_year varchar:= ' release_year = '||$3||'';
	set_price varchar:= ' price = '||$4||'';
	set_artist_id varchar:= ' artist_id = '||$5||'';
	set_photo varchar:= ' photo = '''||$6||'''';
	set_modified varchar:= ' modified = now() at time zone ''utc''';
    sets varchar[] := array[set_title,set_release_year,set_price,set_photo,set_artist_id,set_modified];
begin  
	execute 'update albums set '||array_to_string(sets, ',')||' where album_id='||$1||';';
end
$$ language plpgsql;
