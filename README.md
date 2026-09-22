# agents

Repositório de experimentos e implementação de um ecossistema de auditoria orientado por agentes.

## Visão geral

Este projeto reúne:
- **documentação arquitetural** (ADRs, regras e fontes de referência);
- **schemas JSON canônicos** para contratos de auditoria;
- **skills** que implementam partes do pipeline (orquestração, normalização e delegação).

O conteúdo principal está em português e focado em rastreabilidade, determinismo e segurança na execução de auditorias automatizadas.

## Estrutura do repositório

```text
agents/
├── docs/
│   ├── decisions/            # decisões arquiteturais
│   ├── references/           # especificações e modelo canônico
│   │   └── schemas/          # schemas JSON oficiais
│   ├── rules/                # regras e políticas do projeto
│   └── sources/              # fontes base e diretrizes
├── skills/
│   ├── antigravity/          # skills específicas do domínio antigravity
│   └── universal/            # skills reutilizáveis
│       ├── project-audit/
│       ├── audit-normalize/
│       └── omniroute-delegation/
├── auditoring/               # área de auditoria em evolução
├── validate_schemas.py       # validação estrutural dos schemas
└── install_skills.py         # instalação local de skills gerenciadas
```

## Componentes principais

- **project-audit**: motor de orquestração de auditoria e estado incremental.
- **audit-normalize**: normalização determinística da saída de auditoria para contrato canônico.
- **omniroute-delegation**: construção/validação de tarefas de delegação e integração com backend.

## Como começar

1. Leia os documentos em `/home/runner/work/agents/agents/docs/references`.
2. Consulte as decisões em `/home/runner/work/agents/agents/docs/decisions`.
3. Explore as skills em `/home/runner/work/agents/agents/skills/universal`.

## Validação de schemas

Para validar os schemas canônicos:

```bash
python /home/runner/work/agents/agents/validate_schemas.py
```

> O script depende de `jsonschema` e `referencing` instalados no ambiente.

## Observações

- Este repositório contém documentação e implementação em diferentes níveis de maturidade.
- Prefira tratar `docs/references/schemas` como fonte de verdade para contratos de dados.
