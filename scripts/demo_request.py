"""UTF-8-safe API example for Windows PowerShell users."""
import argparse
import json
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?", default="终于成功了")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    request = Request(f"http://127.0.0.1:{args.port}/recommend", data=json.dumps({"text": args.text, "top_k": 3}, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=2) as response:
        print(json.dumps(json.load(response), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
