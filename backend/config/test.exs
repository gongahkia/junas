import Config

config :say_less, SayLessWeb.Endpoint,
  http: [ip: {127, 0, 0, 1}, port: 4002],
  secret_key_base: "m659DntuLwKn/VZfCpXTxvX8jbD6XqDhEAzS7vsb+yx2hMVaShqkn6rNilDeCPtO",
  server: false

config :logger, level: :warning

config :phoenix, :plug_init_mode, :runtime
