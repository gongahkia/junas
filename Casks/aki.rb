cask "aki" do
  version "0.1.0"
  sha256 :no_check

  url "https://github.com/gongahkia/aki/releases/download/v#{version}/Aki-#{version}-macos.dmg"
  name "Aki"
  desc "Local-first real-time privacy filter for screen sharing and livestreaming"
  homepage "https://github.com/gongahkia/aki"

  livecheck do
    url :url
    strategy :github_latest
  end

  depends_on macos: :ventura

  app "Aki.app"

  uninstall quit: "dev.gongahkia.aki"

  zap trash: [
    "~/.config/ascii-privacy",
    "~/Library/Caches/dev.gongahkia.aki",
    "~/Library/Logs/Aki",
  ]
end
