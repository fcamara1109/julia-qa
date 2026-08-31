"""O que o gabarito ao vivo espera ler, dito pelo simulador.

O texto certo mora no `fluxos.json`, que o Felipe edita no navegador. O gabarito não guarda
mais frase escrita na mão: pergunta aqui. Comparar o texto inteiro não serve (o de verdade tem
outro nome, outra data), então a conta é a mesma do verificador estático: os pedaços do texto
que NÃO dependem de dado têm que aparecer na mensagem de verdade.

    from fluxos import casa
    ok, faltou = casa(cartao, "card_cancelado")
"""
import json, pathlib, sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from verificar_fluxos import fragmentos                    # noqa: E402

_D = None


def _dados():
    global _D
    if _D is None:
        _D = json.loads((AQUI / "fluxos.json").read_text())
    return _D


def bolha(apelido):
    """O texto que o simulador diz que esta mensagem é. Estoura se o apelido não existe: apelido
    errado no gabarito tem que quebrar alto, não passar verde por engano."""
    d = _dados()
    for fn in d["funcoes"]:
        for c in fn.get("cenarios", []):
            for painel in ("hoje", "depois"):
                for m in (c.get(painel) or {}).get("msgs", []):
                    if m.get("k") == apelido:
                        return m["t"]
    raise KeyError("apelido que não existe no fluxos.json: " + apelido)


def casa(real, apelido):
    """A mensagem de verdade diz o que o simulador manda dizer? Devolve (ok, o que faltou)."""
    faltou = [f for f in fragmentos(bolha(apelido), _dados()["exemplo"]) if f not in str(real)]
    return (not faltou), faltou


# os apelidos que o gabarito ao vivo cobra: mensagem de verdade tem outro nome e outra data,
# então o teste é a mesma mensagem com os dados trocados.
TROCA = [("Felipe Teste Camara", "Joana Pereira de Sá"), ("31/08", "09/09"),
         ("15h30", "08h00"), ("15:30", "08:00"), ("02/09", "12/09"), ("14h", "10h"),
         ("segunda", "terça"), ("Segunda", "Terça"), ("quarta", "sexta"), ("Quarta", "Sexta"),
         ("38 99911-0509", "31 98888-1111"), ("(38) 99911-0509", "(31) 98888-1111"),
         ("5538999110509", "5531988881111"), ("350", "420"), ("400", "480"), ("4412", "9901")]


def demo():
    for apelido in ("card_agendado", "card_ocupado", "card_erp", "card_sem_alvo",
                    "card_cancelado", "card_remarcado", "msg_cancelado", "msg_remarcado",
                    "readback_agendamento", "readback_cancelar", "readback_remarcar"):
        real = bolha(apelido)
        for de, para in TROCA:
            real = real.replace(de, para)
        ok, faltou = casa(real, apelido)
        assert ok, (apelido, faltou)
    # e o contrário: texto de outro cartão não pode passar por este
    assert not casa("🗑️ Desmarcado · Dr. X", "card_cancelado")[0]
    assert not casa(bolha("card_agendado"), "card_cancelado")[0]
    print("fluxos.py ok: 11 apelidos batem com dado trocado, e não batem com cartão errado")


if __name__ == "__main__":
    demo()
