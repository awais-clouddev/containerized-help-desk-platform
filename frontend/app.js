async function checkHealth() {
    const response = await fetch("http://localhost:8000/health");
    const data = await response.json();

    document.getElementById("output").textContent =
        JSON.stringify(data, null, 2);
}
EOFcat > frontend/app.js <<'EOF'
async function checkHealth() {
    const response = await fetch("http://localhost:8000/health");
    const data = await response.json();

    document.getElementById("output").textContent =
        JSON.stringify(data, null, 2);
}
