{
  lib,
  buildPythonPackage,
  hatchling,
  loguru,
  pydantic,
  tqdm,
  src,
}:
# Y-Offline as an importable library, packaged here rather than consumed from its own
# flake. That flake exposes `packages.default`, a `buildPythonApplication` on
# `python313Packages`: an application carries no `pythonModule`, so
# `python3.withPackages` takes it without complaint and `import y_offline` then fails at
# run time. The site build would succeed with only the rhythm loaders dead, which is a
# worse failure than a rejected argument.
#
# Only the three dependencies the loaders actually reach are listed. `y_offline` as a
# whole also wants fastapi, uvicorn, numpy, pillow and imagehash — for the web API and
# the jacket-matching code, neither of which a loader imports. Pulling those in would
# add a large closure to every site build to satisfy modules that are never loaded.
#
# `pythonImportsCheck` is the point of packaging it separately: it fails the build here,
# where the cause is obvious, rather than at site-build time inside a loader.
buildPythonPackage {
  pname = "y-offline";
  version = "0.1.0";
  pyproject = true;
  inherit src;

  build-system = [ hatchling ];

  dependencies = [
    loguru
    pydantic
    tqdm
  ];

  # `pyproject.toml` declares the whole application's dependencies, including the six
  # left out above. The runtime-deps check compares the wheel's metadata against what is
  # present and fails on those, so it has to be off — `pythonRelaxDeps` only rewrites
  # version bounds and does not drop a requirement.
  #
  # Safe only because `pythonImportsCheck` below covers every module a loader reaches: if
  # one of the excluded six were needed on that path, the import would fail here. Adding
  # a loader that imports `y_offline.app` or `y_offline.jacket` means adding its
  # dependencies rather than trusting this.
  dontCheckRuntimeDeps = true;

  # No tests: they live outside the wheel and need pytest, and this derivation exists to
  # make the library importable rather than to re-verify it. Y-Offline's own flake runs
  # them.
  doCheck = false;

  # Exactly the modules the loaders import, so a missing runtime dependency is caught
  # here. `base.analysis` covers the aggregations the pages are built on; the three game
  # modules each pull their own chart repository and manager.
  pythonImportsCheck = [
    "y_offline"
    "y_offline.base.analysis"
    "y_offline.base.pool"
    "y_offline.arcaea.utils"
    "y_offline.pjsk.utils"
    "y_offline.cytus2.utils"
  ];

  meta = {
    description = "Local rhythm game score database, as a library for the dashboards";
  };
}
