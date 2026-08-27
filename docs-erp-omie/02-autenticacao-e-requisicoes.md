# 02 — Autenticação e Formato de Requisições

## Autenticação

A API Omie autentica cada requisição com um par de credenciais enviado **no corpo**
da própria chamada (não há header `Authorization` nem token de sessão):

- **`app_key`** — identificador do aplicativo/integração.
- **`app_secret`** — segredo do aplicativo.

Cada aplicativo cadastrado no Omie possui seu próprio par de chaves, o que permite
segmentar e auditar o consumo por integração. **Trate `app_secret` como segredo**:
nunca versione em repositório, use variáveis de ambiente ou um cofre de segredos.

## Estrutura padrão da requisição

Todas as chamadas seguem o mesmo envelope JSON, enviado via **POST** ao endpoint
do recurso:

```json
{
  "call": "ListarClientes",
  "app_key": "SEU_APP_KEY",
  "app_secret": "SEU_APP_SECRET",
  "param": [
    {
      "pagina": 1,
      "registros_por_pagina": 100,
      "apenas_importado_api": "N"
    }
  ]
}
```

Campos do envelope:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `call` | string | Nome do método a executar (ex.: `ListarClientes`, `IncluirCliente`). |
| `app_key` | string | Chave do aplicativo. |
| `app_secret` | string | Segredo do aplicativo. |
| `param` | array | Array com **um** objeto contendo os parâmetros do método. |

> Observação: `param` é sempre um array, mesmo quando o método recebe um único
> objeto de parâmetros.

## Cabeçalhos

```
Content-Type: application/json
```

## Padrão de nomenclatura dos métodos (`call`)

Os métodos seguem convenções previsíveis por recurso:

| Prefixo | Finalidade | Exemplo |
|---------|-----------|---------|
| `Listar*` | Listagem em lote (paginada) | `ListarClientes` |
| `Consultar*` | Consulta de um único registro | `ConsultarCliente` |
| `Incluir*` | Criação de registro | `IncluirCliente` |
| `Alterar*` | Atualização de registro | `AlterarCliente` |
| `Excluir*` | Exclusão de registro | `ExcluirCliente` |
| `Upsert*` | Inclui ou altera conforme existência | `UpsertCliente` |

> Os nomes exatos variam por recurso. Consulte a página do serviço no Portal do
> Desenvolvedor para a lista definitiva de métodos.

## Paginação (métodos `Listar*`)

Parâmetros comuns de paginação:

| Parâmetro | Descrição |
|-----------|-----------|
| `pagina` | Número da página (inicia em 1). |
| `registros_por_pagina` | Quantidade de registros por página (recomendado ≤ 100). |
| `apenas_importado_api` | `S`/`N` — filtra apenas registros criados via API. |

A resposta de listagem normalmente inclui metadados de paginação, permitindo
percorrer todas as páginas:

| Campo de resposta | Descrição |
|-------------------|-----------|
| `pagina` | Página atual retornada. |
| `total_de_paginas` | Total de páginas disponíveis. |
| `registros` | Registros nesta página. |
| `total_de_registros` | Total de registros disponíveis. |

## Formato da resposta

### Sucesso

Retorna HTTP `200` com o corpo JSON específico do método (ex.: lista de clientes,
cadastro consultado, `codigo_cliente_omie` de um cadastro incluído).

### Erro

A API sinaliza erros de negócio/validação retornando um corpo com mensagem de
falha (comumente em campos como `faultstring` / `faultcode`), e em alguns casos
pode retornar HTTP `500` mesmo para erros tratáveis de negócio. Por isso:

- **Não** confie apenas no status HTTP; inspecione o corpo da resposta.
- Trate mensagens de falha para diferenciar erro de credencial, erro de parâmetro
  e erro de negócio.

Exemplo de erro de acesso negado (credencial inválida ou aplicativo sem permissão):

```json
{ "faultstring": "Client [...] not authorized.", "faultcode": "SOAP-ENV:Client-XXX" }
```

## Segurança e credenciais

- Armazene `app_key`/`app_secret` fora do código (variáveis de ambiente / secret manager).
- Use um aplicativo/credencial distinto por integração para isolar o rate limit e
  facilitar a revogação.
- Nunca exponha `app_secret` em logs ou em requisições client-side.

## Referências

- [Cadastrando um Cliente ou Fornecedor via API](https://ajuda.omie.com.br/pt-BR/articles/6596048-cadastrando-um-cliente-ou-fornecedor-via-api)
- [Configurando o Postman](https://ajuda.omie.com.br/pt-BR/articles/5412735-configurando-o-postman)

_Conteúdo reescrito para fins de documentação interna._
