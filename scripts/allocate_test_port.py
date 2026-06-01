#!/usr/bin/env python3
from __future__ import annotations

import socket


def allocate_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    print(allocate_port())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
