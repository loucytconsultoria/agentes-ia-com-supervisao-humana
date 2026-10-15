#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Núcleo do bot de rascunho com aprovação humana.

O bot NUNCA fala com o público. Ele recebe uma mensagem colada por alguém da equipe,
gera um RASCUNHO de resposta a partir de uma base de conhecimento filtrada por camada,
e o rascunho só é liberado quando um aprovador autorizado aprova. Quem envia ao
público é sempre uma pessoa, copiando o texto aprovado.

Este módulo não depende de Discord nem de rede: dá para testar tudo com o gerador
fictício (ver demo.py). O adaptador do Discord fica em bot_discord.py.

Camadas de confidencialidade (ver docs/01):
    N1 = público · N2 = interno · N3 = sensível (nunca carregado por nenhum agente)
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

ROTULO = "RASCUNHO, revisão humana obrigatória"
ORDEM_CAMADAS = {"N1": 1, "N2": 2, "N3": 3}

# ---------------------------------------------------------------------------
# Base de conhecimento por camada
# ---------------------------------------------------------------------------
_RE_CAMADA = re.compile(r"^Camada:\s*(N[123])", re.MULTILINE)


def camada_do_arquivo(texto: str) -> str | None:
    """Lê a linha 'Camada: Nx' do cabeçalho. Arquivo sem camada é tratado como N3
    (o mais restrito): na dúvida de sigilo, não entra."""
    m = _RE_CAMADA.search(texto[:800])
    return m.group(1) if m else None


def carregar_base(pasta: str | Path, camada_max: str = "N1") -> dict[str, str]:
    """Carrega os .md da base cuja camada <= camada_max. N3 nunca é carregado,
    nem que camada_max peça (N3 informa estilo no estudo, não vai para agente)."""
    if camada_max not in ("N1", "N2"):
        raise ValueError("camada_max precisa ser N1 ou N2; N3 nunca é carregado")
    limite = ORDEM_CAMADAS[camada_max]
    base: dict[str, str] = {}
    for arq in sorted(Path(pasta).glob("*.md")):
        texto = arq.read_text(encoding="utf-8")
        camada = camada_do_arquivo(texto) or "N3"
        if ORDEM_CAMADAS[camada] <= limite:
            base[arq.name] = texto
    if not any(n.startswith("05") for n in base):
        raise RuntimeError("a base precisa ter o arquivo 05 de linhas vermelhas em N1")
    return base


def montar_system_prompt(persona: str, base: dict[str, str]) -> str:
    """Persona do agente + base, com as linhas vermelhas sempre primeiro."""
    ordem = sorted(base, key=lambda n: (0 if n.startswith("05") else 1, n))
    blocos = [persona.strip(), "", "# Base de conhecimento (só use o que está aqui)"]
    for nome in ordem:
        blocos += ["", f"## Arquivo: {nome}", base[nome].strip()]
    return "\n".join(blocos)


# ---------------------------------------------------------------------------
# Higiene da entrada: dado pessoal não vai para o modelo
# ---------------------------------------------------------------------------
_PADROES_PESSOAIS = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b"), "[TELEFONE]"),
]


def mascarar_dados_pessoais(texto: str) -> str:
    for padrao, marca in _PADROES_PESSOAIS:
        texto = padrao.sub(marca, texto)
    return texto


# ---------------------------------------------------------------------------
# Pré-filtro determinístico de escalação (defesa em profundidade: o modelo
# também escala, mas o código não depende só dele)
# ---------------------------------------------------------------------------
@dataclass
class RegrasEscalacao:
    gatilhos: dict[str, list[str]] = field(default_factory=dict)  # motivo -> termos

    @classmethod
    def de_arquivo(cls, caminho: str | Path) -> "RegrasEscalacao":
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        return cls(gatilhos=dados.get("gatilhos", {}))

    def avaliar(self, texto: str) -> str | None:
        t = texto.lower()
        for motivo, termos in self.gatilhos.items():
            if any(termo.lower() in t for termo in termos):
                return motivo
        return None


_RE_TAG_ESCALAR = re.compile(r"\[ESCALAR:\s*([^\]]+)\]")


# ---------------------------------------------------------------------------
# Checagem da saída antes de mostrar ao aprovador
# ---------------------------------------------------------------------------
def checar_saida(texto: str, termos_proibidos: Iterable[str]) -> list[str]:
    """Problemas objetivos (não de estilo). Estilo é do revisor humano."""
    problemas = []
    t = texto.lower()
    for termo in termos_proibidos:
        if termo.lower() in t:
            problemas.append(f"termo proibido na saída: '{termo}'")
    if "pronto para publicar" in t:
        problemas.append("o rascunho se declarou pronto para publicar")
    return problemas


# ---------------------------------------------------------------------------
# Rascunho e fila de aprovação
# ---------------------------------------------------------------------------
PENDENTE, APROVADO, REJEITADO, BLOQUEADO = "PENDENTE", "APROVADO", "REJEITADO", "BLOQUEADO"


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Rascunho:
    id: str
    pedido_por: str
    mensagem: str          # já mascarada
    texto: str
    escalar: str | None
    problemas: list[str]
    estado: str = PENDENTE
    decidido_por: str | None = None
    motivo_decisao: str | None = None
    criado_em: str = field(default_factory=_agora)
    decidido_em: str | None = None

    def para_revisao(self) -> str:
        linhas = [f"[{ROTULO}] id {self.id}", "", self.texto]
        if self.escalar:
            linhas += ["", f"[ESCALAR: {self.escalar}]"]
        if self.problemas:
            linhas += ["", "[CHECAGEM AUTOMÁTICA] " + "; ".join(self.problemas)]
        return "\n".join(linhas)


Gerador = Callable[[str, str], str]  # (system_prompt, mensagem) -> texto


class FilaDeAprovacao:
    """Estado + trilha de auditoria. Cada evento vira uma linha JSON (append-only)."""

    def __init__(self, aprovadores: Iterable[str], trilha: str | Path,
                 exigir_aprovador_diferente: bool = True):
        self.aprovadores = set(aprovadores)
        self.trilha = Path(trilha)
        self.trilha.parent.mkdir(parents=True, exist_ok=True)
        self.exigir_aprovador_diferente = exigir_aprovador_diferente
        self.rascunhos: dict[str, Rascunho] = {}

    def _registrar(self, evento: str, r: Rascunho, ator: str, extra: dict | None = None):
        linha = {"quando": _agora(), "evento": evento, "rascunho": r.id,
                 "ator": ator, "estado": r.estado}
        if extra:
            linha.update(extra)
        with self.trilha.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")

    def criar(self, pedido_por: str, mensagem: str, system_prompt: str,
              gerador: Gerador, regras: RegrasEscalacao,
              termos_proibidos: Iterable[str] = ()) -> Rascunho:
        limpa = mascarar_dados_pessoais(mensagem)
        motivo = regras.avaliar(limpa)
        texto = gerador(system_prompt, limpa).strip()
        tag = _RE_TAG_ESCALAR.search(texto)
        if tag:
            motivo = motivo or tag.group(1).strip()
            texto = _RE_TAG_ESCALAR.sub("", texto).strip()
        r = Rascunho(id=uuid.uuid4().hex[:8], pedido_por=pedido_por, mensagem=limpa,
                     texto=texto, escalar=motivo,
                     problemas=checar_saida(texto, termos_proibidos))
        if r.problemas:
            r.estado = BLOQUEADO  # não pode ser aprovado como está; volta para reescrita
        self.rascunhos[r.id] = r
        self._registrar("criado", r, pedido_por,
                        {"escalar": motivo, "problemas": r.problemas})
        return r

    def decidir(self, rid: str, usuario: str, aprovar: bool, motivo: str = "") -> tuple[bool, str]:
        r = self.rascunhos.get(rid)
        if r is None:
            return False, "rascunho não encontrado"
        if usuario not in self.aprovadores:
            self._registrar("tentativa_negada", r, usuario, {"razao": "não é aprovador"})
            return False, "você não está na lista de aprovadores"
        if self.exigir_aprovador_diferente and usuario == r.pedido_por and aprovar:
            self._registrar("tentativa_negada", r, usuario, {"razao": "autoaprovação"})
            return False, "quem pediu o rascunho não aprova o próprio pedido"
        if r.estado != PENDENTE:
            return False, f"rascunho está {r.estado}, não pode ser decidido"
        r.estado = APROVADO if aprovar else REJEITADO
        r.decidido_por, r.motivo_decisao, r.decidido_em = usuario, motivo or None, _agora()
        self._registrar("aprovado" if aprovar else "rejeitado", r, usuario, {"motivo": motivo})
        return True, r.estado


# ---------------------------------------------------------------------------
# Geradores
# ---------------------------------------------------------------------------
def gerador_claude(modelo: str | None = None) -> Gerador:
    """Gera o rascunho com o Claude pela SDK oficial. Credenciais vêm do ambiente
    (ANTHROPIC_API_KEY ou perfil do `ant auth login`); nada fica no código."""
    import anthropic  # import tardio: o demo roda sem a SDK instalada

    cliente = anthropic.Anthropic()
    modelo = modelo or os.environ.get("MODELO_RASCUNHO", "claude-opus-5-5")

    def gerar(system_prompt: str, mensagem: str) -> str:
        resp = cliente.messages.create(
            model=modelo,
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role": "user", "content": mensagem}],
        )
        if resp.stop_reason == "refusal":
            return "[ESCALAR: o modelo recusou gerar rascunho para esta mensagem]"
        return "".join(b.text for b in resp.content if b.type == "text")

    return gerar


def gerador_ficticio(respostas: dict[str, str], padrao: str) -> Gerador:
    """Para demonstração e testes: devolve respostas gravadas por palavra-chave."""
    def gerar(system_prompt: str, mensagem: str) -> str:
        m = mensagem.lower()
        for chave, resposta in respostas.items():
            if chave in m:
                return resposta
        return padrao
    return gerar


def salvar_estado(fila: FilaDeAprovacao, caminho: str | Path) -> None:
    Path(caminho).write_text(
        json.dumps({k: asdict(v) for k, v in fila.rascunhos.items()},
                   ensure_ascii=False, indent=2), encoding="utf-8")
