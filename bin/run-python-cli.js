#!/usr/bin/env node
import { fileURLToPath } from "node:url";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";

const MINIMUM_PYTHON = [3, 11];

function packageRoot() {
  return path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
}

function pythonCandidates() {
  const candidates = [];
  if (process.env.PYTHON) candidates.push(process.env.PYTHON);
  candidates.push("python3", "python");
  return [...new Set(candidates)];
}

function supportsRequiredPython(command) {
  const probe = spawnSync(
    command,
    [
      "-c",
      [
        "import sys",
        `raise SystemExit(0 if sys.version_info >= (${MINIMUM_PYTHON.join(", ")}) else 1)`,
      ].join("; "),
    ],
    { stdio: "ignore" },
  );
  return probe.status === 0;
}

function findPython() {
  for (const candidate of pythonCandidates()) {
    if (supportsRequiredPython(candidate)) return candidate;
  }
  return null;
}

function failMissingPython() {
  const version = MINIMUM_PYTHON.join(".");
  console.error(`Error: howoldisthisjob requires Python ${version}+ on PATH.`);
  console.error("Set PYTHON to a compatible interpreter or install python3.");
  process.exit(1);
}

export function runPythonCli(moduleFile) {
  const python = findPython();
  if (!python) failMissingPython();

  const child = spawn(
    python,
    [path.join(packageRoot(), moduleFile), ...process.argv.slice(2)],
    { stdio: "inherit" },
  );

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 1);
  });

  child.on("error", (error) => {
    console.error(`Error: failed to start Python CLI: ${error.message}`);
    process.exit(1);
  });
}
