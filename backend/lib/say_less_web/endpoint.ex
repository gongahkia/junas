defmodule SayLessWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :say_less

  @session_options [
    store: :cookie,
    key: "_say_less_key",
    signing_salt: "I_LIKE_MY_FOOD_NICE_AND_SALTY",
    same_site: "Lax"
  ]

  plug Plug.Static,
    at: "/",
    from: :say_less,
    gzip: false,
    only: ~w(assets fonts images favicon.ico robots.txt)

  if code_reloading? do
    plug Phoenix.CodeReloader
  end

  plug Plug.RequestId
  plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]

  plug Plug.Parsers,
    parsers: [:urlencoded, :multipart, :json],
    pass: ["*/*"],
    json_decoder: Phoenix.json_library()

  plug Plug.MethodOverride
  plug Plug.Head
  plug Plug.Session, @session_options
  plug CORSPlug
  plug SayLessWeb.Router
end
