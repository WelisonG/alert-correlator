\# Alert Correlator — Contexto do Projeto



\## Objetivo

Ferramenta de portfólio para NOC/ITSM que sugere correlações entre tickets relacionados à mesma falha, evitando análise duplicada de incidentes.



\## Tecnologias

\- Python, FastAPI, SQLite e unittest.

\- API REST em main.py.

\- Motor de correlação em correlator.py.

\- Persistência em storage.py.

\- Modelos em models.py.

\- Testes em test\_correlator.py, test\_storage.py e test\_main.py.



\## Algoritmo atual

\- Mesmo ativo: 30 pontos.

\- Mesmo serviço: 30 pontos.

\- Sintomas comuns: 20 pontos.

\- Descrição similar (>70%): 10 pontos.

\- Diferença temporal inferior a 10 minutos: 10 pontos.

\- Correlação sugerida quando score >= 60.



\## Regras de desenvolvimento

\- Utilizar somente dados fictícios.

\- Nunca modificar, fechar ou integrar tickets reais automaticamente.

\- Priorizar soluções simples, explicáveis e testáveis.

\- Trabalhar em etapas pequenas.

\- Propor alterações e aguardar aprovação antes de editar arquivos.

\- Evitar subagentes, leituras extensas e comandos desnecessários.

\- Minimizar o consumo de créditos.

\- Explicar decisões técnicas de forma didática para permitir aprendizado ativo.



\## Estado atual

\- 19 testes automatizados aprovados.

\- API e persistência implementadas.

\- Próxima tarefa: reduzir falsos positivos no algoritmo de correlação, especialmente quando ativo e serviço coincidem, mas os tickets representam ocorrências distintas.

