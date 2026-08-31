#!/usr/bin/env python3
"""Serve o simulador e recebe o Salvar. O navegador não escreve em disco sozinho e o Chrome
recusa file://, então o botão manda o JSON inteiro pra cá e aqui ele vira arquivo.

    python3 _shared/qa/servir.py        # abre em http://localhost:8777
"""
import http.server, json, pathlib, functools, sys

AQUI = pathlib.Path(__file__).resolve().parent


GRAVAVEIS = {"fluxos.json", "prompts.json"}


class Mao(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if not self.path.startswith("/salvar"):
            return self.send_error(404)
        # /salvar continua sendo o fluxos.json: a página antiga não muda
        alvo = self.path.partition("?")[2].partition("=")[2] or "fluxos.json"
        if alvo not in GRAVAVEIS:
            return self.send_error(400, f"so gravo {' ou '.join(sorted(GRAVAVEIS))}")
        corpo = self.rfile.read(int(self.headers["Content-Length"]))
        # json.loads antes de gravar: metade de um POST não vira arquivo pela metade
        dados = json.loads(corpo)
        (AQUI / alvo).write_text(json.dumps(dados, ensure_ascii=False, indent=1) + "\n")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
        print(f"{alvo} gravado")


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    print(f"http://localhost:{porta}/  (ctrl+c pra parar)")
    http.server.HTTPServer(("", porta),
        functools.partial(Mao, directory=str(AQUI))).serve_forever()
