defmodule SayLessWeb.ConnCase do
  @moduledoc """
  Test case template for controller and endpoint tests.
  """

  use ExUnit.CaseTemplate

  using do
    quote do
      @endpoint SayLessWeb.Endpoint

      import Plug.Conn
      import Phoenix.ConnTest
      import SayLessWeb.ConnCase
    end
  end

  setup _tags do
    {:ok, conn: Phoenix.ConnTest.build_conn()}
  end
end
