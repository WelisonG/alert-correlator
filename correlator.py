from difflib import SequenceMatcher
from datetime import datetime
from models import Ticket, CorrelationResult, CorrelationReason


def _similarity(s1: str, s2: str) -> float:
    """Calcula similaridade entre duas strings (0.0 a 1.0)."""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


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
        sintomas_comuns = set(ticket1.sintomas) & set(ticket2.sintomas)
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

    # Temporal próximo: +10 (< 10 minutos)
    if ticket1.timestamp and ticket2.timestamp:
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

    return CorrelationResult(
        ticket1_id=ticket1.id,
        ticket2_id=ticket2.id,
        score=min(score, 100),
        reasons=reasons,
        correlacionado=correlacionado
    )
