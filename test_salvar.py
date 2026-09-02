#!/usr/bin/env python3
"""Gabarito da Fase 3: editar na página e a bateria já ler a mudança.

A página não escreve em disco: ela manda o JSON inteiro pro `servir.py`. Este teste é esse
caminho inteiro, sem navegador: sobe o servidor, manda o POST que o botão Salvar manda, e lê
de volta com a mesma função que a bateria usa. Se o `carregar_gabarito` não vir a edição, o
"um gabarito só" virou dois.

    python3 _shared/qa/test_salvar.py
"""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from qa import carregar_gabarito                                            # noqa: E402

ARQ = AQUI / "gabarito.json"
PORTA = 8791
MARCA = "  (editado pelo teste, pode apagar)"


def main():
    antes = ARQ.read_text()
    srv = subprocess.Popen([sys.executable, str(AQUI / "servir.py"), str(PORTA)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://localhost:{PORTA}/gabarito.json", timeout=1).read()
                break
            except Exception:
                time.sleep(0.1)
        else:
            raise SystemExit("🔴 o servidor não subiu")

        d = json.loads(antes)
        alvo = next(c for c in d["casos"] if c["id"] == "manha")
        alvo["regras"] += MARCA
        req = urllib.request.Request(f"http://localhost:{PORTA}/salvar?alvo=gabarito.json",
                                     data=json.dumps(d, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5).read()

        lido = {c["id"]: c for c in carregar_gabarito(ARQ)}["manha"]
        if not lido["regras"].endswith(MARCA):
            raise SystemExit("🔴 salvou, mas a bateria continuou lendo a versão velha")
        if ARQ.read_text().count('"id": "S1"') != 1:
            raise SystemExit("🔴 o arquivo voltou torto do POST")
        print("🟢 a edição da página chega na bateria: salvar → carregar_gabarito → lê a mudança")
    finally:
        srv.terminate()
        ARQ.write_text(antes)   # o teste não deixa a sua marca no gabarito de verdade


if __name__ == "__main__":
    main()
