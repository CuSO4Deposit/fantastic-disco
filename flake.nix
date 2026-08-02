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
    # `follows` matters more here than it looks: `packages.y-offline` is a Python
    # library, and a library built against another nixpkgs carries a different
    # interpreter. `python3.withPackages` would then install modules where this build's
    # python cannot see them — accepted silently, failing only when a loader runs.
    # HTTPS rather than SSH: the builder runs unattended from a systemd unit, which has
    # no agent and no key of its own, and a public repository needs neither to fetch.
    y-offline = {
      url = "git+https://codeberg.org/cocvu/Y-Offline.git";
      inputs.nixpkgs.follows = "nixpkgs";
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
              # The library output, not `default` — that one is the `y`/`yweb`
              # application and is not importable.
              y-offline = inputs'.y-offline.packages.y-offline;
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
