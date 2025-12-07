
import http.server
import socketserver
import os

PORT = 8000
# We are in app/, so frontend is ../frontend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_DIR = os.path.join(BASE_DIR, "data")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith('/beers.json'):
            # Serve beers.json from data directory
            try:
                file_path = os.path.join(DATA_DIR, "beers.json")
                with open(file_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, "File not found")
            except Exception as e:
                self.send_error(500, str(e))
        else:
            super().do_GET()

    def end_headers(self):
        # Enable CORS for local development flexibility if needed
        self.send_header('Access-Control-Allow-Origin', '*')
        # Disable caching for development
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

def run_server(port=PORT):
    # No need to chdir if we use absolute paths for directory
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"Serving HTTP on http://localhost:{port}")
        print(f"Frontend: {FRONTEND_DIR}")
        print(f"Data: {DATA_DIR}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
