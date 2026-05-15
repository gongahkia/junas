defmodule SayLess.MixProject do
  use Mix.Project

  def project do
    [
      app: :say_less, # Changed from :backend
      version: "0.1.0",
      elixir: "~> 1.15",
      elixirc_paths: elixirc_paths(Mix.env()),
      start_permanent: Mix.env() == :prod,
      aliases: aliases(),
      deps: deps()
    ]
  end

  def application do
    [
      mod: {SayLess.Application, []}, # Changed from Backend.Application
      extra_applications: [:logger, :runtime_tools]
    ]
  end

  defp elixirc_paths(:test), do: ["lib", "test/support"]
  defp elixirc_paths(_), do: ["lib"]

  defp deps do
    [
      {:phoenix, "~> 1.7.12"},
      {:phoenix_pubsub, "~> 2.1"},
      {:jason, "~> 1.2"},
      {:plug_cowboy, "~> 2.7"},
      {:cors_plug, "~> 1.5"},
      {:httpoison, "~> 2.0"},
      {:dotenvy, "~> 0.6.0"}
    ]
  end

  defp aliases do
    []
  end
end
