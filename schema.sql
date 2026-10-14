-- =====================================================================
-- schema.sql : Supermarket Management System
-- Target: MySQL 5.7+ / 8.x (InnoDB, required for foreign keys)
-- =====================================================================

CREATE DATABASE IF NOT EXISTS supermarket_db;
USE supermarket_db;

-- ---------------------------------------------------------------------
-- Products: catalogue and live stock levels
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Products (
    ProductID   INT AUTO_INCREMENT PRIMARY KEY,
    ProductName VARCHAR(255) NOT NULL,
    Category    VARCHAR(255),
    Price       DECIMAL(10, 2),   -- Exact decimal type, avoids float rounding errors on money
    Stock       INT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Customers: login accounts
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Customers (
    CustomerID   INT AUTO_INCREMENT PRIMARY KEY,
    CustomerName VARCHAR(255) NOT NULL,
    PhoneNumber  VARCHAR(15)  NOT NULL,
    Address      TEXT         NOT NULL,
    Password     VARCHAR(255) NOT NULL  -- Stores '<32-char hex salt>$<64-char SHA-256 hex>' (97 chars); 255 leaves room for stronger schemes later
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Transactions: one row per purchase
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Transactions (
    TransactionID   INT AUTO_INCREMENT PRIMARY KEY,
    CustomerID      INT,
    ProductID       INT,
    Quantity        INT,
    TotalPrice      DECIMAL(10, 2),
    TransactionDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Set automatically when the row is inserted

    -- ON DELETE RESTRICT (explicit, same as MySQL's default behaviour):
    -- a product that has been sold cannot be deleted, which protects purchase history.
    -- To retire a product, set Stock = 0 rather than deleting it.
    -- ON DELETE CASCADE is deliberately NOT used: deleting a product would silently
    -- erase its sales records and corrupt revenue reporting.
    -- ON DELETE SET NULL is also possible, but the history would lose the product reference.
    FOREIGN KEY (ProductID)  REFERENCES Products(ProductID)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    -- Same reasoning for customers: accounts with purchase history cannot be removed,
    -- so there is an audit trail for every sale.
    FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
-- SAMPLE DATA (for reviewers / quick testing only; remove in production)
-- =====================================================================

INSERT INTO Products (ProductName, Category, Price, Stock) VALUES
    ('Basmati Rice 1kg',  'Grains',    89.50, 120),
    ('Whole Milk 1L',     'Dairy',     62.00,  80),
    ('Brown Bread Loaf',  'Bakery',    45.00,  50),
    ('Bananas (dozen)',   'Fruits',    58.00,  65),
    ('Orange Juice 1L',   'Beverages', 110.00, 40);

-- Demo customers. Passwords are stored in the same 'salt$sha256(salt + password)' format
-- the Python app uses, so these accounts can log in right away:
--   CustomerID 1 -> password: Alice@123
--   CustomerID 2 -> password: Bob@12345
-- SHA2(..., 256) returns lowercase hex, matching hashlib.sha256(...).hexdigest().
INSERT INTO Customers (CustomerName, PhoneNumber, Address, Password) VALUES
    ('Alice Sharma', '9876543210', '12 MG Road, Hubballi, Karnataka',
        CONCAT('a1b2c3d4e5f60718293a4b5c6d7e8f90', '$',
               SHA2(CONCAT('a1b2c3d4e5f60718293a4b5c6d7e8f90', 'Alice@123'), 256))),
    ('Bob Patil',    '9123456780', '45 Gokul Road, Hubballi, Karnataka',
        CONCAT('0f9e8d7c6b5a49382716f5e4d3c2b1a0', '$',
               SHA2(CONCAT('0f9e8d7c6b5a49382716f5e4d3c2b1a0', 'Bob@12345'), 256)));