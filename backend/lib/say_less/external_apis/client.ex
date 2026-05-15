defmodule SayLess.ExternalApis.Client do
  @moduledoc """
  Behaviour and registry for fetching media data from external APIs.
  """

  @type error_tuple :: {:error, atom(), String.t(), String.t()}

  @callback search_titles(query :: String.t()) :: {:ok, list(map())} | error_tuple
  @callback list_targets(media_id :: String.t()) :: {:ok, map()} | error_tuple
  @callback fetch_summary_subject(request :: map()) :: {:ok, map()} | error_tuple

  @source_specs %{
    "myanimelistanime" => %{
      module: SayLess.ExternalApis.MyAnimeListAnime,
      label: "MyAnimeList Anime",
      media_type: "anime",
      target_types: ["episode"],
      supports_segments: true
    },
    "themoviedbtv" => %{
      module: SayLess.ExternalApis.TheMovieDbTv,
      label: "TMDb TV",
      media_type: "tv",
      target_types: ["episode"],
      supports_segments: true
    },
    "themoviedbmovie" => %{
      module: SayLess.ExternalApis.TheMovieDbMovie,
      label: "TMDb Movie",
      media_type: "movie",
      target_types: ["title"],
      supports_segments: false
    },
    "myanimelistmanga" => %{
      module: SayLess.ExternalApis.MyAnimeListManga,
      label: "MyAnimeList Manga",
      media_type: "manga",
      target_types: ["title"],
      supports_segments: false
    },
    "openlibrary" => %{
      module: SayLess.ExternalApis.OpenLibrary,
      label: "OpenLibrary",
      media_type: "book",
      target_types: ["title"],
      supports_segments: false
    }
  }

  def normalize_source("themoviedb"), do: "themoviedbmovie"
  def normalize_source(source) when is_binary(source), do: source
  def normalize_source(_), do: nil

  def source_spec(source) do
    Map.get(@source_specs, normalize_source(source))
  end

  def source_specs do
    @source_specs
  end

  def supported_sources do
    Map.keys(@source_specs)
  end

  def adapter_for_source(source) do
    case source_spec(source) do
      %{module: module} -> {:ok, module}
      nil -> error(:unprocessable_entity, "unsupported_source", "Unsupported media source.")
    end
  end

  def error(status, code, detail) do
    {:error, status, code, detail}
  end

  def parse_json(body, code) do
    case Jason.decode(body) do
      {:ok, json} -> {:ok, json}
      {:error, _reason} -> error(:bad_gateway, code, "Received invalid JSON from an upstream service.")
    end
  end

  def request_json(url, options \\ []) do
    headers = Keyword.get(options, :headers, [])
    request_options = Keyword.get(options, :request_options, [])

    case http_client().get(url, headers, request_options) do
      {:ok, %{status_code: 200, body: body}} ->
        parse_json(body, "upstream_invalid_json")

      {:ok, %{status_code: 401}} ->
        error(:bad_gateway, "upstream_unauthorized", "An upstream API rejected the configured credentials.")

      {:ok, %{status_code: 404}} ->
        error(:not_found, "upstream_not_found", "The requested media item could not be found upstream.")

      {:ok, %{status_code: 429}} ->
        error(:too_many_requests, "upstream_rate_limited", "An upstream API rate limit was reached. Please try again later.")

      {:ok, %{status_code: status_code}} when status_code >= 500 ->
        error(:bad_gateway, "upstream_unavailable", "An upstream API is currently unavailable.")

      {:ok, %{status_code: status_code}} ->
        error(:bad_gateway, "upstream_request_failed", "An upstream API returned status #{status_code}.")

      {:error, %{reason: reason}} ->
        error(:bad_gateway, "upstream_connection_failed", "Failed to connect to an upstream API: #{inspect(reason)}")

      {:error, reason} ->
        error(:bad_gateway, "upstream_connection_failed", "Failed to connect to an upstream API: #{inspect(reason)}")
    end
  end

  defp http_client do
    Application.get_env(:say_less, :http_client, SayLess.HttpClient)
  end
end
