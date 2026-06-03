#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Build, package, sign, notarize, staple, and verify the macOS Aki DMG.

Usage:
  scripts/release_macos_dmg.sh [--version VERSION] [--skip-notarize] [--unsigned]

Environment for signed releases:
  AKI_SIGN_IDENTITY             Developer ID Application identity name.
  AKI_NOTARY_KEYCHAIN_PROFILE   Optional notarytool keychain profile.

Or, instead of AKI_NOTARY_KEYCHAIN_PROFILE:
  AKI_NOTARY_APPLE_ID           Apple ID for notarytool.
  AKI_NOTARY_TEAM_ID            Apple Developer Team ID.
  AKI_NOTARY_PASSWORD           App-specific password.

Options:
  --version VERSION   Override version from Cargo.toml.
  --skip-notarize     Sign and create the DMG, but do not submit to Apple.
  --unsigned          Ad-hoc sign for local bundle/DMG smoke tests only.
  --help              Show this help.
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

log() {
  echo "==> $*"
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${AKI_VERSION:-}"
SKIP_NOTARIZE=0
UNSIGNED=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      [[ $# -ge 2 ]] || die "--version requires a value"
      VERSION="$2"
      shift 2
      ;;
    --skip-notarize)
      SKIP_NOTARIZE=1
      shift
      ;;
    --unsigned)
      UNSIGNED=1
      SKIP_NOTARIZE=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

if [[ -z "$VERSION" ]]; then
  VERSION="$(awk -F '"' '/^version =/ { print $2; exit }' "$ROOT/Cargo.toml")"
fi
[[ -n "$VERSION" ]] || die "could not determine version"

APP_NAME="Aki"
BUNDLE_ID="${AKI_BUNDLE_ID:-dev.gongahkia.aki}"
DIST_DIR="${AKI_DIST_DIR:-$ROOT/dist/macos}"
WORK_DIR="$ROOT/target/release/macos-dmg"
APP="$WORK_DIR/$APP_NAME.app"
CONTENTS="$APP/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RESOURCES_DIR="$CONTENTS/Resources"
FRAMEWORKS_DIR="$CONTENTS/Frameworks"
SWIFT_EXE="$ROOT/macos/AkiMenuBar/.build/release/AkiMenuBar"
SIDECAR_EXE="$ROOT/target/release/aki"
APP_ZIP="$DIST_DIR/$APP_NAME-$VERSION-macos-app.zip"
DMG="$DIST_DIR/$APP_NAME-$VERSION-macos.dmg"
SHA256="$DMG.sha256"

if [[ "$UNSIGNED" -eq 0 ]]; then
  [[ -n "${AKI_SIGN_IDENTITY:-}" ]] || die "AKI_SIGN_IDENTITY must name a Developer ID Application identity"
  [[ "$AKI_SIGN_IDENTITY" == *"Developer ID Application"* ]] || die "AKI_SIGN_IDENTITY must be a Developer ID Application identity"
  security find-identity -v -p codesigning | grep -F "$AKI_SIGN_IDENTITY" >/dev/null \
    || die "codesigning identity not found in keychain: $AKI_SIGN_IDENTITY"

  if [[ "$SKIP_NOTARIZE" -eq 0 ]]; then
    if [[ -z "${AKI_NOTARY_KEYCHAIN_PROFILE:-}" ]]; then
      [[ -n "${AKI_NOTARY_APPLE_ID:-}" ]] || die "AKI_NOTARY_APPLE_ID or AKI_NOTARY_KEYCHAIN_PROFILE is required"
      [[ -n "${AKI_NOTARY_TEAM_ID:-}" ]] || die "AKI_NOTARY_TEAM_ID or AKI_NOTARY_KEYCHAIN_PROFILE is required"
      [[ -n "${AKI_NOTARY_PASSWORD:-}" ]] || die "AKI_NOTARY_PASSWORD or AKI_NOTARY_KEYCHAIN_PROFILE is required"
    fi
  fi
fi

sign_path() {
  local path="$1"
  if [[ "$UNSIGNED" -eq 1 ]]; then
    codesign --force --sign - "$path"
  else
    codesign --force --timestamp --options runtime --sign "$AKI_SIGN_IDENTITY" "$path"
  fi
}

notary_submit() {
  local archive="$1"
  [[ "$SKIP_NOTARIZE" -eq 0 ]] || return 0

  if [[ -n "${AKI_NOTARY_KEYCHAIN_PROFILE:-}" ]]; then
    xcrun notarytool submit "$archive" \
      --keychain-profile "$AKI_NOTARY_KEYCHAIN_PROFILE" \
      --wait
  else
    xcrun notarytool submit "$archive" \
      --apple-id "$AKI_NOTARY_APPLE_ID" \
      --team-id "$AKI_NOTARY_TEAM_ID" \
      --password "$AKI_NOTARY_PASSWORD" \
      --wait
  fi
}

is_external_dylib() {
  case "$1" in
    /opt/homebrew/*|/usr/local/*) return 0 ;;
    *) return 1 ;;
  esac
}

external_dylibs_for() {
  local file="$1"
  otool -L "$file" | awk 'NR > 1 { print $1 }' | while read -r dep; do
    if is_external_dylib "$dep"; then
      printf '%s\n' "$dep"
    fi
  done
}

bundle_external_dylibs() {
  local queue=("$RESOURCES_DIR/aki")
  local current dep dest

  while [[ "${#queue[@]}" -gt 0 ]]; do
    current="${queue[0]}"
    queue=("${queue[@]:1}")

    while read -r dep; do
      [[ -z "$dep" ]] && continue
      [[ -f "$dep" ]] || die "linked dylib is missing: $dep"
      dest="$FRAMEWORKS_DIR/$(basename "$dep")"
      if [[ ! -f "$dest" ]]; then
        log "Bundling $(basename "$dep")"
        cp "$dep" "$dest"
        chmod u+w "$dest"
        queue+=("$dest")
      fi
    done < <(external_dylibs_for "$current")
  done
}

rewrite_install_names() {
  local targets=("$RESOURCES_DIR/aki")
  local target dep rewritten

  while IFS= read -r -d '' target; do
    targets+=("$target")
  done < <(find "$FRAMEWORKS_DIR" -type f -name '*.dylib' -print0)

  for target in "${targets[@]}"; do
    if [[ "$target" == "$FRAMEWORKS_DIR/"* ]]; then
      install_name_tool -id "@executable_path/../Frameworks/$(basename "$target")" "$target"
    fi

    while read -r dep; do
      [[ -z "$dep" ]] && continue
      rewritten="@executable_path/../Frameworks/$(basename "$dep")"
      install_name_tool -change "$dep" "$rewritten" "$target"
    done < <(external_dylibs_for "$target")
  done
}

write_info_plist() {
  cat > "$CONTENTS/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundleDisplayName</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key>
  <string>AkiMenuBar</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$VERSION</string>
  <key>CFBundleVersion</key>
  <string>$VERSION</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF
  printf 'APPL????' > "$CONTENTS/PkgInfo"
}

log "Building Rust sidecar"
cargo build --release -p privacy-tui

log "Building Swift menu-bar executable"
swift build -c release --package-path "$ROOT/macos/AkiMenuBar"

log "Creating app bundle at $APP"
rm -rf "$WORK_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR" "$FRAMEWORKS_DIR" "$DIST_DIR"
install -m 755 "$SWIFT_EXE" "$MACOS_DIR/AkiMenuBar"
install -m 755 "$SIDECAR_EXE" "$RESOURCES_DIR/aki"
write_info_plist

log "Bundling non-system dylib dependencies"
bundle_external_dylibs
rewrite_install_names

log "Signing nested code"
while IFS= read -r -d '' dylib; do
  sign_path "$dylib"
done < <(find "$FRAMEWORKS_DIR" -type f -name '*.dylib' -print0)
sign_path "$RESOURCES_DIR/aki"
sign_path "$MACOS_DIR/AkiMenuBar"
sign_path "$APP"
codesign --verify --strict --verbose=2 "$APP"

if [[ "$SKIP_NOTARIZE" -eq 0 ]]; then
  log "Submitting app bundle for notarization"
  rm -f "$APP_ZIP"
  ditto -c -k --keepParent "$APP" "$APP_ZIP"
  notary_submit "$APP_ZIP"
  xcrun stapler staple "$APP"
  xcrun stapler validate "$APP"
fi

log "Creating DMG"
DMG_ROOT="$WORK_DIR/dmg-root"
rm -rf "$DMG_ROOT" "$DMG" "$SHA256"
mkdir -p "$DMG_ROOT"
ditto "$APP" "$DMG_ROOT/$APP_NAME.app"
ln -s /Applications "$DMG_ROOT/Applications"
hdiutil create -volname "$APP_NAME $VERSION" -srcfolder "$DMG_ROOT" -ov -format UDZO "$DMG"
sign_path "$DMG"

if [[ "$SKIP_NOTARIZE" -eq 0 ]]; then
  log "Submitting DMG for notarization"
  notary_submit "$DMG"
  xcrun stapler staple "$DMG"
  xcrun stapler validate "$DMG"
  spctl --assess --type execute --verbose=4 "$APP"
  spctl --assess --type open --context context:primary-signature --verbose=4 "$DMG"
fi

shasum -a 256 "$DMG" > "$SHA256"
log "Wrote $DMG"
log "Wrote $SHA256"
