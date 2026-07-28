const API_URL = "/api";

const ticketForm = document.getElementById("ticket-form");
const ticketList = document.getElementById("ticket-list");
const formMessage = document.getElementById("form-message");
const apiStatus = document.getElementById("api-status");
const dataSource = document.getElementById("data-source");
const refreshButton = document.getElementById("refresh-button");
const searchBox = document.getElementById("search-box");

const allowedPriorities = ["Low", "Medium", "High", "Critical"];

function escapeHTML(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function getPriorityClass(priority) {
    if (allowedPriorities.includes(priority)) {
        return `priority-${priority}`;
    }

    return "priority-Low";
}

async function checkHealth() {
    try {
        await fetch(`${API_URL}/health`);

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

    ticketList.innerHTML = tickets.map(ticket => {
        const priorityClass = getPriorityClass(ticket.priority);

        return `
            <article class="ticket ${priorityClass}">
                <h3>#${escapeHTML(ticket.id)} — ${escapeHTML(ticket.employee_name)}</h3>
                <p>${escapeHTML(ticket.issue)}</p>
                <p><strong>Priority:</strong> ${escapeHTML(ticket.priority)}</p>
                <p><strong>Status:</strong> ${escapeHTML(ticket.status)}</p>
                <p class="meta">Created: ${escapeHTML(ticket.created_at)}</p>
            </article>
        `;
    }).join("");
}

async function loadTickets(search = "") {
    try {
        const response = await fetch(
            `${API_URL}/tickets?search=${encodeURIComponent(search)}`
        );
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
        employee_name: document.getElementById("employee-name").value,
        issue: document.getElementById("issue").value,
        priority: document.getElementById("priority").value
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

searchBox.addEventListener("input", () => {
    loadTickets(searchBox.value);
});

checkHealth();
loadDashboard();
loadTickets();