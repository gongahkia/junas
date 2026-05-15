defmodule SayLess.ExternalApis.MyAnimeListAnime do
  @moduledoc """
  Jikan-backed MyAnimeList anime adapter with episode-level support.
  """

  @behaviour SayLess.ExternalApis.Client

  alias SayLess.ExternalApis.Client

  @base_url "https://api.jikan.moe/v4"

  @impl SayLess.ExternalApis.Client
  def search_titles(query) do
    url = "#{@base_url}/anime?#{URI.encode_query(%{"q" => query, "limit" => "8"})}"

    with {:ok, json} <- Client.request_json(url) do
      {:ok, Enum.map(Map.get(json, "data", []), &to_search_result/1)}
    end
  end

  @impl SayLess.ExternalApis.Client
  def list_targets(media_id) do
    with {:ok, anime} <- fetch_anime(media_id),
         {:ok, episodes} <- fetch_episode_index(media_id) do
      {:ok,
       %{
         media: to_media(anime),
         target_mode: "segment",
         targets: episodes
       }}
    end
  end

  @impl SayLess.ExternalApis.Client
  def fetch_summary_subject(%{media_id: media_id, target_id: target_id, target_type: "episode"}) do
    with {:ok, anime} <- fetch_anime(media_id),
         {:ok, episode_number} <- parse_episode_number(target_id),
         {:ok, episode} <- fetch_episode(media_id, episode_number) do
      series_synopsis = Map.get(anime, "synopsis") || "No series synopsis is available."
      episode_synopsis = Map.get(episode, "synopsis") || "No episode synopsis is available."

      {:ok,
       %{
         content: """
         Series overview:
         #{series_synopsis}

         Episode summary:
         #{episode_synopsis}
         """,
         media: to_media(anime),
         target: %{
           id: Integer.to_string(episode_number),
           type: "episode",
           label: episode_label(episode_number, episode),
           season_number: nil,
           episode_number: episode_number
         }
       }}
    end
  end

  def fetch_summary_subject(_request) do
    Client.error(:unprocessable_entity, "invalid_target_type", "Anime summaries currently require an episode target.")
  end

  defp fetch_anime(media_id) do
    Client.request_json("#{@base_url}/anime/#{media_id}")
    |> case do
      {:ok, %{"data" => anime}} -> {:ok, anime}
      {:ok, _json} -> Client.error(:bad_gateway, "upstream_invalid_shape", "Anime data was missing the expected payload.")
      {:error, _, _, _} = error -> error
    end
  end

  defp fetch_episode(media_id, episode_number) do
    Client.request_json("#{@base_url}/anime/#{media_id}/episodes/#{episode_number}")
    |> case do
      {:ok, %{"data" => episode}} -> {:ok, episode}
      {:ok, _json} -> Client.error(:bad_gateway, "upstream_invalid_shape", "Episode data was missing the expected payload.")
      {:error, _, _, _} = error -> error
    end
  end

  defp fetch_episode_index(media_id) do
    do_fetch_episode_index(media_id, 1, [])
  end

  defp do_fetch_episode_index(media_id, page, acc) do
    url = "#{@base_url}/anime/#{media_id}/episodes?#{URI.encode_query(%{"page" => Integer.to_string(page)})}"

    with {:ok, json} <- Client.request_json(url) do
      entries =
        json
        |> Map.get("data", [])
        |> Enum.with_index(length(acc) + 1)
        |> Enum.map(fn {episode, index} ->
          %{
            id: Integer.to_string(index),
            type: "episode",
            label: episode_label(index, episode),
            season_number: nil,
            episode_number: index,
            description: truncate_text(Map.get(episode, "synopsis"))
          }
        end)

      if get_in(json, ["pagination", "has_next_page"]) do
        do_fetch_episode_index(media_id, page + 1, acc ++ entries)
      else
        {:ok, acc ++ entries}
      end
    end
  end

  defp parse_episode_number(target_id) do
    case Integer.parse(target_id) do
      {number, ""} when number > 0 -> {:ok, number}
      _ -> Client.error(:unprocessable_entity, "invalid_target_id", "Anime episode identifiers must be positive integers.")
    end
  end

  defp to_search_result(anime) do
    %{
      id: to_string(Map.get(anime, "mal_id")),
      title: Map.get(anime, "title") || "Unknown title",
      subtitle: build_subtitle(anime),
      source: "myanimelistanime",
      source_label: "MyAnimeList Anime",
      media_type: "anime",
      image_url: image_url(anime),
      external_url: Map.get(anime, "url"),
      supports_segments: true
    }
  end

  defp to_media(anime) do
    %{
      id: to_string(Map.get(anime, "mal_id")),
      title: Map.get(anime, "title") || "Unknown title",
      subtitle: build_subtitle(anime),
      source: "myanimelistanime",
      source_label: "MyAnimeList Anime",
      media_type: "anime",
      image_url: image_url(anime),
      external_url: Map.get(anime, "url")
    }
  end

  defp build_subtitle(anime) do
    [
      Map.get(anime, "type"),
      year_text(anime),
      episodes_text(anime)
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" • ")
  end

  defp year_text(anime) do
    case get_in(anime, ["aired", "prop", "from", "year"]) || Map.get(anime, "year") do
      year when is_integer(year) -> Integer.to_string(year)
      _ -> nil
    end
  end

  defp episodes_text(anime) do
    case Map.get(anime, "episodes") do
      total when is_integer(total) -> "#{total} eps"
      _ -> nil
    end
  end

  defp image_url(anime) do
    get_in(anime, ["images", "jpg", "large_image_url"]) ||
      get_in(anime, ["images", "jpg", "image_url"])
  end

  defp episode_label(number, episode) do
    title =
      Map.get(episode, "title") ||
        Map.get(episode, "title_romanji") ||
        Map.get(episode, "title_japanese")

    case title do
      nil -> "Episode #{number}"
      "" -> "Episode #{number}"
      episode_title -> "Episode #{number} • #{episode_title}"
    end
  end

  defp truncate_text(nil), do: nil

  defp truncate_text(text) when byte_size(text) > 140 do
    text
    |> binary_part(0, 137)
    |> Kernel.<>("...")
  end

  defp truncate_text(text), do: text
end
