defmodule SayLessWeb.V1.MediaController do
  use Phoenix.Controller, format: "json", layout: false

  alias SayLess

  action_fallback SayLessWeb.V1.FallbackController

  def targets(conn, %{"source" => source, "media_id" => media_id}) do
    with {:ok, payload} <- SayLess.list_targets(%{"source" => source, "media_id" => media_id}) do
      json(conn, %{data: payload})
    end
  end
end
