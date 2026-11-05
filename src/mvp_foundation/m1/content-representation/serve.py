"""Local read-only reference viewer; no model calls, no product state writes."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=5183);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(SimpleHTTPRequestHandler,directory=str(Path(__file__).resolve().parent)))
    print(f'Content review: http://127.0.0.1:{args.port}/',flush=True)
    server.serve_forever()
