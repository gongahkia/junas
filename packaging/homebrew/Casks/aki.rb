cask "aki" do
  version "0.1.0"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"

  url "https://github.com/gongahkia/junas/releases/download/v#{version}/JunasMenuBar-#{version}.dmg"
  name "Aki"
  name "Junas Menu Bar"
  desc "Local privacy redaction menu bar app"
  homepage "https://github.com/gongahkia/junas"

  app "JunasMenuBar.app"
end
