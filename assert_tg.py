#!/usr/bin/env python3
"""assert_tg.py — o roleplay: um caso do gabarito, atendido de verdade, no Telegram.

O caso roda na Júlia de verdade, a conversa acontece no bot do paciente como um atendimento
normal, e o grupo recebe o placar das travas do lado do que está aprovado na página. Você lê no
celular e me diz aqui se passou; eu gravo com `--veredito`.

    python3 _shared/qa/assert_tg.py manha              # toca o caso
    python3 _shared/qa/assert_tg.py --lista            # os casos que dá pra tocar
    python3 _shared/qa/assert_tg.py --veredito "nao ofereceu horário sem perguntar"

Custo: uma conversa por caso, centavos de Gemini. Nenhuma mensagem sai pra telefone: o payload
carimba a instância `qa` e manda o destino do sandbox junto (regra 8).
"""
import argparse
import datetime
import json
import pathlib
import sys
import time
import urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI.parent / "tools"))

from n8n import CTX                                                         # noqa: E402
from qa import carregar_gabarito                                            # noqa: E402
from travas import julgar                                                   # noqa: E402
from telegram_qa import TG_FELIPE, url as tg_url                            # noqa: E402
import qa_runner as R                                                       # noqa: E402

GABARITO = AQUI / "gabarito.json"
SIM = ("ok", "sim", "aprovado", "bom")
NAO = ("nao", "não", "reprovado", "ruim")


# --------------------------------------------------------------------- Telegram
def manda(alvo, chat, texto):
    for pedaco in [texto[i:i + 3900] for i in range(0, len(texto), 3900)] or [""]:
        corpo = json.dumps({"chat_id": chat or TG_FELIPE, "text": pedaco}).encode()
        req = urllib.request.Request(tg_url(alvo), data=corpo,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, context=CTX, timeout=20).read()


def como_texto(msgs):
    return "\n\n".join(("👤 " if m["quem"] == "paciente" else "🤖 ") + m["t"] for m in msgs)


# --------------------------------------------------------------------- gabarito
def casos():
    return {c["id"]: c for c in carregar_gabarito(GABARITO)}


def salvar(caso):
    d = json.loads(GABARITO.read_text())
    for i, c in enumerate(d["casos"]):
        if c["id"] == caso["id"]:
            # o que a página escreve não passa por aqui: só o histórico é meu
            d["casos"][i]["historico"] = caso["historico"]
    GABARITO.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")


def lista():
    L = ["Os casos do gabarito:"]
    for c in casos().values():
        h = (c.get("historico") or [{}])[-1]
        marca = {"aprovado": "🟢", "reprovado": "🔴"}.get(h.get("veredito"), "·")
        L.append(f"{marca} {c['id']} — {c['caso'][:58]}")
    L.append("\nassert_tg.py <id> pra tocar. Os outros casos não custam Gemini: são teste de código.")
    return "\n".join(L)


# --------------------------------------------------------------------- rodar
def rodar(cid, chat_pac="", chat_gru=""):
    c = casos().get(cid)
    if not c:
        manda("grupo", chat_gru, f"Não conheço o caso '{cid}'. /assert mostra a lista.")
        return
    R.usa_fluxo("core")
    base, key = R.load_creds()
    nonce = str(int(time.time()))[-6:]
    chatid = f"{R.CHATID_PREFIX}{nonce}@s.whatsapp.net"
    sender = c.get("sender") or c.get("paciente") or "Felipe Teste Camara"
    piso = max((int(e["id"]) for e in R._req(
        f"{base}/api/v1/executions?workflowId={R.WORKFLOW_ID}&limit=1", key).get("data", [])),
        default=0)

    manda("grupo", chat_gru, f"🧪 {c['id']}: {c['caso']}\n\nTocando agora, {len(c['turns'])} "
                             f"turnos. A conversa sai no bot do paciente.")
    turnos, skip = [], set()
    for n, fala in enumerate(c["turns"], 1):
        # a fala do paciente é ecoada: sem ela você vê só o lado dela, meia conversa
        manda("paciente", chat_pac, "👤 " + fala)
        R.fire_turn(base, chatid, fala, f"{c['id']}t{n}", sender, c.get("tenant", "fred"))
        exid, julia = R.poll_julia(base, key, chatid, fala, piso, skip)
        if julia is None:
            manda("grupo", chat_gru, f"⏱ o turno {n} não voltou a tempo. Rodada abortada.")
            return
        piso = exid
        turnos.append([fala, (julia or {}).get("mensagem") or "",
                       (julia or {}).get("handoff_tipo") or "nenhum"])

    ids = [t["id"] for t in (c.get("travas") or [])]
    veredito = julgar(turnos, ids) if ids else []
    linhas = []
    for tid, ok, motivo in veredito:
        diz = next((t["diz"] for t in c["travas"] if t["id"] == tid), tid)
        linhas.append(f"{'🟢' if ok else '⚪️' if ok is None else '🔴'} {diz}\n    {motivo}")
    placar = "\n".join(linhas) or "(este caso ainda não tem trava de máquina: julga o seu olho)"

    msgs = [{"quem": q, "t": t} for p, j, _ in turnos for q, t in (("paciente", p), ("Júlia", j))]
    c["historico"] = (c.get("historico") or []) + [{
        "data": datetime.date.today().isoformat(),
        "travas": [{"id": t, "ok": o, "motivo": m} for t, o, m in veredito],
        "msgs": msgs, "veredito": None, "feedback": None}]
    salvar(c)

    ap = (c.get("aprovado") or {}).get("msgs") or []
    manda("grupo", chat_gru,
          f"🧪 {c['id']}\n\nAS TRAVAS:\n{placar}\n\n" +
          (f"O QUE ESTÁ APROVADO NA PÁGINA:\n\n{como_texto(ap)}\n\n" if ap else "") +
          "❓ Aprovado ou reprovado? Responde aqui com /assert ok ... ou /assert nao ...")
    print(f"{c['id']}: {sum(1 for _, o, _ in veredito if o is False)} trava(s) quebrada(s)")


def veredito(pedido, chat_gru=""):
    """`pedido` é 'ok ...' ou 'nao ...'. Cai na última rodada que ainda não tem veredito."""
    v = pedido.split()[0].lower()
    feedback = pedido[len(v):].strip()
    quais = [c for c in casos().values()
             if c.get("historico") and c["historico"][-1].get("veredito") is None]
    if not quais:
        manda("grupo", chat_gru, "Não tem rodada esperando veredito. /assert <id> pra rodar uma.")
        return
    c = max(quais, key=lambda x: x["historico"][-1]["data"])
    ult = c["historico"][-1]
    ult["veredito"] = "aprovado" if v in SIM else "reprovado"
    ult["feedback"] = feedback
    # o passo que fecha o ciclo: rodada reprovada VIRA o contra-exemplo da página
    if ult["veredito"] == "reprovado":
        d = json.loads(GABARITO.read_text())
        for i, x in enumerate(d["casos"]):
            if x["id"] == c["id"]:
                d["casos"][i]["rejeitado"] = {
                    "porque": feedback or "reprovado sem motivo escrito",
                    "de_onde": f"rodada real de {ult['data']}", "msgs": ult["msgs"]}
        GABARITO.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    salvar(c)
    manda("grupo", chat_gru, f"Gravado no {c['id']}: {ult['veredito']}."
          + (" A rodada virou o contra-exemplo da página."
             if ult["veredito"] == "reprovado" else ""))
    print(f"{c['id']}: {ult['veredito']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caso", nargs="?", help="o id do caso a tocar")
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--veredito", help="'ok ...' ou 'nao ...' pra última rodada")
    a = ap.parse_args()
    if a.lista:
        print(lista())
    elif a.veredito:
        veredito(a.veredito)
    elif a.caso:
        rodar(a.caso)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
