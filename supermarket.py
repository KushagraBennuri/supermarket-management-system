import os
import hmac
import hashlib
from contextlib import closing

import pymysql  # MySQL library for database connectivity
from tabulate import tabulate  # For displaying tables in a formatted way

# ---------- Configuration (from environment variables) ----------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "supermarket_db")
STAFF_PASSWORD = os.getenv("STAFF_PASSWORD", "")  # Staff login is disabled if empty


# ---------- Password hashing ----------
def hash_password(password):
    """Returns 'salt$sha256hex' for the given password using a random 16-byte salt."""
    salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(stored, password):
    """Checks a plaintext password against a stored 'salt$hash' string."""
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False  # Legacy/plaintext or malformed value
    candidate = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, digest)


# ---------- Database ----------
def connect_to_db(database=None):
    """
    Establish a connection to the MySQL database.
    Returns a connection object.
    """
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=database,
        autocommit=False,
        port=3306
    )


def get_connection():
    """Connection to the application database (DB_NAME)."""
    return connect_to_db(DB_NAME)


def initialize_database():
    """
    Initializes the database and creates required tables if they do not exist:
    - `Products`: Stores product details
    - `Customers`: Stores customer information
    - `Transactions`: Tracks transactions for purchases
    """
    with closing(connect_to_db()) as conn, conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
        cursor.execute(f"USE `{DB_NAME}`")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Products (
                ProductID INT AUTO_INCREMENT PRIMARY KEY,
                ProductName VARCHAR(255) NOT NULL,
                Category VARCHAR(255),
                Price DECIMAL(10, 2),
                Stock INT
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Customers (
                CustomerID INT AUTO_INCREMENT PRIMARY KEY,
                CustomerName VARCHAR(255) NOT NULL,
                PhoneNumber VARCHAR(15) NOT NULL,
                Address TEXT NOT NULL,
                Password VARCHAR(255) NOT NULL  -- Stores 'salt$sha256hash'
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Transactions (
                TransactionID INT AUTO_INCREMENT PRIMARY KEY,
                CustomerID INT,
                ProductID INT,
                Quantity INT,
                TotalPrice DECIMAL(10, 2),
                TransactionDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ProductID) REFERENCES Products(ProductID),
                FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID)
            );
        ''')


# ---------- Input validation ----------
def get_positive_int(prompt):
    """Prompts the user for a positive integer and validates the input."""
    while True:
        try:
            value = int(input(prompt))
            if value < 0:
                raise ValueError("Value cannot be negative.")
            return value
        except ValueError as e:
            print(e)


def get_positive_float(prompt):
    """Prompts the user for a positive float and validates the input."""
    while True:
        try:
            value = float(input(prompt))
            if value < 0:
                raise ValueError("Value cannot be negative.")
            return value
        except ValueError as e:
            print(e)


# ---------- Data access ----------
def view_products():
    """Fetches and returns all products from the Products table."""
    with closing(get_connection()) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Products")
        return cursor.fetchall()


def search_product_by_name(name):
    """Search for products that match the given name (partial or full)."""
    with closing(get_connection()) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Products WHERE ProductName LIKE %s", ("%" + name + "%",))
        return cursor.fetchall()


def purchase_product(customer_id, product_id, quantity):
    """
    Purchases a product atomically:
    - Locks the product row and checks availability.
    - Reduces stock and records the transaction in a single DB transaction.
    Returns the total price, or None if the purchase fails.
    """
    conn = get_connection()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT Price, Stock FROM Products WHERE ProductID = %s FOR UPDATE",
                (product_id,)
            )
            product = cursor.fetchone()

            if not product or quantity <= 0 or quantity > product[1]:
                conn.rollback()
                return None

            price = product[0]
            total_price = price * quantity

            cursor.execute(
                "UPDATE Products SET Stock = Stock - %s WHERE ProductID = %s",
                (quantity, product_id)
            )
            cursor.execute('''
                INSERT INTO Transactions (CustomerID, ProductID, Quantity, TotalPrice)
                VALUES (%s, %s, %s, %s)
            ''', (customer_id, product_id, quantity, total_price))

        conn.commit()
        return total_price
    except pymysql.MySQLError as e:
        conn.rollback()
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()


def add_product(name, category, price, stock):
    """Adds a new product to the Products table."""
    with closing(get_connection()) as conn, conn.cursor() as cursor:
        cursor.execute('''
            INSERT INTO Products (ProductName, Category, Price, Stock)
            VALUES (%s, %s, %s, %s)
        ''', (name, category, price, stock))


def remove_product(product_id):
    """Removes a product from the Products table based on its ProductID."""
    with closing(get_connection()) as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM Products WHERE ProductID = %s", (product_id,))


def update_stock(product_id, new_stock):
    """Updates the stock for a specific product."""
    with closing(get_connection()) as conn, conn.cursor() as cursor:
        cursor.execute("UPDATE Products SET Stock = %s WHERE ProductID = %s", (new_stock, product_id))


def view_transactions():
    """Fetches and returns all transactions from the Transactions table."""
    with closing(get_connection()) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Transactions")
        return cursor.fetchall()


def view_users():
    """Fetches and returns all customers (excluding passwords)."""
    with closing(get_connection()) as conn, conn.cursor() as cursor:
        cursor.execute("SELECT CustomerID, CustomerName, PhoneNumber, Address FROM Customers")
        return cursor.fetchall()


def display_table(data, headers, empty_message="No data available"):
    """
    Utility function to display data in a tabulated format using tabulate.
    If no data, print an empty message.
    """
    if data:
        print(tabulate(data, headers, tablefmt="grid"))
    else:
        print(empty_message)


# ---------- Customer authentication ----------
def customer_login():
    """
    Handles customer login by verifying CustomerID and password.
    Returns the CustomerID on success, or None if login fails / user goes back.
    """
    while True:
        print("\nCustomer Login")
        print("1. Login")
        print("2. Back to Main Menu")
        choice = input("Enter your choice: ")

        if choice == "1":
            customer_id = get_positive_int("Enter your CustomerID: ")
            password = input("Enter your password: ")

            with closing(get_connection()) as conn, conn.cursor() as cursor:
                cursor.execute("SELECT Password FROM Customers WHERE CustomerID = %s", (customer_id,))
                row = cursor.fetchone()

            if row and verify_password(row[0], password):
                print("Login successful.")
                return customer_id
            print("Invalid CustomerID or password.")
        elif choice == "2":
            return None
        else:
            print("Invalid choice. Please try again.")


def sign_up():
    """Handles customer sign-up by adding a new record to the Customers table."""
    customer_name = input("Enter your name: ")
    phone_number = input("Enter your phone number: ")
    address = input("Enter your address: ")
    password = input("Enter your password: ")

    with closing(get_connection()) as conn, conn.cursor() as cursor:
        cursor.execute('''
            INSERT INTO Customers (CustomerName, PhoneNumber, Address, Password)
            VALUES (%s, %s, %s, %s)
        ''', (customer_name, phone_number, address, hash_password(password)))
        new_id = cursor.lastrowid

    print(f"Sign-up successful. Your CustomerID is {new_id}. You can now login.")


# ---------- Menus ----------
def customer_menu():
    customer_id = None  # None means not logged in

    while True:
        logged_in = customer_id is not None
        print("\nCustomer Menu")
        if not logged_in:
            print("1. Login")
            print("2. Sign Up")
        else:
            print("1. View Products")
            print("2. Search Product by Name")
            print("3. Purchase Product")
            print("4. Logout")
        print("5. Exit")
        choice = input("Enter your choice: ")

        if choice == "1" and not logged_in:
            customer_id = customer_login()
        elif choice == "2" and not logged_in:
            sign_up()
        elif choice == "1" and logged_in:
            products = view_products()
            display_table(products, ["Product ID", "Product Name", "Category", "Price", "Stock"])
        elif choice == "2" and logged_in:
            search_query = input("Enter product name to search: ")
            results = search_product_by_name(search_query)
            display_table(results, ["Product ID", "Product Name", "Category", "Price", "Stock"], "No products found.")
        elif choice == "3" and logged_in:
            product_id = get_positive_int("Enter the ProductID to purchase: ")
            quantity = get_positive_int("Enter the quantity: ")
            total_price = purchase_product(customer_id, product_id, quantity)
            if total_price is not None:
                print(f"Purchase successful. Total Price: ${total_price:.2f}")
            else:
                print("Purchase failed. Either product does not exist or insufficient stock.")
        elif choice == "4" and logged_in:
            customer_id = None
            print("Logged out successfully.")
        elif choice == "5":
            break
        else:
            print("Invalid choice. Please try again.")


def staff_menu():
    if not STAFF_PASSWORD:
        print("Staff login is disabled: STAFF_PASSWORD environment variable is not set.")
        return

    entered = input("Enter Staff Password: ")
    if not hmac.compare_digest(entered.encode("utf-8"), STAFF_PASSWORD.encode("utf-8")):
        print("Invalid Password. Please Try again")
        return

    print("Login successful.")
    while True:
        print("\nStaff Menu")
        print("1. Add Product")
        print("2. Update Stock")
        print("3. View Products")
        print("4. View Transactions")
        print("5. View Customers")
        print("6. Exit")
        choice = input("Enter your choice: ")

        if choice == "1":
            name = input("Enter product name: ")
            category = input("Enter product category: ")
            price = get_positive_float("Enter product price: ")
            stock = get_positive_int("Enter product stock: ")
            add_product(name, category, price, stock)
            print("Product added successfully.")
        elif choice == "2":
            product_id = get_positive_int("Enter ProductID to update stock: ")
            new_stock = get_positive_int("Enter new stock value: ")
            update_stock(product_id, new_stock)
            print("Stock updated successfully.")
        elif choice == "3":
            products = view_products()
            display_table(products, ["Product ID", "Product Name", "Category", "Price", "Stock"])
        elif choice == "4":
            transactions = view_transactions()
            display_table(transactions, ["Transaction ID", "Customer ID", "Product ID", "Quantity",
                                         "Total Price", "Transaction Date"])
        elif choice == "5":
            users = view_users()
            display_table(users, ["CustomerID", "CustomerName", "PhoneNumber", "Address"])
        elif choice == "6":
            break
        else:
            print("Invalid choice. Please try again.")
