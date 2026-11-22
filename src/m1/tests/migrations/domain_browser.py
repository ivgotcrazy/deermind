"""给本机 HTTPS 代理提供真实 API 和隔离的合成领域测试库。"""

import signal

from auth_browser import main
from realtime_browser import terminate
from usage_browser import seed

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    main(seed, origin="https://127.0.0.1:5206", port=5207, serve_client=False)
