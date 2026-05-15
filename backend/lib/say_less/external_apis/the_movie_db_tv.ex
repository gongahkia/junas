defmodule SayLess.ExternalApis.TheMovieDbTv do
  @moduledoc """
  TMDb adapter for TV search and episode-level summaries.
  """

  @behaviour SayLess.ExternalApis.Client

  alias SayLess.ExternalApis.Client

  @base_url "https://api.themoviedb.org/3"
  @image_url "https://image.tmdb.org/t/p/w500"

  @impl SayLess.ExternalApis.Client
  def search_titles(query) do
    url = "#{@base_url}/search/tv?#{URI.encode_query(base_query(%{"query" => query}))}"

    with {:ok, json} <- Client.request_json(url) do
      {:ok, Enum.map(Map.get(json, "results", []), &to_search_result/1)}
    end
  end

  @impl SayLess.ExternalApis.Client
  def list_targets(media_id) do
    with {:ok, show} <- fetch_show(media_id),
         {:ok, targets} <- fetch_season_targets(media_id, show) do
      {:ok,
       %{
         media: to_media(show),
         target_mode: "segment",
         targets: targets
       }}
    end
  end

  @impl SayLess.ExternalApis.Client
  def fetch_summary_subject(%{media_id: media_id, target_id: target_id, target_type: "episode"}) do
    with {:ok, show} <- fetch_show(media_id),
         {:ok, season_number, episode_number} <- parse_target_id(target_id),
         {:ok, episode} <- fetch_episode(media_id, season_number, episode_number) do
      content = """
      Series overview:
      #{Map.get(show, "overview") || "No series overview is available."}

      Episode overview:
      #{Map.get(episode, "overview") || "No episode overview is available."}
      """

      {:ok,
       %{
         content: content,
         media: to_media(show),
         target: %{
           id: target_id,
           type: "episode",
           label: episode_label(season_number, episode_number, episode),
           season_number: season_number,
           episode_number: episode_number
         }
       }}
    end
  end

  def fetch_summary_subject(_request) do
    Client.error(:unprocessable_entity, "invalid_target_type", "TV summaries currently require an episode target.")
  end

  defp fetch_show(media_id) do
    Client.request_json("#{@base_url}/tv/#{media_id}?#{URI.encode_query(base_query())}")
  end

  defp fetch_season_targets(media_id, show) do
    seasons =
      show
      |> Map.get("seasons", [])
      |> Enum.filter(fn season ->
        season_number = Map.get(season, "season_number")
        is_integer(season_number) and season_number > 0
      end)

    Enum.reduce_while(seasons, {:ok, []}, fn season, {:ok, acc} ->
      season_number = Map.fetch!(season, "season_number")

      case fetch_season(media_id, season_number) do
        {:ok, season_payload} ->
          season_targets =
            season_payload
            |> Map.get("episodes", [])
            |> Enum.map(fn episode ->
              episode_number = Map.get(episode, "episode_number")

              %{
                id: "#{season_number}:#{episode_number}",
                type: "episode",
                label: episode_label(season_number, episode_number, episode),
                season_number: season_number,
                episode_number: episode_number,
                description: truncate_text(Map.get(episode, "overview"))
              }
            end)

          {:cont, {:ok, acc ++ season_targets}}

        {:error, _, _, _} = error ->
          {:halt, error}
      end
    end)
  end

  defp fetch_season(media_id, season_number) do
    Client.request_json(
      "#{@base_url}/tv/#{media_id}/season/#{season_number}?#{URI.encode_query(base_query())}"
    )
  end

  defp fetch_episode(media_id, season_number, episode_number) do
    Client.request_json(
      "#{@base_url}/tv/#{media_id}/season/#{season_number}/episode/#{episode_number}?#{URI.encode_query(base_query())}"
    )
  end

  defp parse_target_id(target_id) do
    case String.split(target_id, ":", parts: 2) do
      [season, episode] ->
        with {season_number, ""} <- Integer.parse(season),
             {episode_number, ""} <- Integer.parse(episode),
             true <- season_number > 0 and episode_number > 0 do
          {:ok, season_number, episode_number}
        else
          _ ->
            Client.error(
              :unprocessable_entity,
              "invalid_target_id",
              "TV episode identifiers must be in the form season:episode."
            )
        end

      _ ->
        Client.error(
          :unprocessable_entity,
          "invalid_target_id",
          "TV episode identifiers must be in the form season:episode."
        )
    end
  end

  defp to_search_result(show) do
    %{
      id: to_string(Map.get(show, "id")),
      title: Map.get(show, "name") || "Unknown title",
      subtitle: show_subtitle(show),
      source: "themoviedbtv",
      source_label: "TMDb TV",
      media_type: "tv",
      image_url: image_url(Map.get(show, "poster_path")),
      external_url: external_url(Map.get(show, "id")),
      supports_segments: true
    }
  end

  defp to_media(show) do
    %{
      id: to_string(Map.get(show, "id")),
      title: Map.get(show, "name") || "Unknown title",
      subtitle: show_subtitle(show),
      source: "themoviedbtv",
      source_label: "TMDb TV",
      media_type: "tv",
      image_url: image_url(Map.get(show, "poster_path")),
      external_url: external_url(Map.get(show, "id"))
    }
  end

  defp show_subtitle(show) do
    [
      year_from_date(Map.get(show, "first_air_date")),
      seasons_text(show)
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" • ")
  end

  defp seasons_text(show) do
    case Map.get(show, "number_of_seasons") do
      count when is_integer(count) -> "#{count} seasons"
      _ -> nil
    end
  end

  defp episode_label(season_number, episode_number, episode) do
    title = Map.get(episode, "name")
    prefix = "S#{pad_number(season_number)}E#{pad_number(episode_number)}"

    case title do
      nil -> prefix
      "" -> prefix
      episode_title -> "#{prefix} • #{episode_title}"
    end
  end

  defp pad_number(number) when number < 10, do: "0#{number}"
  defp pad_number(number), do: Integer.to_string(number)

  defp base_query(extra \\ %{}) do
    Map.merge(%{"api_key" => tmdb_api_key()}, extra)
  end

  defp tmdb_api_key do
    Application.fetch_env!(:say_less, :tmdb_api_key)
  end

  defp image_url(nil), do: nil
  defp image_url(path), do: "#{@image_url}#{path}"

  defp external_url(nil), do: nil
  defp external_url(id), do: "https://www.themoviedb.org/tv/#{id}"

  defp year_from_date(nil), do: nil

  defp year_from_date(<<year::binary-size(4), "-", _rest::binary>>) do
    year
  end

  defp year_from_date(_), do: nil

  defp truncate_text(nil), do: nil

  defp truncate_text(text) when byte_size(text) > 140 do
    text
    |> binary_part(0, 137)
    |> Kernel.<>("...")
  end

  defp truncate_text(text), do: text
end
