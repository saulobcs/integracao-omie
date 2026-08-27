# Regras de Roteamento e Conciliação

Regras de negócio que definem, para cada linha do OFX, qual ação executar no
Omie. Baseado no OFX de referência (Stone) analisado em
[`02-analise-ofx-referencia.md`](./02-analise-ofx-referencia.md).

---

## 1. Princípio geral

Cada transação do extrato segue uma de duas rotas, decidida pelo **sinal**
(crédito/débito) e pelo **texto do `MEMO`**:

- **Créditos** → **roteados para uma conta corrente específica** conforme o
  `MEMO`, via **mapa de configuração** (não são baixa de título).
- **Débitos de pagamento** → **baixa de conta a pagar** correspondente no Omie.
- **Sem correspondência / MEMO não reconhecido** → **fila manual** (exceção).

---

## 2. Créditos — roteamento por MEMO para conta destino

Os créditos não casam 1:1 com títulos a receber. Em vez disso, são direcionados
para contas correntes específicas do Omie conforme o padrão do `MEMO`.

### Exemplos de mapeamento (definidos pelo negócio)

| Padrão de MEMO | Conta destino |
|----------------|---------------|
| `Recebimento vendas - Antecipação` | Conta de crédito |
| `<nome> - Pix \| Maquininha` | Conta Pix |
| `IFOODCOM ... - Transferência \| Pix` | Conta iFood |
| *(não reconhecido)* | **Fila manual** |

> O nome da contraparte varia (ex.: "Patriny Martins de Lacerda"), mas o
> **sufixo do MEMO** (`- Pix | Maquininha`) é estável. Por isso o casamento é por
> **padrão** (sufixo/regex), não por texto exato.

### Ação no Omie
Registrar o crédito na conta destino via **`IncluirLancCC`**
(`/api/v1/financas/contacorrentelancamentos/`), informando `cabecalho.nCodCC` (a
conta mapeada), `dDtLanc`, `nValorLanc` e a categoria configurada.

---

## 3. Mapa de configuração (requisito central)

Deve existir um **arquivo de configuração editável** que mapeia padrões de MEMO
para contas do Omie, sem necessidade de alterar código. Estrutura proposta:

```yaml
# config de roteamento (exemplo ilustrativo)
conta_corrente_origem:
  acctid_ofx: "6684788-0"      # conta Stone do extrato
  ncodcc_omie: null            # PENDÊNCIA: nCodCC correspondente no Omie

regras_credito:
  - nome: "Antecipação de vendas"
    match: { campo: MEMO, tipo: igual, valor: "Recebimento vendas - Antecipação" }
    ncodcc_destino: null       # Conta de crédito (preencher)
    ccodcateg: null            # categoria Omie (preencher)

  - nome: "Pix Maquininha"
    match: { campo: MEMO, tipo: sufixo, valor: " - Pix | Maquininha" }
    ncodcc_destino: null       # Conta Pix (preencher)
    ccodcateg: null

  - nome: "iFood"
    match: { campo: MEMO, tipo: contem, valor: "IFOODCOM" }
    ncodcc_destino: null       # Conta iFood (preencher)
    ccodcateg: null

# créditos que não casarem com nenhuma regra -> fila manual

regras_debito:
  - nome: "Pagamento a fornecedor"
    match: { campo: MEMO, tipo: sufixo, valor: " - Pagamento" }
    acao: baixar_conta_pagar   # busca título em contas a pagar

# débitos sem título correspondente -> fila manual
```

- Tipos de match sugeridos: `igual`, `sufixo`, `prefixo`, `contem`, `regex`.
- Ordem das regras importa: primeira que casar vence.
- Toda linha sem regra aplicável cai na **fila manual**.

---

## 4. Débitos de pagamento — baixa de conta a pagar

Para débitos com MEMO de pagamento (`... - Pagamento`):

1. Buscar título correspondente em contas a pagar via `PesquisarTitulos`
   (`/api/v1/financas/pesquisartitulos/`) por valor + data (+ nome do MEMO como
   apoio).
2. **Achou 1 título** → baixar via `/api/v1/financas/contapagar/`.
3. **Não achou / múltiplos candidatos** → fila manual.

Observação: transferências Pix de débito (`... - Transferência | Pix`) que não
forem pagamento de fornecedor podem exigir regra própria (conta destino ou
exceção) — a definir conforme o caso.

---

## 5. Fluxo consolidado

```
Linha OFX (fitid, dtposted, trnamt, memo)
   │
   ├─ já processada (fitid)?  ──sim──► pula (idempotência)
   │
   ├─ CRÉDITO ─► casa alguma regra_credito?
   │               ├─ sim ─► IncluirLancCC na conta destino mapeada
   │               └─ não ─► fila manual
   │
   └─ DÉBITO ──► casa regra_debito (pagamento)?
                   ├─ sim ─► PesquisarTitulos → baixa conta a pagar
                   │           └─ sem título/ambíguo ─► fila manual
                   └─ não ─► fila manual
```

Ao final: persistir vínculo `fitid ⇄ (tipo_acao, codigo_lancamento/codigo_baixa,
nCodCC)` e conferir saldo com `ExtratoContaCorrente`.

---

_Documento de regras elaborado para documentação interna do projeto de
conciliação._
