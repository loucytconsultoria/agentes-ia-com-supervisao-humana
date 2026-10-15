# 08 · Lições aprendidas

Agrupadas por tema. Cada uma veio de uma falha ou de um custo real.

## Conhecimento e voz

1. **Destile uma vez; nunca jogue o bruto no agente.** Corrigir uma posição num arquivo e ver
   todos os agentes herdarem a correção vale mais que qualquer ajuste de prompt.
2. **A camada é propriedade do dado, não instrução ao modelo.** O que o agente não recebe, ele não
   vaza. Arquivo sem camada é tratado como sigiloso.
3. **A voz se carrega, não se lembra.** Descrição de voz ("caloroso, direto") produz texto genérico.
   O agente precisa abrir exemplos reais antes de escrever, toda vez.
4. **Microfato pessoal não se inventa.** O erro mais natural do modelo não é inventar posição; é
   inventar naturalidade ("que pena que perdi o evento"). Placeholder explícito resolve.
5. **A régua de tom é por registro.** "Nunca mais agressivo que a pessoa" deixou o agente mais
   manso que ela onde a aspereza era parte da voz, e certo onde não era.

## Regras e governança

6. **Ordem é regra; comentário é direção.** Transformar cada comentário em proibição acumula vetos
   contraditórios e empurra tudo para o genérico. Toda regra tem grau (REGRA, ORIENTAÇÃO,
   PREFERÊNCIA, EXEMPLO) e o revisor respeita o grau.
7. **Regras se destilam, não se empilham.** Uma versão vigente, curta; o histórico fica em outro
   arquivo. Pilha de regra é onde o agente se perde.
8. **Núcleo positivo antes dos vetos.** Quem escreve fugindo de quarenta proibições escreve a coisa
   mais neutra possível.
9. **Red team produz mais regra que reprovação.** O placar limpo (0 vazamentos, 0 violações em 20
   perguntas) veio acompanhado de 10 ambiguidades a corrigir. O agente acertar contornando uma
   lacuna é sorte, não controle.
10. **Lacuna precisa de fraseado público.** A frase interna "não documentado, escalar" não pode
    chegar ao cliente final.

## Humano no circuito

11. **Quem escreve não revisa.** E o revisor de conformidade não reescreve: se corrigisse, viraria
    autor do que deveria auditar.
12. **Parecer não é aprovação.** "O agente aprovou" é frase proibida; o agente deu parecer.
13. **Confirmação é texto explícito.** Emoji e silêncio não gravam nada.
14. **Lista de bloqueio é parada, não duplicata.** Nenhuma flag de "forçar" destrava quem pediu
    para não ser contatado.
15. **Agente em produção nunca pede permissão.** O que não está nem em `allow` nem em `deny` vira
    pedido para a equipe inteira, aprovável por qualquer um.
16. **O que precisa acontecer sempre, o código faz.** Enviar, registrar, mascarar dado pessoal:
    tudo que não pode ser esquecido sai das mãos do modelo.

## Operação

17. **Serviço de pé não é serviço funcionando.** Só uma pergunta real ao modelo pega sessão
    expirada e limite estourado.
18. **Alerta que ninguém lê não é alerta.** Saiu do chat dos agentes (23 avisos sem ação) para
    e-mail com gravidade no assunto.
19. **A ausência é um sinal.** Pulso diário mesmo com tudo bem é o único aviso de servidor fora.
20. **Heurística de tela precisa de teste de falso positivo.** Um detector ingênuo gerou 24
    religamentos e 19 alarmes falsos.
21. **O log não pode mentir por omissão.** "ok" com o modelo mudo (208 vezes) é pior que nenhum log.
22. **Meça antes de dimensionar.** 440 MB por agente, não "1 a 1,5 GB". E o custo relevante é o do
    modelo, não o do servidor: 83% do consumo veio do único agente no modelo maior.
23. **Cópia tem versão velha por padrão.** Fontes copiadas para agentes isolados se sincronizam
    por script com simulação, nunca à mão; e o agente é reiniciado para reler.
24. **"Verificado" tem definição.** Reboot real, serviços ativos, processos nas pastas certas, e
    uma mensagem respondida por agente.

## Adoção

25. **Comece pelo canal que a equipe já usa.** Bot no chat não exige instalação.
26. **Configuração assistida por função, terminando num pedido real.**
27. **Diferença de acesso se faz por arquivo entregue, não por instrução "não mostre".**
