defmodule SayLessWeb.Router do
  use Phoenix.Router

  pipeline :api do
    plug :accepts, ["json"]
  end

  scope "/", SayLessWeb do
    pipe_through :api
    get "/", V1.PageController, :index
  end

  scope "/api/v1", SayLessWeb do
    pipe_through :api

    get "/search", V1.SearchController, :index
    get "/media/:source/:media_id/targets", V1.MediaController, :targets
    post "/summarize", V1.SummaryController, :create
  end
end
