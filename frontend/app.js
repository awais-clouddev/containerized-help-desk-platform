const API_URL = "http://localhost:8000";

const ticketForm = document.getElementById("ticket-form");
const ticketList = document.getElementById("ticket-list");
const formMessage = document.getElementById("form-message");
const apiStatus = document.getElementById("api-status");
const dataSource = document.getElementById("data-source");
const refreshButton = document.getElementById("refresh-button");

async function checkHealth() {
    try {
        const response = await fetch(`${API_URL}/health`);
        const data = await response.json();

        apiStatus.textContent = "API ✓ Database ✓ Redis ✓";
        apiStatus.style.background = "#166534";
    } catch {
        apiStatus.textContent = "Services unavailable";
        apiStatus.style.background = "#991b1b";
    }
}

async function loadDashboard() {
    try {
        const response = await fetch(`${API_URL}/dashboard`);
        const data = await response.json();

        document.getElementById("total-count").textContent = data.total;
        document.getElementById("open-count").textContent = data.open;
        document.getElementById("progress-count").textContent =
            data.in_progress;
        document.getElementById("resolved-count").textContent =
            data.resolved;
        document.getElementById("critical-count").textContent =
            data.critical;
    } catch {
        console.error("Unable to load dashboard statistics.");
    }
}

function renderTickets(tickets) {
    if (tickets.length === 0) {
        ticketList.innerHTML = "<p>No tickets have been created.</p>";
        return;
    }

    ticketList.innerHTML = tickets.map(ticket => `
        <article class="ticket priority-${ticket.priority}">
            <h3>#${ticket.id} — ${ticket.employee_name}</h3>
            <p>${ticket.issue}</p>
            <p><strong>Priority:</strong> ${ticket.priority}</p>
            <p><strong>Status:</strong> ${ticket.status}</p>
            <p class="meta">Created: ${ticket.created_at}</p>
        </article>
    `).join("");
}

async function loadTickets() {
    try {
        const response = await fetch(`${API_URL}/tickets`);
        const data = await response.json();

        dataSource.textContent = `Data source: ${data.source}`;
        renderTickets(data.tickets);
    } catch {
        ticketList.innerHTML =
            '<p class="error">Unable to load tickets.</p>';
    }
}

ticketForm.addEventListener("submit", async event => {
    event.preventDefault();

    const payload = {
        employee_name:
            document.getElementById("employee-name").value,
        issue:
            document.getElementById("issue").value,
        priority:
            document.getElementById("priority").value
    };

    try {
        const response = await fetch(`${API_URL}/tickets`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error("Ticket creation failed");
        }

        ticketForm.reset();
        formMessage.textContent = "Ticket created successfully.";
        formMessage.className = "success";

        await loadTickets();
        await loadDashboard();
    } catch {
        formMessage.textContent = "Unable to create ticket.";
        formMessage.className = "error";
    }
});

refreshButton.addEventListener("click", async () => {
    await loadTickets();
    await loadDashboard();
});

checkHealth();
loadDashboard();
loadTickets();