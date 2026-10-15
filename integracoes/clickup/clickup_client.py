#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente fino e genérico da API REST v2 do ClickUp, sem MCP.

Por que direto na API: conectores genéricos costumam listar tarefas com subtarefas
incluídas e sem filtro de arquivadas; em listas de CRM com subtarefas-lembrete (uma por
contato), isso infla a contagem de pessoas. Com subtasks=false e archived=false a
contagem bate com a real.

O que este cliente garante:
  - token só por variável de ambiente (CLICKUP_TOKEN), nunca em código;
  - retry automático em 429 respeitando Retry-After, e em 5xx com espera crescente;
  - paginação até a página vazia ou last_page=true;
  - leitura livre; ESCRITA sempre em simulação, a menos que aplicar=True seja passado
    explicitamente (na CLI: --aplicar).

IDs de workspace/lista ficam num arquivo de configuração local (CLICKUP_CONFIG,
modelo em config.exemplo.json), fora do controle de versão.

CLI:
    python clickup_client.py hierarchy
    python clickup_client.py tasks <lista|apelido> [--subtasks] [--include-archived] [--out arq.json]
    python clickup_client.py list <lista|apelido>
    python clickup_client.py fields <lista|apelido>
    python clickup_client.py get /list/<id>/task
    python clickup_client.py criar <lista|apelido> --nome "..." [--descricao "..."] [--aplicar]
    python clickup_client.py config
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

API = "https://api.clickup.com/api/v2"


# ---------------------------------------------------------------------------
# Configuração e token
# ---------------------------------------------------------------------------
def carregar_config(caminho: str | None = None) -> dict:
    caminho = caminho or os.environ.get("CLICKUP_CONFIG", "")
    if caminho and Path(caminho).exists():
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    return {"workspace_id": "", "listas": {}}


def resolver_lista(valor: str, config: dict | None = None) -> str:
    config = config or carregar_config()
    return config.get("listas", {}).get(valor, valor)


def get_token() -> str:
    tok = os.environ.get("CLICKUP_TOKEN", "").strip()
    if not tok:
        sys.exit("ERRO: defina a variável de ambiente CLICKUP_TOKEN (token pessoal do ClickUp).")
    return tok


def _cabecalhos() -> dict:
    return {"Authorization": get_token(), "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Chamadas com retry
# ---------------------------------------------------------------------------
def api_request(metodo: str, caminho: str, params: dict | None = None,
                corpo: dict | None = None, tentativas: int = 6) -> dict:
    import requests  # import tardio: py_compile e testes offline não precisam

    url = caminho if caminho.startswith("http") else API + caminho
    for tentativa in range(tentativas):
        r = requests.request(metodo, url, headers=_cabecalhos(), params=params or {},
                             json=corpo, timeout=60)
        if r.status_code == 429:
            espera = int(r.headers.get("Retry-After", "5") or 5)
            time.sleep(espera + 1)
            continue
        if r.status_code >= 500:
            time.sleep(min(2 ** tentativa, 30))
            continue
        r.raise_for_status()
        return r.json() if r.content else {}
    raise RuntimeError(f"falhou após {tentativas} tentativas em {metodo} {url}")


def api_get(caminho: str, params: dict | None = None) -> dict:
    return api_request("GET", caminho, params=params)


def get_all_tasks(list_id: str, subtasks: bool = False, archived: bool = False,
                  include_closed: bool = True, extra: dict | None = None) -> list[dict]:
    """Pagina TODAS as tarefas de uma lista com os parâmetros que batem com a contagem real."""
    params = {"include_closed": str(include_closed).lower(),
              "subtasks": str(subtasks).lower(),
              "archived": str(archived).lower()}
    params.update(extra or {})
    tarefas, pagina = [], 0
    while True:
        params["page"] = pagina
        dados = api_get(f"/list/{list_id}/task", params)
        lote = dados.get("tasks", [])
        if not lote:
            break
        tarefas.extend(lote)
        if dados.get("last_page") is True or len(lote) < 100:
            break
        pagina += 1
        time.sleep(0.2)
    return tarefas


def get_list(list_id: str) -> dict:
    return api_get(f"/list/{list_id}")  # traz task_count: contagem oficial sem paginar


def get_list_fields(list_id: str) -> list[dict]:
    return api_get(f"/list/{list_id}/field").get("fields", [])


def get_hierarchy(workspace_id: str) -> list[dict]:
    saida = []
    for esp in api_get(f"/team/{workspace_id}/space").get("spaces", []):
        no = {"id": esp["id"], "nome": esp["name"], "tipo": "espaco", "filhos": []}
        for pasta in api_get(f"/space/{esp['id']}/folder").get("folders", []):
            no["filhos"].append({"id": pasta["id"], "nome": pasta["name"], "tipo": "pasta",
                                 "filhos": [{"id": l["id"], "nome": l["name"], "tipo": "lista"}
                                            for l in pasta.get("lists", [])]})
        for l in api_get(f"/space/{esp['id']}/list").get("lists", []):
            no["filhos"].append({"id": l["id"], "nome": l["name"], "tipo": "lista"})
        saida.append(no)
    return saida


# ---------------------------------------------------------------------------
# Escrita: simulação por padrão
# ---------------------------------------------------------------------------
def criar_tarefa(list_id: str, corpo: dict, aplicar: bool = False) -> dict:
    plano = {"acao": "POST", "endpoint": f"/list/{list_id}/task", "corpo": corpo}
    if not aplicar:
        return {"simulacao": True, **plano}
    return {"simulacao": False, "resultado": api_request("POST", plano["endpoint"], corpo=corpo)}


def atualizar_tarefa(task_id: str, corpo: dict, aplicar: bool = False) -> dict:
    plano = {"acao": "PUT", "endpoint": f"/task/{task_id}", "corpo": corpo}
    if not aplicar:
        return {"simulacao": True, **plano}
    return {"simulacao": False, "resultado": api_request("PUT", plano["endpoint"], corpo=corpo)}


def definir_campo(task_id: str, field_id: str, valor, aplicar: bool = False) -> dict:
    plano = {"acao": "POST", "endpoint": f"/task/{task_id}/field/{field_id}", "corpo": {"value": valor}}
    if not aplicar:
        return {"simulacao": True, **plano}
    return {"simulacao": False, "resultado": api_request("POST", plano["endpoint"], corpo=plano["corpo"])}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _imprimir(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Cliente da API REST do ClickUp (sem MCP)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tasks"); p.add_argument("lista")
    p.add_argument("--subtasks", action="store_true"); p.add_argument("--include-archived", action="store_true")
    p.add_argument("--out")
    sub.add_parser("list").add_argument("lista")
    sub.add_parser("fields").add_argument("lista")
    sub.add_parser("hierarchy")
    sub.add_parser("get").add_argument("caminho")
    sub.add_parser("config")
    p = sub.add_parser("criar"); p.add_argument("lista"); p.add_argument("--nome", required=True)
    p.add_argument("--descricao", default=""); p.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    cfg = carregar_config()

    if a.cmd == "config":
        _imprimir(cfg)
    elif a.cmd == "hierarchy":
        if not cfg.get("workspace_id"):
            sys.exit("defina workspace_id no arquivo apontado por CLICKUP_CONFIG")
        _imprimir(get_hierarchy(cfg["workspace_id"]))
    elif a.cmd == "tasks":
        t = get_all_tasks(resolver_lista(a.lista, cfg), a.subtasks, a.include_archived)
        if a.out:
            Path(a.out).write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{len(t)} tarefas -> {a.out}", file=sys.stderr)
        else:
            _imprimir(t)
    elif a.cmd == "list":
        _imprimir(get_list(resolver_lista(a.lista, cfg)))
    elif a.cmd == "fields":
        _imprimir(get_list_fields(resolver_lista(a.lista, cfg)))
    elif a.cmd == "get":
        _imprimir(api_get(a.caminho))
    elif a.cmd == "criar":
        r = criar_tarefa(resolver_lista(a.lista, cfg), {"name": a.nome, "description": a.descricao}, a.aplicar)
        _imprimir(r)
        if r.get("simulacao"):
            print(">>> simulação: nada foi gravado. Para valer: --aplicar", file=sys.stderr)


if __name__ == "__main__":
    main()
