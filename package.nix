{
  lib,
  stdenvNoCC,
  writeShellApplication,
  bash,
  coreutils,
  nodejs,
  fetchNpmDeps,
  npmHooks,
  python3,
  cpi,
}:
# The site cannot be a single derivation. Building it means reading the archived
# exports, and the sandbox has no access to them (verified: /data/redmi50 is simply
# absent inside a build). So this packages everything that *is* pure — node_modules,
# the page sources, the interpreter carrying CPI — and hands back a command that
# performs the impure step wherever the archive is readable.
let
  python = python3.withPackages (_: [ cpi ]);

  src = lib.fileset.toSource {
    root = ./.;
    fileset = lib.fileset.unions [
      ./package.json
      ./package-lock.json
      ./observablehq.config.js
      ./src
      ./scripts
    ];
  };

  # node_modules and the page sources, ready to build but not yet built.
  workspace = stdenvNoCC.mkDerivation (finalAttrs: {
    pname = "observable-cuso4d-workspace";
    version = "0.1.0";
    inherit src;

    # fetchNpmDeps rather than importNpmLock: Framework's `@clack/prompts` bundles
    # `is-unicode-supported`, whose lockfile entry carries no `resolved` URL, so the
    # per-entry importer cannot fetch it and npm falls back to the network. A
    # fixed-output derivation over the whole tree has no such problem.
    npmDeps = fetchNpmDeps {
      inherit (finalAttrs) src;
      hash = "sha256-3nFOKP1w9i6OJCWQ7ntDkh00IWKKPgF2v7cSaxVEQqo=";
    };

    nativeBuildInputs = [
      nodejs
      npmHooks.npmConfigHook
    ];

    dontBuild = true;
    installPhase = ''
      runHook preInstall
      mkdir -p $out
      cp -r package.json package-lock.json observablehq.config.js src scripts $out/
      cp -r node_modules $out/
      runHook postInstall
    '';
  });
in
writeShellApplication {
  name = "observable-cuso4d-build";

  runtimeInputs = [
    nodejs
    python
    # npm spawns `sh` to run package scripts, and a systemd unit has no PATH of its
    # own to fall back on: without this the build dies with `spawn sh ENOENT`.
    bash
    coreutils
  ];

  text = ''
    # Usage: observable-cuso4d-build <exports-glob> <output-dir> [config-dir]
    #
    # config-dir may hold `blocked.txt` and `fandoms.txt`. Both name things about the
    # person whose data this is, so they stay out of the store and are passed in at
    # run time; absent, the site simply publishes everything untagged.
    #
    # Publishing is an atomic rename: nginx must never serve a half-written tree, and
    # a failed build must leave the previous site up rather than replacing it with
    # something broken.
    usage="usage: observable-cuso4d-build <exports-glob> <output-dir> [config-dir]"
    exports=''${1:?$usage}
    outdir=''${2:?$usage}
    configdir=''${3:-}

    # Refuse to build from nothing: an empty glob would otherwise publish a site
    # claiming the watch history is empty.
    shopt -s nullglob
    # shellcheck disable=SC2206  # word splitting is the point: $exports is a glob
    matches=($exports)
    shopt -u nullglob
    if [ ''${#matches[@]} -eq 0 ]; then
      echo "no exports match $exports; refusing to build" >&2
      exit 1
    fi
    echo "building from ''${#matches[@]} export(s)" >&2

    work=$(mktemp -d)
    trap 'rm -rf "$work"' EXIT
    cp -r ${workspace}/. "$work/"
    chmod -R u+w "$work"
    cd "$work"

    if [ -n "$configdir" ]; then
      for f in blocked.txt fandoms.txt; do
        if [ -e "$configdir/$f" ]; then
          cp "$configdir/$f" "src/lib/$f"
          echo "using $configdir/$f" >&2
        fi
      done
    fi

    export CPI_PIPEPIPE_EXPORTS="$exports"
    export HOME="$work"
    npm run build

    [ -f dist/index.html ] || { echo "build produced no dist/index.html" >&2; exit 1; }

    mkdir -p "$(dirname "$outdir")"
    staging="$outdir.new.$$"
    rm -rf "$staging"
    cp -r dist "$staging"
    # Rename over the target so readers see the old tree or the new one, never a mix.
    if [ -e "$outdir" ]; then
      old="$outdir.old.$$"
      mv "$outdir" "$old"
      mv "$staging" "$outdir"
      rm -rf "$old"
    else
      mv "$staging" "$outdir"
    fi
    echo "published $(du -sh "$outdir" | cut -f1) to $outdir" >&2
  '';

  meta = {
    description = "Build the cuso4d dashboards from an archive of exports";
    license = lib.licenses.cc0;
  };
}
