defmodule SayLess.ExternalApis.OpenLibrary do
  @moduledoc """
  OpenLibrary adapter for title search and title-level summaries.
  """

  @behaviour SayLess.ExternalApis.Client

  alias SayLess.ExternalApis.Client

  @search_url "https://openlibrary.org/search.json"
  @works_url "https://openlibrary.org/works"
  @covers_url "https://covers.openlibrary.org/b/id"

  @impl SayLess.ExternalApis.Client
  def search_titles(query) do
    url = "#{@search_url}?#{URI.encode_query(%{"q" => query, "limit" => "8"})}"

    with {:ok, json} <- Client.request_json(url) do
      results =
        json
        |> Map.get("docs", [])
        |> Enum.map(&to_search_result/1)
        |> Enum.reject(&is_nil/1)

      {:ok, results}
    end
  end

  @impl SayLess.ExternalApis.Client
  def list_targets(media_id) do
    with {:ok, work} <- fetch_work(media_id) do
      media = to_media(work, media_id)

      {:ok,
       %{
         media: media,
         target_mode: "title",
         targets: [
           %{
             id: media_id,
             type: "title",
             label: "Whole book",
             description: "Summarize the overall work overview available from OpenLibrary."
           }
         ]
       }}
    end
  end

  @impl SayLess.ExternalApis.Client
  def fetch_summary_subject(request) do
    with {:ok, work} <- fetch_work(request.media_id) do
      media = to_media(work, request.media_id)

      {:ok,
       %{
         content: description_from_work(work),
         media: media,
         target: %{
           id: request.media_id,
           type: "title",
           label: "Whole book"
         }
       }}
    end
  end

  defp fetch_work(media_id) do
    url = "#{@works_url}/#{media_id}.json"
    Client.request_json(url)
  end

  defp to_search_result(doc) do
    with key when is_binary(key) <- Map.get(doc, "key"),
         "works/" <> work_id <- String.trim_leading(key, "/") do
      %{
        id: work_id,
        title: Map.get(doc, "title") || "Unknown title",
        subtitle: build_subtitle(doc),
        source: "openlibrary",
        source_label: "OpenLibrary",
        media_type: "book",
        image_url: build_cover_url(Map.get(doc, "cover_i")),
        external_url: "https://openlibrary.org/works/#{work_id}",
        supports_segments: false
      }
    else
      _ -> nil
    end
  end

  defp to_media(work, media_id) do
    %{
      id: media_id,
      title: Map.get(work, "title") || "Unknown title",
      subtitle: build_media_subtitle(work),
      source: "openlibrary",
      source_label: "OpenLibrary",
      media_type: "book",
      image_url: work |> Map.get("covers", []) |> List.first() |> build_cover_url(),
      external_url: "https://openlibrary.org/works/#{media_id}"
    }
  end

  defp description_from_work(work) do
    case Map.get(work, "description") do
      %{"value" => text} when is_binary(text) and text != "" -> text
      text when is_binary(text) and text != "" -> text
      _ -> "No description is available for this work."
    end
  end

  defp build_subtitle(doc) do
    author =
      doc
      |> Map.get("author_name", [])
      |> List.first()

    year =
      case Map.get(doc, "first_publish_year") do
        year when is_integer(year) -> Integer.to_string(year)
        _ -> nil
      end

    [author, year]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" • ")
  end

  defp build_media_subtitle(work) do
    subjects =
      work
      |> Map.get("subjects", [])
      |> Enum.take(2)
      |> Enum.join(" • ")

    if subjects == "", do: nil, else: subjects
  end

  defp build_cover_url(nil), do: nil
  defp build_cover_url(cover_id), do: "#{@covers_url}/#{cover_id}-L.jpg"
end
