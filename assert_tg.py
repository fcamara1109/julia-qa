#!/usr/bin/env python3
"""assert_tg.py — o ▶ da página, tocado pelo Telegram.

Você digita `/assert manha` no sandbox (em qualquer um dos dois bots). O caso roda na Júlia de
verdade, a conversa acontece no bot do paciente como um atendimento normal, e o grupo recebe o
placar das travas do lado do que está aprovado na página, com a pergunta. O que você responder
(`/assert ok ...` ou `/assert nao ...`) vira o histórico do caso.

    python3 _shared/qa/assert_tg.py --escutar     # fica ouvindo os /assert do Telegram
    python3 _shared/qa/assert_tg.py manha         # toca um caso sem passar pelo Telegram
    python3 _shared/qa/assert_tg.py --lista       # a lista, no terminal

Por que o miolo mora aqui e não no n8n: pra julgar é preciso ler o que a Júlia respondeu, e
isso sai da execução, pela API. Quem já sabe fazer isso é o runner da bateria. Refazer isso
dentro do fluxo seria a mesma regra escrita duas vezes, que é o que este projeto existe pra
matar. O n8n só registra o pedido; ele fica na execução e este programa lê de lá.

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
sys.path.insert(0, str(AQUI.parent))
sys.path.insert(0, str(AQUI.parent / "tools"))
sys.path.insert(0, str(AQUI.parent / "piloto-assert"))

from n8n import api, env, CTX                                               # noqa: E402
from qa import carregar_gabarito                                            # noqa: E402
from travas import julgar                                                   # noqa: E402
from telegram_qa import TG_FELIPE, url as tg_url                            # noqa: E402
import qa_runner as R                                                       # noqa: E402

GABARITO = AQUI / "gabarito.json"
FLUXO = "Sandbox · Telegram"
VISTO = AQUI / ".visto.json"          # até onde já li as execuções do sandbox
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


def lista(so_bateria=True):
    L = ["Os casos do gabarito:"]
    for c in casos().values():
        if so_bateria and (c.get("camada") or "bateria") != "bateria":
            continue
        h = (c.get("historico") or [{}])[-1]
        marca = {"aprovado": "🟢", "reprovado": "🔴"}.get(h.get("veredito"), "·")
        L.append(f"{marca} {c['id']} — {c['caso'][:58]}")
    L.append("\n/assert <id> pra tocar. Os outros 36 casos não custam Gemini: são teste de código.")
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


# --------------------------------------------------------------------- escutar
def fluxo_id():
    return [w for w in api("/workflows?limit=100")["data"] if w["name"] == FLUXO][0]["id"]


def pedidos(wid, desde):
    """Os /assert que apareceram nas execuções do sandbox depois de `desde`."""
    ids = sorted(int(e["id"]) for e in
                 api(f"/executions?workflowId={wid}&limit=30").get("data", []))
    saida, ultimo = [], desde
    for exid in [i for i in ids if i > desde]:
        ultimo = max(ultimo, exid)
        try:
            d = api(f"/executions/{exid}?includeData=true")
        except Exception:
            continue
        try:
            j = d["data"]["resultData"]["runData"]["Decidir"][0]["data"]["main"][0][0]["json"]
        except Exception:
            continue
        if j.get("assert_pedido"):
            e = json.loads(j.get("estado") or "{}")
            saida.append((j["assert_pedido"], e.get("paciente", ""), e.get("grupo", "")))
    return saida, ultimo


def escutar(intervalo=15):
    wid = fluxo_id()
    visto = json.loads(VISTO.read_text()).get("execucao", 0) if VISTO.is_file() else 0
    if not visto:   # na primeira vez começa de agora: pedido velho não é pedido
        visto = max((int(e["id"]) for e in
                     api(f"/executions?workflowId={wid}&limit=1").get("data", [])), default=0)
        VISTO.write_text(json.dumps({"execucao": visto}) + "\n")
    print(f"ouvindo os /assert do sandbox (execução {visto} pra frente). ctrl+c pra parar.")
    while True:
        try:
            novos, visto = pedidos(wid, visto)
            VISTO.write_text(json.dumps({"execucao": visto}) + "\n")
            for pedido, pac, gru in novos:
                print(f"→ /assert {pedido}")
                agir(pedido, pac, gru)
        except Exception as e:
            print("erro no ciclo:", e)
        time.sleep(intervalo)


def agir(pedido, chat_pac="", chat_gru=""):
    v = pedido.split()[0].lower() if pedido.split() else ""
    if pedido == "(lista)" or not pedido:
        manda("grupo", chat_gru, lista())
    elif v in SIM or v in NAO:
        veredito(pedido, chat_gru)
    else:
        rodar(v, chat_pac, chat_gru)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caso", nargs="?", help="o id do caso a tocar")
    ap.add_argument("--escutar", action="store_true", help="fica ouvindo o Telegram")
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--veredito", help="'ok ...' ou 'nao ...' pra última rodada")
    a = ap.parse_args()
    if a.escutar:
        return escutar()
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
