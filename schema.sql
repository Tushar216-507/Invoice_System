CREATE DATABASE IF NOT EXISTS invoice_uat_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE invoice_uat_db;

CREATE TABLE IF NOT EXISTS departments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  department_name VARCHAR(100) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_departments_name (department_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(120) NOT NULL,
  name VARCHAR(120) NOT NULL,
  otp VARCHAR(64) NULL,
  otp_created_at DATETIME NULL,
  otp_attempts INT NOT NULL DEFAULT 0,
  role VARCHAR(50) NOT NULL DEFAULT 'user',
  department VARCHAR(100) NOT NULL DEFAULT 'marketing',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_users_email (email),
  KEY idx_users_role (role),
  KEY idx_users_department (department),
  KEY idx_users_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS vendors (
  id INT AUTO_INCREMENT PRIMARY KEY,
  vendor_name VARCHAR(255) NOT NULL,
  vendor_status ENUM('Active', 'Inactive') NOT NULL DEFAULT 'Active',
  department VARCHAR(100) NOT NULL,
  description TEXT NULL,
  shortforms_of_vendors VARCHAR(50) NULL,
  vendor_address TEXT NOT NULL,
  PAN VARCHAR(20) NULL,
  GSTIN VARCHAR(20) NULL,
  POC VARCHAR(255) NULL,
  POC_number VARCHAR(30) NULL,
  POC_email VARCHAR(255) NULL,
  deleted_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_vendors_name (vendor_name),
  KEY idx_vendors_department (department),
  KEY idx_vendors_status (vendor_status),
  KEY idx_vendors_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS invoices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  invoice_date DATE NOT NULL,
  date_received DATE NOT NULL,
  vendor VARCHAR(255) NOT NULL,
  mobile_no VARCHAR(30) NULL,
  invoice_number VARCHAR(100) NOT NULL,
  po_approved VARCHAR(20) NOT NULL DEFAULT 'No',
  po_number VARCHAR(100) NULL,
  po_expiry_date DATE NULL,
  agreement_signed VARCHAR(20) NOT NULL DEFAULT 'No',
  agreement_signed_date DATE NULL,
  date_submission DATE NOT NULL,
  approved_by VARCHAR(255) NULL,
  created_by VARCHAR(255) NOT NULL,
  tag1 VARCHAR(255) NULL,
  tag2 VARCHAR(255) NULL,
  invoice_amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  gst DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  total_amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  isd VARCHAR(20) NOT NULL DEFAULT 'No',
  msme VARCHAR(20) NOT NULL DEFAULT 'No',
  hod_values VARCHAR(255) NULL,
  ceo_values VARCHAR(255) NULL,
  reviewed_by VARCHAR(255) NULL,
  invoice_cleared VARCHAR(20) NOT NULL DEFAULT 'No',
  invoice_cleared_date DATE NULL,
  department VARCHAR(100) NOT NULL DEFAULT 'marketing',
  deleted_at DATETIME NULL,
  deleted_by VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_invoices_invoice_number (invoice_number),
  KEY idx_invoices_date (invoice_date),
  KEY idx_invoices_vendor (vendor),
  KEY idx_invoices_department (department),
  KEY idx_invoices_cleared (invoice_cleared),
  KEY idx_invoices_po_number (po_number),
  KEY idx_invoices_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS purchase_orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  po_number VARCHAR(100) NULL,
  vendor_id INT NOT NULL,
  po_date DATE NULL,
  total_amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  cgst_amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  sgst_amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  grand_total DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  pdf_path VARCHAR(255) NULL,
  approved_by INT NULL,
  reviewed_by INT NULL,
  created_by INT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_purchase_orders_po_number (po_number),
  KEY idx_purchase_orders_vendor_id (vendor_id),
  KEY idx_purchase_orders_po_date (po_date),
  KEY idx_purchase_orders_created_at (created_at),
  CONSTRAINT fk_purchase_orders_vendor
    FOREIGN KEY (vendor_id) REFERENCES vendors (id)
    ON UPDATE CASCADE
    ON DELETE RESTRICT,
  CONSTRAINT fk_purchase_orders_approved_by
    FOREIGN KEY (approved_by) REFERENCES users (id)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  CONSTRAINT fk_purchase_orders_reviewed_by
    FOREIGN KEY (reviewed_by) REFERENCES users (id)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  CONSTRAINT fk_purchase_orders_created_by
    FOREIGN KEY (created_by) REFERENCES users (id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS purchase_order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  po_id INT NOT NULL,
  product_description TEXT NOT NULL,
  quantity DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  rate DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  line_total DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_purchase_order_items_po_id (po_id),
  CONSTRAINT fk_purchase_order_items_po
    FOREIGN KEY (po_id) REFERENCES purchase_orders (id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS dropdown_values (
  id INT AUTO_INCREMENT PRIMARY KEY,
  type VARCHAR(100) NOT NULL,
  value VARCHAR(255) NOT NULL,
  department VARCHAR(100) NOT NULL DEFAULT 'marketing',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_dropdown_values_type_value_department (type, value, department),
  KEY idx_dropdown_values_type (type),
  KEY idx_dropdown_values_department (department),
  KEY idx_dropdown_values_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS vendor_requests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  vendor_name VARCHAR(255) NOT NULL,
  description TEXT NULL,
  department VARCHAR(100) NULL,
  vendor_address TEXT NULL,
  PAN VARCHAR(20) NULL,
  GSTIN VARCHAR(20) NULL,
  POC VARCHAR(255) NULL,
  POC_number VARCHAR(30) NULL,
  POC_email VARCHAR(255) NULL,
  requested_by_user_id INT NULL,
  requested_by_name VARCHAR(255) NULL,
  requested_by_email VARCHAR(255) NULL,
  status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
  request_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_by_user_id INT NULL,
  reviewed_by_name VARCHAR(255) NULL,
  reviewed_date DATETIME NULL,
  rejection_reason TEXT NULL,
  KEY idx_vendor_requests_status (status),
  KEY idx_vendor_requests_department (department),
  KEY idx_vendor_requests_request_date (request_date),
  CONSTRAINT fk_vendor_requests_requested_by
    FOREIGN KEY (requested_by_user_id) REFERENCES users (id)
    ON UPDATE CASCADE
    ON DELETE SET NULL,
  CONSTRAINT fk_vendor_requests_reviewed_by
    FOREIGN KEY (reviewed_by_user_id) REFERENCES users (id)
    ON UPDATE CASCADE
    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS activity_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_email VARCHAR(255) NOT NULL,
  action TEXT NOT NULL,
  department VARCHAR(100) NOT NULL DEFAULT 'marketing',
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_activity_log_user_email (user_email),
  KEY idx_activity_log_department (department),
  KEY idx_activity_log_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS activity_of_po (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_email VARCHAR(255) NOT NULL,
  po_number VARCHAR(100) NULL,
  action TEXT NOT NULL,
  action_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_activity_of_po_user_email (user_email),
  KEY idx_activity_of_po_po_number (po_number),
  KEY idx_activity_of_po_action_timestamp (action_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO departments (department_name)
VALUES ('marketing');
