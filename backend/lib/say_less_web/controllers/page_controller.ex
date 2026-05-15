defmodule SayLessWeb.V1.PageController do
  use Phoenix.Controller, format: "json", layout: false

  def index(conn, _params) do
    json(conn, %{
      data: %{
        name: "SayLess API",
        version: "v1",
        endpoints: %{
          search: "/api/v1/search",
          targets: "/api/v1/media/:source/:media_id/targets",
          summarize: "/api/v1/summarize"
        }
      }
    })
  end
end
