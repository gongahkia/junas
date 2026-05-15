defmodule SayLess.ExternalApis.MyAnimeListManga do
  @moduledoc """
  Jikan-backed MyAnimeList manga adapter for title search and title-level summaries.
  """

  @behaviour SayLess.ExternalApis.Client

  alias SayLess.ExternalApis.Client

  @base_url "https://api.jikan.moe/v4"

  @impl SayLess.ExternalApis.Client
  def search_titles(query) do
    url = "#{@base_url}/manga?#{URI.encode_query(%{"q" => query, "limit" => "8"})}"

    with {:ok, json} <- Client.request_json(url) do
      {:ok, Enum.map(Map.get(json, "data", []), &to_search_result/1)}
    end
  end

  @impl SayLess.ExternalApis.Client
  def list_targets(media_id) do
    with {:ok, manga} <- fetch_manga(media_id) do
      media = to_media(manga)

      {:ok,
       %{
         media: media,
         target_mode: "title",
         targets: [
           %{
             id: media_id,
             type: "title",
             label: "Whole manga",
             description: "Summarize the overall manga synopsis available from MyAnimeList."
           }
         ]
       }}
    end
  end

  @impl SayLess.ExternalApis.Client
  def fetch_summary_subject(request) do
    with {:ok, manga} <- fetch_manga(request.media_id) do
      {:ok,
       %{
         content: Map.get(manga, "synopsis") || "No synopsis is available for this manga.",
         media: to_media(manga),
         target: %{
           id: request.media_id,
           type: "title",
           label: "Whole manga"
         }
       }}
    end
  end

  defp fetch_manga(media_id) do
    Client.request_json("#{@base_url}/manga/#{media_id}")
    |> case do
      {:ok, %{"data" => manga}} -> {:ok, manga}
      {:ok, _json} -> Client.error(:bad_gateway, "upstream_invalid_shape", "MyAnimeList manga data was missing the expected payload.")
      {:error, _, _, _} = error -> error
    end
  end

  defp to_search_result(manga) do
    %{
      id: to_string(Map.get(manga, "mal_id")),
      title: Map.get(manga, "title") || "Unknown title",
      subtitle: build_subtitle(manga),
      source: "myanimelistmanga",
      source_label: "MyAnimeList Manga",
      media_type: "manga",
      image_url: image_url(manga),
      external_url: Map.get(manga, "url"),
      supports_segments: false
    }
  end

  defp to_media(manga) do
    %{
      id: to_string(Map.get(manga, "mal_id")),
      title: Map.get(manga, "title") || "Unknown title",
      subtitle: build_subtitle(manga),
      source: "myanimelistmanga",
      source_label: "MyAnimeList Manga",
      media_type: "manga",
      image_url: image_url(manga),
      external_url: Map.get(manga, "url")
    }
  end

  defp build_subtitle(manga) do
    [
      Map.get(manga, "status"),
      build_volume_text(manga)
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" • ")
  end

  defp build_volume_text(manga) do
    volumes = Map.get(manga, "volumes")
    chapters = Map.get(manga, "chapters")

    parts =
      [
        if(is_integer(volumes), do: "#{volumes} vols", else: nil),
        if(is_integer(chapters), do: "#{chapters} chs", else: nil)
      ]
      |> Enum.reject(&is_nil/1)

    case parts do
      [] -> nil
      _ -> Enum.join(parts, " • ")
    end
  end

  defp image_url(manga) do
    get_in(manga, ["images", "jpg", "large_image_url"]) ||
      get_in(manga, ["images", "jpg", "image_url"])
  end
end
