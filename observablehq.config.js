import {existsSync} from "node:fs";

// Framework maps `.py` to a bare `python3` on $PATH. There is no system python3 on
// NixOS, so a dev server started outside the activated venv fails with
// `spawn python3 ENOENT`. Prefer the venv's interpreter so loaders work regardless
// of which shell launched the server, but fall back to PATH: in the Nix build there
// is no venv, and the interpreter there already carries CPI.
const venvPython = new URL("./.venv/bin/python3", import.meta.url).pathname;
const python = existsSync(venvPython) ? venvPython : "python3";

// A source's pages are listed only when its directory is present. The build command
// deletes `src/band/` when the band's environment is unset, so a machine that archives
// only one source publishes a site with no dead nav entries pointing at pages that
// were never rendered. Framework validates links at build time, so a stale entry here
// would fail the build rather than degrade quietly — which is the right failure, but
// only if this list can actually go without.
const sources = [
  {
    dir: "video",
    section: {
      name: "Video",
      path: "/video/",
      pages: [
        { name: "Overview", path: "/video/" },
        { name: "Fandoms", path: "/video/fandoms" },
        { name: "Raw", path: "/video/raw" },
      ],
    },
  },
  {
    dir: "band",
    section: {
      name: "Band",
      path: "/band/",
      pages: [
        { name: "Overview", path: "/band/" },
        { name: "Sleep", path: "/band/sleep" },
        { name: "Device", path: "/band/device" },
      ],
    },
  },
];

const root = new URL("./src/", import.meta.url).pathname;

export default {
  title: "cuso4d",
  root: "src",
  interpreters: { ".py": [python] },
  pages: sources
    .filter(({ dir }) => existsSync(root + dir))
    .map(({ section }) => section),
  // Charts read better wide; the default caps the main column at 1152px.
  theme: ["air", "near-midnight"],
  footer: "Built from archived exports. Nothing here leaves the machine.",
  toc: false,
};
