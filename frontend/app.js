const API_URL = "/api";
const ticketForm = document.getElementById("ticket-form");
const ticketList = document.getElementById("ticket-list");
const formMessage = document.getElementById("form-message");
const apiStatus = document.getElementById("api-status");
const dataSource = document.getElementById("data-source");
const refreshButton = document.getElementById("refresh-button");
const searchBox = document.getElementById("search-box");

const allowedPriorities = ["Low", "Medium", "High", "Critical"];
const statisticIds = {
    total: "total-count",
    open: "open-count",
    in_progress: "progress-count",
    resolved: "resolved-count",
    critical: "critical-count"
};
let latestTicketRequest = 0;
let submitting = false;

function escapeHTML(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function getPriorityClass(priority) {
    return allowedPriorities.includes(priority)
        ? `priority-${priority}` : "priority-Low";
}

async function requestJSON(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
        const response = await fetch(`${API_URL}${path}`, {
            ...options,
            signal: controller.signal
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } finally {
        clearTimeout(timer);
    }
}

async function checkHealth() {
    try {
        const data = await requestJSON("/health");
        if (data.status !== "healthy" ||
            data.database !== "connected" || data.redis !== "connected") {
            throw new Error("Dependencies unavailable");
        }
        apiStatus.textContent = "API ✓ Database ✓ Redis ✓";
        apiStatus.style.background = "#166534";
    } catch {
        apiStatus.textContent = "Services unavailable — check platform health";
        apiStatus.style.background = "#991b1b";
    }
}

async function loadDashboard() {
    try {
        const data = await requestJSON("/dashboard");
        for (const key of Object.keys(statisticIds)) {
            if (!Number.isInteger(data[key]) || data[key] < 0) {
                throw new Error("Invalid statistics response");
            }
        }
        for (const [key, id] of Object.entries(statisticIds)) {
            document.getElementById(id).textContent = data[key];
        }
    } catch {
        for (const id of Object.values(statisticIds)) {
            document.getElementById(id).textContent = "Unavailable";
        }
    }
}

function renderTickets(tickets) {
    if (tickets.length === 0) {
        ticketList.innerHTML = "<p>No matching tickets.</p>";
        return;
    }
    ticketList.innerHTML = tickets.map(ticket => `
        <article class="ticket ${getPriorityClass(ticket.priority)}">
            <h3>#${escapeHTML(ticket.id)} — ${escapeHTML(ticket.employee_name)}</h3>
            <p>${escapeHTML(ticket.issue)}</p>
            <p><strong>Priority:</strong> ${escapeHTML(ticket.priority)}</p>
            <p><strong>Status:</strong> ${escapeHTML(ticket.status)}</p>
            <p class="meta">Created: ${escapeHTML(ticket.created_at)}</p>
        </article>
    `).join("");
}

async function loadTickets(search = "") {
    const request = ++latestTicketRequest;
    try {
        const data = await requestJSON(`/tickets?search=${encodeURIComponent(search)}`);
        if (!data || !Array.isArray(data.tickets)) {
            throw new Error("Invalid tickets response");
        }
        if (request !== latestTicketRequest) return;
        dataSource.textContent = `Data source: ${data.source}`;
        renderTickets(data.tickets);
    } catch {
        if (request !== latestTicketRequest) return;
        dataSource.textContent = "Data source: unavailable";
        ticketList.innerHTML = '<p class="error">Unable to load tickets. Try Refresh.</p>';
    }
}

ticketForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (submitting) return;
    submitting = true;
    formMessage.textContent = "Creating ticket...";
    try {
        await requestJSON("/tickets", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                employee_name: document.getElementById("employee-name").value,
                issue: document.getElementById("issue").value,
                priority: document.getElementById("priority").value
            })
        });
        ticketForm.reset();
        formMessage.textContent = "Ticket created successfully.";
        formMessage.className = "success";
        await Promise.all([
            loadTickets(searchBox.value), loadDashboard(), checkHealth()
        ]);
    } catch {
        formMessage.textContent =
            "Creation could not be confirmed. Refresh the list before retrying.";
        formMessage.className = "error";
    } finally {
        submitting = false;
    }
});

refreshButton.addEventListener("click", async () => {
    await Promise.all([
        loadTickets(searchBox.value), loadDashboard(), checkHealth()
    ]);
});
searchBox.addEventListener("input", () => loadTickets(searchBox.value));

checkHealth();
loadDashboard();
loadTickets();
setInterval(checkHealth, 30000);
