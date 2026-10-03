-- Practice dataset for the SQL tasks (an online stationery shop). Recreated fresh for every run.
CREATE TABLE customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT,
  signup_date TEXT NOT NULL
);
CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT,
  price REAL NOT NULL
);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  order_date TEXT NOT NULL,
  status TEXT,
  amount REAL NOT NULL
);
CREATE TABLE order_items (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  product_id INTEGER NOT NULL REFERENCES products(id),
  qty INTEGER NOT NULL
);

INSERT INTO customers (id, name, city, signup_date) VALUES
  (1, 'Aarav Sharma', 'Lucknow',   '2025-01-10'),
  (2, 'Priya Verma',  'Gorakhpur', '2025-02-14'),
  (3, 'Rohan Gupta',  'Varanasi',  '2025-03-02'),
  (4, 'Sneha Iyer',   'Chennai',   '2025-03-20'),
  (5, 'Imran Khan',   'Lucknow',   '2025-04-05'),
  (6, 'Kavya Nair',   NULL,        '2025-04-18'),
  (7, 'Deepak Yadav', 'Gorakhpur', '2025-05-01'),
  (8, 'Meera Joshi',  'Varanasi',  '2025-05-12');

INSERT INTO products (id, name, category, price) VALUES
  (1, 'Notebook',    'Stationery',  60),
  (2, 'Pen Set',     'Stationery', 120),
  (3, 'Backpack',    'Bags',       899),
  (4, 'Water Bottle', NULL,        250),
  (5, 'Headphones',  'Electronics', 1499),
  (6, 'Calculator',  'Electronics', 650),
  (7, 'Desk Lamp',   'Electronics', 799);

INSERT INTO orders (id, customer_id, order_date, status, amount) VALUES
  (101, 1, '2025-06-01', 'delivered', 480),
  (102, 1, '2025-06-15', 'delivered', 1499),
  (103, 2, '2025-06-03', 'delivered', 899),
  (104, 2, '2025-06-20', 'cancelled', 250),
  (105, 3, '2025-07-01', 'delivered', 770),
  (106, 3, '2025-07-09', NULL,        120),
  (107, 4, '2025-07-12', 'delivered', 1499),
  (108, 4, '2025-07-18', 'pending',   650),
  (109, 5, '2025-07-20', 'delivered', 959),
  (110, 5, '2025-08-02', 'delivered', 500),
  (111, 6, '2025-08-05', 'delivered', 300),
  (112, 1, '2025-08-10', 'pending',   490);

INSERT INTO order_items (id, order_id, product_id, qty) VALUES
  (1, 101, 1, 2), (2, 101, 2, 3), (3, 102, 5, 1), (4, 103, 3, 1),
  (5, 104, 4, 1), (6, 105, 6, 1), (7, 105, 1, 2), (8, 106, 2, 1),
  (9, 107, 5, 1), (10, 108, 6, 1), (11, 109, 3, 1), (12, 109, 1, 1),
  (13, 110, 4, 2), (14, 111, 1, 5), (15, 112, 2, 2), (16, 112, 4, 1);
