defmodule SayLessWeb.V1.FallbackController do
  use Phoenix.Controller, format: "json", layout: false

  def call(conn, {:error, status, code, detail}) do
    conn
    |> put_status(status)
    |> json(%{errors: %{code: code, detail: detail}})
  end

  def call(conn, {:error, reason}) when is_binary(reason) do
    conn
    |> put_status(:bad_request)
    |> json(%{errors: %{code: "bad_request", detail: reason}})
  end
end
