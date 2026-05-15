defmodule SayLessWeb.ErrorJSONTest do
  use ExUnit.Case, async: true

  test "renders 404" do
    assert SayLessWeb.ErrorJSON.render("404.json", %{}) ==
             %{errors: %{code: "not_found", detail: "Not Found"}}
  end

  test "renders 500" do
    assert SayLessWeb.ErrorJSON.render("500.json", %{}) ==
             %{errors: %{code: "internal_server_error", detail: "Internal Server Error"}}
  end
end
