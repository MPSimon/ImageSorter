import os
import socket
import argparse

from imagesorter.web.app import create_app


def _env_int(name: str):
    v = os.getenv(name)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _can_bind(host: str, port: int) -> bool:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        infos = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (host, port))]

    for family, socktype, proto, _canonname, sockaddr in infos:
        s = None
        try:
            s = socket.socket(family, socktype, proto)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(sockaddr)
            return True
        except OSError:
            continue
        finally:
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
    return False


def _pick_available_port(host: str, preferred_port: int, attempts: int = 50) -> int:
    if preferred_port < 0:
        raise ValueError("port must be >= 0")
    if preferred_port == 0:
        return 0

    for port in range(preferred_port, preferred_port + max(1, attempts)):
        if _can_bind(host, port):
            return port
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the ImageSorter server (dev)")
    default_host = os.getenv("HOST", "0.0.0.0")
    default_port = _env_int("PORT") or 5050
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=default_port)
    args = parser.parse_args()

    debug = os.getenv("DEBUG", "1") not in ("0", "false", "False")
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    requested_port = args.port
    chosen_port_env = _env_int("IMAGESORTER_CHOSEN_PORT")
    if debug and is_reloader_child and chosen_port_env is not None:
        chosen_port = chosen_port_env
    else:
        chosen_port = _pick_available_port(args.host, requested_port)
        os.environ["IMAGESORTER_CHOSEN_PORT"] = str(chosen_port)

    if (not debug) or is_reloader_child:
        if chosen_port != requested_port and chosen_port != 0:
            print(f"Port {requested_port} is unavailable; using {chosen_port} instead.")
        elif chosen_port == 0 and requested_port != 0:
            print(f"Port {requested_port} is unavailable; using an ephemeral free port instead.")
        print(f"Starting server on {args.host}:{chosen_port}")

    app = create_app()
    app.run(host=args.host, port=chosen_port, debug=debug)

