{
  description = "Projeto Python gerenciado por uv";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-26.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Libs que wheels binarias do PyPI (pyzmq, numpy, scipy, xgboost,
        # torch...) esperam encontrar em tempo de execucao. O Python do Nix
        # nao acha essas .so sozinho (e o nix-ld nao intercepta binario Nix),
        # entao apontamos explicitamente via LD_LIBRARY_PATH.
        libs = with pkgs; [
          stdenv.cc.cc.lib   # libstdc++.so.6
          zlib
          zstd
          openssl
          glib
        ];
      in {
        devShells.default = pkgs.mkShell {
          # uv cria e gerencia o .venv a partir do pyproject.toml ou
          # requirements.txt. O Nix so fornece o interpretador base e o uv.
          buildInputs = [
            pkgs.python313
            pkgs.uv
          ];

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath libs;

          shellHook = ''
            echo "Python $(python3 --version) + uv $(uv --version)"
            export UV_PYTHON_PREFERENCE=only-system
            [ -f pyproject.toml ] && echo "-> uv sync" || \
              echo "-> uv venv && uv pip install -r requirements.txt"
          '';
        };
      });
}
