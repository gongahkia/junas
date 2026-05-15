defmodule SayLessWeb.V1.SearchController do
  use Phoenix.Controller, format: "json", layout: false

  alias SayLess

  action_fallback SayLessWeb.V1.FallbackController

  def index(conn, params) do
    with {:ok, payload} <- SayLess.search_titles(params) do
      json(conn, %{data: payload})
    end
  end
end
