---
inclusion: manual
---

# Como adicionar um novo cliente ao conciliador

Guia passo a passo para cadastrar um novo cliente no conciliador OFX → Omie.
Cada cliente é **isolado**: tem o seu próprio roteamento, plano de contas,
credenciais e pasta de saída. Nada é compartilhado entre clientes.

> Exemplo usado no guia: um cliente novo de `id` **`acme`**. Troque `acme` pelo
> identificador real (use só letras minúsculas, números, `-` ou `_`).

## Visão geral (o que você vai criar)

```
conciliador-ofx/
  clientes/
    clientes.json          ← adicionar 1 bloco com o novo cliente
    acme/                   ← (novo) pasta do cliente
      .env                  ← credenciais do Omie do cliente (NÃO versionado)
      roteamento.json       ← regras de crédito/débito por conta de origem
      contas-acme.json      ← plano de contas do Omie do cliente (opcional, ajuda)
```

## Passo 1 — Criar a pasta do cliente

Crie `conciliador-ofx/clientes/acme/`.

## Passo 2 — Credenciais (`.env`)

Copie o modelo do haru e preencha as chaves do Omie **do cliente novo**:

```bash
cp conciliador-ofx/clientes/haru/.env.example conciliador-ofx/clientes/acme/.env
```

Edite `clientes/acme/.env`:

```
OMIE_APP_KEY=<app_key do cliente>
OMIE_APP_SECRET=<app_secret do cliente>
OMIE_BASE=https://app.omie.com.br/api/v1
```

O `.env` não é versionado (está no `.gitignore`). Sem ele, o cliente ainda roda
em `--modo offline` (sem consultar a API).

## Passo 3 — Plano de contas (`contas-acme.json`) — opcional, recomendado

É a resposta do endpoint **`ListarContasCorrentes`** do Omie do cliente. Serve
para exibir as contas como `(nCodCC) descrição` e para você descobrir os
`nCodCC`. Salve o JSON como `clientes/acme/contas-acme.json`.

Se você não tiver esse arquivo, o conciliador funciona mesmo assim: só mostra a
descrição vinda do próprio roteamento.

## Passo 4 — Roteamento (`roteamento.json`)

É o coração da configuração do cliente. Comece a partir do modelo do haru:

```bash
cp conciliador-ofx/clientes/haru/roteamento.json conciliador-ofx/clientes/acme/roteamento.json
```

Depois, ajuste para o cliente novo. Estrutura mínima:

```json
{
  "descricao": "Roteamento do cliente Acme.",
  "versao_schema": 2,
  "origens": [
    {
      "nome": "Stone",
      "match_origem": { "bankid": "0197", "acctid": "0000000-0" },
      "ncodcc_omie": 0,
      "descricao_origem": "Stone",
      "regras_credito": [
        {
          "nome": "Exemplo recebimento",
          "match": { "tipo": "contem", "valor": "TEXTO DO MEMO" },
          "acao": "incluir_lanc_cc",
          "ncodcc_destino": 0,
          "descricao_destino": "Conta destino",
          "ccodcateg": null
        }
      ],
      "regras_debito": [
        {
          "nome": "Exemplo pagamento",
          "match": { "tipo": "sufixo", "valor": " - Pagamento" },
          "acao": "baixar_conta_pagar",
          "observacao": "Pesquisa título a pagar em aberto e casa por valor + nome no MEMO."
        }
      ]
    }
  ]
}
```

O que preencher em cada campo:

| Campo | O que é |
|-------|---------|
| `match_origem.bankid` / `acctid` | Banco e conta do extrato OFX do cliente (identificam a origem). |
| `ncodcc_omie` | `nCodCC` da conta de origem no Omie do cliente. |
| `ncodcc_destino` | `nCodCC` da conta de destino no Omie (crédito). |
| `match.tipo` | Como casar o MEMO: `contem`, `igual` ou `sufixo`. |
| `match.valor` | O texto procurado no MEMO da transação. |
| `acao` | `incluir_lanc_cc` (crédito) ou `baixar_conta_pagar` (débito). |
| `ccodcateg` | Código da categoria no Omie (ou `null` se ainda não souber). |

> Os `nCodCC` e `ccodcateg` são **específicos do Omie deste cliente**. Nunca
> reutilize os IDs de outro cliente — o sistema bloqueia o compartilhamento do
> arquivo de roteamento entre clientes.

## Passo 5 — Registrar em `clientes.json`

Adicione um bloco novo dentro de `"clientes"` em
`conciliador-ofx/clientes/clientes.json`:

```json
{
  "id": "acme",
  "nome": "Acme",
  "config": "clientes/acme/roteamento.json",
  "plano_contas": "clientes/acme/contas-acme.json",
  "env": "clientes/acme/.env",
  "saida": "saida/acme",
  "confirmacao_apply": "ACME",
  "contas_ofx_permitidas": [
    { "bankid": "0197", "acctid": "0000000-0", "nome": "Stone" }
  ]
}
```

| Campo | O que é |
|-------|---------|
| `id` | Identificador usado em `--cliente` (minúsculas/números/`-`/`_`). |
| `nome` | Nome de exibição. |
| `config` | Caminho do roteamento do cliente. |
| `plano_contas` | Caminho do plano de contas do cliente. |
| `env` | Caminho do `.env` do cliente. |
| `saida` | Pasta onde os relatórios são gravados (`saida/<id>`). |
| `confirmacao_apply` | Código exigido em `--modo apply --confirmar` (proteção). |
| `contas_ofx_permitidas` | **Trava de segurança**: só processa OFX cujo `bankid`/`acctid` estejam nesta lista. Impede rodar o extrato de um cliente no perfil de outro. |

## Passo 6 — Testar (modo seguro, sem escrever nada)

Rode em `offline` (não toca a API) apontando para um OFX do cliente:

```bash
cd conciliador-ofx
python3 main.py --cliente acme --ofx "/caminho/do/extrato.ofx" --modo offline
```

Confira no resumo:
- A conta do extrato foi **aceita** (se não, revise `contas_ofx_permitidas`).
- As transações caíram nas regras certas (poucas em `manual`).

Depois, se tiver credenciais, valide com consulta read-only (não escreve):

```bash
python3 main.py --cliente acme --ofx "/caminho/do/extrato.ofx"   # dry-run
```

Só use `--modo apply --confirmar ACME` quando o dry-run estiver correto: esse
modo **escreve de verdade** no Omie.

## Checklist rápido

- [ ] Pasta `clientes/acme/` criada
- [ ] `.env` do cliente preenchido (ou vai rodar só em `offline`)
- [ ] `roteamento.json` com `match_origem`, `nCodCC` e regras do cliente
- [ ] `contas-acme.json` salvo (opcional)
- [ ] Bloco do cliente adicionado em `clientes.json`
- [ ] `contas_ofx_permitidas` lista as contas do OFX do cliente
- [ ] Testado em `--modo offline` sem cair tudo em `manual`
