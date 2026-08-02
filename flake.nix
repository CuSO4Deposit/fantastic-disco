{
  description = "observable-cuso4d - dashboards over CPI";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    pre-commit-hooks.url = "github:cachix/git-hooks.nix";
    cpi = {
      url = "github:CuSO4Deposit/CPI";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Source only, and packaged in `package.nix` rather than taken as a flake output.
    # Y-Offline exposes `packages.default`, which is a `buildPythonApplication` built
    # against `python313Packages` — an application, so it carries no `pythonModule` and
    # is pinned to an interpreter that is not this nixpkgs' default. Passing it to
    # `python3.withPackages` is accepted without complaint and then `import y_offline`
    # fails at run time, which is the worst of the available failures: the build
    # succeeds and only the rhythm loaders die.
    #
    # `flake = false` also keeps this repo from inheriting Y-Offline's own nixpkgs pin
    # and its fastapi/numpy/pillow closure, none of which a loader touches.
    y-offline = {
      url = "git+ssh://git@codeberg.org/cocvu/Y-Offline.git";
      flake = false;
    };
  };

  outputs =
    inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        inputs.pre-commit-hooks.flakeModule
      ];
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];
      # `inputs` is not a `perSystem` argument — flake-parts binds it at the top level
      # only — so `y-offline` is reached through the outer `inputs@{ ... }` closure
      # instead. It is `flake = false`, a bare source tree, so there is nothing
      # per-system for `inputs'` to select anyway.
      perSystem =
        {
          config,
          pkgs,
          inputs',
          ...
        }:
        {
          packages = {
            default = config.packages.site;
            # A build command rather than the built site: producing the site means
            # reading the archive, which the Nix sandbox cannot do. Everything pure
            # is packaged; the archive path is passed at run time.
            site = pkgs.callPackage ./package.nix {
              cpi = inputs'.cpi.packages.cpi;
              y-offline = config.packages.y-offline;
            };
            # Y-Offline as an importable library, built here from its source rather
            # than taken from its flake — see the input's comment. Exposed as its own
            # output so `nix build .#y-offline` can check it in isolation, which is
            # where an import failure is cheap to find rather than mid-site-build.
            y-offline = pkgs.python3Packages.callPackage ./nix/y-offline.nix {
              src = inputs.y-offline;
            };
          };

          pre-commit.settings = {
            src = ./.;
            hooks = {
              nixfmt-rfc-style.enable = true;
              ruff.enable = true;
              ruff-format.enable = true;
            };
          };
          devShells = {
            default = pkgs.mkShellNoCC {
              buildInputs = with pkgs; [
                nodejs
                uv
                pythonManylinuxPackages.manylinux2014Package
              ];
              NIX_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
                pkgs.stdenv.cc.cc
                pkgs.pythonManylinuxPackages.manylinux2014Package
              ];
              NIX_LD = builtins.readFile "${pkgs.stdenv.cc}/nix-support/dynamic-linker";

              shellHook = ''
                ${config.pre-commit.installationScript}

                uv venv --allow-existing
                . .venv/bin/activate
                uv sync
              '';
            };
          };
        };
    };
}
