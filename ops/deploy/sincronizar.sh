#!/bin/bash
# Envia ao servidor o que os agentes leem (persona, permissões e fontes) e reinicia
# só quem mudou. Simulação por padrão; --aplicar para valer.
#
#   ORIGEM=./agentes-servidor DESTINO_SSH=usuario@servidor bash sincronizar.sh
#   ORIGEM=./agentes-servidor DESTINO_SSH=usuario@servidor bash sincronizar.sh --aplicar
#
# Existe porque, com os agentes no servidor, a cópia local vira a FONTE. Quem edita
# só um lado cria divergência sem erro nenhum: o agente continua respondendo, pela
# versão velha.
#
# Comparação por CONTEÚDO (--checksum), não por data nem permissão: relógio e
# permissões de sistemas diferentes nunca batem, e sem isso todo arquivo pareceria
# diferente e todos os agentes seriam reiniciados sem motivo.

set -uo pipefail

ORIGEM="${ORIGEM:?defina ORIGEM (pasta local com uma subpasta por agente)}"
DESTINO_SSH="${DESTINO_SSH:?defina DESTINO_SSH (usuario@servidor)}"
DESTINO_DIR="${DESTINO_DIR:-agentes}"
CHAVE_SSH="${CHAVE_SSH:-$HOME/.ssh/id_ed25519}"
PREFIXO="${PREFIXO_SERVICO:-agente}"
AGENTES="${AGENTES:-$(cd "$ORIGEM" && ls -d */ 2>/dev/null | tr -d '/' | tr '\n' ' ')}"
COMPARA="-rz --checksum --itemize-changes"

if [ "${1:-}" = "--aplicar" ]; then SECO=""; echo ">>> ENVIANDO DE VERDADE"
else SECO="--dry-run"; echo ">>> simulação (nada sai daqui). Para valer: --aplicar"; fi
echo

mudaram=""
for a in $AGENTES; do
  echo "=== $a ==="
  [ -d "$ORIGEM/$a" ] || { echo "  !! pasta não encontrada, pulando"; continue; }
  for arq in CLAUDE.md .claude/settings.json; do
    [ -f "$ORIGEM/$a/$arq" ] || continue
    saida=$(rsync $COMPARA $SECO -e "ssh -i $CHAVE_SSH" "$ORIGEM/$a/$arq" "$DESTINO_SSH:$DESTINO_DIR/$a/$arq" 2>&1)
    if [ -n "$saida" ]; then echo "  ~ $arq (difere)"; mudaram="$mudaram $a"; else echo "  = $arq"; fi
  done
  if [ -d "$ORIGEM/$a/fontes" ]; then
    saida=$(rsync $COMPARA $SECO --delete -e "ssh -i $CHAVE_SSH" "$ORIGEM/$a/fontes/" "$DESTINO_SSH:$DESTINO_DIR/$a/fontes/" 2>&1)
    if [ -n "$saida" ]; then echo "  ~ fontes/:"; printf '%s\n' "$saida" | sed 's/^/      /'; mudaram="$mudaram $a"
    else echo "  = fontes/"; fi
  fi
done

[ -z "$mudaram" ] && { echo; echo ">>> nada a fazer: local e servidor iguais"; exit 0; }
lista=$(printf '%s\n' $mudaram | sort -u)
echo; echo ">>> agentes que mudaram:"; printf '      %s\n' $lista
[ -n "$SECO" ] && { echo; echo ">>> era simulação. Rode de novo com --aplicar"; exit 0; }

for a in $lista; do
  ssh -i "$CHAVE_SSH" "$DESTINO_SSH" "systemctl --user restart $PREFIXO@$a" </dev/null
  sleep 30
  echo "    $PREFIXO@$a -> $(ssh -i "$CHAVE_SSH" "$DESTINO_SSH" "systemctl --user is-active $PREFIXO@$a" </dev/null 2>&1)"
done
echo; echo ">>> mande uma mensagem de teste a cada agente reiniciado: é a única prova de que voltou."
