#!/usr/bin/env python3
"""Monta o `prompts.json` da página de revisão a partir das fontes de verdade.

A página existe pro cliente ler o que a IA dele recebe. Enquanto o JSON era escrito na mão,
ele envelhecia calado: em 01/09 estava 15 linhas atrás do contrato e com 5 frases diferentes
das que o paciente recebia. Agora ele é gerado, e o `test_prompts.py` vira a checagem de que
alguém rodou isto depois de mexer no prompt ou nas frases.

    python3 _shared/qa/gerar_prompts.py            # mostra o que mudaria
    python3 _shared/qa/gerar_prompts.py --aplicar
"""
import importlib.util
import json
import pathlib
import sys

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
DESTINO = AQUI / "prompts.json"


def contrato():
    s = importlib.util.spec_from_file_location(
        "core_atendente_deploy", RAIZ / "_shared/tools/core_atendente_deploy.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m.PROMPT_CONTEXTO


def vigente(linhas):
    return [x for x in linhas if not x.get("valid_to")]


def main():
    velho = json.loads(DESTINO.read_text())
    novo = dict(velho, contrato=dict(velho["contrato"], texto=contrato()))
    for t in novo["tenants"]:
        n8n = json.loads((RAIZ / t["id"] / "n8n.json").read_text())
        t["system_prompt"] = vigente(n8n["clients"])[0]["system_prompt"]
        # a página mostra o que o paciente recebe, então vai o texto; o `quando` e o `tipo`
        # são instrução pra IA, e o cliente não revisa isso
        t["snippets"] = [{"key": s["key"], "text": s["text"]}
                         for s in sorted(vigente(n8n.get("snippets", [])), key=lambda s: s["key"])]
    saida = json.dumps(novo, ensure_ascii=False, indent=2) + "\n"
    if "--aplicar" not in sys.argv:
        print("mudaria" if saida != DESTINO.read_text() else "nada a fazer")
        return 0
    DESTINO.write_text(saida)
    print("prompts.json atualizado:",
          sum(len(t["snippets"]) for t in novo["tenants"]), "frases,",
          len(novo["tenants"]), "cliente(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
