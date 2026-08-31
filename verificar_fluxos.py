#!/usr/bin/env python3
"""Gabarito estático do simulador: o texto que está no HTML ainda é o texto que o código manda?

O `fluxos.json` é a fonte da verdade visual: o Felipe edita a bolha no navegador, salva, e
aqui a gente cobra o código. Cada mensagem que é NOSSA (não é prosa do modelo nem fala de
gente) carrega o campo `f`, o arquivo de onde ela sai. Esta tool quebra o texto nos pedaços
que não dependem de dado (tira nome, data, hora, valor) e exige que cada pedaço ainda exista
naquele arquivo.

    python3 verificar_fluxos.py              # placar
    python3 verificar_fluxos.py -v           # mostra cada pedaço que sumiu

Vermelho aqui não é bug: é a lista do que falta mudar no código pra alcançar o HTML.
"""
import json, re, sys, pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent      # doctors/
FLUXOS = pathlib.Path(__file__).resolve().parent / "fluxos.json"

# de onde uma mensagem nossa pode sair. `snippet:<key>` é caso à parte: mora na tabela do cliente.
FONTES = {
    "core":      "_shared/tools/core_atendente_deploy.py",
    "comandos":  "_shared/tools/core_comandos_deploy.py",
    "cancelar":  "_shared/adaptadores/asa/cancelar.js",
    "agenda":    "_shared/agenda.js",
    "v1comandos": "_shared/tools/comandos_base.json",
    "widget":    "_shared/tools/leads_deploy.py",
    "destinos":  "_shared/tools/encaminhamentos_tabela.py",
}

_CACHE = {}


def texto_fonte(chave):
    """O conteúdo de uma fonte, já achatado. JSON vira a concatenação dos valores de string:
    o que interessa é o texto que o nó manda, não a sintaxe do arquivo."""
    if chave in _CACHE:
        return _CACHE[chave]
    if chave.startswith("snippet:"):
        alvo = chave.split(":", 1)[1]
        d = json.loads((RAIZ / "fred" / "n8n.json").read_text())
        s = [x["text"] for x in d.get("snippets", []) if x["key"] == alvo]
        t = "\n".join(s)
    else:
        p = RAIZ / FONTES[chave]
        bruto = p.read_text()
        if p.suffix == ".json":
            pedacos = []
            def anda(o):
                if isinstance(o, str):
                    pedacos.append(o)
                elif isinstance(o, dict):
                    [anda(v) for v in o.values()]
                elif isinstance(o, list):
                    [anda(v) for v in o]
            anda(json.loads(bruto))
            t = "\n".join(pedacos)
        else:
            t = bruto
    # o código escapa aspas e quebra de linha; o texto renderizado não. Desfaz antes de comparar.
    t = t.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n")
    _CACHE[chave] = t
    return t


DIAS = ["segunda", "terça", "terca", "quarta", "quinta", "sexta", "sábado", "sabado", "domingo",
        "seg", "ter", "qua", "qui", "sex", "sáb", "sab", "dom"]


def fragmentos(texto, exemplo):
    """Os pedaços do texto que NÃO dependem de dado: é isso que tem que existir no código.

    Tira os valores de exemplo (nome, telefone, local), os números (data, hora, valor, id do Asa)
    e o nome do dia da semana, que o código monta. O que sobra é literal nosso."""
    t = texto
    for v in sorted([str(v) for v in exemplo.values()], key=len, reverse=True):
        if len(v) >= 3:
            t = t.replace(v, "\x00")
    t = re.sub(r"\b(?:%s)\b" % "|".join(DIAS), "\x00", t, flags=re.I)
    t = re.sub(r"[\d]+(?:[.,:/\-][\d]+)*", "\x00", t)
    saida = []
    for pedaco in re.split(r"[\x00\n]", t):
        p = pedaco.strip()
        if len(p) >= 6 and len(re.findall(r"[A-Za-zÀ-ÿ]", p)) >= 4:
            saida.append(p)
    return saida


MIN = 4


def cobre(frag, alvo):
    """O código monta a linha por pedaços ('- Local: ' + nome), então o pedaço inteiro pode não
    existir contíguo em lugar nenhum. A pergunta certa não é "esta linha está no arquivo?", é
    "dá pra montar esta linha com pedaços do arquivo?". Devolve o ponto onde travou, ou None."""
    if frag in alvo:
        return None
    i = 0
    while i < len(frag):
        # sobra sem palavra (' de', '):', 'R$') é emenda de concatenação, não texto que sumiu
        if len(re.findall(r"[A-Za-zÀ-ÿ]", frag[i:])) < 4:
            return None
        maior = 0
        for j in range(len(frag), i + MIN - 1, -1):
            if frag[i:j] in alvo:
                maior = j
                break
        if not maior:
            return frag[i:]
        i = maior
    return None


def achar_fonte(texto, exemplo, candidatos=None):
    """Em que arquivo esse texto mora? Só responde quando TODOS os pedaços casam: meio-casamento
    viraria vermelho no dia seguinte, e aí ninguém olha mais o placar."""
    frags = fragmentos(texto, exemplo)
    if not frags:
        return None
    d = json.loads((RAIZ / "fred" / "n8n.json").read_text())
    chaves = ["snippet:" + x["key"] for x in d.get("snippets", []) if x["tenant"] == "fred"]
    # cartão do grupo e comando começam com marca; frase solta do modelo, não. Sem a marca,
    # duas linhas curtas ("Criança o" + "atende na") casam com qualquer arquivo grande por acaso.
    marcado = bool(re.match(r"[/\W]", texto.strip()[:1])) and texto.strip()[:1] != '"'
    letras = sum(len(re.findall(r"[A-Za-zÀ-ÿ]", f)) for f in frags)
    for chave in (candidatos or (chaves + list(FONTES))):
        alvo = texto_fonte(chave)
        if not all(cobre(f, alvo) is None for f in frags):
            continue
        if chave.startswith("snippet:") or marcado or (len(frags) >= 2 and letras >= 20):
            return chave
    return None


def main():
    v = "-v" in sys.argv
    dados = json.loads(FLUXOS.read_text())
    ex = dados["exemplo"]
    ok = falha = livres = soltos = 0
    problemas = []
    for fn in dados["funcoes"]:
        for cen in fn.get("cenarios", []):
            for painel in ("hoje", "depois"):
                for m in (cen.get(painel) or {}).get("msgs", []):
                    if not m.get("f"):
                        livres += 1
                        continue
                    if m["f"].startswith("n8n:"):
                        soltos += 1
                        continue
                    frags = fragmentos(m["t"], ex)
                    alvo = texto_fonte(m["f"])
                    sumiu = [x for x in (cobre(f, alvo) for f in frags) if x]
                    if sumiu:
                        falha += 1
                        problemas.append((fn["id"], cen["id"], painel, m["f"], sumiu))
                    else:
                        ok += 1
    for fid, cid, painel, fonte, sumiu in problemas:
        print(f"VERMELHO {fid}/{cid}/{painel}  o código de {fonte} não tem mais:")
        for s in (sumiu if v else sumiu[:2]):
            print(f"           {s!r}")
    print(f"\n{ok} textos nossos batem, {falha} não batem, {soltos} moram só no n8n velho "
          f"(sem como cobrar daqui), {livres} são prosa do modelo ou fala de gente.")
    return 1 if falha else 0


if __name__ == "__main__":
    sys.exit(main())
