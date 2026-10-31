# Servidor PTA

Implementacao do servidor do Protocolo de Transferencia de Arquivos descrito em [pta.pdf](../pta.pdf).

## Requisitos

- Python 3.8 ou superior (testado com Python 3.13.12).
- Apenas biblioteca padrao (`socket`, `threading`, `os`, `logging`). Nenhuma instalacao extra.

## Execucao

A partir da raiz do repositorio:

```bash
python pta-server/pta_server.py          # porta padrao 11550
python pta-server/pta_server.py 12000    # porta alternativa
```

O servidor le `pta-server/users.txt` e serve os arquivos de `pta-server/files/`, resolvendo os caminhos a partir da propria pasta do script (funciona de qualquer diretorio). Cada pedido e resposta e registrado no terminal. Encerrar com `Ctrl+C`.

Teste com o cliente fornecido (em outro terminal):

```bash
python pta-client.py 127.0.0.1 11550 user1
```

## Comportamento implementado

| Estado | Pedido | Resposta | Conexao |
|---|---|---|---|
| ESPERANDO | `SEQ CUMP <usuario>` com usuario em `users.txt` (sensivel a maiusculas) | `SEQ OK` | vai para PRONTO |
| ESPERANDO | qualquer outro pedido, usuario invalido ou formato invalido | `SEQ NOK` | fechada |
| PRONTO | `SEQ LIST` | `SEQ ARQS <num> a1,a2,...` (ou `SEQ NOK` se a pasta nao puder ser lida) | mantida |
| PRONTO | `SEQ PEGA <arquivo>` existente | `SEQ ARQ <tamanho> <bytes do arquivo>` | mantida |
| PRONTO | `SEQ PEGA <arquivo>` inexistente | `SEQ NOK` | mantida |
| PRONTO | `SEQ TERM` | `SEQ OK` | fechada |
| PRONTO | qualquer outro pedido ou formato invalido | `SEQ NOK` | mantida |

Detalhes:

- O `SEQ_NUM` da resposta repete o do pedido.
- Cada conexao e atendida por uma thread propria; dentro dela os pedidos sao processados um por vez, ate o fim, o que garante a atomicidade de LIST e PEGA.
- `PEGA` envia um arquivo por vez; nomes adicionais no mesmo pedido sao ignorados.
- `PEGA` so aceita nomes presentes na listagem, entao caminhos como `../users.txt` recebem `NOK`.
- Os arquivos sao enviados como bytes crus (inclusive o `.png`). Para arquivos vazios a resposta e `SEQ ARQ 0 ` (com espaco final).

## Diagramas

Os PNGs em [`docs/`](../docs) mostram o fluxo. Para gera-los novamente (requer `matplotlib`), com o servidor em execucao:

```bash
python docs/gerar_diagramas.py
```
