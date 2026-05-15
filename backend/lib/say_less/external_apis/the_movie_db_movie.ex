defmodule SayLess.ExternalApis.TheMovieDbMovie do
  @moduledoc """
  TMDb adapter for movie search and title-level summaries.
  """

  @behaviour SayLess.ExternalApis.Client

  alias SayLess.ExternalApis.Client

  @base_url "https://api.themoviedb.org/3"
  @image_url "https://image.tmdb.org/t/p/w500"

  @impl SayLess.ExternalApis.Client
  def search_titles(query) do
    url = "#{@base_url}/search/movie?#{URI.encode_query(base_query(%{"query" => query}))}"

    with {:ok, json} <- Client.request_json(url) do
      {:ok, Enum.map(Map.get(json, "results", []), &to_search_result/1)}
    end
  end

  @impl SayLess.ExternalApis.Client
  def list_targets(media_id) do
    with {:ok, movie} <- fetch_movie(media_id) do
      media = to_media(movie)

      {:ok,
       %{
         media: media,
         target_mode: "title",
         targets: [
           %{
             id: media_id,
             type: "title",
             label: "Whole movie",
             description: "Summarize the movie overview available from TMDb."
           }
         ]
       }}
    end
  end

  @impl SayLess.ExternalApis.Client
  def fetch_summary_subject(request) do
    with {:ok, movie} <- fetch_movie(request.media_id) do
      overview = Map.get(movie, "overview") || "No overview is available for this movie."

      {:ok,
       %{
         content: overview,
         media: to_media(movie),
         target: %{
           id: request.media_id,
           type: "title",
           label: "Whole movie"
         }
       }}
    end
  end

  defp fetch_movie(media_id) do
    Client.request_json("#{@base_url}/movie/#{media_id}?#{URI.encode_query(base_query())}")
    |> case do
      {:ok, movie} -> {:ok, movie}
      {:error, _, _, _} = error -> error
    end
  end

  defp to_search_result(movie) do
    %{
      id: to_string(Map.get(movie, "id")),
      title: Map.get(movie, "title") || "Unknown title",
      subtitle: movie_subtitle(movie),
      source: "themoviedbmovie",
      source_label: "TMDb Movie",
      media_type: "movie",
      image_url: image_url(Map.get(movie, "poster_path")),
      external_url: external_url(Map.get(movie, "id"), "movie"),
      supports_segments: false
    }
  end

  defp to_media(movie) do
    %{
      id: to_string(Map.get(movie, "id")),
      title: Map.get(movie, "title") || "Unknown title",
      subtitle: movie_subtitle(movie),
      source: "themoviedbmovie",
      source_label: "TMDb Movie",
      media_type: "movie",
      image_url: image_url(Map.get(movie, "poster_path")),
      external_url: external_url(Map.get(movie, "id"), "movie")
    }
  end

  defp movie_subtitle(movie) do
    [
      year_from_date(Map.get(movie, "release_date")),
      Map.get(movie, "original_language")
      |> normalize_language()
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" • ")
  end

  defp normalize_language(nil), do: nil
  defp normalize_language(language), do: String.upcase(language)

  defp base_query(extra \\ %{}) do
    Map.merge(%{"api_key" => tmdb_api_key()}, extra)
  end

  defp tmdb_api_key do
    Application.fetch_env!(:say_less, :tmdb_api_key)
  end

  defp image_url(nil), do: nil
  defp image_url(path), do: "#{@image_url}#{path}"

  defp external_url(nil, _kind), do: nil
  defp external_url(id, kind), do: "https://www.themoviedb.org/#{kind}/#{id}"

  defp year_from_date(nil), do: nil

  defp year_from_date(<<year::binary-size(4), "-", _rest::binary>>) do
    year
  end

  defp year_from_date(_), do: nil
end
