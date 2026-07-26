CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    issue TEXT NOT NULL,
    priority VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'Open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);