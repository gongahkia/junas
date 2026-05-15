defmodule SayLessWeb.ApiWorkflowTest do
  use SayLessWeb.ConnCase, async: false

  alias SayLess.TestSupport.FakeHttpClient

  setup do
    Application.put_env(:say_less, :http_client, FakeHttpClient)
    Application.put_env(:say_less, :gemini_api_key, "test-gemini-key")
    Application.put_env(:say_less, :tmdb_api_key, "test-tmdb-key")
    FakeHttpClient.reset()

    on_exit(fn ->
      Application.put_env(:say_less, :http_client, SayLess.HttpClient)
      FakeHttpClient.reset()
    end)

    :ok
  end

  test "search returns normalized anime results", %{conn: conn} do
    FakeHttpClient.stub_get(fn url, _headers, _options ->
      assert url =~ "https://api.jikan.moe/v4/anime?"
      assert url =~ "q=rezero"

      {:ok,
       %{
         status_code: 200,
         body:
           Jason.encode!(%{
             "data" => [
               %{
                 "mal_id" => 31240,
                 "title" => "Re:ZERO -Starting Life in Another World-",
                 "url" => "https://myanimelist.net/anime/31240",
                 "type" => "TV",
                 "episodes" => 25,
                 "year" => 2016,
                 "images" => %{"jpg" => %{"image_url" => "https://cdn.example/anime.jpg"}}
               }
             ]
           })
       }}
    end)

    response =
      conn
      |> get("/api/v1/search", %{source: "myanimelistanime", query: "rezero"})
      |> json_response(200)

    assert response["data"]["results"] == [
             %{
               "external_url" => "https://myanimelist.net/anime/31240",
               "id" => "31240",
               "image_url" => "https://cdn.example/anime.jpg",
               "media_type" => "anime",
               "source" => "myanimelistanime",
               "source_label" => "MyAnimeList Anime",
               "subtitle" => "TV • 2016 • 25 eps",
               "supports_segments" => true,
               "title" => "Re:ZERO -Starting Life in Another World-"
             }
           ]
  end

  test "targets returns episode options for tv shows", %{conn: conn} do
    FakeHttpClient.stub_get(fn url, _headers, _options ->
      cond do
        url =~ "https://api.themoviedb.org/3/tv/1399?" ->
          {:ok,
           %{
             status_code: 200,
             body:
               Jason.encode!(%{
                 "id" => 1399,
                 "name" => "Game of Thrones",
                 "first_air_date" => "2011-04-17",
                 "number_of_seasons" => 1,
                 "poster_path" => "/got.jpg",
                 "seasons" => [
                   %{"season_number" => 0},
                   %{"season_number" => 1}
                 ]
               })
           }}

        url =~ "https://api.themoviedb.org/3/tv/1399/season/1?" ->
          {:ok,
           %{
             status_code: 200,
             body:
               Jason.encode!(%{
                 "episodes" => [
                   %{
                     "episode_number" => 1,
                     "name" => "Winter Is Coming",
                     "overview" => "The Stark family receives royal visitors."
                   },
                   %{
                     "episode_number" => 2,
                     "name" => "The Kingsroad",
                     "overview" => "The parties begin to split across the realm."
                   }
                 ]
               })
           }}

        true ->
          flunk("unexpected GET url: #{url}")
      end
    end)

    response =
      conn
      |> get("/api/v1/media/themoviedbtv/1399/targets")
      |> json_response(200)

    assert response["data"]["media"]["title"] == "Game of Thrones"
    assert response["data"]["target_mode"] == "segment"

    assert response["data"]["targets"] == [
             %{
               "description" => "The Stark family receives royal visitors.",
               "episode_number" => 1,
               "id" => "1:1",
               "label" => "S01E01 • Winter Is Coming",
               "season_number" => 1,
               "type" => "episode"
             },
             %{
               "description" => "The parties begin to split across the realm.",
               "episode_number" => 2,
               "id" => "1:2",
               "label" => "S01E02 • The Kingsroad",
               "season_number" => 1,
               "type" => "episode"
             }
           ]
  end

  test "summarize returns a structured summary payload", %{conn: conn} do
    FakeHttpClient.stub_get(fn url, _headers, _options ->
      assert url =~ "https://api.themoviedb.org/3/movie/550?"

      {:ok,
       %{
         status_code: 200,
         body:
           Jason.encode!(%{
             "id" => 550,
             "title" => "Fight Club",
             "release_date" => "1999-10-15",
             "original_language" => "en",
             "poster_path" => "/fightclub.jpg",
             "overview" => "An insomniac office worker crosses paths with a charismatic soap maker."
           })
       }}
    end)

    FakeHttpClient.stub_post(fn url, body, headers, _options ->
      assert url =~ "generativelanguage.googleapis.com"
      assert {"X-goog-api-key", "test-gemini-key"} in headers
      assert body =~ "Be explicit and comprehensive"
      assert body =~ "\"responseMimeType\":\"application/json\""

      {:ok,
       %{
         status_code: 200,
         body:
           Jason.encode!(%{
             "candidates" => [
               %{
                 "content" => %{
                   "parts" => [
                     %{
                       "text" =>
                         Jason.encode!(%{
                           "characters" => ["The Narrator", "Tyler Durden"],
                           "key_events" => ["The narrator forms an escalating bond with Tyler."],
                           "plot_points" => ["The underground movement starts to reshape his life."],
                           "skip_context" => "The protagonist is now deeply entangled in Tyler's worldview."
                         })
                     }
                   ]
                 }
               }
             ]
           })
       }}
    end)

    response =
      conn
      |> put_req_header("content-type", "application/json")
      |> post("/api/v1/summarize", %{
        source: "themoviedbmovie",
        media_id: "550",
        target_type: "title",
        spoiler_level: "full"
      })
      |> json_response(201)

    assert response["data"]["media"]["title"] == "Fight Club"
    assert response["data"]["target"]["label"] == "Whole movie"
    assert response["data"]["meta"]["spoiler_level"] == "full"

    assert response["data"]["summary"] == %{
             "characters" => ["The Narrator", "Tyler Durden"],
             "key_events" => ["The narrator forms an escalating bond with Tyler."],
             "plot_points" => ["The underground movement starts to reshape his life."],
             "skip_context" => "The protagonist is now deeply entangled in Tyler's worldview."
           }
  end

  test "summarize rejects unsupported target types before upstream calls", %{conn: conn} do
    response =
      conn
      |> put_req_header("content-type", "application/json")
      |> post("/api/v1/summarize", %{
        source: "themoviedbmovie",
        media_id: "550",
        target_type: "episode",
        target_id: "1:1",
        spoiler_level: "standard"
      })
      |> json_response(422)

    assert response == %{
             "errors" => %{
               "code" => "invalid_target_type",
               "detail" => "This source does not support the requested target type."
             }
           }
  end
end
