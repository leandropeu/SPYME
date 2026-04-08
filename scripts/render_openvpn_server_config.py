from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "deploy" / "openvpn-server.conf.example"
ROUTES_PATH = ROOT / "deploy" / "openvpn-routing" / "server-routes.conf"


def main() -> None:
    parser = argparse.ArgumentParser(description="Renderiza o server config do OpenVPN com as rotas cadastradas.")
    parser.add_argument("--template", default=str(TEMPLATE_PATH))
    parser.add_argument("--routes", default=str(ROUTES_PATH))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    template = Path(args.template).read_text(encoding="utf-8").rstrip()
    routes_path = Path(args.routes)
    routes = routes_path.read_text(encoding="utf-8").strip() if routes_path.exists() else ""

    output = template
    if routes:
        output += "\n\n# Rotas geradas automaticamente\n" + routes.strip()
    output += "\n"

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    print(f"Config OpenVPN renderizada em: {output_path}")


if __name__ == "__main__":
    main()
