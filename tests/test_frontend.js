const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
    path.join(__dirname, "../frontend/app.js"), "utf8"
);
const response = (data, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data
});
const ticket = name => ({
    id: 1, employee_name: name, issue: "Example issue",
    priority: "High", status: "Open", created_at: "2026-10-15"
});

async function setup() {
    const elements = {};
    const element = id => elements[id] ||= {
        textContent: "", innerHTML: "", value: "", style: {},
        listeners: {},
        addEventListener(event, callback) { this.listeners[event] = callback; },
        reset() {}
    };
    const runtime = {
        Date, AbortController,
        document: {getElementById: element},
        forceTimeout: false,
        setTimeout(callback) {
            if (runtime.forceTimeout) callback();
            return 1;
        },
        clearTimeout() {},
        setInterval() {},
        fetch: async url => {
            if (url.endsWith("/health")) {
                return response({
                    status: "healthy", database: "connected", redis: "connected"
                });
            }
            if (url.endsWith("/dashboard")) {
                return response({
                    total: 1, open: 1, in_progress: 0, resolved: 0, critical: 0
                });
            }
            return response({source: "postgresql", tickets: []});
        }
    };
    const context = vm.createContext(runtime);
    vm.runInContext(source, context);
    await new Promise(resolve => setImmediate(resolve));
    return {elements, runtime, run: code => vm.runInContext(code, context)};
}

(async () => {
    let h = await setup();
    assert.match(h.elements["api-status"].textContent, /API ✓/);
    console.log("PASS: healthy dependency response");

    for (const status of [503, 404]) {
        h = await setup();
        h.runtime.fetch = async () => response({detail: "unavailable"}, status);
        await h.run("checkHealth()");
        assert.match(h.elements["api-status"].textContent, /unavailable/);
        await h.run("loadDashboard()");
        assert.equal(h.elements["total-count"].textContent, "Unavailable");
        await h.run("loadTickets()");
        assert.match(h.elements["ticket-list"].innerHTML, /Unable to load/);
        console.log(`PASS: HTTP ${status} health, statistics and tickets`);
    }

    h = await setup();
    h.runtime.fetch = async () => response({status: "degraded"});
    await h.run("checkHealth()");
    assert.match(h.elements["api-status"].textContent, /unavailable/);
    console.log("PASS: degraded response is not shown as healthy");

    h = await setup();
    h.runtime.fetch = async () => { throw new Error("offline"); };
    await h.run("loadTickets()");
    assert.match(h.elements["ticket-list"].innerHTML, /Unable to load/);
    console.log("PASS: network failure");

    h = await setup();
    h.runtime.forceTimeout = true;
    h.runtime.fetch = async (url, options) => {
        assert.equal(options.signal.aborted, true);
        const error = new Error("timeout");
        error.name = "AbortError";
        throw error;
    };
    await h.run("checkHealth()");
    assert.match(h.elements["api-status"].textContent, /unavailable/);
    console.log("PASS: request timeout");

    h = await setup();
    h.runtime.fetch = async () => ({
        ok: true, json: async () => { throw new Error("Invalid JSON"); }
    });
    await h.run("loadTickets()");
    assert.match(h.elements["ticket-list"].innerHTML, /Unable to load/);
    console.log("PASS: malformed JSON response");

    for (const oldFails of [false, true]) {
        h = await setup();
        const pending = [];
        h.runtime.fetch = url => new Promise((resolve, reject) => {
            pending.push({resolve, reject});
        });
        const older = h.run('loadTickets("older")');
        const newer = h.run('loadTickets("newer")');
        pending[1].resolve(response({
            source: "postgresql", tickets: [ticket("LATEST RESULT")]
        }));
        await newer;
        if (oldFails) pending[0].reject(new Error("old request failed"));
        else pending[0].resolve(response({
            source: "postgresql", tickets: [ticket("OLD RESULT")]
        }));
        await older;
        assert.match(h.elements["ticket-list"].innerHTML, /LATEST RESULT/);
        assert.doesNotMatch(h.elements["ticket-list"].innerHTML, /OLD RESULT/);
        console.log(`PASS: older ${oldFails ? "failure" : "response"} cannot replace latest search`);
    }

    h = await setup();
    h.run('renderTickets([{id:1, employee_name:"<script>alert(1)</script>", issue:"test", priority:"High", status:"Open", created_at:"now"}])');
    assert.doesNotMatch(h.elements["ticket-list"].innerHTML, /<script>/);
    assert.match(h.elements["ticket-list"].innerHTML, /&lt;script&gt;/);
    console.log("PASS: ticket text remains HTML-escaped");

    console.log("All frontend regression scenarios passed.");
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
