"""Local Vivian demo. Run from the project with PYTHONPATH=src."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path

from tiny_voca.local_infer import DEFAULT_CHECKPOINT, load_local, synthesize_wav

PAGE = Path(__file__).with_name("index.html")


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, kind, data):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != "/":
            return self.send_error(404)
        self.reply(200, "text/html; charset=utf-8", PAGE.read_bytes())

    def do_POST(self):
        if self.path != "/synthesize":
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 32000:
                raise ValueError("请输入 1 至 2000 个字符")
            query = json.loads(self.rfile.read(length))
            phrase = query["text"]
            if not isinstance(phrase, str) or not 0 < len(phrase.strip()) <= 2000:
                raise ValueError("请输入 1 至 2000 个字符")
            audio = synthesize_wav(self.server.model, phrase.strip(), float(query.get("speed", 1)))
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            return self.reply(400, "text/plain; charset=utf-8", str(exc).encode())
        self.reply(200, "audio/wav", audio)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    args = parser.parse_args()
    model = load_local(args.checkpoint)
    with HTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.model = model
        print(f"http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
