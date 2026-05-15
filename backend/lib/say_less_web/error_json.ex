defmodule SayLessWeb.ErrorJSON do
  def render("404.json", _assigns) do
    %{errors: %{code: "not_found", detail: "Not Found"}}
  end

  def render("500.json", _assigns) do
    %{errors: %{code: "internal_server_error", detail: "Internal Server Error"}}
  end

  def render(_template, _assigns) do
    %{errors: %{code: "error", detail: "Unexpected error"}}
  end
end
