CREATE TABLE IF NOT EXISTS users (
	user_id serial,
	name varchar(50) NOT NULL,
	organization varchar,
	primary key (user_id)
);

CREATE TABLE IF NOT EXISTS categories (
	category_id serial,
	name varchar(50) NOT NULL,
	primary key (category_id)
);

CREATE TABLE IF NOT EXISTS phone (
	phone_number varchar(20),
	user_id int,
	primary key(phone_number),
	foreign key (user_id) references users on delete cascade
);

CREATE TABLE IF NOT EXISTS location (
	location_id serial,
	location_name varchar(50) NOT NULL,
	city varchar(50) NOT NULL,
	district varchar(50) NOT NULL,
	street varchar(100) NOT NULL,
	number varchar(20) NOT NULL,
	primary key (location_id)
);

CREATE TABLE IF NOT EXISTS post (
	post_id serial,
	user_id int NOT NULL,
	description TEXT NOT NULL,
	post_time timestamp DEFAULT current_timestamp,
	available boolean DEFAULT true,
	primary key (post_id),
	foreign key (user_id) references users on delete cascade
);

CREATE TABLE IF NOT EXISTS comment (
	comment_id serial,
	post_id int NOT NULL,
	user_id int NOT NULL,
	rating int NOT NULL CHECK (rating >= 0 and rating <= 5),
	comment_str text NOT NULL,
	comment_time timestamp DEFAULT current_timestamp,
	primary key (comment_id),
	foreign key (user_id) references users on delete cascade,
	foreign key (post_id) references post on delete cascade
);

CREATE TABLE IF NOT EXISTS item (
	item_id serial,
	category_id int NOT NULL,
	post_id int NOT NULL,
	location_id int NOT NULL,
	item_name text NOT NULL,
	expiration_date timestamp NOT NULL,
	quantity int NOT NULL CHECK (quantity >= 0),
	primary key (item_id),
	foreign key (category_id) references categories,
	foreign key (post_id) references post on delete cascade,
	foreign key (location_id) references "location" 
);

CREATE TABLE IF NOT EXISTS trade (
	trade_id serial,
	user_id int NOT NULL,
	item_id int NOT NULL,
	quantity int NOT NULL CHECK (quantity > 0),
	trade_time timestamp NOT NULL,
	primary key (trade_id),
	foreign key (user_id) references users on delete cascade,
	foreign key (item_id) references item on delete cascade
);

CREATE TABLE IF NOT EXISTS account (
	user_id int NOT NULL,
	username varchar(50) NOT NULL UNIQUE,
	pwd varchar(255) NOT NULL,
	lastlogin timestamp DEFAULT current_timestamp,
	PRIMARY KEY (user_id),
	FOREIGN KEY (user_id) references users on delete cascade
);

CREATE OR REPLACE FUNCTION update_inventory() RETURNS TRIGGER AS $$
DECLARE
    target_post_id INT;
    remaining_items INT;
BEGIN
    -- 找到 item 在哪個 post
    SELECT post_id INTO target_post_id FROM item WHERE item_id = NEW.item_id;

    -- 把 item 庫存減少
    UPDATE item
    SET quantity = quantity - NEW.quantity
    WHERE item_id = NEW.item_id;

    -- 檢查有沒有其他數量大於 0 的物品
    SELECT COUNT(*) INTO remaining_items
    FROM item
    WHERE post_id = target_post_id
    AND quantity > 0;

    -- 如果物品數量都歸 0 了 -> post available = false
    IF remaining_items = 0 THEN
        UPDATE post
        SET available = false
        WHERE post_id = target_post_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 綁定 Trigger
CREATE TRIGGER trade_insert_trigger
AFTER INSERT ON trade
FOR EACH ROW
EXECUTE FUNCTION update_inventory();