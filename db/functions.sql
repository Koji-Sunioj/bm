create function get_dispatches(out purchase_order int,out dispatch_id varchar,out status varchar,
	out address varchar, out estimated_receipt varchar,out shipping_cost numeric)
returns setof record as 
$$
	select dispatches.purchase_order,dispatches.dispatch_id,dispatches.status,dispatches.address,
	purchase_orders.estimated_receipt::varchar,purchase_orders.shipping_cost::float from dispatches join
	purchase_orders on purchase_orders.purchase_order = dispatches.purchase_order order by estimated_receipt desc;
$$
language sql;

create function create_dispatch(in dispatch_id uuid, in purchase_order int,in status varchar,in address varchar)
returns void as
$$
	insert into dispatches (dispatch_id,purchase_order,status,address) values ($1,$2,$3,$4);
$$
language sql;

create function update_dispatch_status(in dispatch_id uuid, in status varchar) 
returns void as
$$
	update dispatches set status = $2 where dispatch_id = $1
$$
language sql;

create function get_dispatch_status(in dispatch_id uuid, out status varchar)
returns varchar as
$$
	select status from dispatches where dispatch_id = $1
$$
language sql;

create function update_stock(in dispatch_id uuid) 
returns void as
$$
	update albums
	set stock = stock + po.confirmed_quantity from
	(select album_id,confirmed_quantity from purchase_orders 
	join dispatches on 
	dispatches.purchase_order = purchase_orders.purchase_order
	join purchase_order_lines on 
	purchase_order_lines.purchase_order = dispatches.purchase_order
	where dispatch_id = $1) 
	as po
	where po.album_id = albums.album_id;
$$
language sql;

create function merchant_update_dispatch_status(in status varchar,in dispatch_id uuid)
returns void as
$$
	update dispatches set status = $1 where dispatch_id = $2;
$$
language sql;

create function get_pending_orders_dispatches_count(out pending_pos int, out pending_dispatches int) 
returns setof record as
$$
	select pending_pos,pending_dispatches from
	(select count(purchase_order) as pending_pos from purchase_orders where status != 'confirmed') purchase_orders,
	(select count(dispatch_id) as pending_dispatches from dispatches where status != 'received') dispatches;
$$
language sql;

create function create_purchase_order(in shipping_cost numeric, in estimated_receipt timestamp,
         out purchase_order int,out modified timestamp,out status varchar)
returns setof record as
$$
         insert into purchase_orders (status,shipping_cost,estimated_receipt) values ('pending-supplier',$1,$2) returning purchase_order,modified,status;;
$$
language sql;

create function create_purchase_order_lines(in line int[],in album_id int[],
	in quantity int[],in line_total numeric[],in confirmed_quantity int[],in purchase_order int)
returns void as
$$
	insert into purchase_order_lines (line,album_id,quantity,line_total,confirmed_quantity,purchase_order)
	select  unnest($1), unnest($2),unnest($3),unnest($4),unnest($5),$6;
$$
language sql;


create function get_purchase_orders(out purchase_order int,out modified varchar,out status varchar,out count int) 
returns setof record as
$$
	select purchase_orders.purchase_order,modified::varchar,status,count(distinct(album_id)) 
	as albums from purchase_orders 
	join purchase_order_lines on purchase_orders.purchase_order = purchase_order_lines.purchase_order 
	group by purchase_orders.purchase_order,status,modified order by modified desc;
$$
language sql;

create function get_purchase_order(in purchase_order int,out purchase_order int,out status varchar,
	out modified varchar,out estimated_receipt varchar,out shipping_cost float, out line_total float,
	out invoice_total float,out lines json) 
returns setof record as
$$
	select purchase_orders.purchase_order, purchase_orders.status,purchase_orders.modified::varchar,
	purchase_orders.estimated_receipt::varchar,purchase_orders.shipping_cost::float,
	sum(purchase_order_lines.line_total)::float as line_total,
	(sum(purchase_order_lines.line_total) + purchase_orders.shipping_cost)::float as invoice_total,
	json_agg(json_build_object('line',purchase_order_lines.line,'artist_id',artists.artist_id,
	'name',artists.name,'album_id',purchase_order_lines.album_id,'title',albums.title,
	'quantity',purchase_order_lines.quantity,'confirmed',purchase_order_lines.confirmed_quantity,
	'line_total',purchase_order_lines.line_total) order by purchase_order_lines.line) as lines
	from purchase_orders join purchase_order_lines on
	purchase_orders.purchase_order = purchase_order_lines.purchase_order
	join albums on albums.album_id = purchase_order_lines.album_id
	join artists on artists.artist_id = albums.artist_id where purchase_orders.purchase_order=$1
	group by purchase_orders.purchase_order;
$$
language sql;

create function update_purchase_order_lines(in line int[],in album_id int[],in quantity int[],
	in line_total float[], in confirmed_quantity int[],in purchase_order int)
returns void as    
$$
	update purchase_order_lines
	set line = new_lines.line,
	album_id = new_lines.album_id,
	quantity = new_lines.quantity,
	confirmed_quantity = new_lines.confirmed_quantity,
	line_total = new_lines.line_total
	from (select
	unnest($1) as line,
	unnest($2) as album_id,
	unnest($3) as quantity,
	unnest($4) as line_total,
	unnest($5::smallint[]) as confirmed_quantity) as new_lines
	where purchase_order_lines.purchase_order=$6 and purchase_order_lines.line = new_lines.line;
$$
language sql;

create function merchant_update_purchase_order_lines(in line int[],in confirmed_quantities int[],in purchase_order int,
	out line int, out quantity int,out confirmed_quantity int)
as
$$
	update purchase_order_lines
	set confirmed_quantity = merchant.quantity from
	(select
		unnest($1) as line,
		unnest($2) as quantity
	) as merchant
	where merchant.line = purchase_order_lines.line
	and purchase_order=$3
	returning purchase_order_lines.line,purchase_order_lines.quantity,purchase_order_lines.confirmed_quantity
$$
language sql;

create function delete_purchase_order_lines(in line int[],in purchase_order int)
returns void as
$$
	delete from purchase_order_lines where line in (select unnest($1)) and purchase_order = $2;
$$ 
language sql;

create function update_purchase_order(in modified varchar,in status varchar,
	in shipping_cost float,in estimated_receipt varchar,in purchase_order int,
	out purchase_order int, out modified timestamp, out status varchar)
returns setof record as
$$
	update purchase_orders
	set modified = $1::timestamp, status = $2,
	shipping_cost = $3,estimated_receipt = $4::timestamp
	where purchase_order = $5
	returning purchase_order,modified,status;
$$
language sql;

create function merchant_update_purchase_order(in modified varchar,in status varchar,in purchase_order int)
returns void as
$$
	update purchase_orders
	set modified = $1::timestamp, status = $2
	where purchase_order = $3;
$$
language sql;

create function merchant_update_purchase_order_delivery(in estimated_receipt varchar,in modified varchar,in dispatch_id uuid)
returns void as
$$
	update purchase_orders
	set estimated_receipt = $1::timestamp,modified = $2::timestamp
	where purchase_order = (select purchase_order from dispatches where dispatch_id = $3);
$$
language sql;

create function delete_album(in album_id int)
returns void as    
$$
	delete from albums where album_id = $1;
$$
language sql;

create function get_album(in album_id int,out album json) 
returns setof json as 
$$
begin   
	return query select json_build_object('album_id',albums.album_id,'artist_id',artists.artist_id,'name',name,
	'title', title, 'release_year',release_year,'photo', photo,'stock',stock,'price',price::float,
	'songs',json_agg(json_build_object('track',track,'song',song,'duration',duration) order by track)) 
	as album
        from albums join artists on artists.artist_id = albums.artist_id
        join songs on songs.album_id = albums.album_id 
        where albums.album_id = $1
        group by albums.album_id,artists.artist_id,name;
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
    'album_id',albums.album_id,
	'photo',albums.photo,'title',albums.title,'artist',artists.name,
	'quantity',cart.quantity,'price',albums.price))) as cart from cart
    join albums on albums.album_id = cart.album_id
    join artists on artists.artist_id = albums.artist_id
    join users on users.user_id = cart.user_id
    where users.username = $1) as cart,
    (select coalesce(json_agg(orders),'[]') as orders from (select 
    json_build_object('order_id',orders.order_id,'dispatched',orders.dispatched,
    'balance',sum(orders_bridge.quantity * albums.price),'albums',
    json_agg(json_build_object('artist_id',artists.artist_id,
    'album_id',albums.album_id,
    'photo',albums.photo,'title',albums.title,'artist',artists.name,
    'quantity',orders_bridge.quantity,'price',albums.price))) as orders
    from orders
    join orders_bridge on orders_bridge.order_id = orders.order_id
    join albums on albums.album_id = orders_bridge.album_id
    join artists on artists.artist_id = albums.artist_id
    join users on users.user_id = orders.user_id
    where users.username = $1 
    group by orders.order_id order by orders.order_id asc) orders ) as orders;
$$ language sql;


create function delete_artist(in artist_id int, out name varchar)
returns varchar as 
$$
	delete from artists where artist_id = $1 returning name;
$$
language sql;

create function get_artist_by_name(in name, out artist_id int)
returns int as 
$$
	select artists.artist_id from artists where lower(name) = lower($1);
$$
language sql;

create function get_artist(in artist_id int,in view varchar,out artist json) returns setof json as
$$
begin
    case view
        when 'user' then 
            return query select json_build_object('name',artists.name,'bio',artists.bio,'albums',
			coalesce(json_agg(json_build_object('album_id',albums.album_id,'artist_id',
			artists.artist_id,'title',albums.title,'name',artists.name,'release_year',
			albums.release_year,'photo',albums.photo,'stock',albums.stock,'price',
			albums.price::float)) 
			filter (where albums.album_id is not null),'[]')) 
			as artist from artists 
			left join albums on artists.artist_id = albums.artist_id 
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
            from users where users.username=$0;
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


create function get_artists(in page int default null,in sort varchar default null,in direction varchar default null,in query varchar default null,out artists json)
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
    name varchar, 
    album_id integer,
    title varchar,
    photo varchar,
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
    select albums.artist_id,artists.name,albums.album_id,albums.title,albums.photo,
    albums.stock,albums.release_year,albums.price::float, albums.modified::varchar
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

create function update_modified(in album_id int,out title varchar, out album_id smallint) as
$$  
    with updated as (
    update albums set modified = now() at time zone 'utc'
    where album_id = $1 returning *)
    select title, album_id from updated join artists on artists.artist_id = updated.artist_id;
$$ language sql;

create function insert_album(in title varchar,in release_year int,in price double precision,
    in photo varchar,in artist_id int,out album_id int,out title varchar) 
as
$$
    with inserted as 
    (insert into albums (title,release_year,price,photo,artist_id) 
    values ($1,$2,$3,$4,$5) returning *) 
    select album_id,title
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
