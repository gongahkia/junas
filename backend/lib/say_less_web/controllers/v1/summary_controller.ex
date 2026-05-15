defmodule SayLessWeb.V1.SummaryController do
  use Phoenix.Controller, format: "json", layout: false

  alias SayLess

  action_fallback SayLessWeb.V1.FallbackController

  def create(conn, params) do
    with {:ok, summary} <- SayLess.summarize(params) do
      conn
      |> put_status(:created)
      |> json(%{data: summary})
    end
  end
end
