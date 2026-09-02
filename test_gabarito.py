#!/usr/bin/env python3
"""O gabarito confere consigo mesmo: a conversa aprovada passa no que o próprio caso cobra?

Se a conversa que está escrita como certa reprova no assert do mesmo caso, um dos dois está
errado, e descobrir isso não pode custar uma bateria paga. Roda de graça, em segundos.

    python3 _shared/qa/test_gabarito.py
"""
import json
import pathlib
import sys
import unicodedata

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI.parent / "piloto-assert"))
from qa import carregar_gabarito                                            # noqa: E402
from travas import julgar                                                   # noqa: E402

erros = []
n = 0


def limpo(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def falas(msgs):
    """As msgs viram os turnos que as travas leem. Sem handoff: conversa escrita não tem
    execução, então quem julga aqui é o texto."""
    turnos, pac = [], None
    for m in msgs:
        if m["quem"] == "paciente":
            pac = m["t"]
        elif pac is not None:
            turnos.append([pac, m["t"]])
            pac = None
    return turnos


for c in carregar_gabarito(AQUI / "gabarito.json"):
    ap = c.get("aprovado")
    if not ap:
        continue
    n += 1
    julia = limpo("\n".join(m["t"] for m in ap["msgs"] if m["quem"] != "paciente"))
    ch = c.get("checagens") or {}
    for termo in ch.get("contem", []):
        if limpo(termo) not in julia:
            erros.append(f"{c['id']}: a conversa aprovada não diz '{termo}', e o caso exige")
    for termo in ch.get("nao_contem", []):
        if limpo(termo) in julia:
            erros.append(f"{c['id']}: a conversa aprovada diz '{termo}', e o caso proíbe")

    ids = [t["id"] for t in (c.get("travas") or [])]
    if not ids:
        continue
    if any(ok is False for _, ok, _ in julgar(falas(ap["msgs"]), ids)):
        quais = [f"{i} ({m})" for i, ok, m in julgar(falas(ap["msgs"]), ids) if ok is False]
        erros.append(f"{c['id']}: a conversa aprovada quebra a própria trava: {', '.join(quais)}")
    rj = c.get("rejeitado")
    if rj and not any(ok is False for _, ok, _ in julgar(falas(rj["msgs"]), ids)):
        erros.append(f"{c['id']}: a conversa rejeitada passa em todas as travas, "
                     "então as travas não pegam o erro que o caso existe pra pegar")

print("\n".join("🔴 " + e for e in erros) if erros else
      f"🟢 as {n} conversas escritas passam no que o próprio caso cobra")
sys.exit(1 if erros else 0)
