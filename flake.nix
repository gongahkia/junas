{
  description = "Aki local-first screen privacy filter";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];

      forAllSystems = f:
        nixpkgs.lib.genAttrs systems (system:
          f system (import nixpkgs { inherit system; }));
    in
    {
      packages = forAllSystems (system: pkgs:
        let
          lib = pkgs.lib;
          frameworks =
            if pkgs.stdenv.isDarwin
            then pkgs.darwin.apple_sdk.frameworks
            else { };
          optionalFramework = name:
            lib.optional
              (pkgs.stdenv.isDarwin && lib.hasAttr name frameworks)
              frameworks.${name};
          darwinBuildInputs = lib.concatMap optionalFramework [
            "Cocoa"
            "CoreFoundation"
            "CoreGraphics"
            "CoreMedia"
            "CoreVideo"
            "ScreenCaptureKit"
          ];
          linuxBuildInputs = lib.optionals pkgs.stdenv.isLinux [
            pkgs.pipewire
            pkgs.xorg.libxcb
          ];
        in
        rec {
          aki = pkgs.rustPlatform.buildRustPackage {
            pname = "aki";
            version = "0.1.0";
            src = ./.;

            cargoLock.lockFile = ./Cargo.lock;
            cargoBuildFlags = [ "-p" "privacy-tui" ];
            cargoTestFlags = [ "--all" ];

            nativeBuildInputs = [
              pkgs.makeWrapper
              pkgs.llvmPackages.libclang
              pkgs.pkg-config
            ];

            buildInputs = [
              pkgs.leptonica
              pkgs.tesseract
            ] ++ darwinBuildInputs ++ linuxBuildInputs;

            nativeCheckInputs = [
              pkgs.ffmpeg
              pkgs.tesseract
            ];

            LIBCLANG_PATH = "${pkgs.llvmPackages.libclang.lib}/lib";

            postInstall = ''
              wrapProgram "$out/bin/aki" \
                --prefix PATH : ${lib.makeBinPath [ pkgs.ffmpeg ]} \
                --set-default TESSDATA_PREFIX "${pkgs.tesseract}/share/tessdata"
            '';

            meta = {
              description = "Local-first real-time privacy filter for screen sharing and livestreaming";
              homepage = "https://github.com/gongahkia/aki";
              license = lib.licenses.mit;
              mainProgram = "aki";
            };
          };

          default = aki;
        });

      apps = forAllSystems (system: pkgs: {
        aki = {
          type = "app";
          program = "${self.packages.${system}.aki}/bin/aki";
        };
        default = self.apps.${system}.aki;
      });

      devShells = forAllSystems (system: pkgs:
        let
          lib = pkgs.lib;
          frameworks =
            if pkgs.stdenv.isDarwin
            then pkgs.darwin.apple_sdk.frameworks
            else { };
          optionalFramework = name:
            lib.optional
              (pkgs.stdenv.isDarwin && lib.hasAttr name frameworks)
              frameworks.${name};
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.cargo
              pkgs.clippy
              pkgs.ffmpeg
              pkgs.llvmPackages.libclang
              pkgs.pkg-config
              pkgs.rustc
              pkgs.rustfmt
              pkgs.tesseract
            ]
            ++ lib.optionals pkgs.stdenv.isLinux [
              pkgs.pipewire
              pkgs.xorg.libxcb
            ]
            ++ lib.concatMap optionalFramework [
              "Cocoa"
              "CoreFoundation"
              "CoreGraphics"
              "CoreMedia"
              "CoreVideo"
              "ScreenCaptureKit"
            ];

            LIBCLANG_PATH = "${pkgs.llvmPackages.libclang.lib}/lib";
            TESSDATA_PREFIX = "${pkgs.tesseract}/share/tessdata";
          };
        });
    };
}
