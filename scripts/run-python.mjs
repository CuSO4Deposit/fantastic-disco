// Run a Python script with whichever interpreter this checkout has.
//
// Two environments to satisfy, for the same reason the Framework config picks its
// interpreter the same way: the dev shell has a venv holding CPI, while the Nix
// build has no venv and instead puts an interpreter carrying CPI on PATH.
import {spawnSync} from "node:child_process";
import {existsSync} from "node:fs";

const venv = new URL("../.venv/bin/python3", import.meta.url).pathname;
const python = existsSync(venv) ? venv : "python3";

const {status, error} = spawnSync(python, process.argv.slice(2), {stdio: "inherit"});
if (error) {
  console.error(`could not run ${python}: ${error.message}`);
  process.exit(1);
}
process.exit(status ?? 1);
