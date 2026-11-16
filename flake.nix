{
  description = "filmcraft-studio: marketplace juan-local con el plugin de video y su binario `cine` compilado para cada plataforma";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      lib = nixpkgs.lib;
      # sistema de Nix → carpeta que busca plugins/filmcraft-studio/bin/cine
      carpetas = {
        aarch64-darwin = "darwin-arm64";
        x86_64-darwin = "darwin-x64";
        x86_64-linux = "linux-x64";
        aarch64-linux = "linux-arm64";
      };
      plugin = "plugins/filmcraft-studio";
      version = (builtins.fromTOML (builtins.readFile ./plugins/filmcraft-studio/motor/Cargo.toml)).package.version;
      para = f: lib.genAttrs (builtins.attrNames carpetas) (s: f nixpkgs.legacyPackages.${s} carpetas.${s});
    in
    {
      packages = para (pkgs: carpeta: rec {
        # El binario. ds.schema.json se incluye en tiempo de compilación desde schemas/, por eso la fuente
        # es motor/ + schemas/ y Cargo trabaja en motor/.
        cine = pkgs.rustPlatform.buildRustPackage {
          pname = "cine";
          inherit version;
          src = lib.fileset.toSource {
            root = ./.;
            fileset = lib.fileset.unions [ ./plugins/filmcraft-studio/motor ./plugins/filmcraft-studio/schemas ];
          };
          cargoRoot = "${plugin}/motor";
          buildAndTestSubdir = "${plugin}/motor";
          cargoLock.lockFile = ./plugins/filmcraft-studio/motor/Cargo.lock;
          meta = {
            description = "Motor determinista de filmcraft-studio";
            mainProgram = "cine";
            license = lib.licenses.mit;
          };
        };

        # El plugin listo para Claude Code: la carpeta del plugin + el binario en bin/<so>-<arq>/, donde lo
        # busca el lanzador bin/cine.
        filmcraft-studio = pkgs.runCommand "filmcraft-studio-${version}" { } ''
          cp -R ${self}/${plugin} $out
          chmod -R u+w $out
          rm -rf $out/motor/target
          mkdir -p $out/bin/${carpeta}
          cp ${cine}/bin/cine $out/bin/${carpeta}/cine
        '';

        # El marketplace juan-local entero (lo que se registra como directorio en Claude Code).
        marketplace = pkgs.runCommand "juan-local-${version}" { } ''
          mkdir -p $out/plugins
          cp -R ${self}/.claude-plugin $out/
          cp ${self}/README.md ${self}/LICENSE $out/
          cp -R ${filmcraft-studio} $out/${plugin}
        '';

        default = marketplace;
      });
    };
}
