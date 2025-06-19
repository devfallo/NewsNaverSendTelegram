import http.server
import socketserver
import os

# Define the port to serve on
PORT = 8000

# Change the directory to the location of the HTML file
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Create a simple HTTP request handler
Handler = http.server.SimpleHTTPRequestHandler

# Start the server
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at port {PORT}. Open http://localhost:{PORT} in your browser.")
    httpd.serve_forever()
