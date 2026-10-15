# ops · rodar os agentes 24/7

Explicação completa em [docs/06](../docs/06-operacao-24x7.md). Aqui, só o passo a passo.

## Conteúdo

| Pasta | O que tem |
|---|---|
| `bot_rascunho/` | Bot de chat que só gera rascunho e exige aprovação (`demo.py` roda offline) |
| `monitor/` | `monitor.sh` (três profundidades), `alerta.py` (e-mail + webhook de reserva), `reinicio.sh` |
| `systemd/` | `agente@.service` (uma instância por agente de terminal), `iniciar_agente.sh`, `bot-rascunho.service` |
| `cron/` | `crontab.exemplo` com horários que não se cruzam |
| `deploy/` | `sincronizar.sh`: envia persona, permissões e fontes; simulação por padrão |
| `permissoes/` | `settings.producao.exemplo.json`: allow/deny de um agente que grava no CRM |
| `.env.example` | Todas as variáveis, vazias |

## Instalação num servidor Linux (resumo)

```bash
# 1. Usuário sem privilégio para os agentes; segredos num arquivo 600
sudo install -d -m 700 -o $USER /etc/agentes
cp ops/.env.example /etc/agentes/agentes.env && chmod 600 /etc/agentes/agentes.env
#    (preencha o arquivo no servidor; nunca o copie de volta)

# 2. Scripts
mkdir -p ~/bin ~/logs
cp ops/monitor/*.sh ops/monitor/alerta.py ops/systemd/iniciar_agente.sh ~/bin/
sed -i 's/\r$//' ~/bin/*          # se os arquivos passaram por Windows
chmod 700 ~/bin/*

# 3. Serviços
mkdir -p ~/.config/systemd/user
cp ops/systemd/agente@.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agente@atendimento agente@comentarios agente@crm
sudo loginctl enable-linger $USER && loginctl show-user $USER -p Linger   # Linger=yes

# 4. Monitor
crontab ops/cron/crontab.exemplo && crontab -l
python3 ~/bin/alerta.py --testar
~/bin/monitor.sh --profundo < /dev/null && tail -3 ~/logs/monitor.log
```

## Verificação (o que conta)

1. `sudo reboot`; depois `uptime -s` mostra a hora do reboot.
2. `for a in atendimento comentarios crm; do systemctl --user is-active agente@$a; done`
3. `for p in $(pgrep -f "claude --channels"); do readlink /proc/$p/cwd; done` (cada um na sua pasta)
4. `crontab -l`
5. **Uma mensagem real para cada agente, com resposta.** Serviço ativo não prova que responde.

## Cuidados

- Nunca rode o mesmo agente em duas máquinas: a segunda conexão fica muda sem erro.
- Não reinicie o mesmo agente várias vezes seguidas: a plataforma de chat bloqueia por 15 a 30 min.
- Antes de sair de uma sessão tmux, feche qualquer menu aberto (Esc): menu aberto trava a fila.
- `tmux ls` não vê os agentes; use `tmux -L agente-<nome> ls`.
