# O que a Júlia escreve

Toda mensagem que a Júlia manda, função por função, numa página que dá pra editar. E, ao lado
dela, **o gabarito**: como cada situação tem que terminar (`gabarito.html`).

Pensando nela como uma secretária que a gente está treinando, são três etapas:

1. **A página é o roteiro de atendimento** que você entrega pra ela. Você escreve como cada
   situação tem que terminar, e é isso que vale.
2. **O Telegram é o roleplay.** `/assert <caso>` faz ela atender de verdade, você vê a conversa
   acontecer e diz se passou ou não.
3. **O paciente real vem depois**, e aí ela está sozinha. Tudo que você reprovar no roleplay
   fica escrito aqui e vira o que impede o erro de voltar.

A regra que manda nas duas: **a página é o certo, a IA é que se ajusta.** Deu diferente do que
está escrito aqui, quem muda é a IA. O gabarito só muda quando você decide que a conversa
deveria ser outra, e aí você muda na página, de propósito.

É o controle de qualidade do projeto: o texto certo mora aqui, e o código é cobrado contra ele.
Quem quiser mudar o que a Júlia fala não abre o n8n nem o Python: abre a página, escreve como
quer que fique e salva.

## Abrir

```
python3 _shared/qa/servir.py
```

Abre `http://localhost:8777`. O Chrome recusa abrir o arquivo direto (`file://`), por isso o
servidor. Ele também é quem recebe o **Salvar**: o botão manda a página inteira de volta e o
`fluxos.json` é reescrito no disco. Sem servidor (por exemplo abrindo pelo GitHub), o Salvar
vira um download do `fluxos.json`.

## Como o código é cobrado

Cada bolha tem uma etiqueta:

- **cobrado: `<arquivo>`** — o texto é nosso e determinístico. `python3 _shared/qa/verificar_fluxos.py`
  quebra o texto nos pedaços que não dependem de dado (tira nome, data, valor) e exige que cada
  pedaço ainda exista naquele arquivo. Editou a bolha e o código não mudou: fica vermelho.
  **O vermelho é a lista de tarefas, não é bug.**
- **prosa do modelo** — quem escreve é a IA, com os fatos da ficha do cliente. Não dá pra cobrar
  palavra por palavra, e não é pra cobrar.
- **fluxo velho (V1)** — o texto ainda mora só no n8n, não tem fonte no repositório.

As mensagens que o gabarito ao vivo confere ganharam apelido (`"k"` no JSON). O
`gabarito_agendamento.py` não guarda mais frase escrita na mão: pergunta pro `fluxos.py` qual é
o texto certo e confere se a mensagem de verdade diz aquilo. Mudou aqui, mudou o assert.

## Os arquivos

| Arquivo | O quê |
|---|---|
| `gabarito.json` | **Como ela tem que se comportar**: um caso por situação, com as regras, a conversa aprovada, a rejeitada e o histórico das rodadas reais |
| `gabarito.html` | A página do gabarito: escolhe o caso, toca as duas conversas lado a lado, edita as regras e salva |
| `assert_tg.py` | O roleplay: `/assert <caso>` no Telegram faz ela atender de verdade e devolve o placar |
| `travas.js` | As regras com nome, em JS. O mesmo arquivo roda aqui e dentro do n8n. `node travas.js` roda o autoteste |
| `test_salvar.py` | O gabarito da página: editar, salvar, e a bateria já ler a mudança |
| `test_gabarito.py` | O gabarito confere consigo mesmo: a conversa aprovada passa no que o próprio caso cobra, e a rejeitada quebra pelo menos uma trava |
| `fluxos.json` | A fonte da verdade: funções, cenários, mensagens |
| `index.html` | A página que mostra e edita |
| `prompts.html` + `prompts.json` | A outra página: a instrução do modelo e as frases prontas de cada cliente. Gabarito: `test_prompts.py` |
| `servir.py` | Serve a página e grava o Salvar |
| `verificar_fluxos.py` | O gabarito estático: o código ainda diz isso? |
| `fluxos.py` | O que o gabarito ao vivo usa pra perguntar o texto certo |

O inventário de funções (F, G, S) sai de `state/plans/2026-08-30-mapa-modulos-funcoes.md`.
