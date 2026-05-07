# PDR — Orion_Fert (Simulador Industrial)
Versão: 1.0  
Data: 2026-04-30  

## 1) Propósito
Definir requisitos e critérios de aceitação para o Orion_Fert, um aplicativo desktop (Flet) que formula fertilizantes líquidos por metas de nutrientes e valida a viabilidade físico-química, gerando POP e relatório.

## 2) Escopo do Produto
### 2.1 Incluído
- Formulação por metas percentuais (N, P2O5, K2O, Ca, Mg, S e micros).
- Geração de múltiplas rotas (Top 12) com foco em exibição de Top 5.
- Validação de estabilidade (saturação, pares críticos, risco de precipitação/“sorvete”).
- Recomendações de processo (POP) e mitigadores (aditivos/quelantes/co-solventes).
- Registro de dados de bancada (pH, CE, turbidez, observações) por formulação.
- Exportação de relatório/POP (PDF quando disponível) e histórico local.

### 2.2 Fora de Escopo (por enquanto)
- Modelos termodinâmicos completos por atividade iônica (Pitzer/Debye-Hückel).
- Otimização com variáveis binárias (MILP) para “usar pelo menos N insumos”.
- Colaboração em nuvem/multiusuário e auditoria corporativa.

## 3) Personas
- Engenheiro de formulação: busca bater metas com estabilidade e custo/lead time aceitáveis.
- CQ/Laboratório: registra bancada e valida alertas do modelo.
- Operação/PCP: executa POP e precisa de instruções claras e rastreáveis.

## 4) Fluxos Principais (UI)
### 4.1 Abas principais
- ⚗️ Formulação
- ⚖️ Estabilidade
- 📋 Relatório & POP

### 4.2 Ações chave
- Calcular e Validar: calcula formulações, envia ao módulo de estabilidade e navega para Estabilidade quando houver alertas relevantes.
- Reset: limpa inputs, outputs, estabilidade, laudo e histórico de sessão.

## 5) Requisitos Funcionais (FR)
### FR-01 — Entradas de formulação
- O usuário informa volume, temperatura, metas e preferências (diversificação por fonte, modo anti-cristalização/anti-sorvete, flags de otimização).

### FR-02 — Geração de rotas
- O sistema retorna rotas com BOM (insumo, massa, contribuição por nutriente, custo, fornecedor, lead time).
- Deve apresentar múltiplas rotas para comparação.

### FR-03 — Regras de viabilidade
- O sistema aplica limites de solubilidade/saturação e restrições de volume/fração de sólidos.
- Deve identificar pares críticos (ex.: Ca + SO4; Ca + P2O5) e aplicar mitigação quando disponível (quelante).

### FR-04 — Tiering (1/2/3)
- Tier 1: prioriza soluções “frias” e conservadoras.
- Tier 2: permite co-solventes/suspensão seguros.
- Tier 3 (F9–F12): tenta rotas “não ortodoxas” quando Tier 1/2 falham.

### FR-05 — Variáveis de processo/aditivos no Tier 3 (F9–F12)
- O solver pode ajustar variáveis auxiliares (ex.: co-solvente variável) com limites e custo para buscar viabilidade.
- Deve permitir insumos “bloqueados” apenas no Tier 3 sob penalidade de custo (para entrarem somente quando necessário).

### FR-06 — Estabilidade
- Exibir semáforo (verde/amarelo/vermelho) e motivos.
- Exibir cards de diagnóstico (ex.: saturação, pares críticos, pontos de atenção).
- Registrar dados de bancada por formulação.

### FR-07 — Relatório & POP
- Gerar visualização de laudo/POP.
- Exportar PDF quando ambiente suportar.
- Salvar histórico local (mínimo: targets, BOM, alertas, POP, dados de bancada).

## 6) Requisitos Não Funcionais (NFR)
- Plataforma: Windows.
- Resposta: deve retornar resultados interativos (adequado ao uso em bancada/escritório).
- Confiabilidade: falhas devem ser reportadas com mensagem clara e log.
- Reprodutibilidade: mesmas entradas devem produzir rotas consistentes (respeitando regras/ordem de tentativas).

## 7) Regras de Negócio
- Respeitar bloqueios regulatórios/observacionais por padrão; Tier 3 pode flexibilizar sob penalidade.
- Diversificação: limitar contribuição máxima por fonte (cap) quando configurado.
- Pairs críticos: exigir mitigação (quelante) quando aplicável e registrar alerta.

## 8) Critérios de Aceitação (AC)
- AC-01: Para um conjunto de metas “simples”, Tier 1 encontra ao menos 1 rota válida.
- AC-02: Para um conjunto de metas “difíceis”, quando Tier 1/2 falham, F9–F12 tentam rota Tier 3 e retornam rota quando houver viabilidade.
- AC-03: Estabilidade recebe a formulação calculada, gera semáforo e motivos e permite salvar bancada.
- AC-04: Reset limpa estado da sessão e volta para Formulação/Principal.
- AC-05: Relatório & POP renderiza BOM/POP e salva histórico local.

## 9) Dependências
- Base de dados local (SQLite) com insumos, teores e aditivos.
- SciPy disponível para otimização (quando usar linprog).
- Ambiente de PDF (ex.: reportlab) disponível para exportação (opcional).

## 10) Riscos e Mitigações
- Risco: falso-positivo de viabilidade por ausência de modelo de pH/atividade iônica.
  - Mitigação: coletar dados de bancada e calibrar limites/coeficientes por família de insumos.
- Risco: “sempre possível” não existe fisicamente para certas metas.
  - Mitigação: o sistema deve explicar o gargalo (nutriente/insumo/limite) e sugerir relaxamentos ou alternativa de produto.

## 11) Entregáveis
- App com abas e fluxos descritos.
- Motor com tiers e fallback Tier 3 (F9–F12) com variáveis auxiliares e penalidade para bloqueados.
- Módulo de estabilidade e relatório/POP com histórico local.
