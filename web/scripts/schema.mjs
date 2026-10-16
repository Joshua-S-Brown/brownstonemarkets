import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
const root = fileURLToPath(new URL("../../", import.meta.url));
const python =
  process.env.BROWNSTONE_PYTHON ||
  (existsSync(root + ".venv/bin/python")
    ? root + ".venv/bin/python"
    : "python");
const schema = JSON.parse(
  execFileSync(python, ["-m", "api"], { cwd: root, encoding: "utf8" }),
);
const output = astToString(await openapiTS(schema));
const target = new URL("../src/api/schema.d.ts", import.meta.url);
if (process.argv.includes("--check")) {
  if (!existsSync(target) || readFileSync(target, "utf8") !== output) {
    console.error("API schema is out of date. Run npm run schema in web/.");
    process.exit(1);
  }
} else writeFileSync(target, output);
