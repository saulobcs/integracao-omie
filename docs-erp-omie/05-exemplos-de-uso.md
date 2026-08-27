# 05 — Exemplos de Uso

Exemplos práticos de consumo da API Omie via JSON/HTTP. Substitua
`SEU_APP_KEY` e `SEU_APP_SECRET` pelas credenciais do seu aplicativo (carregadas
de variáveis de ambiente, não hardcoded).

> Os payloads abaixo são ilustrativos. Confirme os parâmetros exatos de cada
> método na página do serviço no [Portal do Desenvolvedor](https://developer.omie.com.br/service-list/).

## Listar clientes (cURL)

```bash
curl -s https://app.omie.com.br/api/v1/geral/clientes/ \
  -H 'Content-Type: application/json' \
  -d '{
    "call": "ListarClientes",
    "app_key": "SEU_APP_KEY",
    "app_secret": "SEU_APP_SECRET",
    "param": [
      { "pagina": 1, "registros_por_pagina": 100, "apenas_importado_api": "N" }
    ]
  }'
```

## Listar contas a pagar (cURL)

```bash
curl -s https://app.omie.com.br/api/v1/financas/contapagar/ \
  -H 'Content-Type: application/json' \
  -d '{
    "call": "ListarContasPagar",
    "app_key": "SEU_APP_KEY",
    "app_secret": "SEU_APP_SECRET",
    "param": [
      { "pagina": 1, "registros_por_pagina": 100, "apenas_importado_api": "N" }
    ]
  }'
```

## Python (requests) — listagem paginada completa

```python
import os
import requests

APP_KEY = os.environ["OMIE_APP_KEY"]
APP_SECRET = os.environ["OMIE_APP_SECRET"]
BASE_URL = "https://app.omie.com.br/api/v1"


def chamar(recurso: str, call: str, param: dict) -> dict:
    """Executa uma chamada à API Omie e retorna o JSON de resposta."""
    resp = requests.post(
        f"{BASE_URL}/{recurso}/",
        json={
            "call": call,
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "param": [param],
        },
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    data = resp.json()
    # A API pode sinalizar erro de negócio no corpo mesmo com status != 200.
    if isinstance(data, dict) and "faultstring" in data:
        raise RuntimeError(f"Erro Omie: {data.get('faultstring')}")
    resp.raise_for_status()
    return data


def listar_todos(recurso: str, call: str, chave_lista: str, extra: dict | None = None):
    """Percorre todas as páginas de um método Listar* e devolve todos os registros."""
    registros = []
    pagina = 1
    while True:
        param = {"pagina": pagina, "registros_por_pagina": 100}
        if extra:
            param.update(extra)
        data = chamar(recurso, call, param)
        registros.extend(data.get(chave_lista, []))
        total_paginas = data.get("total_de_paginas", 1)
        if pagina >= total_paginas:
            break
        pagina += 1
    return registros


if __name__ == "__main__":
    clientes = listar_todos(
        recurso="geral/clientes",
        call="ListarClientes",
        chave_lista="clientes_cadastro",
        extra={"apenas_importado_api": "N"},
    )
    print(f"Total de clientes: {len(clientes)}")
```

## PHP — chamada simples

```php
<?php
$app_key = getenv('OMIE_APP_KEY');
$app_secret = getenv('OMIE_APP_SECRET');

$payload = json_encode([
    'call' => 'ListarClientes',
    'app_key' => $app_key,
    'app_secret' => $app_secret,
    'param' => [[
        'pagina' => 1,
        'registros_por_pagina' => 100,
        'apenas_importado_api' => 'N',
    ]],
]);

$ch = curl_init('https://app.omie.com.br/api/v1/geral/clientes/');
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);

$response = curl_exec($ch);
curl_close($ch);

$data = json_decode($response, true);
if (isset($data['faultstring'])) {
    throw new RuntimeException('Erro Omie: ' . $data['faultstring']);
}
print_r($data);
```

## Dicas

- Reaproveite a função de chamada genérica: apenas o `recurso` e o `call` mudam
  entre os serviços; o envelope é sempre o mesmo.
- Para sincronizações recorrentes, adicione filtros de data para trazer apenas
  registros novos/alterados (ver [04-boas-praticas.md](./04-boas-praticas.md)).
- Verifique o nome exato da chave da lista na resposta de cada método
  (ex.: `clientes_cadastro` para clientes) — ela varia por recurso.

_Exemplos elaborados para documentação interna, com base no padrão de requisição
da API Omie._
