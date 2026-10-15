# 06 · Operação 24/7: deploy, monitor em camadas, alertas e pós-mortems

## Arquitetura de execução

```mermaid
flowchart TB
  subgraph Local[Máquina de trabalho · a FONTE]
    S[persona, permissões, fontes<br/>de cada agente] --> SY[sincronizar.sh<br/>simulação · --aplicar]
  end
  SY -- rsync por conteúdo + reinício só de quem mudou --> SV
  subgraph SV[Servidor Linux · usuário sem privilégio]
    U1[agente@atendimento] --> T1[tmux -L agente-atendimento]
    U2[agente@comentarios] --> T2[tmux -L agente-comentarios]
    U3[agente@crm] --> T3[tmux -L agente-crm]
    C[cron] --> MB[monitor barato · 10 min]
    C --> MP[monitor profundo · 2 h]
    C --> PU[pulso · diário]
    C --> RE[reinício escalonado · madrugada]
    ENV[/etc/agentes/agentes.env<br/>600 · segredos/]
  end
  MB & MP & PU --> AL[alerta.py<br/>e-mail · webhook de reserva]
```

- **Unidade systemd de usuário em modelo** (`agente@.service`): uma instância por agente,
  `Restart=always`, `linger` habilitado para sobreviver ao fim do SSH. Cada agente roda dentro de
  um tmux com **soquete próprio**, porque agentes de terminal em modo de canal precisam de um
  terminal de verdade.
- **Segredos** num único arquivo `600` no servidor, carregado pelo script de partida. Nada em
  código, nada sincronizado da máquina local.
- **Isolamento**: cada agente roda da sua pasta enxuta (doc 02) e tem diretório de estado de canal
  próprio; sem isso, um agente lê o token do outro e derruba o que está no ar.
- **Dimensionamento medido**: cerca de **440 MB de memória por agente** (três processos cada). A
  estimativa inicial, feita sem medir, errava por três vezes.
- **Custo medido**: o servidor é o custo irrelevante. O consumo de modelo de três agentes foi de
  cerca de **US$ 118 equivalentes em 30 dias, rodando 3 horas por dia**, e **83% disso veio de um
  único agente**, o que rodava o modelo maior. Escolher o modelo por agente economiza mais que
  trocar de provedor de servidor.
- **Reinício diário escalonado** (90 segundos entre agentes): sessões longas acumulam contexto e
  ficam mais lentas e caras; plataformas de chat bloqueiam por 15 a 30 minutos quem reconecta
  demais em sequência.
- **Prova de reboot**: o servidor foi reiniciado de propósito; voltou em cerca de 15 segundos com
  os três serviços de pé, cada processo na sua pasta, e o cron ativo. Sem esse teste, "sobe
  sozinho no boot" é suposição.

Arquivos: [`ops/systemd/`](../ops/systemd/), [`ops/cron/crontab.exemplo`](../ops/cron/crontab.exemplo),
[`ops/deploy/sincronizar.sh`](../ops/deploy/sincronizar.sh), [`ops/.env.example`](../ops/.env.example).

## Monitor em camadas

O princípio: **serviço de pé não é serviço funcionando.** O monitor tem três profundidades, porque
checar o modelo a cada 10 minutos gastaria token à toa e checar uma vez por dia deixaria os
agentes mudos por horas.

| Quando | O que confere | Gasta token? | Ação automática |
|---|---|---|---|
| A cada 10 min | Serviço ativo; processo não suspenso; tela travada em menu; mensagem parada; pontes com o chat; login (lendo o **campo** `loggedIn`, não o código de saída) | Não | Religa serviço caído, retoma processo suspenso, fecha menu de limite, religa fila travada há ~50 min |
| A cada 2 h | Tudo acima **+ uma pergunta de verdade ao modelo** ("quanto é 7+5?") com o modelo mais barato | Pouco | Avisa |
| 1x por dia | Tudo acima e **manda o resumo mesmo com tudo bem** | Pouco | O pulso: se não chegar, o servidor caiu |

Detalhes que importam:
- **Cadeado** (`flock`) compartilhado entre monitor e reinício: duas rotinas nunca se atropelam.
- **Janela de silêncio por tipo de aviso** (1 a 6 horas): numa pane longa, a mesma notícia não sai
  a cada 10 minutos.
- **O log não diz "ok" enquanto o modelo está mudo.** Se a última checagem profunda falhou, toda
  checagem barata registra "serviços de pé, MAS O MODELO ESTÁ MUDO".
- **Chamadas ao CLI em script sempre com `< /dev/null`**: sem isso, o CLI consome a entrada
  padrão e engole o resto do script.

## Alertas

| Decisão | Motivo |
|---|---|
| Canal primário: **e-mail**, com assunto que já diz a gravidade (`[AGENTES] CRÍTICO: ...`) | Avisos postados no mesmo chat onde os agentes conversam se perderam: **23 avisos em dez dias não viraram nenhuma ação** |
| Reserva: webhook, **só se o e-mail falhar**, dizendo que o e-mail falhou | Uma pane de SMTP não silencia o monitor; e a reserva não vira ruído duplicado |
| Nenhum canal de alerta passa pelo modelo | A pane mais importante é o modelo parar |
| Pulso diário mesmo com tudo bem | A ausência do pulso é o único alerta possível quando o servidor inteiro cai |

Código: [`ops/monitor/monitor.sh`](../ops/monitor/monitor.sh), [`ops/monitor/alerta.py`](../ops/monitor/alerta.py),
[`ops/monitor/reinicio.sh`](../ops/monitor/reinicio.sh).

## Pós-mortems (anonimizados)

Formato: o que se viu · causa raiz · por que a monitoração não pegou · correção · o que mudou no
sistema.

### PM-1 · Sessão expirada: agentes online e mudos

- **O que se viu:** os três agentes apareciam online no chat, a ponte dizia "conectado", e
  ninguém recebia resposta. Usuários perceberam horas depois.
- **Causa raiz:** a credencial de sessão do modelo no servidor expirou. Os registros da sessão
  pediam novo login; nada era exibido no canal.
- **Por que não foi pego:** a única checagem era "o processo está de pé e a ponte conectada".
  As duas eram verdadeiras.
- **Correção:** credencial de longa duração, checagem de login lendo o campo `loggedIn` do JSON,
  e a **checagem profunda** que faz uma pergunta real ao modelo a cada 2 horas. Na revisão, viu-se
  que o login pode parecer válido com o limite de uso estourado; só a pergunta real pega os dois.
- **O que mudou:** a regra "a prova final é mandar mensagem e receber resposta" virou o critério
  de todo teste de deploy.

### PM-2 · Agente que escrevia a resposta e não enviava

- **O que se viu:** uma pessoa repetiu a mesma pergunta **8 vezes** ao longo de horas.
- **Causa raiz:** o agente redigia a resposta no próprio registro em vez de chamar a ferramenta de
  envio do chat. Em alguns casos, marcava "[ESCALAR]" e considerava a tarefa encerrada.
- **Por que não foi pego:** do ponto de vista do servidor, o agente estava trabalhando.
- **Correção:** bloco no topo de todas as personas ("sua resposta só existe se você enviar";
  "escalar não substitui responder"). No bot de rascunho deste repositório, o envio ao canal de
  revisão é feito pelo código, não pelo modelo.

### PM-3 · Monitor que gerava alarme falso e derrubava agente saudável

- **O que se viu:** **24 religamentos automáticos** de agentes saudáveis e **19 e-mails de alarme
  falso** em pouco mais de três semanas.
- **Causa raiz:** o detector de "mensagem parada" lia a linha de digitação do terminal. Depois de
  cada resposta, a interface desenha ali uma **sugestão esmaecida** de próxima fala, que não é
  mensagem de ninguém. O monitor a lia como fila travada.
- **Correção:** ignorar texto com código de estilo esmaecido e usar como chave o **carimbo da
  última resposta concluída**, não o texto da caixa (que, numa variante do mesmo problema, mudava
  a cada mensagem nova e zerava o contador, escondendo uma trava real).
- **Lição:** um detector baseado em tela é frágil; cada heurística precisa de um caso de teste
  com o falso positivo que a derrubou.

### PM-4 · Agentes presos no menu de limite de uso

- **O que se viu:** dois agentes mudos por **16 horas**, mesmo depois de o limite de uso ter sido
  liberado.
- **Causa raiz:** ao bater o limite, a interface abre um menu de escolha; nenhuma opção é "tentar
  de novo agora". Sem ninguém na tela, o agente esperava para sempre.
- **Correção:** o monitor detecta o menu e envia Esc, sem reiniciar o serviço. O aviso diz que a
  mensagem em processamento se perdeu e precisa ser reenviada.

### PM-5 · Log dizendo "ok" com os agentes mudos

- **O que se viu:** durante uma pane, o log acumulou **208 linhas "ok"** enquanto os agentes não
  respondiam.
- **Causa raiz:** a checagem barata (serviço de pé) registrava "ok" independentemente do
  resultado da checagem profunda.
- **Correção:** estado persistente "modelo quebrado desde X"; enquanto existir, nenhuma linha
  diz "ok".

### PM-6 · Falso alarme causado pelo próprio religamento

- **Causa raiz:** no mesmo ciclo em que religou um agente, o monitor contou as pontes antes de o
  plugin reconectar.
- **Correção:** depois de religar algo, a contagem de pontes fica para o ciclo seguinte.

## Checklist de deploy (o que conta como "verificado")

1. `uptime -s` mostra a hora do reboot de teste (prova que reiniciou, e não que a conexão caiu).
2. Todos os serviços `active`.
3. Cada processo na sua pasta (`readlink /proc/<pid>/cwd`).
4. Cron com todas as tarefas.
5. **Uma mensagem real para cada agente, com resposta.** Nada abaixo disso conta.
