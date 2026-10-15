# integracoes/clickup

Cliente REST genérico do ClickUp e a ferramenta de operação de contatos usada pelo agente
`operador-crm`.

| Arquivo | Função |
|---|---|
| `clickup_client.py` | Leitura com paginação e retry (429 com `Retry-After`, 5xx com espera crescente); escrita sempre em simulação sem `aplicar=True` / `--aplicar` |
| `operar_contato.py` | `buscar` / `inserir` / `editar` com duplicata exata em todas as listas, lista de bloqueio intransponível, `--forcar` só com confirmação humana, `--aplicar` para gravar |
| `config.exemplo.json` | Modelo dos IDs de workspace, listas e campos (copie para fora do repositório) |

## Configuração

```bash
export CLICKUP_TOKEN=...                      # token pessoal; nunca em arquivo versionado
export CLICKUP_CONFIG=~/.config/agentes/clickup.json
python clickup_client.py hierarchy            # descobre os IDs para preencher o config
```

Um mesmo token pode alcançar mais de um workspace. Antes de qualquer escrita, confira que o
`workspace_id` do config é o da operação certa; sem isso, um teste pode cair na base de outra
organização.

## Por que API direta

Conectores genéricos tendem a listar tarefas com subtarefas e sem filtro de arquivadas. Em listas
de CRM com subtarefas-lembrete, isso infla a contagem de pessoas. `subtasks=false` e
`archived=false` batem com a contagem real; `GET /list/{id}` traz `task_count` sem paginar.

## Demonstração offline

```bash
python operar_contato.py buscar --telefone "+55 00 90000-0001" --offline ../../exemplos/crm_ficticio.json
python operar_contato.py inserir --nome "Joana Exemplo" --offline ../../exemplos/crm_ficticio.json
python operar_contato.py inserir --nome "Rita Bloqueada" --forcar --aplicar --offline ../../exemplos/crm_ficticio.json
```
