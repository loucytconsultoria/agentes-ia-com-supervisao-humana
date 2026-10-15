# 07 · Adoção pela equipe não técnica

Agente que só o implementador sabe usar não é implantação, é protótipo. A operação real tinha
uma equipe pequena, sem formação técnica, com funções diferentes e permissões diferentes. O que
funcionou foi tratar a adoção como produto: um caminho por função, configuração assistida e
regras curtas que valem sempre.

## 1. Quem usa o quê

| Ferramenta | Para quem | Para quê |
|---|---|---|
| Bots no chat da equipe | Atendimento, social media, gestores de relacionamento | Rascunho de resposta, rascunho de comentário, cadastro no CRM. Zero instalação: é só mandar mensagem |
| App de conversa com IA (sem acesso a arquivos) | Todo mundo | Perguntar, resumir, rascunhar o que a pessoa cola |
| Agente de terminal com a pasta de trabalho | Coordenações | Ler a base da organização, usar skills, puxar dados do sistema de tarefas |

A regra de bolso que evitou a maior parte da confusão: **o app de conversa não enxerga sua
pasta; o agente de terminal enxerga.** Quem precisa de dado da organização usa o segundo.

## 2. Kit de treinamento

1. **Tutorial único, do zero ao uso**, escrito para quem nunca abriu um terminal: conta, instalação,
   pasta de trabalho, token pessoal do sistema de tarefas, skills, uso no dia a dia, segurança,
   "se algo der errado", e quem é o dono do tutorial.
2. **Um prompt de configuração por função**, que a pessoa cola na primeira conversa do agente de
   terminal. O próprio agente conduz a configuração, uma etapa por vez, explicando cada termo e
   pedindo "pode seguir?" antes de instalar ou criar qualquer coisa. No caso real: **5 assentos**
   com o agente no computador e **4 prompts de configuração** personalizados.
3. **Teste só de leitura** no fim da configuração, com um pedido que vale para o trabalho real
   daquela função (ex.: a coordenação operacional puxa o calendário da semana; a de comunicação
   pede três ganchos para um vídeo). A primeira experiência é útil, não um "olá mundo".

### Estrutura do prompt de configuração (por função)

```
0. Apresente-se e diga o que vamos fazer (lista curta).
1. Confira o ambiente (o que já está instalado). Só leitura.
2. Confirme a pasta de trabalho.
3. Configure o token pessoal (nunca de outra pessoa; nunca em conversa com terceiros).
4. Teste a ligação SÓ COM LEITURA, usando um caso do trabalho desta função.
   Se a estrutura do sistema mudou, não invente: mostre o que existe e pergunte.
5. Mostre as ferramentas e exemplos de pedido em português, desta função.
6. Explique os limites (uma linha cada): o que é feito em outro lugar, o que é sempre humano.
7. Combine as regras que valem sempre.
8. Resumo do que ficou pronto e a quem recorrer.
```

Permissões por função ficam no próprio prompt: quem vê valores financeiros, quem não vê, quem
grava, quem só consulta. **A diferença de acesso está nos arquivos que cada pasta recebe**, não
numa instrução para o modelo "não mostrar".

## 3. Prompts por função (exemplos para a campanha fictícia)

| Função | Pedidos típicos |
|---|---|
| Coordenação-geral | "O que vence esta semana e de quem é cada item?" · "Monta a pauta da reunião de segunda a partir das tarefas atrasadas" |
| Comunicação | "Três ganchos para um vídeo sobre estágio garantido, para jovens de 16 a 24" · "Passa essa legenda no revisor de voz" |
| Mobilização | "Quantos voluntários em Porto do Sal estão sem próxima ação?" · "Rascunha o convite do encontro de sábado" |
| Atendimento | (no bot) "!rascunho a pessoa pergunta se o estágio vale para curso noturno" |
| Gestor de relacionamento | (no bot de CRM) "Cadastra: nome, telefone, município, segmento" |
| Financeiro | "Confere se os lançamentos da semana estão na planilha" (o agente prepara; quem paga é sempre humano) |

## 4. As regras que valem sempre (versão para a equipe)

1. Senhas e cartão nunca entram em conversa. O token pessoal fica só na sua máquina.
2. Dado pessoal de cliente/eleitor tem finalidade restrita: nunca copie listas para fora.
3. **Tudo é rascunho.** Você lê, confere e decide o que sai.
4. Números de carteira (quantos contatos, quantos voluntários) vêm do sistema ao vivo, nunca de
   estimativa.
5. Em comunicado interno, cargo e não nome da pessoa; e nada de urgência que ninguém informou.
6. Dúvida jurídica não se decide no agente: vai para o jurídico.
7. Se a resposta parece errada ou contra uma regra, não use: leve à coordenação.

## 5. O que fez a adoção pegar

- **Começar pelo canal que a equipe já usa.** Os bots no chat tiveram adoção imediata porque não
  exigiam instalar nada. O agente de terminal veio depois, para quem precisava.
- **Um pedido real na primeira sessão.** Configuração que termina com um resultado do trabalho da
  pessoa vende o resto.
- **Dono para cada material.** Tutorial sem dono envelhece na primeira mudança de tela.
- **Linguagem sem jargão também nos agentes.** O agente de CRM diz "verifiquei antes de gravar",
  nunca "dry-run".

## 6. Treinamento de quem decide

Além da equipe, os líderes (aqui, candidatos de uma chapa) passaram por uma aula sobre método:
planejamento com meta numérica, base de dados própria antes da campanha, funil. A IA aparece
como ferramenta de execução do método, não como o método. A aula foi gerada a partir de um
prompt estruturado com os objetivos de aprendizagem em ordem e analogias definidas pelo
instrutor, e revisada por ele.
