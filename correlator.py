from difflib import SequenceMatcher
from datetime import datetime
from models import Ticket, CorrelationResult, CorrelationReason


def _similarity(s1: str, s2: str) -> float:
    """Calcula similaridade entre duas strings (0.0 a 1.0), independente da ordem dos argumentos."""
    if not s1 or not s2:
        return 0.0
    a, b = s1.lower(), s2.lower()
    return max(SequenceMatcher(None, a, b).ratio(), SequenceMatcher(None, b, a).ratio())


def _possui_fuso(data: datetime | None) -> bool:
    """Indica se a data existe e tem fuso horário explícito."""
    return data is not None and data.tzinfo is not None


def _intervalo_atividade(ticket: Ticket) -> tuple[datetime, datetime | None] | None:
    """Retorna (inicio, fim) do período de atividade do chamado, ou None se indeterminado.

    fim None significa período em aberto (aberto ou em_andamento).
    Para resolvido e encerrado, o fim é resolvido_em; encerrado_em não é usado.
    Datas sem fuso explícito tornam o período indeterminado.
    Resolução anterior à abertura é inconsistente e também torna o período indeterminado.
    """
    if not _possui_fuso(ticket.timestamp):
        return None
    if ticket.status in ("aberto", "em_andamento"):
        return (ticket.timestamp, None)
    if not _possui_fuso(ticket.resolvido_em):
        return None
    if ticket.resolvido_em < ticket.timestamp:
        return None
    return (ticket.timestamp, ticket.resolvido_em)


def _periodos_nao_sobrepostos(periodo1, periodo2) -> bool:
    """Verdadeiro somente quando é possível demonstrar que os períodos não se sobrepõem."""
    inicio1, fim1 = periodo1
    inicio2, fim2 = periodo2
    if fim1 is not None and fim1 < inicio2:
        return True
    if fim2 is not None and fim2 < inicio1:
        return True
    return False


def correlate(ticket1: Ticket, ticket2: Ticket) -> CorrelationResult:
    """
    Compara dois chamados e retorna score de correlação (0-100).
    Score >= 60 indica correlação sugerida (não confirmada).
    Campos ausentes são ignorados (não penalizam, não geram pontos).
    """
    score = 0
    reasons = []

    # Ativo idêntico: +30
    if ticket1.ativo and ticket2.ativo and ticket1.ativo == ticket2.ativo:
        score += 30
        reasons.append(CorrelationReason(
            tipo="ativo",
            peso=30,
            explicação=f"Mesmo ativo: {ticket1.ativo}"
        ))

    # Serviço idêntico: +30
    if ticket1.serviço and ticket2.serviço and ticket1.serviço == ticket2.serviço:
        score += 30
        reasons.append(CorrelationReason(
            tipo="serviço",
            peso=30,
            explicação=f"Mesmo serviço: {ticket1.serviço}"
        ))

    # Sintomas sobrepostos: +20 (se >= 1 sintoma em comum)
    if ticket1.sintomas and ticket2.sintomas:
        sintomas_comuns = sorted(set(ticket1.sintomas) & set(ticket2.sintomas))
        if sintomas_comuns:
            score += 20
            reasons.append(CorrelationReason(
                tipo="sintoma",
                peso=20,
                explicação=f"Sintomas em comum: {', '.join(sintomas_comuns)}"
            ))

    # Descrição similar: +10 (se ambas existem E similaridade > 70%)
    if ticket1.descrição and ticket2.descrição:
        sim = _similarity(ticket1.descrição, ticket2.descrição)
        if sim > 0.7:
            score += 10
            reasons.append(CorrelationReason(
                tipo="descrição",
                peso=10,
                explicação=f"Descrições similares ({sim:.0%})"
            ))

    # Temporal próximo: +10 (< 10 minutos). Naive e aware não são comparados.
    if ticket1.timestamp and ticket2.timestamp and (ticket1.timestamp.tzinfo is None) == (ticket2.timestamp.tzinfo is None):
        delta = abs((ticket1.timestamp - ticket2.timestamp).total_seconds())
        if delta < 600:
            score += 10
            minutes = delta / 60
            reasons.append(CorrelationReason(
                tipo="temporal",
                peso=10,
                explicação=f"Eventos com {minutes:.1f} min de diferença"
            ))

    correlacionado = score >= 60

    # Bloqueio temporal: só com períodos determinados (datas com fuso) que não se sobrepõem
    intervalo1 = _intervalo_atividade(ticket1)
    intervalo2 = _intervalo_atividade(ticket2)
    if intervalo1 and intervalo2 and _periodos_nao_sobrepostos(intervalo1, intervalo2):
        correlacionado = False

    return CorrelationResult(
        ticket1_id=ticket1.id,
        ticket2_id=ticket2.id,
        score=min(score, 100),
        reasons=reasons,
        correlacionado=correlacionado
    )
