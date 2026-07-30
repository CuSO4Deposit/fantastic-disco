// Framework maps `.py` to a bare `python3` on $PATH. There is no system python3 on
// NixOS, so a dev server started outside the activated venv fails with
// `spawn python3 ENOENT`. Pointing at the venv's interpreter makes loaders work
// regardless of which shell launched the server.
const python = new URL("./.venv/bin/python3", import.meta.url).pathname;

export default {
  title: "cuso4d",
  root: "src",
  interpreters: { ".py": [python] },
  pages: [
    {
      name: "Video",
      path: "/video/",
      pages: [
        { name: "Overview", path: "/video/" },
        { name: "Fandoms", path: "/video/fandoms" },
        { name: "Raw", path: "/video/raw" },
      ],
    },
  ],
  // Charts read better wide; the default caps the main column at 1152px.
  theme: ["air", "near-midnight"],
  footer: "Built from archived exports. Nothing here leaves the machine.",
  toc: false,
};
