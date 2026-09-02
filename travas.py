#!/usr/bin/env python3
"""travas.py — a ponte pro `_shared/qa/travas.js`, que é onde as regras moram de verdade.

As travas precisam rodar dentro do n8n (que é JS, e é onde o `/assert` do Telegram roda) e aqui
na linha de comando. Escrever as duas é escrever a mesma regra duas vezes, e elas divergem no
primeiro ajuste que esquecer uma. Então o arquivo é um só, `.js`, e este aqui chama `node`.

    python3 travas.py      # roda o autoteste do arquivo JS
"""
import json
import pathlib
import subprocess
import sys

JS = pathlib.Path(__file__).resolve().parent / "travas.js"


def julgar(turnos, ids=None):
    """[(id, veredito, motivo)]. veredito: True passou, False quebrou, None não se aplica."""
    prog = (f"const {{julgar}} = require({json.dumps(str(JS))});"
            "let e='';process.stdin.on('data',d=>e+=d).on('end',()=>{"
            "const a=JSON.parse(e);console.log(JSON.stringify(julgar(a.turnos,a.ids)));});")
    r = subprocess.run(["node", "-e", prog], input=json.dumps({"turnos": turnos, "ids": ids}),
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"travas.js falhou: {r.stderr.strip()}")
    return [tuple(x) for x in json.loads(r.stdout)]


if __name__ == "__main__":
    sys.exit(subprocess.run(["node", str(JS)]).returncode)
