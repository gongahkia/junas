package handlers

import (
	"fmt"
	"html"
	"net/http"

	"github.com/go-chi/chi/v5"
)

// JoinPage handles GET /join/{slug}.
// Renders a fallback HTML page for users who don't have the app installed.
func JoinPage(w http.ResponseWriter, r *http.Request) {
	slug := chi.URLParam(r, "slug")
	if slug == "" {
		http.NotFound(w, r)
		return
	}
	safeSlug := html.EscapeString(slug)
	host := r.Host
	deepLink := fmt.Sprintf("kiltertogether://join?slug=%s&server=%s", safeSlug, html.EscapeString(host))

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprintf(w, `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Join Room – Kilter Together</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#111;color:#e8e8e8;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:1rem}
.card{max-width:420px;width:100%%;text-align:center;padding:2.5rem 2rem;background:#1a1a1a;border-radius:16px;border:1px solid #333}
h1{font-size:1.5rem;margin-bottom:.5rem}
.slug{color:#999;font-size:.875rem;margin-bottom:1.25rem}
p{color:#aaa;font-size:.9rem;line-height:1.5;margin-bottom:1.5rem}
.btn{display:inline-block;padding:.75rem 2rem;background:#e05c2e;color:#fff;text-decoration:none;border-radius:10px;font-weight:600;font-size:1rem;transition:background .15s}
.btn:hover{background:#c44e26}
.stores{margin-top:1.5rem;font-size:.8rem;color:#777}
.stores a{color:#999;text-decoration:underline;margin:0 .5rem}
</style>
</head>
<body>
<div class="card">
<h1>Join Room</h1>
<p class="slug">%s</p>
<p>Kilter Together is a collaborative climbing session app. Open this link in the app to join the room.</p>
<a class="btn" href="%s">Open in app</a>
<div class="stores">
<p>Don't have the app?</p>
<a href="https://apps.apple.com/app/kilter-together">App Store</a>
<a href="https://play.google.com/store/apps/details?id=com.kiltertogether">Google Play</a>
</div>
</div>
</body>
</html>`, safeSlug, deepLink)
}
