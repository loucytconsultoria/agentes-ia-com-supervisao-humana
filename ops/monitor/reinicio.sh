#!/bin/bash
# Reinício diário dos agentes, de madrugada, um de cada vez.
#
# Por que reiniciar se eles ficam de pé sozinhos: uma sessão que roda por semanas
# acumula contexto e cada resposta fica mais lenta e mais cara. Reiniciar zera isso
# e recupera travamentos silenciosos que o monitor não sabe nomear.
# O preço: quem estiver conversando no horário perde o fio. Daí a madrugada.
#
# Por que um de cada vez: plataformas de chat bloqueiam por 15 a 30 minutos quem
# reconecta demais em sequência.

set -uo pipefail

ENV_FILE="${ENV_FILE:-/etc/agentes/agentes.env}"
if [ -r "$ENV_FILE" ]; then set -a; . "$ENV_FILE"; set +a; fi

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
AGENTES="${AGENTES:-atendimento comentarios crm}"
PREFIXO="${PREFIXO_SERVICO:-agente}"
LOG="${LOG_DIR:-$HOME/logs}/monitor.log"
ESTADO="${ESTADO_DIR:-$HOME/.local/state/agentes-monitor}"
ESPACO="${ESPACO_REINICIO_S:-90}"

mkdir -p "$(dirname "$LOG")" "$ESTADO"
registrar() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

# Mesmo cadeado do monitor: as duas rotinas não se atropelam.
exec 9>"$ESTADO/lock"
if ! flock -w 300 9; then
  registrar "[reinicio] sem cadeado em 5 min, adiando"
  exit 0
fi

registrar "[reinicio] começando"
for a in $AGENTES; do
  systemctl --user restart "$PREFIXO@$a"
  sleep "$ESPACO"
  registrar "[reinicio] $PREFIXO@$a -> $(systemctl --user is-active "$PREFIXO@$a" 2>&1)"
done
registrar "[reinicio] terminado"
exit 0
