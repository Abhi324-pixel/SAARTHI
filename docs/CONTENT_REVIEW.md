# Content review sheet (AI-drafted — needs your review)

Content version: `0.1-ai-drafted-pending-review`. Source files: `backend/app/content/*.json`.

**How to review:** read each block, tick the box if it is correct, edit the JSON if not. Priority order: (1) SQL tasks and misconceptions, (2) questions marked `correct`, (3) rubrics, (4) notes.

After editing run: `cd backend && python -m pytest tests/test_sqlcheck.py tests/test_content.py` — every task and every wrong-variant is executed against the practice database.


## 1. Practice database

Tables: customers(8), products(7), orders(12), order_items(16). Deliberate traps: customer 6 has `city = NULL`; order 106 has `status = NULL`; product 4 has `category = NULL`; customers 7 and 8 have no orders; product 7 was never ordered; customer 1 bought *Pen Set* in two orders.

- [ ] Data and traps are suitable


## 2. SQL tasks (each with the expected result and the wrong variants SAARTHI recognises)


### t_select_1 — SELECT and aliases

**Prompt:** List the name and city of every customer.

```sql
SELECT name, city FROM customers
```
Expected: 8 row(s), columns `name, city`
- [ ] Reference query is correct for the prompt

### t_select_2 — SELECT and aliases

**Prompt:** Show each product's name and its price with 18% GST added, as a column called price_with_gst.

```sql
SELECT name, price * 1.18 AS price_with_gst FROM products
```
Expected: 7 row(s), columns `name, price_with_gst`
- [ ] Reference query is correct for the prompt

### t_filter_1 — Filtering with WHERE

**Prompt:** Find the names of customers who live in Lucknow or Varanasi AND signed up after 2025-03-01.

```sql
SELECT name FROM customers WHERE (city = 'Lucknow' OR city = 'Varanasi') AND signup_date > '2025-03-01'
```
Expected: 3 row(s), columns `name`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **AND binds tighter than OR**
  ```sql
  SELECT name FROM customers WHERE city = 'Lucknow' OR city = 'Varanasi' AND signup_date > '2025-03-01'
  ```
  Note shown to learner: AND is evaluated before OR, so the date test only applied to Varanasi.
  - [ ] This variant really reflects that misconception

### t_filter_2 — Filtering with WHERE

**Prompt:** List the names of products whose name contains the text 'Pen'.

```sql
SELECT name FROM products WHERE name LIKE '%Pen%'
```
Expected: 1 row(s), columns `name`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **LIKE without wildcards matches whole values**
  ```sql
  SELECT name FROM products WHERE name LIKE 'Pen'
  ```
  Note shown to learner: Without % the pattern must match the whole name.
  - [ ] This variant really reflects that misconception

### t_null_1 — NULL and three-valued logic

**Prompt:** Find the names of customers whose city is missing (NULL).

```sql
SELECT name FROM customers WHERE city IS NULL
```
Expected: 1 row(s), columns `name`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **Comparing with NULL using = or <>**
  ```sql
  SELECT name FROM customers WHERE city = NULL
  ```
  Note shown to learner: `= NULL` is never true; use IS NULL.
  - [ ] This variant really reflects that misconception

### t_null_2 — NULL and three-valued logic

**Prompt:** List the ids of orders whose status is not 'delivered' — including orders that have no status recorded.

```sql
SELECT id FROM orders WHERE status <> 'delivered' OR status IS NULL
```
Expected: 4 row(s), columns `id`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **<> 'x' also keeps rows where the value is NULL**
  ```sql
  SELECT id FROM orders WHERE status <> 'delivered'
  ```
  Note shown to learner: Rows with a NULL status are dropped by <>.
  - [ ] This variant really reflects that misconception

### t_sort_1 — ORDER BY, LIMIT and DISTINCT

**Prompt:** Show the names and prices of the 3 most expensive products.

```sql
SELECT name, price FROM products ORDER BY price DESC LIMIT 3
```
Expected: 3 row(s), columns `name, price` (order matters)
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **LIMIT alone gives the top rows**
  ```sql
  SELECT name, price FROM products LIMIT 3
  ```
  Note shown to learner: Without ORDER BY the 'first 3' rows are arbitrary, not the most expensive.
  - [ ] This variant really reflects that misconception

### t_sort_2 — ORDER BY, LIMIT and DISTINCT

**Prompt:** List each distinct city that has at least one customer (ignore customers with no city).

```sql
SELECT DISTINCT city FROM customers WHERE city IS NOT NULL
```
Expected: 4 row(s), columns `city`
- [ ] Reference query is correct for the prompt

### t_agg_1 — Aggregate functions

**Prompt:** How many orders have a status recorded (status is not NULL)? Return a single number.

```sql
SELECT COUNT(status) FROM orders
```
Expected: 1 row(s), columns `COUNT(status)`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **COUNT(*) and COUNT(column) are the same**
  ```sql
  SELECT COUNT(*) FROM orders
  ```
  Note shown to learner: COUNT(*) counts every row, including the order with no status.
  - [ ] This variant really reflects that misconception

### t_agg_2 — Aggregate functions

**Prompt:** What is the highest and the lowest order amount? Return two columns: max_amount and min_amount.

```sql
SELECT MAX(amount) AS max_amount, MIN(amount) AS min_amount FROM orders
```
Expected: 1 row(s), columns `max_amount, min_amount`
- [ ] Reference query is correct for the prompt

### t_group_1 — GROUP BY

**Prompt:** Show each customer_id with the total amount of their orders (column named total).

```sql
SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id
```
Expected: 6 row(s), columns `customer_id, total`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **Selecting a plain column next to an aggregate without GROUP BY**
  ```sql
  SELECT customer_id, SUM(amount) AS total FROM orders
  ```
  Note shown to learner: Without GROUP BY the SUM collapses everything into a single row.
  - [ ] This variant really reflects that misconception

### t_group_2 — GROUP BY

**Prompt:** How many orders are there for each status? Include the group of orders with no status. Columns: status, n.

```sql
SELECT status, COUNT(*) AS n FROM orders GROUP BY status
```
Expected: 4 row(s), columns `status, n`
- [ ] Reference query is correct for the prompt

### t_having_1 — HAVING vs WHERE

**Prompt:** Show the customer_id and number of orders (column n) for customers who placed MORE THAN ONE order.

```sql
SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id HAVING COUNT(*) > 1
```
Expected: 5 row(s), columns `customer_id, n`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **Using WHERE to filter on an aggregate** (by error text `misuse of aggregate`)
  ```sql
  SELECT customer_id, COUNT(*) AS n FROM orders WHERE COUNT(*) > 1 GROUP BY customer_id
  ```
  Note shown to learner: WHERE runs before grouping, so it cannot see COUNT(*). Use HAVING.
  - [ ] This variant really reflects that misconception

### t_inner_1 — INNER JOIN

**Prompt:** List every order id together with the name of the customer who placed it.

```sql
SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id
```
Expected: 12 row(s), columns `id, name`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **Joining tables without a join condition**
  ```sql
  SELECT o.id, c.name FROM orders o, customers c
  ```
  Note shown to learner: No join condition: every order was paired with every customer (12 x 8 = 96 rows).
  - [ ] This variant really reflects that misconception

### t_inner_2 — INNER JOIN

**Prompt:** Show each product name with the total quantity sold (column total_qty), only for products that have been sold.

```sql
SELECT p.name, SUM(oi.qty) AS total_qty FROM products p JOIN order_items oi ON oi.product_id = p.id GROUP BY p.name
```
Expected: 6 row(s), columns `name, total_qty`
- [ ] Reference query is correct for the prompt

### t_outer_1 — LEFT and other outer joins

**Prompt:** List ALL customers with the number of orders they placed (column n_orders). Customers with no orders must appear with 0.

```sql
SELECT c.name, COUNT(o.id) AS n_orders FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name
```
Expected: 8 row(s), columns `name, n_orders`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **LEFT JOIN returns only matching rows**
  ```sql
  SELECT c.name, COUNT(o.id) AS n_orders FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name
  ```
  Note shown to learner: An INNER JOIN drops customers with no orders.
  - [ ] This variant really reflects that misconception

  *Wrong variant → recognised as* **COUNT(*) after a LEFT JOIN counts the NULL row as 1**
  ```sql
  SELECT c.name, COUNT(*) AS n_orders FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name
  ```
  Note shown to learner: COUNT(*) counts the NULL-padded row, so customers without orders show 1 instead of 0.
  - [ ] This variant really reflects that misconception

### t_outer_2 — LEFT and other outer joins

**Prompt:** Find the names of customers who have NEVER placed an order.

```sql
SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL
```
Expected: 2 row(s), columns `name`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **LEFT JOIN returns only matching rows**
  ```sql
  SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL
  ```
  Note shown to learner: An INNER JOIN never keeps unmatched customers.
  - [ ] This variant really reflects that misconception

  *Wrong variant → recognised as* **Comparing with NULL using = or <>**
  ```sql
  SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id = NULL
  ```
  Note shown to learner: `= NULL` is never true; use IS NULL.
  - [ ] This variant really reflects that misconception

### t_outer_3 — LEFT and other outer joins

**Prompt:** Show every customer name with the id of each of their DELIVERED orders (columns: name, order_id). Customers with no delivered order must still appear, with a NULL order_id.

```sql
SELECT c.name, o.id FROM customers c LEFT JOIN orders o ON o.customer_id = c.id AND o.status = 'delivered'
```
Expected: 10 row(s), columns `name, id`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **Filtering the right table in WHERE cancels the LEFT JOIN**
  ```sql
  SELECT c.name, o.id FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.status = 'delivered'
  ```
  Note shown to learner: A WHERE on the right table removes the NULL rows, turning the LEFT JOIN into an INNER JOIN.
  - [ ] This variant really reflects that misconception

### t_multi_1 — Joining many tables

**Prompt:** List each distinct pair of customer name and product name that the customer has bought (columns: name, product).

```sql
SELECT DISTINCT c.name, p.name AS product FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id
```
Expected: 15 row(s), columns `name, product`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **Multi-table joins repeat rows**
  ```sql
  SELECT c.name, p.name AS product FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id
  ```
  Note shown to learner: Joining through order_items repeats pairs when a customer bought the same product more than once.
  - [ ] This variant really reflects that misconception

### t_multi_2 — Joining many tables

**Prompt:** Show each customer name with the total of their orders' amounts (column total), using the orders table's amount column.

```sql
SELECT c.name, SUM(o.amount) AS total FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.name
```
Expected: 6 row(s), columns `name, total`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **Summing after a one-to-many join counts values more than once**
  ```sql
  SELECT c.name, SUM(o.amount) AS total FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id GROUP BY c.name
  ```
  Note shown to learner: Joining order_items repeats each order's amount once per item, inflating the total.
  - [ ] This variant really reflects that misconception

### t_sub_1 — Subqueries

**Prompt:** List the names of products priced above the average product price.

```sql
SELECT name FROM products WHERE price > (SELECT AVG(price) FROM products)
```
Expected: 4 row(s), columns `name`
- [ ] Reference query is correct for the prompt

  *Wrong variant → recognised as* **Using WHERE to filter on an aggregate** (by error text `misuse of aggregate`)
  ```sql
  SELECT name FROM products WHERE price > AVG(price)
  ```
  Note shown to learner: An aggregate cannot be used directly in WHERE; compute it in a subquery.
  - [ ] This variant really reflects that misconception

### t_case_1 — CASE expressions

**Prompt:** For every order show its id and a label (column size): 'big' if the amount is 500 or more, otherwise 'small'.

```sql
SELECT id, CASE WHEN amount >= 500 THEN 'big' ELSE 'small' END AS size FROM orders
```
Expected: 12 row(s), columns `id, size`
- [ ] Reference query is correct for the prompt

## 3. Misconception library


### LEFT JOIN returns only matching rows  (`left_join_as_inner` · LEFT and other outer joins)

Treats LEFT JOIN like INNER JOIN. In fact a LEFT JOIN keeps every row of the left table; where there is no match the right-hand columns are NULL.

- Typical learner statements: “a left join only returns the rows that match”; “left join is basically inner join”; “left join only gives rows present in both tables”
- Check question: Customer 7 has no orders. After `customers LEFT JOIN orders`, does customer 7 appear in the result? What do the order columns show?
- Counter-example: `SELECT c.name, o.id FROM customers c LEFT JOIN orders o ON o.customer_id = c.id`
- Explanation: Deepak Yadav and Meera Joshi have no orders, yet they appear — with NULL in the order columns. An INNER JOIN would drop them.
- Fix hint: Count the left-table rows before and after the join: a LEFT JOIN never has fewer rows than the left table.
- [ ] Accurate and clearly worded

### Filtering the right table in WHERE cancels the LEFT JOIN  (`left_join_where_filter` · LEFT and other outer joins)

A condition on the right table in WHERE removes the NULL-padded rows, so the LEFT JOIN silently behaves like an INNER JOIN. Put the condition in ON to keep unmatched left rows.

- Typical learner statements: “i put the filter in where after the left join”; “where and on do the same thing in a left join”
- Check question: If you LEFT JOIN orders and then write WHERE o.status = 'delivered', what happens to customers who have no orders?
- Counter-example: `SELECT c.name, o.id FROM customers c LEFT JOIN orders o ON o.customer_id = c.id AND o.status = 'delivered'`
- Explanation: With the condition in ON, every customer still appears; customers without a delivered order show NULL.
- Fix hint: Move conditions on the right table from WHERE into the ON clause when you must keep unmatched left rows.
- [ ] Accurate and clearly worded

### Joining tables without a join condition  (`join_without_condition` · INNER JOIN)

Listing two tables (or JOIN without ON) pairs every row with every row — a cartesian product.

- Typical learner statements: “sql will figure out how the tables are related”; “i just wrote from orders, customers”
- Check question: If orders has 12 rows and customers has 8, how many rows come out of `FROM orders, customers` with no condition?
- Counter-example: `SELECT o.id, c.name FROM orders o, customers c`
- Explanation: 12 x 8 = 96 rows: every order is paired with every customer. The ON condition is what links an order to its own customer.
- Fix hint: Always state how the tables relate: JOIN ... ON a.key = b.key.
- [ ] Accurate and clearly worded

### Summing after a one-to-many join counts values more than once  (`join_fanout_sum` · Joining many tables)

Joining orders to order_items repeats each order's amount once per item, so SUM(o.amount) is inflated.

- Typical learner statements: “joins dont change the totals”; “i joined the items table and summed the amount”
- Check question: Order 101 has two item rows. If you join orders to order_items and SUM(orders.amount), how many times is order 101's amount counted?
- Counter-example: `SELECT c.name, SUM(o.amount) AS total FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.name`
- Explanation: Without the order_items join each order is counted once. Aggregate at the right level, or sum item-level values instead.
- Fix hint: Before aggregating, ask: does this join repeat my rows? Aggregate before joining or sum values from the many-side table.
- [ ] Accurate and clearly worded

### Multi-table joins repeat rows  (`join_fanout_duplicates` · Joining many tables)

Joining through a one-to-many chain repeats combinations. Use DISTINCT or aggregation when you want unique pairs.

- Typical learner statements: “why am i getting the same row twice”; “my join returns duplicates”
- Check question: Aarav bought a Pen Set in two different orders. How many times does the pair (Aarav, Pen Set) appear after joining through orders and order_items?
- Counter-example: `SELECT DISTINCT c.name, p.name AS product FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id`
- Explanation: DISTINCT collapses repeated (customer, product) pairs.
- Fix hint: Count rows at each join step; use DISTINCT only after you understand why rows repeat.
- [ ] Accurate and clearly worded

### Comparing with NULL using = or <>  (`null_comparison` · NULL and three-valued logic)

NULL means unknown; `= NULL` and `<> NULL` are never true. Use IS NULL / IS NOT NULL.

- Typical learner statements: “where city = null”; “null equals null”; “i compare with null using equals”
- Check question: What does `SELECT 1 WHERE NULL = NULL` return — one row or none? Why?
- Counter-example: `SELECT name FROM customers WHERE city IS NULL`
- Explanation: IS NULL finds the customer whose city is unknown. `city = NULL` finds nothing because NULL = NULL is unknown, not true.
- Fix hint: Use IS NULL and IS NOT NULL.
- [ ] Accurate and clearly worded

### <> 'x' also keeps rows where the value is NULL  (`null_in_not_equal` · NULL and three-valued logic)

A row whose status is NULL is neither equal to nor different from 'delivered'; a `<>` filter silently drops it.

- Typical learner statements: “not equal to delivered will include everything else”; “status <> delivered gives all the other orders”
- Check question: Order 106 has status NULL. Does `WHERE status <> 'delivered'` include it?
- Counter-example: `SELECT id FROM orders WHERE status <> 'delivered' OR status IS NULL`
- Explanation: Add `OR status IS NULL` to include rows with an unknown status.
- Fix hint: When a column can be NULL, decide explicitly what should happen to the NULL rows.
- [ ] Accurate and clearly worded

### NOT IN with a subquery that returns NULL matches nothing  (`not_in_null` · Subqueries)

If the subquery result contains a NULL, `x NOT IN (...)` is never true. Use NOT EXISTS or filter NULLs out.

- Typical learner statements: “not in always works”
- Check question: What does `WHERE 5 NOT IN (1, 2, NULL)` evaluate to?
- Counter-example: `SELECT name FROM customers c WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)`
- Explanation: NOT EXISTS is not tripped up by NULLs.
- Fix hint: Prefer NOT EXISTS, or add WHERE col IS NOT NULL inside the subquery.
- [ ] Accurate and clearly worded

### COUNT(*) and COUNT(column) are the same  (`count_star_vs_column` · Aggregate functions)

COUNT(*) counts rows; COUNT(column) counts rows where the column is not NULL.

- Typical learner statements: “count star and count column give the same number”; “count counts everything”
- Check question: Order 106 has no status. Will COUNT(*) and COUNT(status) over all orders give the same number?
- Counter-example: `SELECT COUNT(*) AS all_orders, COUNT(status) AS with_status FROM orders`
- Explanation: 12 orders, but only 11 have a status.
- Fix hint: Use COUNT(column) to ignore NULLs, COUNT(*) to count rows.
- [ ] Accurate and clearly worded

### COUNT(*) after a LEFT JOIN counts the NULL row as 1  (`count_star_with_left_join` · LEFT and other outer joins)

A customer with no orders still produces one NULL-padded row, so COUNT(*) gives 1 instead of 0. Count a column from the right table.

- Typical learner statements: “count star gives the number of orders”
- Check question: Customer 7 has no orders. After a LEFT JOIN to orders, what does COUNT(*) return for that customer — and what should it be?
- Counter-example: `SELECT c.name, COUNT(o.id) AS n_orders FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name`
- Explanation: COUNT(o.id) ignores the NULL, so unmatched customers get 0.
- Fix hint: After a LEFT JOIN, count a column from the right-hand table (COUNT(o.id)), not *.
- [ ] Accurate and clearly worded

### Selecting a plain column next to an aggregate without GROUP BY  (`group_by_select_nonaggregated` · GROUP BY)

Without GROUP BY an aggregate collapses the table to one row; the plain column then shows an arbitrary value (or errors in other databases).

- Typical learner statements: “i selected the customer and the sum together”; “sql will group it automatically”
- Check question: What does `SELECT customer_id, SUM(amount) FROM orders` (no GROUP BY) return — one row per customer, or one row total?
- Counter-example: `SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id`
- Explanation: GROUP BY makes one result row per customer_id.
- Fix hint: Every non-aggregated column in SELECT must appear in GROUP BY.
- [ ] Accurate and clearly worded

### Using WHERE to filter on an aggregate  (`where_vs_having` · HAVING vs WHERE)

WHERE filters rows before grouping, so it cannot use COUNT/SUM results. HAVING filters groups after aggregation.

- Typical learner statements: “where count greater than one”; “where and having are the same”
- Check question: Which runs first — WHERE or GROUP BY? So can WHERE see COUNT(*)?
- Counter-example: `SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id HAVING COUNT(*) > 1`
- Explanation: HAVING runs after the groups exist.
- Fix hint: Row conditions -> WHERE. Conditions on aggregates -> HAVING.
- [ ] Accurate and clearly worded

### AND binds tighter than OR  (`and_or_precedence` · Filtering with WHERE)

`a OR b AND c` means `a OR (b AND c)`. Use parentheses to say what you mean.

- Typical learner statements: “sql reads the conditions left to right”; “i did not use brackets”
- Check question: How does SQL read `city='Lucknow' OR city='Varanasi' AND signup_date > '2025-03-01'`? Which part is grouped?
- Counter-example: `SELECT name FROM customers WHERE (city='Lucknow' OR city='Varanasi') AND signup_date > '2025-03-01'`
- Explanation: Brackets make the date test apply to both cities.
- Fix hint: Whenever you mix AND and OR, add parentheses.
- [ ] Accurate and clearly worded

### LIKE without wildcards matches whole values  (`like_wildcards` · Filtering with WHERE)

`LIKE 'Pen'` only matches the exact text 'Pen'. Use % for 'anything': '%Pen%'.

- Typical learner statements: “like pen finds anything containing pen”
- Check question: Does `name LIKE 'Pen'` match 'Pen Set'?
- Counter-example: `SELECT name FROM products WHERE name LIKE '%Pen%'`
- Explanation: % stands for any number of characters.
- Fix hint: Use % at the start/end for 'contains'.
- [ ] Accurate and clearly worded

### LIMIT alone gives the top rows  (`limit_without_order` · ORDER BY, LIMIT and DISTINCT)

Without ORDER BY the row order is not defined, so LIMIT 3 returns three arbitrary rows, not the 'top 3'.

- Typical learner statements: “limit 3 gives the top three”; “rows come out in the order they were inserted”
- Check question: Is the first row of a table without ORDER BY guaranteed to be the highest price?
- Counter-example: `SELECT name, price FROM products ORDER BY price DESC LIMIT 3`
- Explanation: ORDER BY defines 'top'; LIMIT then cuts the list.
- Fix hint: ORDER BY before LIMIT whenever the answer depends on order.
- [ ] Accurate and clearly worded

### DISTINCT applies to just the first column  (`distinct_one_column` · ORDER BY, LIMIT and DISTINCT)

DISTINCT applies to the whole selected row, not to a single column.

- Typical learner statements: “distinct city, name gives unique cities”
- Check question: What does `SELECT DISTINCT city, name FROM customers` make unique — city, name, or the pair?
- Counter-example: `SELECT DISTINCT city FROM customers`
- Explanation: To get unique cities select only the city.
- Fix hint: DISTINCT works on the full combination of selected columns.
- [ ] Accurate and clearly worded

### AVG treats NULL as zero  (`avg_ignores_null` · Aggregate functions)

AVG ignores NULLs: the average of 10, 20 and NULL is 15, not 10.

- Typical learner statements: “null counts as zero in averages”
- Check question: What is AVG of the values 10, 20 and NULL?
- Counter-example: `SELECT AVG(amount) FROM orders`
- Explanation: NULL values are skipped; use COALESCE(x, 0) if zeros are intended.
- Fix hint: Decide whether a missing value should count as 0 and use COALESCE explicitly.
- [ ] Accurate and clearly worded

### More indexes always make the database faster  (`index_always_faster` · Indexes)

Indexes speed up reads on the indexed columns but slow down writes and use space. They do not help every query.

- Typical learner statements: “index everything”; “an index always helps”
- Check question: What happens to INSERT speed when a table has many indexes?
- Explanation: Each insert must also update every index.
- Fix hint: Index columns used in WHERE / JOIN / ORDER BY of frequent, slow queries.
- [ ] Accurate and clearly worded

### Uncommitted changes are visible to everyone immediately  (`uncommitted_visible` · Transactions and ACID)

Inside a transaction your changes are private until COMMIT (isolation).

- Typical learner statements: “as soon as i run update everybody sees it”
- Check question: Another session reads a row you updated but have not committed. Which value does it see?
- Explanation: It sees the old value; that is isolation, part of ACID.
- Fix hint: Think of a transaction as all-or-nothing and private until commit.
- [ ] Accurate and clearly worded

### POST and PUT are interchangeable  (`put_post_same` · REST API design)

PUT replaces a resource at a known URL and is idempotent; POST usually creates a new resource and is not idempotent.

- Typical learner statements: “post and put do the same thing”
- Check question: If you send the same PUT twice, is the result different from sending it once? What about POST?
- Explanation: Repeating a PUT leaves the same state; repeating a POST can create duplicates.
- Fix hint: Use POST to create, PUT to replace, PATCH to update part of a resource.
- [ ] Accurate and clearly worded

### 401 and 403 mean the same thing  (`status_401_403_swapped` · HTTP fundamentals)

401 = not authenticated (who are you?). 403 = authenticated but not allowed.

- Typical learner statements: “401 is forbidden”; “403 means you need to log in”
- Check question: A logged-in user opens an admin-only page. Which status should the server return?
- Explanation: 403 Forbidden: the identity is known but lacks permission. 401 means credentials are missing or invalid.
- Fix hint: 401 -> prove who you are; 403 -> you are not allowed.
- [ ] Accurate and clearly worded

### A GET request can be used to change data  (`get_changes_data` · HTTP fundamentals)

GET must be safe and read-only; changes should use POST/PUT/PATCH/DELETE.

- Typical learner statements: “i can delete with a get link”
- Check question: Why is a `GET /delete?id=5` link dangerous?
- Explanation: Browsers, crawlers and prefetchers issue GETs freely, so a GET must never change state.
- Fix hint: Use the method that matches the action.
- [ ] Accurate and clearly worded

### A Docker container is a full virtual machine  (`container_is_vm` · Docker basics)

Containers share the host kernel and isolate processes; a VM boots its own operating system.

- Typical learner statements: “docker is like a vm”
- Check question: Does each container run its own operating-system kernel?
- Explanation: Containers share the host kernel, which is why they start in seconds and are lighter.
- Fix hint: Image = recipe, container = running instance sharing the host kernel.
- [ ] Accurate and clearly worded

## 4. Multiple-choice questions (the correct answer is marked ✔; options tied to a misconception are in brackets)


### Python basics

**q_py_basics_1** — What does `print(type(3 / 2))` display in Python 3?
- <class 'float'> ✔
- <class 'int'>
- <class 'str'>
- It raises an error
- Explanation: The / operator always produces a float in Python 3 (1.5). Use // for integer division.
- [ ] Exactly one correct answer, distractors fair

**q_py_basics_2** — What is the output?  for i in range(3):     print(i)
- 0 1 2 (each on its own line) ✔
- 1 2 3
- 0 1 2 3
- 3
- Explanation: range(3) produces 0, 1, 2 — it starts at 0 and stops before 3.
- [ ] Exactly one correct answer, distractors fair


### Python functions

**q_py_functions_1** — What does this function return when called as `f(2)`?  def f(x):     x * 2
- None ✔
- 4
- 2
- It raises a SyntaxError
- Explanation: Without a `return` statement a Python function returns None; the expression x * 2 is computed and discarded.
- [ ] Exactly one correct answer, distractors fair

**q_py_functions_2** — What is printed?  def add(item, bucket=[]):     bucket.append(item)     return bucket  add(1) print(add(2))
- [1, 2] ✔
- [2]
- [1]
- []
- Explanation: A mutable default argument is created once and shared between calls, so the list keeps growing.
- [ ] Exactly one correct answer, distractors fair


### Lists, dicts and sets

**q_py_collections_1** — Which structure should you use to look up a student's marks quickly by their roll number?
- A dict mapping roll number to marks ✔
- A list of marks in any order
- A set of marks
- A tuple of roll numbers
- Explanation: A dict gives fast key-based lookup; searching a list is linear.
- [ ] Exactly one correct answer, distractors fair

**q_py_collections_2** — What is the value of `len(set([1, 2, 2, 3, 3, 3]))`?
- 3 ✔
- 6
- 2
- 1
- Explanation: A set stores each distinct value once: {1, 2, 3}.
- [ ] Exactly one correct answer, distractors fair


### Git basics

**q_git_basics_1** — What does `git commit` do?
- Saves a snapshot of the staged changes in your local repository ✔
- Uploads your changes to GitHub
- Downloads new changes from the remote
- Creates a new branch
- Explanation: Commit records staged changes locally. `git push` is what sends them to a remote like GitHub.
- [ ] Exactly one correct answer, distractors fair

**q_git_basics_2** — You edited a file. What must you do before `git commit` will include it?
- Stage it with `git add` ✔
- Run `git push`
- Create a branch
- Nothing; commit includes every edited file
- Explanation: Only staged changes are committed (unless you use `git commit -a` for tracked files).
- [ ] Exactly one correct answer, distractors fair


### Command line basics

**q_linux_cli_1** — Which command lists the files in the current directory?
- ls ✔
- cd
- pwd
- mkdir
- Explanation: ls lists files; cd changes directory, pwd prints the current path, mkdir creates a directory.
- [ ] Exactly one correct answer, distractors fair

**q_linux_cli_2** — What does `cat notes.txt | grep error` do?
- Prints only the lines of notes.txt that contain 'error' ✔
- Deletes lines containing 'error'
- Counts the files named error
- Edits notes.txt in place
- Explanation: The pipe passes the output of cat to grep, which filters the lines.
- [ ] Exactly one correct answer, distractors fair


### Tables, rows and keys

**q_sql_relational_model_1** — What is a primary key?
- A column (or columns) whose value uniquely identifies each row ✔
- The first column of any table
- A column that can hold repeated values
- A password for the table
- Explanation: A primary key is unique and not NULL for every row.
- [ ] Exactly one correct answer, distractors fair

**q_sql_relational_model_2** — In `orders`, the column `customer_id` refers to `customers.id`. What is `orders.customer_id` called?
- A foreign key ✔
- A primary key
- An index
- An alias
- Explanation: A foreign key points at a row in another table, linking the two.
- [ ] Exactly one correct answer, distractors fair


### SELECT and aliases

**q_sql_select_1** — Which query returns only the `name` column of every customer?
- SELECT name FROM customers ✔
- SELECT * FROM name
- GET name FROM customers
- SELECT customers FROM name
- Explanation: SELECT lists the columns, FROM names the table.
- [ ] Exactly one correct answer, distractors fair

**q_sql_select_2** — What does `SELECT price * 2 AS double_price FROM products` return?
- One column called double_price with each price doubled ✔
- The products table with all prices permanently doubled
- A single number: the sum of all prices x 2
- An error, because you cannot calculate in SELECT
- Explanation: SELECT can compute values per row; AS only names the result column. It does not change the table.
- [ ] Exactly one correct answer, distractors fair

**q_sql_select_3** — Why do many teams avoid `SELECT *` in application code?
- It fetches columns you may not need and breaks if the table's columns change ✔
- It is a syntax error in most databases
- It always returns rows in random order
- It locks the table
- Explanation: Naming the columns keeps queries efficient and stable.
- [ ] Exactly one correct answer, distractors fair


### Filtering with WHERE

**q_sql_filtering_1** — Which rows does `WHERE city = 'Lucknow' OR city = 'Varanasi' AND signup_date > '2025-03-01'` keep?
- All Lucknow customers, plus Varanasi customers who signed up after 2025-03-01 ✔
- Customers from either city who signed up after 2025-03-01 [and_or_precedence]
- Only customers from Varanasi [and_or_precedence]
- It is a syntax error without brackets
- Explanation: AND is evaluated before OR: city='Lucknow' OR (city='Varanasi' AND date>...). Use brackets to group.
- [ ] Exactly one correct answer, distractors fair

**q_sql_filtering_2** — Which condition finds product names that CONTAIN the text 'Pen'?
- name LIKE '%Pen%' ✔
- name LIKE 'Pen' [like_wildcards]
- name = 'Pen%'
- name CONTAINS 'Pen'
- Explanation: % matches any number of characters; without it LIKE matches the whole value.
- [ ] Exactly one correct answer, distractors fair

**q_sql_filtering_3** — Which condition keeps orders with amount from 500 to 1000, inclusive?
- amount BETWEEN 500 AND 1000 ✔
- amount IN (500, 1000)
- amount > 500 AND amount < 1000
- amount = 500 TO 1000
- Explanation: BETWEEN includes both ends.
- [ ] Exactly one correct answer, distractors fair


### NULL and three-valued logic

**q_sql_null_1** — Which query finds customers whose city is unknown?
- WHERE city IS NULL ✔
- WHERE city = NULL [null_comparison]
- WHERE city = ''
- WHERE city == NULL [null_comparison]
- Explanation: NULL means 'unknown'; comparisons with = never evaluate to true, so IS NULL is required.
- [ ] Exactly one correct answer, distractors fair

**q_sql_null_2** — Order 106 has status NULL. Does `WHERE status <> 'delivered'` return it?
- No — NULL <> 'delivered' is unknown, so the row is dropped ✔
- Yes — a missing status is not 'delivered' [null_in_not_equal]
- Yes, but only if you add DISTINCT
- It causes an error
- Explanation: Comparisons with NULL yield UNKNOWN, and WHERE keeps only rows where the condition is TRUE.
- [ ] Exactly one correct answer, distractors fair

**q_sql_null_3** — What does `SELECT 10 + NULL` return?
- NULL ✔
- 10
- 0
- An error
- Explanation: Arithmetic with an unknown value is unknown.
- [ ] Exactly one correct answer, distractors fair


### ORDER BY, LIMIT and DISTINCT

**q_sql_sorting_limit_1** — You want the 3 highest-priced products. Which query is correct?
- SELECT name FROM products ORDER BY price DESC LIMIT 3 ✔
- SELECT name FROM products LIMIT 3 [limit_without_order]
- SELECT TOP 3 name FROM products ORDER BY price
- SELECT name FROM products LIMIT 3 ORDER BY price DESC
- Explanation: Without ORDER BY, 'first 3' is arbitrary. ORDER BY comes before LIMIT.
- [ ] Exactly one correct answer, distractors fair

**q_sql_sorting_limit_2** — What does `SELECT DISTINCT city, name FROM customers` make unique?
- The combination of city and name ✔
- Only city [distinct_one_column]
- Only name [distinct_one_column]
- Nothing; DISTINCT needs a single column
- Explanation: DISTINCT applies to the whole selected row.
- [ ] Exactly one correct answer, distractors fair


### Aggregate functions

**q_sql_aggregates_1** — Orders has 12 rows; one row has status NULL. What does `SELECT COUNT(status) FROM orders` return?
- 11 ✔
- 12 [count_star_vs_column]
- 1
- NULL
- Explanation: COUNT(column) skips NULLs; COUNT(*) counts rows.
- [ ] Exactly one correct answer, distractors fair

**q_sql_aggregates_2** — A column holds the values 10, 20 and NULL. What does AVG(column) return?
- 15 ✔
- 10 [avg_ignores_null]
- 30
- NULL
- Explanation: AVG ignores NULLs: (10 + 20) / 2 = 15.
- [ ] Exactly one correct answer, distractors fair

**q_sql_aggregates_3** — Which function returns the number of rows in a table?
- COUNT(*) ✔
- SUM(*)
- TOTAL(rows)
- LENGTH(*)
- Explanation: COUNT(*) counts rows regardless of NULLs.
- [ ] Exactly one correct answer, distractors fair


### GROUP BY

**q_sql_group_by_1** — What does `SELECT customer_id, SUM(amount) FROM orders` (no GROUP BY) produce in SQLite?
- One row: the total of all orders with an arbitrary customer_id ✔
- One row per customer with their total [group_by_select_nonaggregated]
- A row per order
- Nothing
- Explanation: An aggregate with no GROUP BY collapses the table to one row. Add GROUP BY customer_id for one row per customer.
- [ ] Exactly one correct answer, distractors fair

**q_sql_group_by_2** — To list how many orders each customer placed you write `SELECT customer_id, COUNT(*) FROM orders ...`. What completes it?
- GROUP BY customer_id ✔
- ORDER BY customer_id
- WHERE customer_id
- DISTINCT customer_id
- Explanation: GROUP BY creates one group (one output row) per customer_id.
- [ ] Exactly one correct answer, distractors fair


### HAVING vs WHERE

**q_sql_having_1** — You want customers with more than 1 order. Which query works?
- SELECT customer_id FROM orders GROUP BY customer_id HAVING COUNT(*) > 1 ✔
- SELECT customer_id FROM orders WHERE COUNT(*) > 1 GROUP BY customer_id [where_vs_having]
- SELECT customer_id FROM orders GROUP BY customer_id WHERE COUNT(*) > 1 [where_vs_having]
- SELECT customer_id FROM orders HAVING customer_id > 1
- Explanation: WHERE filters rows before grouping; HAVING filters groups afterwards, so only HAVING can use COUNT(*).
- [ ] Exactly one correct answer, distractors fair

**q_sql_having_2** — In what order does SQL logically process these clauses?
- FROM, WHERE, GROUP BY, HAVING, SELECT, ORDER BY ✔
- SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY [where_vs_having]
- FROM, GROUP BY, WHERE, HAVING, SELECT, ORDER BY [where_vs_having]
- WHERE, FROM, SELECT, GROUP BY, HAVING, ORDER BY
- Explanation: Rows are filtered by WHERE before grouping; HAVING filters the finished groups.
- [ ] Exactly one correct answer, distractors fair


### INNER JOIN

**q_sql_inner_join_1** — orders has 12 rows and customers has 8. How many rows does `SELECT * FROM orders, customers` (no condition) return?
- 96 ✔
- 12 [join_without_condition]
- 8 [join_without_condition]
- 20
- Explanation: Without a join condition every row is paired with every row: 12 x 8.
- [ ] Exactly one correct answer, distractors fair

**q_sql_inner_join_2** — Which rows does an INNER JOIN between customers and orders return?
- Only customers that have at least one matching order (one row per match) ✔
- Every customer, with NULLs for those without orders [left_join_as_inner]
- Every order and every customer
- Only the first matching order per customer
- Explanation: INNER JOIN keeps only rows that match on both sides.
- [ ] Exactly one correct answer, distractors fair

**q_sql_inner_join_3** — Which is the correct way to join orders to customers?
- FROM orders o JOIN customers c ON c.id = o.customer_id ✔
- FROM orders o JOIN customers c ON c.id = o.id
- FROM orders o JOIN customers c
- FROM orders o JOIN customers c WHERE o = c
- Explanation: Match the foreign key (orders.customer_id) to the primary key (customers.id).
- [ ] Exactly one correct answer, distractors fair


### LEFT and other outer joins

**q_sql_outer_join_1** — Customer 7 has no orders. After `FROM customers c LEFT JOIN orders o ON o.customer_id = c.id`, what happens to customer 7?
- They appear once, with NULL in the order columns ✔
- They are removed because nothing matches [left_join_as_inner]
- They appear with order id 0
- The query fails
- Explanation: LEFT JOIN keeps every row of the left table; missing matches become NULL.
- [ ] Exactly one correct answer, distractors fair

**q_sql_outer_join_2** — You LEFT JOIN customers to orders, then add `WHERE o.status = 'delivered'`. What happens to customers without orders?
- They disappear — the WHERE removes the NULL rows ✔
- They stay, with NULL in the order columns [left_join_where_filter]
- They stay with status 'delivered'
- The database ignores the WHERE
- Explanation: NULL = 'delivered' is not true, so the row is filtered out. Put the condition in ON to keep them.
- [ ] Exactly one correct answer, distractors fair

**q_sql_outer_join_3** — After a LEFT JOIN, which expression gives 0 for customers who have no orders?
- COUNT(o.id) ✔
- COUNT(*) [count_star_with_left_join]
- SUM(1)
- COUNT(c.id) [count_star_with_left_join]
- Explanation: COUNT(o.id) ignores the NULL; COUNT(*) and COUNT(c.id) count the unmatched row as 1.
- [ ] Exactly one correct answer, distractors fair


### Joining many tables

**q_sql_multi_table_1** — Order 101 has 2 rows in order_items. If you join orders to order_items and compute SUM(orders.amount), how many times is order 101's amount added?
- Twice — once per item row ✔
- Once [join_fanout_sum]
- Zero times
- It depends on DISTINCT
- Explanation: A one-to-many join repeats the order row for every item, so its amount is counted for each repeat.
- [ ] Exactly one correct answer, distractors fair

**q_sql_multi_table_2** — A customer bought the same product in two different orders. Joining customers, orders, order_items and products gives how many rows for that (customer, product) pair?
- Two (one per order line) ✔
- One [join_fanout_duplicates]
- Zero
- Depends on the product price
- Explanation: Each matching order-line produces a row. Use DISTINCT or aggregate when you want unique pairs.
- [ ] Exactly one correct answer, distractors fair


### Subqueries

**q_sql_subqueries_1** — Which query lists products priced above the average price?
- SELECT name FROM products WHERE price > (SELECT AVG(price) FROM products) ✔
- SELECT name FROM products WHERE price > AVG(price) [where_vs_having]
- SELECT name FROM products HAVING price > AVG(price)
- SELECT name, AVG(price) FROM products
- Explanation: Aggregates cannot be used directly in WHERE; compute the average in a subquery.
- [ ] Exactly one correct answer, distractors fair

**q_sql_subqueries_2** — What does `WHERE 5 NOT IN (1, 2, NULL)` evaluate to?
- UNKNOWN — so a row with this condition is not returned ✔
- TRUE [not_in_null]
- FALSE
- An error
- Explanation: 5 <> NULL is unknown, so NOT IN with a NULL never becomes TRUE. Prefer NOT EXISTS.
- [ ] Exactly one correct answer, distractors fair


### CASE expressions

**q_sql_case_expr_1** — What does `CASE WHEN amount >= 500 THEN 'big' ELSE 'small' END` do?
- Returns 'big' or 'small' for each row depending on its amount ✔
- Deletes rows with a small amount
- Sorts rows by size
- Creates a new column permanently
- Explanation: CASE is an expression evaluated per row; it does not change stored data.
- [ ] Exactly one correct answer, distractors fair

**q_sql_case_expr_2** — If no WHEN matches and there is no ELSE, what does CASE return?
- NULL ✔
- 0
- An empty string
- An error
- Explanation: Without ELSE, unmatched rows get NULL.
- [ ] Exactly one correct answer, distractors fair


### INSERT, UPDATE, DELETE

**q_sql_dml_1** — What does `UPDATE products SET price = 0` (no WHERE) do?
- Sets the price of EVERY product to 0 ✔
- Does nothing without a WHERE
- Sets the price of the first product
- Raises an error
- Explanation: Without WHERE an UPDATE (or DELETE) affects all rows. Always check the WHERE first.
- [ ] Exactly one correct answer, distractors fair

**q_sql_dml_2** — Which statement removes customer 8's row?
- DELETE FROM customers WHERE id = 8 ✔
- DROP customers WHERE id = 8
- REMOVE FROM customers id = 8
- DELETE customers.id = 8
- Explanation: DELETE FROM table WHERE condition. DROP removes whole tables.
- [ ] Exactly one correct answer, distractors fair


### Normalisation and schema design

**q_sql_normalization_1** — An orders table stores the customer's name and city again on every order. What is the main problem?
- Duplicated data can become inconsistent when the customer changes ✔
- SQL forbids repeating text
- The table cannot have a primary key
- Queries will always be slower than 1 second
- Explanation: Normalisation stores each fact once (in customers) and links with a foreign key.
- [ ] Exactly one correct answer, distractors fair

**q_sql_normalization_2** — A student can enrol in many courses and a course has many students. How is this modelled?
- A junction table with student_id and course_id ✔
- A comma-separated list of courses in the students table
- One big table with a column per course
- It cannot be modelled in SQL
- Explanation: Many-to-many relationships need a linking table.
- [ ] Exactly one correct answer, distractors fair


### Indexes

**q_sql_indexes_1** — What is the main benefit of an index on `orders.customer_id`?
- Faster lookups and joins that filter on customer_id ✔
- It makes every query faster [index_always_faster]
- It makes inserts faster [index_always_faster]
- It reduces storage use
- Explanation: Indexes speed up reads on the indexed column but add cost to writes and storage.
- [ ] Exactly one correct answer, distractors fair

**q_sql_indexes_2** — A table has 8 indexes and receives thousands of inserts per second. What is a likely effect?
- Inserts are slower because every index must be updated ✔
- Inserts get faster [index_always_faster]
- No effect
- Reads become impossible
- Explanation: Each insert also writes to every index.
- [ ] Exactly one correct answer, distractors fair


### Transactions and ACID

**q_sql_transactions_1** — A bank transfer debits account A and credits account B. Why use a transaction?
- So both steps happen or neither does ✔
- To make the queries faster
- To avoid needing primary keys
- To let other users see the debit before the credit
- Explanation: Atomicity: a transaction is all-or-nothing.
- [ ] Exactly one correct answer, distractors fair

**q_sql_transactions_2** — Session A updated a row but has not committed. What does session B see when it reads that row (default isolation)?
- The old value ✔
- The new value [uncommitted_visible]
- NULL
- An error
- Explanation: Isolation keeps uncommitted changes private until COMMIT.
- [ ] Exactly one correct answer, distractors fair


### HTTP fundamentals

**q_http_basics_1** — A logged-in user requests an admin-only page. Which status code should the server return?
- 403 Forbidden ✔
- 401 Unauthorized [status_401_403_swapped]
- 404 Not Found
- 500 Internal Server Error
- Explanation: 403 means 'I know who you are, but you are not allowed'. 401 means missing/invalid credentials.
- [ ] Exactly one correct answer, distractors fair

**q_http_basics_2** — Which HTTP method is meant to be safe (never change data on the server)?
- GET ✔
- POST
- DELETE
- PUT
- Explanation: GET is read-only. Using it to change data is dangerous because browsers and crawlers issue GETs freely.
- [ ] Exactly one correct answer, distractors fair

**q_http_basics_3** — What does status code 404 mean?
- The requested resource was not found ✔
- The server crashed
- You are not logged in
- The request succeeded
- Explanation: 4xx codes are client errors; 404 means the URL does not map to a resource.
- [ ] Exactly one correct answer, distractors fair


### REST API design

**q_rest_apis_1** — Sending the same PUT request twice to update a user ends with:
- The same final state as sending it once (idempotent) ✔
- Two users created [put_post_same]
- An error on the second request
- The user deleted
- Explanation: PUT replaces a resource at a known URL, so repeating it leaves the same state. POST usually creates a new resource each time.
- [ ] Exactly one correct answer, distractors fair

**q_rest_apis_2** — Which URL/method pair best follows REST style for fetching user 42?
- GET /users/42 ✔
- POST /getUser?id=42
- GET /deleteUser/42
- PUT /users/get/42
- Explanation: Use nouns for resources and HTTP methods for actions.
- [ ] Exactly one correct answer, distractors fair


### API authentication basics

**q_api_auth_1** — Where should an API secret key (for example for a payment service) live?
- On the server, in environment variables ✔
- In the front-end JavaScript bundle
- In a public GitHub repo
- In the URL query string
- Explanation: Anything shipped to the browser can be read by users. Keep secrets on the server.
- [ ] Exactly one correct answer, distractors fair

**q_api_auth_2** — What is a JWT typically used for in an API?
- A signed token that proves who the caller is ✔
- A database table format
- A way to compress JSON
- A password hashing algorithm
- Explanation: A JSON Web Token is signed by the server so it can verify the caller later without a session lookup.
- [ ] Exactly one correct answer, distractors fair


### FastAPI basics

**q_fastapi_basics_1** — In FastAPI, what does the following do?  @app.get('/hello') def hello():     return {'msg': 'hi'}
- Handles GET /hello and returns JSON ✔
- Handles POST /hello
- Prints 'hi' on the server only
- Creates a database table
- Explanation: The decorator registers the function as the handler for GET /hello; a returned dict becomes JSON.
- [ ] Exactly one correct answer, distractors fair

**q_fastapi_basics_2** — Why do FastAPI apps use Pydantic models for request bodies?
- To validate and parse incoming data automatically ✔
- To encrypt the traffic
- To speed up the database
- To replace HTTP
- Explanation: Pydantic validates types and returns a 422 error for bad input.
- [ ] Exactly one correct answer, distractors fair


### Using a database from Python

**q_py_db_access_1** — Why should you pass values to a SQL query as parameters (`cursor.execute('... WHERE id = ?', (x,))`) instead of building the string yourself?
- It prevents SQL injection ✔
- It makes the table smaller
- It is required for SELECT only
- It converts text to numbers
- Explanation: Parameters are sent separately from the SQL text, so user input can never change the query structure.
- [ ] Exactly one correct answer, distractors fair

**q_py_db_access_2** — After running INSERT through a Python database connection, your row is not visible from another program. What did you probably forget?
- commit() ✔
- close the file
- restart the database
- add DISTINCT
- Explanation: Changes are made inside a transaction and become visible only after commit.
- [ ] Exactly one correct answer, distractors fair


### Docker basics

**q_docker_basics_1** — What is the difference between a Docker image and a container?
- An image is a packaged template; a container is a running instance of it ✔
- They are the same thing
- A container is a template; an image is a running process
- An image is a virtual machine
- Explanation: You build an image once and can start many containers from it.
- [ ] Exactly one correct answer, distractors fair

**q_docker_basics_2** — Compared with a virtual machine, a container:
- Shares the host operating-system kernel and starts much faster ✔
- Boots its own full operating system [container_is_vm]
- Cannot run Python
- Needs a separate physical server
- Explanation: Containers isolate processes while sharing the host kernel.
- [ ] Exactly one correct answer, distractors fair


## 5. Explain-back rubrics (what the grader looks for)


### Tables, rows and keys

Question: Explain what a primary key and a foreign key are, and why we split data into several tables.
- (2) A primary key uniquely identifies each row
- (2) A foreign key refers to a key in another table to link rows
- (2) Splitting avoids repeating data / keeps each fact in one place
- Model answer: A primary key is a column whose value is unique for every row. A foreign key in another table stores that value to point at the row, linking the tables. We split data so each fact is stored once, which avoids inconsistency.
- [ ] Checklist covers what a good answer needs; weights sensible


### Filtering with WHERE

Question: A friend writes WHERE city='Lucknow' OR city='Varanasi' AND signup_date > '2025-03-01'. Explain how SQL reads it and how to fix it if they meant both cities after that date.
- (3) AND is evaluated before OR
- (2) So the date condition only applies to Varanasi
- (2) Use brackets around the OR conditions
- Model answer: AND binds tighter than OR, so the date test applies only to Varanasi and every Lucknow customer is returned. Put brackets around the two city conditions.
- [ ] Checklist covers what a good answer needs; weights sensible


### NULL and three-valued logic

Question: Explain what NULL means in SQL and how you would find customers whose city is missing.
- (2) NULL means unknown / missing, not zero or empty text
- (3) Comparisons with NULL (including = NULL) are never true / are unknown
- (3) Use IS NULL (or IS NOT NULL)
- Model answer: NULL means the value is unknown or missing. Any comparison with NULL, even NULL = NULL, is unknown rather than true, so WHERE city = NULL returns nothing. Use WHERE city IS NULL.
- [ ] Checklist covers what a good answer needs; weights sensible


### Aggregate functions

Question: What is the difference between COUNT(*) and COUNT(column)? Give an example where they differ.
- (2) COUNT(*) counts rows
- (3) COUNT(column) counts only non-NULL values of that column
- (2) Gives a case with NULLs where the counts differ
- Model answer: COUNT(*) counts every row. COUNT(column) counts only the rows where that column is not NULL. If 12 orders exist and one has no status, COUNT(*) is 12 but COUNT(status) is 11.
- [ ] Checklist covers what a good answer needs; weights sensible


### GROUP BY

Question: Explain what GROUP BY does. What would `SELECT customer_id, SUM(amount) FROM orders` return without it?
- (3) GROUP BY forms groups of rows with the same value and aggregates per group
- (2) One output row per group
- (3) Without it the aggregate collapses everything into a single row
- Model answer: GROUP BY splits rows into groups with the same value and calculates the aggregate for each group, giving one output row per group. Without it the SUM covers the whole table and returns a single row.
- [ ] Checklist covers what a good answer needs; weights sensible


### HAVING vs WHERE

Question: What is the difference between WHERE and HAVING? Which would you use to find customers with more than one order, and why?
- (3) WHERE filters rows before grouping
- (3) HAVING filters groups after aggregation
- (3) Use HAVING COUNT(*) > 1 because WHERE cannot see aggregates
- Model answer: WHERE filters individual rows before grouping, HAVING filters groups after the aggregate has been computed. To find customers with more than one order, group by customer and use HAVING COUNT(*) > 1; WHERE cannot use COUNT.
- [ ] Checklist covers what a good answer needs; weights sensible


### INNER JOIN

Question: Explain how an INNER JOIN between customers and orders works, and what goes wrong if you forget the ON condition.
- (3) Rows are combined where the ON condition matches (customer_id = id)
- (2) Rows without a match on either side are not in the result
- (3) Without ON every row pairs with every row (cartesian product)
- Model answer: An INNER JOIN pairs each order with the customer whose id equals its customer_id, and only matched rows appear. Without an ON condition every order is paired with every customer, giving 12 x 8 = 96 rows.
- [ ] Checklist covers what a good answer needs; weights sensible


### LEFT and other outer joins

Question: Explain what a LEFT JOIN returns and how it differs from an INNER JOIN. Use customers and orders as the example.
- (3) LEFT JOIN keeps every row from the left table (all customers)
- (3) Where there is no match the right-side columns are NULL
- (2) INNER JOIN would drop the unmatched (left) rows
- (1) A WHERE condition on the right table can remove the NULL rows (put it in ON)
- Model answer: A LEFT JOIN keeps every customer; if a customer has no orders, the order columns are NULL. An INNER JOIN returns only customers that have matching orders. A WHERE condition on the orders table would remove the NULL rows, so such conditions go in ON.
- [ ] Checklist covers what a good answer needs; weights sensible


### Joining many tables

Question: Orders have several item rows. Explain what happens to SUM(orders.amount) if you join orders to order_items, and how to avoid it.
- (3) Each order row is repeated once per item row (fan-out)
- (3) So the amount is added several times and the total is inflated
- (2) Avoid it by not joining items, aggregating before joining, or summing item-level values
- Model answer: Joining order_items repeats the order row for each item, so SUM(orders.amount) adds the same amount several times and the total is too large. Avoid by aggregating before the join, not joining items when they are not needed, or summing item-level values.
- [ ] Checklist covers what a good answer needs; weights sensible


### Subqueries

Question: Explain when you would use a subquery, with the example of products priced above the average price.
- (2) A subquery is a query inside another query
- (3) The average is computed in a subquery because aggregates cannot be used directly in WHERE
- (2) Gives the form WHERE price > (SELECT AVG(price) FROM products)
- Model answer: A subquery is a query nested inside another. The average price is computed in a subquery - WHERE price > (SELECT AVG(price) FROM products) - because aggregates cannot be used directly in WHERE.
- [ ] Checklist covers what a good answer needs; weights sensible


### Normalisation and schema design

Question: Why is it a bad idea to store the customer's name and city on every order row? What would you do instead?
- (2) The data is duplicated on many rows
- (3) It can become inconsistent when the customer's data changes
- (3) Store customers in their own table and link with a foreign key
- Model answer: It duplicates data, so updating a customer's city means changing many rows and some may be missed. Store customers once in their own table and reference them from orders with a foreign key.
- [ ] Checklist covers what a good answer needs; weights sensible


### Indexes

Question: What is a database index, when does it help, and what is the cost?
- (3) An extra structure that makes lookups on a column faster
- (2) Helps queries that filter, join or sort on that column
- (3) Slows writes and uses extra space
- Model answer: An index is an extra data structure, like a book's index, that makes finding rows by a column fast. It helps queries filtering, joining or sorting on that column, but every insert and update must also update it, and it uses storage.
- [ ] Checklist covers what a good answer needs; weights sensible


### Transactions and ACID

Question: Explain what a database transaction is and what ACID stands for, using a bank transfer.
- (3) A transaction is all-or-nothing (atomicity)
- (2) Names ACID: atomicity, consistency, isolation, durability
- (2) Uncommitted changes are not visible to other sessions (isolation)
- Model answer: A transaction groups statements so they all succeed or all fail - in a transfer the debit and credit both happen or neither. ACID is atomicity, consistency, isolation and durability. Uncommitted changes stay invisible to other sessions.
- [ ] Checklist covers what a good answer needs; weights sensible


### HTTP fundamentals

Question: Explain how an HTTP request and response work, and the difference between 401 and 403.
- (2) Client sends a method and URL; server replies with a status code and body
- (3) 401 means not authenticated (missing or invalid credentials)
- (3) 403 means authenticated but not allowed
- Model answer: A client sends a request with a method (GET, POST...) and a URL; the server answers with a status code and usually a body. 401 means the caller is not authenticated; 403 means the caller is known but not allowed.
- [ ] Checklist covers what a good answer needs; weights sensible


### REST API design

Question: Explain the main ideas of a REST API: how URLs and HTTP methods are used, and what idempotent means for PUT.
- (2) URLs name resources (nouns)
- (3) HTTP methods are the actions (GET read, POST create, PUT replace, DELETE remove)
- (3) PUT is idempotent: repeating it leaves the same state, unlike POST
- Model answer: REST uses URLs as nouns for resources and HTTP methods as the actions: GET reads, POST creates, PUT replaces, DELETE removes. PUT is idempotent - repeating it gives the same state - while repeating POST can create duplicates.
- [ ] Checklist covers what a good answer needs; weights sensible


### API authentication basics

Question: What is the difference between authentication and authorisation, and where should API secrets be kept?
- (3) Authentication proves who you are
- (3) Authorisation decides what you may do
- (2) Secrets stay on the server, not in front-end code or public repos
- Model answer: Authentication verifies who the caller is; authorisation decides what that caller is allowed to do. Secrets such as API keys are kept on the server in environment variables, never in front-end code or public repositories.
- [ ] Checklist covers what a good answer needs; weights sensible


### FastAPI basics

Question: Explain how FastAPI turns a Python function into an API endpoint, and what Pydantic models are for.
- (3) A decorator like @app.get('/path') registers the function as the handler
- (1) The returned dict/object is sent as JSON
- (3) Pydantic models validate and parse request data automatically (422 on bad input)
- Model answer: A decorator such as @app.get('/hello') registers the function for that path and method, and the returned value is sent as JSON. Pydantic models validate and parse request bodies automatically and return a 422 error for invalid data.
- [ ] Checklist covers what a good answer needs; weights sensible


### Python functions

Question: Explain the difference between printing a value and returning it from a Python function, and what happens if there is no return.
- (2) print only shows text on the screen; the caller cannot use it
- (3) return hands a value back to the caller
- (3) A function without return gives None
- Model answer: print displays text but the caller cannot use it; return hands a value back to the caller. A function without a return statement returns None.
- [ ] Checklist covers what a good answer needs; weights sensible


### Docker basics

Question: Explain what a Docker image and a container are, and how a container differs from a virtual machine.
- (2) An image is a packaged template of code and dependencies
- (2) A container is a running instance of an image
- (3) Containers share the host kernel; a VM runs its own OS
- Model answer: An image is a packaged template with code and dependencies; a container is a running instance of it. Unlike a virtual machine, containers share the host's kernel, so they are lighter and start faster.
- [ ] Checklist covers what a good answer needs; weights sensible


## 6. Teaching notes (used to ground explanations)


### Python basics
Python programs are built from values (numbers, text, booleans), variables that name them, and control flow (if, for, while) that decides what runs. `/` always gives a float; `//` divides and rounds down.

- [ ] Accurate


### Python functions
A function packages steps behind a name. It returns a value only if it executes `return`; otherwise it returns None. Default arguments are evaluated once, so a mutable default (like a list) is shared between calls.

- [ ] Accurate


### Lists, dicts and sets
Lists keep order and allow duplicates, dicts map keys to values with fast lookup, and sets keep unique items. Choose by the question you need to answer: order, lookup, or uniqueness.

- [ ] Accurate


### Git basics
Git records snapshots. You edit files, stage the changes with `git add`, save them with `git commit`, and share them with `git push`.

- [ ] Accurate


### Command line basics
The command line lets you navigate (cd, ls, pwd), manage files (mkdir, cp, rm) and combine commands with pipes (|), where the output of one command becomes the input of the next.

- [ ] Accurate


### Tables, rows and keys
A relational database stores data in tables of rows and columns. A primary key uniquely identifies each row; a foreign key in another table points to it and links the two tables.

- [ ] Accurate


### SELECT and aliases
SELECT chooses which columns to show and can calculate new values per row; FROM names the table; AS renames a result column. SELECT never changes stored data.

Example: `SELECT name, price * 1.18 AS price_with_gst FROM products`
- [ ] Accurate


### Filtering with WHERE
WHERE keeps only the rows for which the condition is TRUE. AND is evaluated before OR, so use brackets when you mix them. LIKE with % matches patterns; without % it must match the whole value.

Example: `SELECT name FROM customers WHERE (city = 'Lucknow' OR city = 'Varanasi') AND signup_date > '2025-03-01'`
- [ ] Accurate


### NULL and three-valued logic
NULL means 'unknown', not zero or empty text. Any comparison with NULL (even NULL = NULL) is UNKNOWN, and WHERE keeps only TRUE rows. Use IS NULL / IS NOT NULL, and decide explicitly what to do with NULL rows when you use <>.

Example: `SELECT id FROM orders WHERE status <> 'delivered' OR status IS NULL`
- [ ] Accurate


### ORDER BY, LIMIT and DISTINCT
Without ORDER BY the order of rows is not defined, so LIMIT alone returns arbitrary rows. ORDER BY ... DESC LIMIT n gives the top n. DISTINCT removes duplicate result rows across all selected columns.

Example: `SELECT name, price FROM products ORDER BY price DESC LIMIT 3`
- [ ] Accurate


### Aggregate functions
Aggregate functions (COUNT, SUM, AVG, MIN, MAX) turn many rows into one value. They ignore NULLs, except COUNT(*), which counts rows. AVG of 10, 20, NULL is 15.

Example: `SELECT COUNT(*) AS all_orders, COUNT(status) AS with_status FROM orders`
- [ ] Accurate


### GROUP BY
GROUP BY splits rows into groups by the listed columns, and each aggregate is calculated per group, giving one output row per group. Every non-aggregated column in SELECT must be in GROUP BY. Without GROUP BY an aggregate collapses the whole table to one row.

Example: `SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id`
- [ ] Accurate


### HAVING vs WHERE
WHERE filters individual rows before grouping; HAVING filters whole groups after aggregation. Only HAVING can test COUNT(*) or SUM(...). Logical order: FROM, WHERE, GROUP BY, HAVING, SELECT, ORDER BY.

Example: `SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id HAVING COUNT(*) > 1`
- [ ] Accurate


### INNER JOIN
JOIN ... ON combines rows from two tables where the ON condition is true. INNER JOIN keeps only rows that match on both sides. Forgetting the ON condition pairs every row with every row (a cartesian product).

Example: `SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id`
- [ ] Accurate


### LEFT and other outer joins
A LEFT JOIN keeps EVERY row of the left table. Where there is no match, the right-hand columns are NULL. Filtering the right table in WHERE removes those NULL rows and silently turns it into an inner join - put the condition in ON instead. After a LEFT JOIN, count a right-table column (COUNT(o.id)) to get 0 for unmatched rows.

Example: `SELECT c.name, o.id FROM customers c LEFT JOIN orders o ON o.customer_id = c.id`
- [ ] Accurate


### Joining many tables
Joining several tables chains the relationships: each one-to-many join can repeat rows. Sums computed after such a join count a value once per repeat. Count rows after each join, use DISTINCT only when you understand the repeats, and aggregate at the right level.

Example: `SELECT c.name, SUM(o.amount) AS total FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.name`
- [ ] Accurate


### Subqueries
A subquery is a query inside another query. Use one when you need a computed value (like an average) in a condition. NOT IN misbehaves if the subquery returns NULL; NOT EXISTS is safer.

Example: `SELECT name FROM products WHERE price > (SELECT AVG(price) FROM products)`
- [ ] Accurate


### CASE expressions
CASE WHEN ... THEN ... ELSE ... END computes a value per row based on conditions. Without ELSE, unmatched rows get NULL. It does not change stored data.

Example: `SELECT id, CASE WHEN amount >= 500 THEN 'big' ELSE 'small' END AS size FROM orders`
- [ ] Accurate


### INSERT, UPDATE, DELETE
INSERT adds rows, UPDATE changes existing rows, DELETE removes them. UPDATE and DELETE without a WHERE affect every row, so check the WHERE first (try it as a SELECT).

- [ ] Accurate


### Normalisation and schema design
Normalisation means storing each fact once and linking tables with keys, so data cannot become inconsistent. Many-to-many relationships need a junction table.

- [ ] Accurate


### Indexes
An index is an extra structure that makes lookups on a column fast, like a book's index. It speeds up reads that filter, join or sort on that column but slows down inserts and updates and uses space.

- [ ] Accurate


### Transactions and ACID
A transaction groups statements so they succeed or fail together (atomicity). ACID: Atomicity, Consistency, Isolation, Durability. Changes are private to your session until COMMIT.

- [ ] Accurate


### HTTP fundamentals
HTTP is request/response: a client sends a method (GET, POST, PUT, DELETE) and a URL, the server replies with a status code and a body. GET is read-only. 2xx = success, 4xx = client error (401 not authenticated, 403 forbidden, 404 not found), 5xx = server error.

- [ ] Accurate


### REST API design
REST models things as resources with URLs (nouns) and uses HTTP methods as the actions: GET reads, POST creates, PUT replaces (idempotent), PATCH updates part, DELETE removes. Status codes tell the result.

- [ ] Accurate


### API authentication basics
Authentication proves who the caller is (for example with a signed JWT or an API key); authorisation decides what they may do. Secrets live on the server, never in front-end code or public repositories.

- [ ] Accurate


### FastAPI basics
FastAPI maps Python functions to endpoints using decorators like @app.get('/hello'). Type hints and Pydantic models validate input automatically (bad input gets a 422 response) and generate interactive docs.

- [ ] Accurate


### Using a database from Python
From Python you connect, execute SQL, and commit. Always pass values as parameters (`?` or `%s`) instead of formatting strings, to prevent SQL injection. Changes are visible to others only after commit.

- [ ] Accurate


### Docker basics
A Docker image is a packaged template (code plus dependencies); a container is a running instance of an image. Containers share the host kernel, so they start fast and are lighter than virtual machines.

- [ ] Accurate
