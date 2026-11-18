import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import http from "node:http";
import { execSync, spawn, spawnSync } from "node:child_process";

const LLAMA_EXE = "C:\\llama.cpp\\llama-server.exe";
const LLAMA_DIR = "C:\\llama.cpp";
const MODELS_DIR = "C:\\models";
const SESSIONS_DIR = path.join(os.homedir(), ".pi", "agent", "sessions");
const PI_CMD = path.join(os.homedir(), ".pi", "agent", "bin", "pi.cmd");
const REPORT_PATH = "C:\\Users\\6700XT\\6700XT-Afterburner\\REPORTS\\PI_MODEL_SMOKE_TEST_REPORT.md";
const PROMPT = "What is the name of this computer?";

function killLlama() {
  try { execSync("taskkill /F /IM llama-server.exe", { stdio: "ignore" }); } catch {}
}

function checkHealth() {
  return new Promise((resolve) => {
    const req = http.get("http://127.0.0.1:8080/health", { timeout: 1500 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

async function waitHealth(timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await checkHealth()) return true;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

function getLatestSession() {
  let latest = null;
  function walk(dir) {
    if (!fs.existsSync(dir)) return;
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) walk(full);
      else if (e.name.endsWith(".jsonl")) {
        const mtime = fs.statSync(full).mtimeMs;
        if (!latest || mtime > latest.mtime) latest = { path: full, mtime };
      }
    }
  }
  walk(SESSIONS_DIR);
  return latest;
}

function parseSession(filePath) {
  let toolCalls = 0, toolResults = 0, finalText = "";
  const lines = fs.readFileSync(filePath, "utf-8").split(/\r?\n/).filter(Boolean);
  for (const line of lines) {
    let obj;
    try { obj = JSON.parse(line); } catch { continue; }
    if (obj.type === "message" && obj.message) {
      if (obj.message.role === "assistant") {
        for (const p of obj.message.content || []) {
          if (p.type === "toolCall" || p.type === "tool_call") toolCalls++;
          else if (p.type === "text") finalText = (p.text || "").trim();
        }
      } else if (obj.message.role === "toolResult") {
        toolResults++;
      }
    }
  }
  return { toolCalls, toolResults, finalText };
}

async function runCase(ggufName, thinking, extraArgs) {
  const modelPath = path.join(MODELS_DIR, ggufName);
  if (!fs.existsSync(modelPath)) {
    return { model: ggufName, thinking, status: "MISSING", toolCalls: 0, elapsed: 0, reply: "File not found" };
  }
  const alias = path.basename(modelPath, path.extname(modelPath)).toLowerCase();
  killLlama();
  await new Promise((r) => setTimeout(r, 500));

  const args = [
    "-m", modelPath,
    "-ngl", "99",
    "-c", "16384",
    "-fa", "1",
    "--jinja",
    "--host", "127.0.0.1",
    "--port", "8080",
    "--alias", alias,
    ...extraArgs
  ];
  const srv = spawn(LLAMA_EXE, args, { cwd: LLAMA_DIR, stdio: "ignore", windowsHide: true });

  try {
    const ok = await waitHealth(45000);
    if (!ok) {
      return { model: ggufName, thinking, status: "SERVER_FAIL", toolCalls: 0, elapsed: 0, cmd: `${LLAMA_EXE} ${args.join(" ")}`, reply: "Health check timeout" };
    }

    const before = getLatestSession();
    const beforeMtime = before ? before.mtime : 0;
    const env = { ...process.env, PATH: `C:\\Program Files\\nodejs;${path.dirname(PI_CMD)};${process.env.PATH || ""}` };

    const t0 = performance.now();
    const res = spawnSync(PI_CMD, ["--model", `local/${alias}`, "--thinking", thinking, "--print", PROMPT], {
      cwd: "C:\\Users\\6700XT",
      env,
      shell: true,
      encoding: "utf-8",
      timeout: 90000,
      input: ""
    });
    const elapsed = ((performance.now() - t0) / 1000).toFixed(2);

    const after = getLatestSession();
    let parsed = { toolCalls: 0, toolResults: 0, finalText: (res.stdout || "").trim() };
    if (after && after.mtime > beforeMtime) {
      parsed = parseSession(after.path);
    }

    const replyText = parsed.finalText || (res.stdout || "").trim() || (res.stderr || "").trim();
    const passed = parsed.toolCalls > 0 && replyText.toUpperCase().includes("SANDBOX");
    return {
      model: ggufName,
      thinking,
      status: passed ? "PASS" : "FAIL",
      toolCalls: parsed.toolCalls,
      toolResults: parsed.toolResults,
      elapsed,
      cmd: `${LLAMA_EXE} ${args.join(" ")}`,
      reply: replyText.replace(/\s+/g, " ").slice(0, 180)
    };
  } finally {
    try { srv.kill(); } catch {}
    killLlama();
  }
}

const cases = [
  ["Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", "off", []],
  ["Qwen2.5-14B-Instruct-Q4_K_M.gguf", "off", []],
  ["qwen2.5-coder-7b-instruct-q4_k_m.gguf", "off", []],
  ["DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf", "off", []],
  ["Mistral-Nemo-Instruct-2407-Q4_K_M.gguf", "off", []],
  ["Qwen3-8B-Q4_K_M.gguf", "off", ["--reasoning-budget", "0"]],
  ["Qwen3-8B-Q4_K_M.gguf", "low", ["--reasoning-budget", "256"]],
  ["Qwen3-14B-Q4_K_M.gguf", "off", ["--reasoning-budget", "0"]],
  ["Qwen3-14B-Q4_K_M.gguf", "low", ["--reasoning-budget", "256"]]
];

const results = [];
for (const [gguf, think, extra] of cases) {
  console.log(`=== Testing ${gguf} (thinking=${think}) ===`);
  const r = await runCase(gguf, think, extra);
  console.log(JSON.stringify(r));
  results.push(r);
}

const md = [
  "# RX 6700 XT — Pi Agent Tool-Calling Smoke Test Matrix",
  "",
  `**Prompt:** \`${PROMPT}\`  `,
  "**Expected Ground Truth:** Tool call (`powershell`) returning `SANDBOX`",
  "",
  "| Model | Thinking | Status | Tool Calls | Time (s) | Reply Preview |",
  "| :--- | :---: | :---: | :---: | :---: | :--- |",
  ...results.map((r) => `| \`${r.model}\` | \`${r.thinking}\` | **${r.status}** | ${r.toolCalls} | ${r.elapsed} | ${r.reply} |`),
  "",
  "## Exact `llama-server.exe` Command Lines Tested",
  ...results.filter((r) => r.cmd).map((r) => `- **\`${r.model}\` (\`thinking=${r.thinking}\`):** \`${r.cmd}\``),
  ""
].join("\n");

fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
fs.writeFileSync(REPORT_PATH, md, "utf-8");
console.log(`WROTE REPORT: ${REPORT_PATH}`);
