#!/bin/bash
# Monitor em camadas para agentes de IA que rodam 24/7 num servidor.
#
# Três profundidades, chamadas pelo cron (ver ops/cron/crontab.exemplo):
#
#   (sem argumento)  BARATA, a cada 10 min. Serviço de pé, processo não suspenso,
#                    menu travado na tela, ponte com o canal de chat, login válido.
#                    Não gasta token.
#   --profundo       a cada 2 h. Tudo acima + uma pergunta de verdade ao modelo.
#                    É a única checagem que pega o "apagão silencioso": serviço de
#                    pé, ponte conectada, e ninguém responde porque a sessão do
#                    modelo expirou ou o limite de uso estourou.
#   --pulso          uma vez por dia. Tudo acima e SEMPRE manda um resumo, mesmo
#                    com tudo bem. Se o resumo não chegar, o servidor caiu: nenhum
#                    monitor de dentro dele conseguiria avisar. A ausência é o sinal.
#
# O aviso sai por um canal que NÃO depende do modelo (alerta.py: e-mail, com
# webhook de reserva), porque a pane que mais importa é justamente o modelo parar.
#
# Tudo vem de variável de ambiente (ver ops/.env.example).

set -uo pipefail

ENV_FILE="${ENV_FILE:-/etc/agentes/agentes.env}"
if [ -r "$ENV_FILE" ]; then set -a; . "$ENV_FILE"; set +a; fi

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
AGENTES="${AGENTES:-atendimento comentarios crm}"         # nomes das instâncias
PREFIXO="${PREFIXO_SERVICO:-agente}"                      # unit = agente@<nome>
CLAUDE="${CLAUDE_BIN:-$HOME/.local/bin/claude}"
MODELO_CHECAGEM="${MODELO_CHECAGEM:-claude-haiku-5-5}"    # o mais barato basta
ALERTA="${ALERTA_BIN:-$HOME/bin/alerta.py}"
LOG="${LOG_DIR:-$HOME/logs}/monitor.log"
ESTADO="${ESTADO_DIR:-$HOME/.local/state/agentes-monitor}"
PROCESSO="${PADRAO_PROCESSO:-claude --channels}"
PONTE="${PADRAO_PONTE:-bun server.ts}"
DETECTOR_FILA="${DETECTOR_FILA:-1}"
MODO="${1:-}"

n_agentes=$(wc -w <<<"$AGENTES")
PONTES_ESPERADAS="${PONTES_ESPERADAS:-$n_agentes}"

mkdir -p "$(dirname "$LOG")" "$ESTADO"
registrar() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }
unidade() { printf '%s@%s' "$PREFIXO" "$1"; }
soquete() { printf '%s-%s' "$PREFIXO" "$1"; }

# Uma rotina por vez: o reinício diário segura o mesmo cadeado.
exec 9>"$ESTADO/lock"
if ! flock -n 9; then
  registrar "[$MODO] outra rotina em andamento, saindo"
  exit 0
fi

# avisar <chave> <horas de silêncio> <texto>
# A janela de silêncio evita repetir a mesma notícia a cada 10 min numa pane longa.
avisar() {
  local chave="$1" horas="$2"; shift 2
  local marca="$ESTADO/aviso-$chave"
  if [ -f "$marca" ]; then
    local idade=$(( ($(date +%s) - $(stat -c %Y "$marca")) / 3600 ))
    if [ "$idade" -lt "$horas" ]; then
      registrar "aviso [$chave] silenciado (último há ${idade}h, janela ${horas}h)"
      return 0
    fi
  fi
  if python3 "$ALERTA" "$*" >/dev/null 2>&1; then
    touch "$marca"; registrar "AVISO ENVIADO [$chave] $*"
  else
    registrar "FALHA AO ENVIAR AVISO [$chave] $*"
  fi
}

problemas=0
resumo=""
religou=0

# 1. Serviços de pé? Se não, religa e conta o que aconteceu.
for a in $AGENTES; do
  u=$(unidade "$a")
  estado=$(systemctl --user is-active "$u" 2>&1)
  if [ "$estado" = "active" ]; then resumo="$resumo $a=ok"; continue; fi
  problemas=1; religou=1
  registrar "SERVIÇO $u está '$estado', religando"
  systemctl --user restart "$u"; sleep 25
  novo=$(systemctl --user is-active "$u" 2>&1)
  if [ "$novo" = "active" ]; then
    resumo="$resumo $a=religado"
    avisar "servico-$a" 6 "MONITOR: o agente $a tinha caído ('$estado') e voltou sozinho. Mande uma mensagem de teste: serviço ativo não prova que ele responde."
  else
    resumo="$resumo $a=FORA"
    avisar "servico-$a" 2 "MONITOR: o agente $a está fora do ar ('$novo') e NÃO voltou no religamento automático. Precisa de alguém olhando."
  fi
done

# 2. Processo suspenso (Ctrl+Z dentro da sessão): fica mudo, sem erro. Retoma.
for pid in $(pgrep -f "$PROCESSO" 2>/dev/null); do
  case "$(ps -o stat= -p "$pid" 2>/dev/null | tr -d ' ')" in
    T*) problemas=1
        registrar "PROCESSO $pid suspenso, retomando"
        kill -CONT "$pid"
        avisar "suspenso" 6 "MONITOR: um agente estava suspenso e foi retomado automaticamente." ;;
  esac
done

# 3. Tela travada (só para agentes de terminal rodando em tmux).
#    3a. Menu de limite de uso esperando escolha humana: nenhuma opção "tenta de novo",
#        então o agente fica parado mesmo depois de o limite liberar. Esc destrava sem
#        reiniciar; a mensagem em processamento se perde e precisa ser reenviada.
#    3b. Mensagem parada na caixa de entrada: compara o carimbo da última resposta
#        concluída entre checagens. Texto esmaecido (sugestão do próprio terminal) é
#        ignorado: tratá-lo como mensagem já gerou religamento de agente saudável.
if [ "$DETECTOR_FILA" = "1" ]; then
  for a in $AGENTES; do
    s=$(soquete "$a")
    tela=$(tmux -L "$s" capture-pane -p -t bot 2>/dev/null | sed 's/\xc2\xa0/ /g')
    [ -z "$tela" ] && continue

    if printf '%s' "$tela" | grep -q "Stop and wait for limit to reset"; then
      problemas=1
      registrar "MENU DE LIMITE em $a, enviando Esc"
      tmux -L "$s" send-keys -t bot Escape
      avisar "menu-limite-$a" 1 "MONITOR: o agente $a estava preso no menu de limite de uso. Destravei com Esc. A mensagem em andamento ficou sem resposta e precisa ser reenviada."
      continue
    fi

    linha=$(printf '%s' "$tela" | grep -m1 '^❯' | sed -e 's/^❯[[:space:]]*//' -e 's/[[:space:]]*$//')
    case "$linha" in 'Try "'*) linha="" ;; esac
    estilo=$(tmux -L "$s" capture-pane -p -e -t bot 2>/dev/null | sed 's/\xc2\xa0/ /g' | grep -m1 -P '^(\x1b\[[0-9;]*m)*❯')
    case "$estilo" in *$'\e[2m'*) linha="" ;; esac

    carimbo=$(printf '%s' "$tela" | grep -oE 'done [0-9]{1,2}:[0-9]{2} [AP]M' | tail -1)
    chave=""; [ -n "$linha" ] && chave="${carimbo:-sem-carimbo}"
    antes=$(cat "$ESTADO/fila-$a" 2>/dev/null)
    if [ -n "$chave" ] && [ "$chave" = "$antes" ]; then
      n=$(( $(cat "$ESTADO/filan-$a" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$ESTADO/filan-$a"
      if [ "$n" -ge 4 ]; then
        problemas=1; religou=1; echo 0 > "$ESTADO/filan-$a"
        registrar "FILA TRAVADA em $a há $n checagens, religando"
        systemctl --user restart "$(unidade "$a")"
        avisar "fila-$a" 3 "MONITOR: o agente $a ficou quase uma hora com mensagem parada e foi religado. Confira se a mensagem foi respondida: o religamento apaga a fila."
      elif [ "$n" -ge 2 ]; then
        problemas=1
        avisar "fila-$a" 3 "MONITOR: o agente $a está há mais de meia hora com mensagem parada. Ele aparece online, o que engana. Se não andar, religo em meia hora."
      fi
    else
      echo 0 > "$ESTADO/filan-$a"
    fi
    printf '%s' "$chave" > "$ESTADO/fila-$a"
  done
fi

# 4. Pontes com o canal de chat. Um agente pode ter o processo vivo e a ponte caída.
#    Logo depois de religar algo, a contagem fica para a próxima rodada (senão o
#    próprio religamento gera falso alarme).
pontes=$(pgrep -fc "$PONTE" 2>/dev/null || echo 0)
if [ "$pontes" -lt "$PONTES_ESPERADAS" ]; then
  if [ "$religou" = "1" ]; then
    registrar "pontes $pontes/$PONTES_ESPERADAS logo após religar; confiro na próxima"
  else
    problemas=1
    avisar "pontes" 3 "MONITOR: só $pontes de $PONTES_ESPERADAS pontes com o canal de chat no ar. Agente sem ponte aparece online e não recebe nada."
  fi
fi

# 5. Login válido? Lê o CAMPO do JSON; o código de saída é sucesso mesmo deslogado.
#    O </dev/null não é enfeite: sem ele, o CLI consome a entrada padrão do script.
auth=$(timeout 40 "$CLAUDE" auth status 2>&1 </dev/null)
if printf '%s' "$auth" | grep -q '"loggedIn"[[:space:]]*:[[:space:]]*true'; then
  resumo="$resumo login=ok"
else
  problemas=1; resumo="$resumo login=FALHOU"
  avisar "login" 6 "MONITOR: o login do modelo no servidor caiu. Os agentes ficam MUDOS: continuam online e não respondem. Refazer o login (ver docs/06)."
fi

# 6. O modelo responde de verdade? (profundo e pulso)
if [ "$MODO" = "--profundo" ] || [ "$MODO" = "--pulso" ]; then
  mkdir -p "$ESTADO/sandbox" && cd "$ESTADO/sandbox" || exit 1
  resposta=$(timeout 150 "$CLAUDE" -p "Quanto é sete mais cinco? Responda só o número." \
             --model "$MODELO_CHECAGEM" 2>&1 </dev/null)
  if printf '%s' "$resposta" | grep -q '12'; then
    resumo="$resumo modelo=ok"; rm -f "$ESTADO/modelo-quebrado"
  else
    problemas=1; resumo="$resumo modelo=MUDO"
    [ -f "$ESTADO/modelo-quebrado" ] || date +%s > "$ESTADO/modelo-quebrado"
    horas=$(( ($(date +%s) - $(cat "$ESTADO/modelo-quebrado")) / 3600 ))
    avisar "profundo" 3 "MONITOR (mudo há ${horas}h): servidor de pé e login aparentemente válido, mas o modelo não respondeu a uma conta simples. Agentes mudos sem erro. Pode ser limite de uso."
  fi
fi

# 7. Pulso diário: resumo sempre, inclusive com tudo bem.
if [ "$MODO" = "--pulso" ]; then
  if [ "$problemas" -eq 0 ]; then texto="MONITOR: tudo no ar.$resumo"
  else texto="MONITOR: com problema.$resumo (detalhe em $LOG)"; fi
  python3 "$ALERTA" "$texto" >/dev/null 2>&1 && registrar "pulso enviado: $texto" || registrar "FALHA no pulso"
fi

# 8. O log não pode dizer "ok" enquanto o modelo está mudo. Serviço de pé não é
#    serviço funcionando.
if [ -f "$ESTADO/modelo-quebrado" ]; then
  registrar "[${MODO:-rapido}] serviços de pé, MAS O MODELO ESTÁ MUDO (última checagem profunda falhou)$resumo"
elif [ "$problemas" -eq 0 ]; then
  registrar "[${MODO:-rapido}] ok$resumo"
fi

# 9. Log com teto.
if [ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 5000000 ]; then
  tail -n 3000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exit 0
