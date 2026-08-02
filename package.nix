{
  lib,
  stdenvNoCC,
  writeShellApplication,
  bash,
  brotli,
  coreutils,
  findutils,
  gzip,
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
    # Precompression, below.
    brotli
    findutils
    gzip
  ];

  text = ''
    # Usage: observable-cuso4d-build <exports-glob> <output-dir> [config-dir]
    #
    # config-dir may hold `blocked.txt` and `fandoms.txt`. Both name things about the
    # person whose data this is, so they stay out of the store and are passed in at
    # run time; absent, the site simply publishes everything untagged.
    #
    # Two environment variables are read rather than taken as arguments, since both
    # are properties of the machine's archive rather than of one build:
    #
    #   CPI_GADGETBRIDGE_EXPORTS  where the band backups are. Optional — unset simply
    #                             leaves the band pages out.
    #   CPI_FIREFOX_EXPORTS       where the places.sqlite snapshots are. Optional in
    #                             the same way, and a glob rather than a path: the
    #                             archive holds one file per machine per export.
    #   CPI_LOCAL_TZ              the IANA zone the data was recorded in. Required
    #                             once band or Firefox data is present, and deliberately
    #                             without a default: it decides which local midnight
    #                             splits a day, and a wrong boundary leaves every daily
    #                             total looking like a perfectly plausible number.
    #
    # Publishing is an atomic rename: nginx must never serve a half-written tree, and
    # a failed build must leave the previous site up rather than replacing it with
    # something broken.
    usage="usage: observable-cuso4d-build <exports-glob> <output-dir> [config-dir]"
    exports=''${1:?$usage}
    outdir=''${2:?$usage}
    configdir=''${3:-}

    if [ -z "''${CPI_LOCAL_TZ:-}" ]; then
      for var in CPI_GADGETBRIDGE_EXPORTS CPI_FIREFOX_EXPORTS; do
        if [ -n "''${!var:-}" ]; then
          echo "$var is set but CPI_LOCAL_TZ is not; refusing to build" >&2
          echo "its pages on an assumed timezone" >&2
          exit 1
        fi
      done
    fi

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

    # A source with no archive to read is removed rather than left to fail. Deleting
    # the directory is what makes it optional: both the nav and the landing page derive
    # their entries from what is on disk, so this drops the pages and every link to
    # them together. Leaving the pages in place would fail the build on the first
    # loader that found its variable unset.
    if [ -z "''${CPI_GADGETBRIDGE_EXPORTS:-}" ]; then
      echo "CPI_GADGETBRIDGE_EXPORTS unset; building without the band pages" >&2
      rm -rf src/band
    fi
    if [ -z "''${CPI_FIREFOX_EXPORTS:-}" ]; then
      echo "CPI_FIREFOX_EXPORTS unset; building without the Firefox pages" >&2
      rm -rf src/firefox
    fi

    export CPI_PIPEPIPE_EXPORTS="$exports"
    export HOME="$work"
    npm run build

    [ -f dist/index.html ] || { echo "build produced no dist/index.html" >&2; exit 1; }

    # Precompress every compressible asset so nginx can answer from a `.br`/`.gz`
    # sibling (`brotli_static`/`gzip_static`) instead of compressing per request.
    #
    # Worth doing here rather than leaving it to nginx's on-the-fly gzip because the
    # site is rebuilt once a day and then served unchanged: the cost is paid once per
    # build instead of once per request, which buys the time for the slowest setting.
    # `brotli -q 11` is far too slow to run per request but is fine once a day, and on
    # this data it beats `gzip -9` by around 25-30% — the largest asset, the video
    # loader's JSON, goes 1874K raw, 336K gzip, 243K brotli.
    #
    # The `.gz` copies are the fallback for clients that do not offer brotli. Both are
    # written next to the original, which stays in place: a client sending no
    # Accept-Encoding still gets the plain file.
    #
    # Only files above 1K, since below that framing overhead eats the gain, and only
    # types that actually compress — the jackets are already-compressed WebP, where
    # both encoders would spend time to produce something marginally larger.
    echo "precompressing" >&2
    find dist -type f \
      \( -name '*.html' -o -name '*.js' -o -name '*.css' -o -name '*.json' \
         -o -name '*.svg' -o -name '*.txt' -o -name '*.map' \) \
      -size +1k -print0 |
      while IFS= read -r -d ''' f; do
        brotli -q 11 -f -o "$f.br" "$f"
        gzip -9 -f -k -c "$f" > "$f.gz"
      done

    mkdir -p "$(dirname "$outdir")"
    staging="$outdir.new.$$"
    rm -rf "$staging"
    cp -r dist "$staging"

    # Hand the tree to the group owning the parent directory — a web server, when
    # this publishes into one. New directories otherwise take the builder's primary
    # group, which no amount of supplementary groups on the service will fix, and
    # the site answers 404 with `Permission denied` in the server log.
    if group=$(stat -c %G "$(dirname "$outdir")") && [ "$group" != "$(id -gn)" ]; then
      chgrp -R "$group" "$staging"
    fi
    # Group-readable, never group-writable, nothing for anyone else. Keeps the owner's
    # write bit so the next run can replace the tree.
    chmod -R u+rwX,g=rX,o= "$staging"
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
