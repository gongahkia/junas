import Config

# This file is loaded at runtime for all environments.
# It's the perfect place to load secrets from a .env file for development
# or from OS environment variables for production.

normalize_env_value = fn
  nil ->
    nil

  value when is_binary(value) ->
    case String.trim(value) do
      "" -> nil
      trimmed -> trimmed
    end

  _ ->
    nil
end

require_env! = fn key, source_label, fetch_fun ->
  case fetch_fun.(key) |> normalize_env_value.() do
    nil ->
      raise "#{source_label} is missing required non-empty environment variable #{key}."

    value ->
      value
  end
end

read_dotenv_file! = fn path ->
  path
  |> File.read!()
  |> String.split("\n")
  |> Enum.with_index(1)
  |> Enum.reduce(%{}, fn {raw_line, line_number}, acc ->
    line = String.trim(raw_line)

    cond do
      line == "" or String.starts_with?(line, "#") ->
        acc

      true ->
        case String.split(raw_line, "=", parts: 2) do
          [raw_key, raw_value] ->
            key = String.trim(raw_key)

            if key == "" do
              raise "Invalid .env format at line #{line_number}: key cannot be empty."
            end

            value =
              raw_value
              |> String.trim()
              |> String.trim("\"")
              |> String.trim("'")

            Map.put(acc, key, value)

          _ ->
            raise "Invalid .env format at line #{line_number}: expected KEY=VALUE."
        end
    end
  end)
end

parse_positive_integer! = fn raw_value, label ->
  case Integer.parse(raw_value) do
    {parsed, ""} when parsed > 0 ->
      parsed

    _ ->
      raise "#{label} must be a positive integer, got: #{inspect(raw_value)}"
  end
end

if config_env() == :dev do
  dotenv_path = Path.expand("../.env", __DIR__)
  dotenv_values = if File.exists?(dotenv_path), do: read_dotenv_file!.(dotenv_path), else: %{}
  fetch_dev_env = fn key -> System.get_env(key) || Map.get(dotenv_values, key) end

  hint =
    if File.exists?(dotenv_path) do
      "Development environment (#{dotenv_path} and process env)"
    else
      "Development environment (process env; or create #{dotenv_path})"
    end

  gemini_key = require_env!.("GEMINI_API_KEY", hint, fetch_dev_env)
  tmdb_key = require_env!.("TMDB_API_KEY", hint, fetch_dev_env)

  config :say_less, :gemini_api_key, gemini_key
  config :say_less, :tmdb_api_key, tmdb_key
end

if config_env() == :prod do
  fetch_prod_env = &System.get_env/1
  gemini_key = require_env!.("GEMINI_API_KEY", "Production environment", fetch_prod_env)
  tmdb_key = require_env!.("TMDB_API_KEY", "Production environment", fetch_prod_env)

  config :say_less, :gemini_api_key, gemini_key
  config :say_less, :tmdb_api_key, tmdb_key

  secret_key_base = require_env!.("SECRET_KEY_BASE", "Production environment", fetch_prod_env)

  host = normalize_env_value.(System.get_env("PHX_HOST")) || "example.com"
  port = parse_positive_integer!.(normalize_env_value.(System.get_env("PORT")) || "4000", "PORT")

  config :say_less, SayLessWeb.Endpoint,
    url: [host: host, port: 443, scheme: "https"],
    http: [ip: {0, 0, 0, 0, 0, 0, 0, 0}, port: port],
    secret_key_base: secret_key_base

  if System.get_env("PHX_SERVER") do
    config :say_less, SayLessWeb.Endpoint, server: true
  end
end
