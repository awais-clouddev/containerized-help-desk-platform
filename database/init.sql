CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    issue TEXT NOT NULL,
    priority VARCHAR(20) NOT NULL CHECK (
        priority IN ('Low', 'Medium', 'High', 'Critical')
    ),
    status VARCHAR(20) DEFAULT 'Open' CHECK (
        status IN ('Open', 'Assigned', 'In Progress', 'Waiting', 'Resolved', 'Closed')
    ),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
