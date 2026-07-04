on run
    set baseURL to system attribute "JUNAS_LOCAL_BASE_URL"
    if baseURL is "" then set baseURL to "http://127.0.0.1:8765"

    set watchCommand to system attribute "AKI_WATCH_COMMAND"
    if watchCommand is "" then set watchCommand to "junas-watch"

    set tokenFile to system attribute "JUNAS_LOCAL_TOKEN_FILE"
    set commandText to "PATH=/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH " & quoted form of watchCommand & " --clipboard --once --copy-anonymized-clipboard --base-url " & quoted form of baseURL & " --foreground-profile auto --notify"
    if tokenFile is not "" then set commandText to commandText & " --local-token-file " & quoted form of tokenFile

    set reviewOutput to do shell script commandText
    display notification "Clipboard review complete" with title "Aki"
    return reviewOutput
end run
