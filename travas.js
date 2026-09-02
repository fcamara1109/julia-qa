// travas.js — as regras com nome, em código. Um arquivo só, dois consumidores: o n8n (que é JS,
// e é onde o /assert do Telegram roda) e a linha de comando. Duas cópias da mesma regra é o que
// este arquivo existe pra matar.
//
// Cada trava sai de uma frase do campo `regras` do caso. A frase é a fonte, a trava é a forma
// executável dela, e a página mostra as duas juntas pra dar pra ver se a tradução está certa.
//
// Contrato, regra 3: a trava cobra o EFEITO, não a frase. "costuma fazer exames" e "costuma
// realizar exames" são a mesma coisa, e comparar letra por letra reprova sinônimo.
//
//   node _shared/qa/travas.js        roda o autoteste

const TARDE = 13 * 60;  // o expediente do consultório começa às 13h; antes disso é exame
const HORA = /\b(\d{1,2})\s?[h:]\s?(\d{2})?\b/g;
const AJUDA = /encaixe|supervisor|equipe|colega|recepc|verificar com|falar com/;

const semAcento = (t) => String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

function horarios(msg) {
  const fora = [];
  for (const m of String(msg || '').matchAll(HORA)) {
    const hh = Number(m[1]);
    if (hh <= 23) fora.push(hh * 60 + Number(m[2] || 0));
  }
  return fora;
}

const pediuManha = (msg) => semAcento(msg).includes('manha');

// (paciente, resposta da Júlia, handoff). O handoff é opcional: turno de 2 é conversa escrita na
// mão; de 3 vem de uma rodada real, onde o fluxo diz se passou pra uma pessoa.
const fala = (t) => [t[0], t[1], t.length > 2 ? t[2] : ''];

// veredito: true passou, false quebrou, null não se aplica
const TRAVAS = {
  // "Ela nunca oferece horário de manhã por conta própria"
  sem_manha_espontanea(turnos) {
    for (const turno of turnos) {
      const [paciente, julia] = fala(turno);
      if (pediuManha(paciente)) continue;
      const cedo = horarios(julia).filter((m) => m < TARDE);
      if (cedo.length) {
        const hh = Math.min(...cedo);
        return [false, `ofereceu ${String(Math.floor(hh / 60)).padStart(2, '0')}h${String(hh % 60).padStart(2, '0')} sem o paciente ter pedido a manhã`];
      }
    }
    return [true, 'não ofereceu manhã por conta própria'];
  },

  // "primeiro avisa que de manhã o Dr costuma fazer exames e pergunta se ele só pode de manhã"
  freio_antes_do_horario(turnos) {
    for (const turno of turnos) {
      const [paciente, julia] = fala(turno);
      if (!pediuManha(paciente)) continue;
      if (!semAcento(julia).includes('exame')) return [false, 'pediu a manhã e ela não disse que de manhã é exame'];
      if (horarios(julia).length) return [false, 'explicou o motivo mas já ofereceu horário na mesma mensagem'];
      return [true, 'explicou o motivo e devolveu a pergunta, sem oferecer'];
    }
    return [null, 'o paciente não pediu a manhã nesta rodada'];
  },

  // "ela diz que vai tentar um encaixe e pede ajuda a um humano".
  // Quem prova que ela chamou alguém é o handoff do fluxo, não a boa vontade da frase.
  encaixe_com_humano(turnos) {
    for (let i = 0; i < turnos.length; i++) {
      if (!pediuManha(turnos[i][0])) continue;
      if (i + 1 >= turnos.length) return [null, 'o paciente não chegou a confirmar que só pode de manhã'];
      const [, julia, handoff] = fala(turnos[i + 1]);
      if (horarios(julia).length) return [false, 'ofereceu horário de manhã em vez de tentar o encaixe'];
      if (handoff) {
        return handoff !== 'nenhum'
          ? [true, `passou pra uma pessoa (${handoff})`]
          : [false, 'não ofereceu horário, mas também não passou pra ninguém'];
      }
      if (!AJUDA.test(semAcento(julia))) return [false, 'não ofereceu horário, mas também não disse que ia chamar alguém'];
      return [true, 'falou em encaixe e chamou alguém'];
    }
    return [null, 'o paciente não perguntou da manhã nesta rodada'];
  },
};

function julgar(turnos, ids) {
  const quais = ids && ids.length ? ids : Object.keys(TRAVAS);
  return quais.map((id) => {
    if (!TRAVAS[id]) return [id, false, `trava '${id}' não existe neste arquivo`];
    return [id, ...TRAVAS[id](turnos)];
  });
}

if (typeof module !== 'undefined') module.exports = { TRAVAS, julgar, horarios, pediuManha };

if (typeof require !== 'undefined' && require.main === module) {
  const abre = 'Olá! Quero saber mais sobre a consulta com Dr. Frederico';
  const sauda = 'Oi Felipe! Muito prazer, sou a Júlia, assistente do proctologista Dr Frederico ☺️\n\nComo posso te ajudar?';
  const aprovado = [
    [abre, sauda],
    ['Tem algum horario de manha, depois das 8h?', 'De manhã o Dr. Frederico só costuma fazer exames, para ser mais confortável para os pacientes que ficam de jejum.\n\nVocê só pode no período da manhã?'],
    ['Sim, só consigo de manhã', 'Vou chamar meu supervisor pra ver um encaixe o quanto antes 🙏🏻'],
  ];
  const rejeitado = [
    [abre, sauda],
    ['Tem algum horario de manha, depois das 8h?', 'Tenho sim! Consigo hoje às 10h50 ☺️'],
    ['Sim, só consigo de manhã', 'Perfeito, deixei reservado às 10h50 então ☺️'],
  ];
  const falhas = [];
  const eq = (veio, esperado, msg) => {
    if (veio !== esperado) falhas.push(`${msg}: esperava ${esperado}, veio ${veio}`);
    console.log((veio === esperado ? '🟢 ' : '🔴 ') + msg);
  };
  const t = TRAVAS;
  eq(t.sem_manha_espontanea(aprovado)[0], true, 'a conversa aprovada passa na trava da oferta');
  eq(t.freio_antes_do_horario(aprovado)[0], true, 'a conversa aprovada passa na trava do freio');
  eq(t.encaixe_com_humano(aprovado)[0], true, 'a conversa aprovada passa na trava do encaixe');
  eq(t.freio_antes_do_horario(rejeitado)[0], false, 'o contra-exemplo quebra a trava do freio');
  eq(t.encaixe_com_humano(rejeitado)[0], false, 'o contra-exemplo quebra a trava do encaixe');
  // o handoff do fluxo manda mais que a frase: falar bonito e não chamar ninguém reprova
  eq(t.encaixe_com_humano([[abre, sauda], ['Tem horario de manha?', 'De manhã é exame. Só de manhã?'],
    ['Sim', 'Vou ver um encaixe pra você 🙏🏻', 'nenhum']])[0], false,
    'prometeu chamar alguém mas o fluxo não passou pra ninguém');
  eq(t.sem_manha_espontanea([['Quero marcar', 'Os próximos horários seriam quinta às 16h30 ou segunda às 15h']])[0], true, 'oferta só de tarde passa');
  eq(t.sem_manha_espontanea([['Quero marcar', 'Os próximos horários seriam hoje às 07h30, 10h50 ou quinta às 13h30']])[0], false, 'oferta com 07h30 e 10h50 quebra a trava');
  // regra 3: a trava cobra o efeito, não a frase. Sinônimo tem que passar.
  for (const frase of ['De manhã o Dr costuma fazer exames. Você só pode de manhã?',
                       'Pela manhã ele reserva a agenda pra exame. Só consegue de manhã?',
                       'A manhã fica pros exames ☺️ Você só pode nesse período?']) {
    eq(t.freio_antes_do_horario([['Tem horario de manha?', frase]])[0], true, `passa dizendo com outras palavras: ${frase.slice(0, 34)}...`);
  }
  eq(t.freio_antes_do_horario([['Quero marcar', 'Tenho 14h40']])[0], null, 'sem pergunta sobre a manhã, a trava do freio não se aplica');
  eq(julgar(aprovado, ['nao_existe'])[0][1], false, 'trava que não existe reprova em vez de sumir do placar');
  console.log(falhas.length ? `\n${falhas.length} falha(s)` : '\nTUDO PASSOU');
  process.exit(falhas.length ? 1 : 0);
}
