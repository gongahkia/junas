"""Loopback-only research server with bounded, atomic synthetic-result checkpoints."""
import argparse
import json
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/checkpoint" or self.headers.get("Origin") not in {"http://localhost:8766", "http://127.0.0.1:8766"}:
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4_000_000:
                raise ValueError("checkpoint size")
            body = json.loads(self.rfile.read(length))
            name = body["name"]
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,120}", name):
                raise ValueError("checkpoint name")
            target = self.server.output / (name + ".json")
            temporary = target.with_suffix(".tmp")
            with temporary.open("w") as stream:
                json.dump(body["data"], stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(target)
            self.send_response(204)
            self.end_headers()
        except (KeyError, ValueError, TypeError):
            self.send_error(400)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8766), partial(Handler, directory="dist"))
    server.output = args.output
    server.serve_forever()
