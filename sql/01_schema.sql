-- Dedicated schema only. Refuse an existing schema: the runner requires --rebuild to replace it.
CREATE SCHEMA portfolio;
SET search_path = portfolio, public;
CREATE TABLE customers (
 customer_key integer PRIMARY KEY, customer_id integer UNIQUE NOT NULL,
 customer_number text UNIQUE NOT NULL, first_name text, last_name text, country text,
 marital_status text, gender text, birthdate date, create_date date
);
CREATE TABLE products (
 product_key integer PRIMARY KEY, product_id integer UNIQUE NOT NULL,
 product_number text, product_name text, category_id text, category text,
 subcategory text, maintenance text, cost numeric, product_line text, start_date date
);
CREATE TABLE sales_raw (
 order_number text NOT NULL, product_key integer REFERENCES products,
 customer_key integer REFERENCES customers, order_date date, shipping_date date,
 due_date date, sales_amount numeric NOT NULL, quantity integer NOT NULL, price numeric NOT NULL,
 PRIMARY KEY(order_number, product_key), CHECK(quantity > 0), CHECK(sales_amount >= 0),
 CHECK(sales_amount = quantity * price)
);
