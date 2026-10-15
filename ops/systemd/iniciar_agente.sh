#!/bin/bash
# Sobe um agente de terminal ligado a um canal de chat, a partir da pasta isolada dele.
# Chamado pela unidade agente@.service:  iniciar_agente.sh <nome>
#
# Isolamento por pasta: cada agente roda numa pasta enxuta que só contém a persona
# (CLAUDE.md), as permissões (.claude/settings.json) e as fontes que ele pode ler.
# Ele não enxerga o resto do servidor nem a raiz do projeto.
#
# Estado do canal separado por agente: sem DISCORD_STATE_DIR próprio, o processo lê
# o token de outro agente e derruba o que estava no ar.

set -euo pipefail
NOME="${1:?uso: iniciar_agente.sh <nome>}"

ENV_FILE="${ENV_FILE:-/etc/agentes/agentes.env}"   # 600, dono = usuário dos agentes
set -a; . "$ENV_FILE"; set +a

export DISCORD_STATE_DIR="$HOME/.claude/channels/discord-$NOME"
cd "${AGENTES_DIR:-$HOME/agentes}/$NOME"
exec "${CLAUDE_BIN:-$HOME/.local/bin/claude}" --channels "${PLUGIN_CANAL:-plugin:discord@claude-plugins-official}"
