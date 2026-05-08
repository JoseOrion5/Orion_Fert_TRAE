# Integração no `main.py`

Para ativar a versão pedagógica integrada no seu projeto atual, faça a troca abaixo no `main.py`.

## Troca principal

Antes:

```python
import estudo_quimico
```

Depois:

```python
import estudo_quimico_integrado as estudo_quimico
```

## O que isso faz

Mantém o restante do fluxo igual, porque o novo módulo preserva a função:

```python
gerar_estudo_completo(idx, output, insumos, targets, volume_l, temp_c)
```

Ou seja, esta linha do seu `main.py` pode continuar exatamente como está:

```python
secoes = estudo_quimico.gerar_estudo_completo(idx, output, insumos_cache, targets, v, t)
```

## Arquivos que precisam ficar juntos

Coloque estes arquivos na mesma pasta do projeto:

- `base_pedagogica_quimica.json`
- `motor_pedagogico.py`
- `estudo_quimico_integrado.py`

## Resultado esperado

Ao clicar em `ESTUDAR`, o sistema passa a mostrar:

- estudo químico original
- leitura pedagógica da fórmula
- seções extras com:
  - intuição
  - explicação técnica
  - matemática
  - lógica
  - Python para iniciante
  - fatos da fórmula
  - perguntas-guia

## Observação importante

O módulo `estudo_quimico_integrado.py` tenta aproveitar o `estudo_quimico.py` original. Então:

- se o módulo original estiver presente, ele complementa o estudo já existente
- se o original não estiver presente, ele ainda gera a parte pedagógica com base no snapshot da fórmula
