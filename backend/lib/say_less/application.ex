defmodule SayLess.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      # Start the PubSub system using the correct tuple format
      {Phoenix.PubSub, name: SayLess.PubSub},
      # Start the Endpoint (the web server)
      SayLessWeb.Endpoint
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: SayLess.Supervisor]
    Supervisor.start_link(children, opts)
  end
end
