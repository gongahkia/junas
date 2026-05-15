import Config

bind_all? =
  System.get_env("PHX_BIND_ALL", "false")
  |> String.downcase()
  |> Kernel.in(["1", "true", "yes"])

http_ip = if(bind_all?, do: {0, 0, 0, 0}, else: {127, 0, 0, 1})

# For development, we disable any cache and enable
# debugging and code reloading.
config :say_less, SayLessWeb.Endpoint,
  # Binding to loopback ipv4 address prevents access from other machines.
  # Change to `ip: {0, 0, 0, 0}` to allow access from other machines.
  http: [ip: http_ip, port: String.to_integer(System.get_env("PORT") || "4000")],
  check_origin: false,
  code_reloader: true,
  debug_errors: true,
  secret_key_base: "pTeMYaFZHeGDT8Gv6Yy3DC0XM+NtZ6tAzyDKZONGrL6PBJQsLCvPhsoT3Zvjvn/U"

# Do not include metadata nor timestamps in development logs
config :logger, :default_formatter, format: "[$level] $message\n"

# Set a higher stacktrace during development.
config :phoenix, :stacktrace_depth, 20

# Initialize plugs at runtime for faster development compilation
config :phoenix, :plug_init_mode, :runtime

config :cors_plug,
  origin: "http://localhost:3000"
