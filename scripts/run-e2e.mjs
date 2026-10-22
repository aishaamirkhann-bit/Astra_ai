import { spawn, spawnSync } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backend = path.join(root, "astra-backend");
const frontendPort = Number(process.env.ASTRA_FRONTEND_PORT || 3000);
const backendPort = 8000; // Browser tests call the API at localhost:8000.
const children = new Set();
let playwrightProcess;
let interrupted = false;

function pythonExecutable() {
  if (process.env.ASTRA_BACKEND_PYTHON) return process.env.ASTRA_BACKEND_PYTHON;
  const candidates = process.platform === "win32"
    ? [path.join(backend, ".venv", "Scripts", "python.exe"), path.join(root, ".venv", "Scripts", "python.exe")]
    : [path.join(backend, ".venv", "bin", "python"), path.join(root, ".venv", "bin", "python")];
  return candidates.find((candidate) => spawnSync(candidate, ["--version"], { stdio: "ignore" }).status === 0)
    ?? (process.platform === "win32" ? "python" : "python3");
}

function spawnOwned(command, args, options) {
  const child = spawn(command, args, {
    stdio: "inherit",
    windowsHide: true,
    detached: process.platform !== "win32",
    ...options,
  });
  children.add(child);
  child.once("exit", () => children.delete(child));
  return child;
}

async function assertPortAvailable(port) {
  await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", () => reject(new Error(`E2E port ${port} is already in use; stop that process or choose another frontend port.`)));
    server.listen(port, "127.0.0.1", () => server.close((error) => error ? reject(error) : resolve()));
  });
}

function ensureRunning(child, name) {
  if (child.exitCode !== null) throw new Error(`${name} exited during startup with code ${child.exitCode}.`);
}

async function waitFor(url, child, name) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    ensureRunning(child, name);
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1_000) });
      if (response.ok) return;
    } catch { /* Keep polling until the startup deadline. */ }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`${name} did not become healthy at ${url} within 120 seconds.`);
}

async function terminateTree(child) {
  if (!child || child.exitCode !== null || child.killed) return;
  if (process.platform === "win32" && child.pid) {
    // Playwright and both dev servers can create grandchildren on Windows.
    // Terminate only this runner's recorded process tree.
    const killed = spawnSync("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
    if (killed.status !== 0) child.kill();
  } else if (child.pid) {
    try { process.kill(-child.pid, "SIGTERM"); } catch { child.kill("SIGTERM"); }
    await Promise.race([
      new Promise((resolve) => child.once("exit", resolve)),
      new Promise((resolve) => setTimeout(resolve, 5_000)),
    ]);
    if (child.exitCode === null) {
      try { process.kill(-child.pid, "SIGKILL"); } catch { child.kill("SIGKILL"); }
    }
  }
  if (child.exitCode === null) {
    await Promise.race([
      new Promise((resolve) => child.once("exit", resolve)),
      new Promise((resolve) => setTimeout(resolve, 5_000)),
    ]);
  }
}

process.on("SIGINT", () => { interrupted = true; void terminateTree(playwrightProcess); });
process.on("SIGTERM", () => { interrupted = true; void terminateTree(playwrightProcess); });

let result = 1;
try {
  await assertPortAvailable(backendPort);
  await assertPortAvailable(frontendPort);

  const backendEnv = {
    ...process.env,
    APP_ENV: "development",
    OTP_DEBUG_LOG: "true",
    RESEND_API_KEY: "",
    SMTP_HOST: "",
    SMTP_USERNAME: "",
    SMTP_USER: "",
    SMTP_PASSWORD: "",
  };
  const backendProcess = spawnOwned(pythonExecutable(), ["-m", "uvicorn", "app.main:app", "--port", String(backendPort)], { cwd: backend, env: backendEnv });
  await waitFor(`http://127.0.0.1:${backendPort}/health`, backendProcess, "Backend");

  const frontendProcess = spawnOwned(process.execPath, ["./node_modules/next/dist/bin/next", "dev", "--port", String(frontendPort)], { cwd: root, env: process.env });
  await waitFor(`http://127.0.0.1:${frontendPort}/login`, frontendProcess, "Frontend");

  const playwrightCli = path.join(root, "node_modules", "@playwright", "test", "cli.js");
  playwrightProcess = spawnOwned(process.execPath, [playwrightCli, "test", ...process.argv.slice(2)], { cwd: root, env: process.env });
  const code = await new Promise((resolve) => playwrightProcess.once("exit", (exitCode) => resolve(exitCode ?? 1)));
  result = interrupted ? 130 : code;
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  result = interrupted ? 130 : 1;
} finally {
  for (const child of [...children].reverse()) await terminateTree(child);
}

console.log(`[e2e-runner] Playwright exit code: ${result}`);
process.exitCode = result;
