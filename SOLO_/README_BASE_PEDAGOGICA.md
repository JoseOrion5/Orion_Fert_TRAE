# Base Pedagógica Aplicada

Este material foi criado para transformar resultados de formulação em explicações didáticas voltadas a:

- estudante de Engenharia Química
- iniciante em programação

## Arquivos

- `base_pedagogica_quimica.json`: base de conhecimento pedagógica
- `motor_pedagogico.py`: módulo Python para consultar a base e gerar explicações

## O que foi aplicado

Foi criada uma estrutura pedagógica para explicar uma fórmula em cinco camadas:

- intuição
- explicação técnica
- matemática
- lógica de decisão
- Python para iniciante

Os conceitos já cobertos são:

- índice de saturação
- carga salina
- pares críticos e Kps
- balanço térmico
- pH teórico
- força iônica
- HLB
- reologia
- aditivos
- tiers de formulação

## Como usar

Exemplo simples:

```python
from motor_pedagogico import renderizar_texto_explicacao

snapshot = {
    "nome_formula": "F1",
    "tier": 1,
    "volume_l": 100.0,
    "temperatura_c": 25.0,
    "indice_saturacao": 0.91,
    "carga_salina_pct_mv": 38.5,
    "ph_teorico": 4.8,
    "forca_ionica": 1.2,
    "pares_criticos": ["Ca + SO4"],
    "aditivos_sugeridos": ["EDTA", "Estabilizante anti-cristalização"],
    "linhas": [
        {"insumo_nome": "Ureia", "massa_kg": 20.0},
        {"insumo_nome": "MAP", "massa_kg": 15.0}
    ],
    "balanco_termico": {
        "temp_entrada_c": 25.0,
        "temp_saida_c": 17.5,
        "delta_t_c": -7.5
    },
    "modo_sc": False,
    "resumo_risco": "Fórmula operacional, mas com margem reduzida."
}

texto = renderizar_texto_explicacao(snapshot)
print(texto)
```

## Campos esperados no snapshot

O `motor_pedagogico.py` foi pensado para receber um dicionário com alguns ou todos os campos abaixo:

- `nome_formula`
- `tier`
- `volume_l`
- `temperatura_c`
- `indice_saturacao`
- `carga_salina_pct_mv`
- `ph_teorico`
- `forca_ionica`
- `pares_criticos`
- `aditivos_sugeridos`
- `linhas`
- `balanco_termico`
- `hlb_requerido`
- `modo_sc`
- `resumo_risco`

## Como conectar ao seu projeto

No seu projeto atual, o melhor ponto de integração é logo após gerar os dados da fórmula no fluxo de estudo químico.

Exemplo de estratégia:

1. gerar a fórmula normalmente com o seu motor
2. montar um `snapshot` com os valores calculados
3. chamar `explicar_formula()` ou `renderizar_texto_explicacao()`
4. usar o retorno para:
   - mostrar em tela
   - salvar em `.txt`
   - alimentar uma aba de estudo
   - enriquecer o `estudo_quimico.py`

## Como encaixar no seu `estudo_quimico.py`

Você pode usar a base de duas formas:

- como fonte principal de texto pedagógico
- como complemento aos cálculos já existentes

Sugestão prática:

1. manter os cálculos no seu motor atual
2. usar `base_pedagogica_quimica.json` para os textos explicativos
3. usar `motor_pedagogico.py` para montar a narrativa por fórmula
4. injetar as seções resultantes no seu `build_study_view(...)`

## Benefício pedagógico

Com isso, cada fórmula passa a ser explicada como:

- o que ela é
- por que funciona
- onde estão os riscos
- como o sistema raciocinou
- como esse raciocínio aparece em Python

## Próximo passo recomendado

O próximo passo ideal é eu integrar isso diretamente ao seu fluxo atual, adaptando:

- `estudo_quimico.py`
- `estudo.py`
- e, se você quiser, o `main.py`

Assim a explicação pedagógica deixa de ser apenas uma base pronta e passa a aparecer dentro da interface do sistema.
