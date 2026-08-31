#!/usr/bin/env python3
"""O gabarito do prompts.json: o que está na página ainda é o que roda?

    python3 _shared/qa/test_prompts.py

Confere, bloco por bloco, se o texto do prompts.json continua igual à fonte de verdade: o
contrato comum no core_atendente_deploy.py, e o texto do cliente mais cada frase pronta no
n8n.json daquele cliente. Vermelho aqui é a lista de tarefas: alguém editou a página e o
arquivo de verdade ainda não foi atualizado.
"""
import importlib.util, json, pathlib, sys

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
CORE = RAIZ / "_shared/tools/core_atendente_deploy.py"


def contrato_de_verdade():
    s = importlib.util.spec_from_file_location("core_atendente_deploy", CORE)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m.PROMPT_CONTEXTO


def vigente(linhas):
    return [x for x in linhas if not x.get("valid_to")]


def main():
    dados = json.loads((AQUI / "prompts.json").read_text())
    falhas = []
    conferidos = 0

    if dados["contrato"]["texto"] != contrato_de_verdade():
        falhas.append("contrato comum: diferente do PROMPT_CONTEXTO em "
                      f"{CORE.relative_to(RAIZ)}")
    conferidos += 1

    for t in dados["tenants"]:
        arq = RAIZ / t["id"] / "n8n.json"
        if not arq.exists():
            falhas.append(f"{t['id']}: não achei {arq.relative_to(RAIZ)}")
            continue
        n8n = json.loads(arq.read_text())
        cli = vigente(n8n["clients"])
        conferidos += 1
        if len(cli) != 1:
            falhas.append(f"{t['id']}: esperava 1 registro vigente em clients, achei {len(cli)}")
        elif cli[0]["system_prompt"] != t["system_prompt"]:
            falhas.append(f"{t['id']}: o texto do cliente não bate com {arq.relative_to(RAIZ)}")

        fonte = {s["key"]: s["text"] for s in vigente(n8n.get("snippets", []))}
        for s in t["snippets"]:
            conferidos += 1
            if s["key"] not in fonte:
                falhas.append(f"{t['id']}: a frase `{s['key']}` não existe mais no n8n.json")
            elif fonte[s["key"]] != s["text"]:
                falhas.append(f"{t['id']}: a frase `{s['key']}` não bate com o n8n.json")
        for k in fonte:
            if k not in {s["key"] for s in t["snippets"]}:
                falhas.append(f"{t['id']}: a frase `{k}` está no n8n.json e falta na página")

    print(f"{conferidos} blocos conferidos, {len(falhas)} fora do lugar")
    for f in falhas:
        print("  x " + f)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
